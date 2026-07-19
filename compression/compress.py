#!/usr/bin/env python3
"""Create a resumable, validator-coupled LZMA baseline for the 5k canonical split."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import resource
import time
import zipfile
from pathlib import Path

import lzma
import numpy as np
from datasets import load_dataset


HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "compression_challenge_submission"
ARCHIVE_STEM = HERE / "compression_challenge_submission"
ARCHIVE_ZIP = Path(f"{ARCHIVE_STEM}.zip")
EVIDENCE_FILE = HERE / "repro" / "run" / "compression_evidence.json"
MANIFEST_FILE = HERE / "repro" / "lzma-5000-manifest.json"

DATASET_NAME = "commaai/commavq"
DATASET_REVISION = "795c839a57b3c4eebd1a28b1ec04eb56d6000e81"
DATA_FILES = {"train": ["data-0000.tar.gz", "data-0001.tar.gz"]}
TARGET_CASES = 5000


def compress_tokens(tokens: np.ndarray) -> bytes:
  flat = tokens.astype(np.int16).reshape(-1, 128).T.ravel().tobytes()
  return lzma.compress(flat)


def decompress_tokens(data: bytes) -> np.ndarray:
  tokens = np.frombuffer(lzma.decompress(data), dtype=np.int16)
  return tokens.reshape(128, -1).T.reshape(-1, 8, 16)


def load_dataset_rows(num_proc: int):
  dataset = load_dataset(
    DATASET_NAME,
    split="train",
    num_proc=num_proc,
    revision=DATASET_REVISION,
    data_files=DATA_FILES,
  )
  validate_dataset_contract(dataset, TARGET_CASES)
  return dataset


def validate_dataset_contract(rows, target_cases: int = TARGET_CASES) -> list[str]:
  if len(rows) != target_cases:
    raise RuntimeError(f"Expected {target_cases} cases, got {len(rows)}")
  names = [row["json"]["file_name"] for row in rows]
  if len(set(names)) != target_cases:
    raise RuntimeError(f"Expected {target_cases:,} unique file names in canonical split")
  if any(not name or Path(name).name != name for name in names):
    raise RuntimeError("Dataset file names must be non-empty plain file names")
  return names


def validate_existing(path: Path, expected: np.ndarray) -> bool:
  try:
    payload = path.read_bytes()
    if not payload:
      return False
    return np.array_equal(decompress_tokens(payload), expected)
  except Exception:
    return False


def sha256_bytes(data: bytes) -> str:
  return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, payload: bytes) -> None:
  temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
  try:
    with temporary.open("wb") as output:
      output.write(payload)
      output.flush()
      os.fsync(output.fileno())
    os.replace(temporary, path)
  finally:
    temporary.unlink(missing_ok=True)


def resume_rows(rows, output_dir: Path, progress_file: Path) -> tuple[dict, list[dict]]:
  """Validate every retained payload and atomically create or repair the rest."""
  output_dir.mkdir(parents=True, exist_ok=True)
  progress_file.parent.mkdir(parents=True, exist_ok=True)
  stats = {"pre_existing": 0, "validated": 0, "repaired": 0, "written": 0}
  manifest = []
  with progress_file.open("w", encoding="utf-8") as progress:
    for index, example in enumerate(rows, start=1):
      name = example["json"]["file_name"]
      if not name or Path(name).name != name:
        raise RuntimeError(f"Unsafe output name: {name!r}")
      tokens = np.asarray(example["token.npy"], dtype=np.int16)
      path = output_dir / name
      status = "written"
      if path.exists():
        stats["pre_existing"] += 1
        if validate_existing(path, tokens):
          stats["validated"] += 1
          status = "validated"
        else:
          stats["repaired"] += 1
      if status != "validated":
        payload = compress_tokens(tokens)
        if not np.array_equal(decompress_tokens(payload), tokens):
          raise RuntimeError(f"In-memory round trip failed for {name}")
        atomic_write(path, payload)
        stats["written"] += 1
      payload = path.read_bytes()
      entry = {
        "name": name,
        "source_sha256": sha256_bytes(tokens.tobytes()),
        "payload_sha256": sha256_bytes(payload),
        "payload_bytes": len(payload),
      }
      manifest.append(entry)
      progress.write(json.dumps({"index": index, "status": status, **entry}, sort_keys=True) + "\n")
      progress.flush()
      os.fsync(progress.fileno())
      if index == 1 or index % 100 == 0 or index == len(rows):
        print(f"progress={index}/{len(rows)} status={status}", flush=True)
  return stats, manifest


def write_manifest(manifest: list[dict]) -> None:
  payload = {
    "dataset": DATASET_NAME,
    "revision": DATASET_REVISION,
    "cases": TARGET_CASES,
    "entries": manifest,
  }
  atomic_write(MANIFEST_FILE, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())


def package_archive(output_dir: Path, archive_path: Path, names: list[str]) -> None:
  """Write a byte-reproducible evaluator-shaped zip without mutating payloads."""
  payload_paths = [path for path in output_dir.iterdir() if path.is_file()]
  if len(names) != TARGET_CASES or len(set(names)) != TARGET_CASES:
    raise RuntimeError(f"Refusing to package anything except {TARGET_CASES} unique cases")
  if {path.name for path in payload_paths} != set(names):
    raise RuntimeError("Payload directory does not exactly match the canonical case names")
  temporary = archive_path.with_name(f".{archive_path.name}.tmp-{os.getpid()}")
  try:
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
      for path in sorted(payload_paths, key=lambda candidate: candidate.name):
        info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, path.read_bytes())
      script = (HERE / "decompress.py").read_bytes()
      info = zipfile.ZipInfo("decompress.py", date_time=(1980, 1, 1, 0, 0, 0))
      info.compress_type = zipfile.ZIP_STORED
      info.external_attr = 0o100755 << 16
      archive.writestr(info, script)
    os.replace(temporary, archive_path)
  finally:
    temporary.unlink(missing_ok=True)


def write_evidence(
  dataset_len: int,
  stats: dict,
  timings: dict,
  archive_size: int,
) -> None:
  EVIDENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
  compression_rate = ((dataset_len * 1200 * 128 * 10 / 8) / archive_size) if archive_size else 0.0
  payload = {
    "dataset": DATASET_NAME,
    "revision": DATASET_REVISION,
    "target_cases": TARGET_CASES,
    "output_dir": str(OUTPUT_DIR),
    "stats": stats,
    "timing_seconds": timings["wall"],
    "resources": {
      "ru_maxrss_kib": timings["maxrss_kib"],
      "user_cpu_seconds": timings["user_cpu_seconds"],
      "system_cpu_seconds": timings["system_cpu_seconds"],
    },
    "archive_bytes": archive_size,
    "compression_rate": compression_rate,
  }
  with EVIDENCE_FILE.open("w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)


def main(num_proc: int) -> None:
  start_wall = time.perf_counter()
  start_cpu = os.times()
  start_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  dataset = load_dataset_rows(num_proc)

  stats, manifest = resume_rows(dataset, OUTPUT_DIR, EVIDENCE_FILE.with_name("compression_progress.jsonl"))
  write_manifest(manifest)
  package_archive(OUTPUT_DIR, ARCHIVE_ZIP, [entry["name"] for entry in manifest])

  elapsed_rusage = resource.getrusage(resource.RUSAGE_SELF)
  end_cpu = os.times()
  timings = {
    "wall": time.perf_counter() - start_wall,
    "user_cpu_seconds": end_cpu.user - start_cpu.user,
    "system_cpu_seconds": end_cpu.system - start_cpu.system,
    "maxrss_kib": max(start_maxrss, elapsed_rusage.ru_maxrss),
  }

  archive_size = ARCHIVE_ZIP.stat().st_size
  rate = (len(dataset) * 1200 * 128 * 10 / 8) / archive_size

  write_evidence(len(dataset), stats, timings, archive_size)
  print(f"Compression rate: {rate:.1f}")
  print(f"Evidence: {EVIDENCE_FILE}")


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--num-proc",
    type=int,
    default=None,
    help="override CPU count for dataset loading",
  )
  arguments = parser.parse_args()

  default_cpus = min(4, multiprocessing.cpu_count())
  cpus = arguments.num_proc if arguments.num_proc is not None else default_cpus
  main(cpus)
