#!/usr/bin/env python3
"""Pinned acquisition and bounded commaVQ neural-codec probe."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
import os
import resource
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from fractions import Fraction
from pathlib import Path

CODEC_REPOSITORY = "https://github.com/ykstorm/commavq-lossless-codec.git"
CODEC_COMMIT = "5bc967f218c551eeb74387b5ce016586baed77a2"
MODEL_REPOSITORY = "commaai/commavq-gpt2m"
MODEL_REVISION = "12f0a5e31c22b492dc391aa348cbe422139e3087"
MODEL_URL = f"https://huggingface.co/{MODEL_REPOSITORY}/resolve/{MODEL_REVISION}/gpt2m.onnx"
MODEL_SHA256 = "d2ee2bd95bc09811404938359395ce78a6dd59a540a44d781f838219752d6cd0"
MODEL_BYTES = 614_166_933
DATASET_REPOSITORY = "commaai/commavq"
DATASET_REVISION = "795c839a57b3c4eebd1a28b1ec04eb56d6000e81"
DATA_FILES = {"train": ["data-0000.tar.gz", "data-0001.tar.gz"]}
CASE_NAME = "3b41c0fa8959aea6c118e5714f412a2e_13"
CASES = 5_000
FRAMES_PER_CASE = 1_200
TOKENS_PER_FRAME = 128
PACKAGE_FILES = (
  "codec/decompress.py",
  "codec/__init__.py",
  "codec/quantize.py",
  "codec/range_coder.py",
  "codec/submission_codec.py",
)
PROBE_REQUIREMENTS = (
  "numpy==2.4.6",
  "onnxruntime==1.27.0",
  "datasets==5.0.0",
  "huggingface-hub==1.24.0",
)


def sha256(path: Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
      digest.update(block)
  return digest.hexdigest()


def verify_model(path: Path) -> None:
  if path.stat().st_size != MODEL_BYTES or sha256(path) != MODEL_SHA256:
    raise RuntimeError(f"model verification failed: {path}")


def fetch(checkout: Path, model: Path) -> None:
  if checkout.exists():
    actual = subprocess.check_output(
      ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True,
    ).strip()
    if actual != CODEC_COMMIT:
      raise RuntimeError(f"existing checkout is {actual}, expected {CODEC_COMMIT}")
  else:
    checkout.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", CODEC_REPOSITORY, str(checkout)], check=True)
    subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", CODEC_COMMIT], check=True)
  if not model.exists():
    model.parent.mkdir(parents=True, exist_ok=True)
    temporary = model.with_suffix(".onnx.partial")
    with urllib.request.urlopen(MODEL_URL) as source, temporary.open("wb") as target:
      shutil.copyfileobj(source, target, 1024 * 1024)
    temporary.replace(model)
  verify_model(model)
  environment = checkout / ".venv"
  if not environment.exists():
    subprocess.run(["uv", "venv", "--python", "3.11", str(environment)], check=True)
  subprocess.run([
    "uv", "pip", "install", "--python", str(environment / "bin/python"),
    *PROBE_REQUIREMENTS,
  ], check=True)
  print(json.dumps({
    "codec_commit": CODEC_COMMIT,
    "codec_path": str(checkout),
    "model_bytes": model.stat().st_size,
    "model_path": str(model),
    "model_sha256": sha256(model),
  }, sort_keys=True))


def deterministic_decoder_zip(checkout: Path) -> tuple[int, int]:
  output = io.BytesIO()
  source_bytes = 0
  with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for relative in PACKAGE_FILES:
      data = (checkout / relative).read_bytes()
      source_bytes += len(data)
      archived = "decompress.py" if relative == "codec/decompress.py" else relative
      info = zipfile.ZipInfo(archived, date_time=(1980, 1, 1, 0, 0, 0))
      info.compress_type = zipfile.ZIP_DEFLATED
      info.external_attr = 0o100644 << 16
      archive.writestr(info, data)
  return source_bytes, len(output.getvalue())


def full_projection(bits_per_token: float, encode_seconds_per_frame: float,
                    decode_seconds_per_frame: float, decoder_zip_bytes: int = 0) -> dict:
  tokens = CASES * FRAMES_PER_CASE * TOKENS_PER_FRAME
  logical_bytes = tokens * 10 // 8
  bitstream_fraction = tokens * Fraction(str(bits_per_token)) / 8
  bitstream_bytes = math.ceil(bitstream_fraction)
  headers_bytes = CASES * 4
  external_model_package_bytes = bitstream_bytes + headers_bytes + decoder_zip_bytes
  self_contained_bytes = external_model_package_bytes + MODEL_BYTES
  return {
    "cases": CASES,
    "tokens": tokens,
    "logical_bytes_10bit": logical_bytes,
    "projected_bitstream_bytes": bitstream_bytes,
    "projected_headers_bytes": headers_bytes,
    "projected_external_model_package_bytes_before_zip_framing": external_model_package_bytes,
    "projected_external_model_ratio_upper_bound": logical_bytes / external_model_package_bytes,
    "projected_self_contained_bytes_before_zip_framing": self_contained_bytes,
    "projected_self_contained_ratio_upper_bound": logical_bytes / self_contained_bytes,
    "projected_encode_days_one_process": CASES * FRAMES_PER_CASE * encode_seconds_per_frame / 86400,
    "projected_decode_days_one_process": CASES * FRAMES_PER_CASE * decode_seconds_per_frame / 86400,
  }


def load_case():
  from datasets import load_dataset
  import numpy as np
  dataset = load_dataset(
    DATASET_REPOSITORY, split="train", revision=DATASET_REVISION,
    data_files=DATA_FILES, num_proc=1,
  )
  if len(dataset) != CASES or dataset[0]["json"]["file_name"] != CASE_NAME:
    raise RuntimeError("canonical commaVQ selection changed")
  return np.asarray(dataset[0]["token.npy"], dtype=np.int64).reshape(-1, TOKENS_PER_FRAME)


def probe(checkout: Path, model: Path, frames: int) -> None:
  if importlib.util.find_spec("onnxruntime") is None:
    interpreter = checkout / ".venv/bin/python"
    if not interpreter.exists():
      raise RuntimeError("probe environment missing; run the fetch command first")
    os.execv(str(interpreter), [str(interpreter), str(Path(__file__).resolve()), *sys.argv[1:]])
  import numpy as np
  if not 0 < frames <= FRAMES_PER_CASE:
    raise ValueError(f"frames must be in [1, {FRAMES_PER_CASE}]")
  actual = subprocess.check_output(
    ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True,
  ).strip()
  if actual != CODEC_COMMIT:
    raise RuntimeError(f"codec commit is {actual}, expected {CODEC_COMMIT}")
  verify_model(model)
  sys.path.insert(0, str(checkout))
  from codec.submission_codec import Gpt2mStepper, compress_segment, decompress_segment

  tokens = load_case()[:frames]
  start = time.perf_counter()
  encoder = Gpt2mStepper(str(model), providers=["CPUExecutionProvider"])
  encode_start = time.perf_counter()
  bitstream = compress_segment(encoder, tokens)
  encode_end = time.perf_counter()
  decoder = Gpt2mStepper(str(model), providers=["CPUExecutionProvider"])
  decode_start = time.perf_counter()
  restored = decompress_segment(decoder, bitstream, frames)
  end = time.perf_counter()
  source_bytes, decoder_zip_bytes = deterministic_decoder_zip(checkout)
  exact_bpt = Fraction(len(bitstream) * 8, tokens.size)
  bpt = float(exact_bpt)
  decompressor = (checkout / "codec/decompress.py").read_text()
  compressor = (checkout / "codec/submission_compress.py").read_text()
  output = {
    "schema": 1,
    "case": CASE_NAME,
    "codec_commit": CODEC_COMMIT,
    "dataset_revision": DATASET_REVISION,
    "model_revision": MODEL_REVISION,
    "model_sha256": MODEL_SHA256,
    "model_bytes_external": MODEL_BYTES,
    "frames": frames,
    "tokens": int(tokens.size),
    "crosses_19_frame_context_boundary": frames > 19,
    "exact": bool(np.array_equal(tokens, restored)),
    "bitstream_bytes": len(bitstream),
    "bitstream_sha256": hashlib.sha256(bitstream).hexdigest(),
    "bits_per_token": bpt,
    "ratio_10bit": 10 / bpt,
    "model_init_encode_seconds": encode_start - start,
    "encode_seconds": encode_end - encode_start,
    "model_init_decode_seconds": decode_start - encode_end,
    "decode_seconds": end - decode_start,
    "wall_seconds": end - start,
    "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    "decoder_source_bytes": source_bytes,
    "decoder_zip_bytes": decoder_zip_bytes,
    "upstream_package_evaluator_compatible": False,
    "package_blockers": [
      "np.save(path, array) appends .npy to the evaluator's extensionless case name"
      if "np.save(OUTPUT_DIR / name, out)" in decompressor else "extensionless output unverified",
      "model download has no pinned revision"
      if 'hf_hub_download("commaai/commavq-gpt2m", "gpt2m.onnx")' in decompressor else "model pin unverified",
      "submission_compress.py resolves package sources outside this flattened checkout"
      if 'HERE / "compression" / "codec"' in compressor else "package source layout unverified",
      "compress prefers CUDA while decompress forces CPU, so provider identity is not preserved",
      "dataset downloads have no pinned revision",
    ],
  }
  output["full_5000_projection_from_probe"] = full_projection(
    exact_bpt, output["encode_seconds"] / frames, output["decode_seconds"] / frames,
    decoder_zip_bytes,
  )
  print(json.dumps(output, indent=2, sort_keys=True))


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("command", choices=("fetch", "probe"))
  parser.add_argument("--checkout", type=Path, default=Path("/tmp/commavq-lossless-codec-r4"))
  parser.add_argument("--model", type=Path, default=Path("/tmp/gpt2m/gpt2m.onnx"))
  parser.add_argument("--frames", type=int, default=3)
  args = parser.parse_args()
  if args.command == "fetch":
    fetch(args.checkout, args.model)
  else:
    probe(args.checkout, args.model, args.frames)


if __name__ == "__main__":
  main()
