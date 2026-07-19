#!/usr/bin/env python3
"""Benchmark exact, portable codecs on a pinned, fixed commaVQ subset."""

from __future__ import annotations

import argparse
import bz2
import gzip
import json
import lzma
import resource
import statistics
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from datasets import load_dataset

HERE = Path(__file__).resolve().parent
OUTPUT_PATH = HERE / "run" / "codec-frontier-r3.json"
DATASET_NAME = "commaai/commavq"
DATASET_REVISION = "795c839a57b3c4eebd1a28b1ec04eb56d6000e81"
DATA_FILES = {"train": ["data-0000.tar.gz", "data-0001.tar.gz"]}
TARGET_CASES = 5000
SHAPE = (1200, 8, 16)
VALUES = int(np.prod(SHAPE))


def load_subset(cases: int) -> list[dict]:
  dataset = load_dataset(
    DATASET_NAME, split="train", num_proc=1, revision=DATASET_REVISION,
    data_files=DATA_FILES,
  )
  if len(dataset) != TARGET_CASES:
    raise RuntimeError(f"Expected {TARGET_CASES} cases, got {len(dataset)}")
  names = list(dataset["json"])
  names = [item["file_name"] for item in names]
  if len(set(names)) != TARGET_CASES or any(not n or Path(n).name != n for n in names):
    raise RuntimeError("Canonical split has duplicate or unsafe names")
  if not 0 < cases <= TARGET_CASES:
    raise ValueError(f"cases must be in [1, {TARGET_CASES}]")
  return [
    {"name": names[index], "tokens": np.asarray(dataset[index]["token.npy"], dtype=np.int16).reshape(SHAPE)}
    for index in range(cases)
  ]


def pack10(values: np.ndarray) -> bytes:
  flat = np.asarray(values, dtype=np.uint16).reshape(-1)
  if np.any(flat > 1023):
    raise ValueError("10-bit packing requires values in [0, 1023]")
  output = bytearray((flat.size * 10 + 7) // 8)
  accumulator = bits = offset = 0
  for value in flat:
    accumulator |= int(value) << bits
    bits += 10
    while bits >= 8:
      output[offset] = accumulator & 255
      offset += 1
      accumulator >>= 8
      bits -= 8
  if bits:
    output[offset] = accumulator & 255
  return bytes(output)


def unpack10(payload: bytes, count: int = VALUES) -> np.ndarray:
  expected = (count * 10 + 7) // 8
  if len(payload) != expected:
    raise ValueError(f"Expected {expected} packed bytes, got {len(payload)}")
  output = np.empty(count, dtype=np.uint16)
  accumulator = bits = index = 0
  for byte in payload:
    accumulator |= byte << bits
    bits += 8
    while bits >= 10 and index < count:
      output[index] = accumulator & 1023
      index += 1
      accumulator >>= 10
      bits -= 10
  if index != count or accumulator:
    raise ValueError("Invalid 10-bit padding or truncated stream")
  return output


@dataclass(frozen=True)
class Layout:
  name: str
  axes: tuple[int, int, int]
  delta_modulus: int | None = None
  bits: int = 16

  @property
  def payload_bytes(self) -> int:
    return (VALUES * self.bits + 7) // 8

  def encode(self, tokens: np.ndarray) -> bytes:
    values = np.asarray(tokens, dtype=np.int16).reshape(SHAPE).astype(np.uint16)
    if np.any(values > 1023):
      raise ValueError("commaVQ tokens must be in [0, 1023]")
    if self.delta_modulus:
      source = values.copy()
      values[1:] = (source[1:] - source[:-1]) % self.delta_modulus
    ordered = values.transpose(self.axes).reshape(-1)
    return pack10(ordered) if self.bits == 10 else ordered.astype("<u2", copy=False).tobytes()

  def decode(self, payload: bytes) -> np.ndarray:
    if len(payload) != self.payload_bytes:
      raise ValueError(f"{self.name}: invalid payload length {len(payload)}")
    ordered = unpack10(payload) if self.bits == 10 else np.frombuffer(payload, dtype="<u2").copy()
    permuted_shape = tuple(SHAPE[axis] for axis in self.axes)
    inverse_axes = tuple(self.axes.index(axis) for axis in range(3))
    values = ordered.reshape(permuted_shape).transpose(inverse_axes).copy()
    if self.delta_modulus:
      values = np.cumsum(values.astype(np.uint64), axis=0) % self.delta_modulus
    return values.astype(np.uint16).view(np.int16)


LAYOUTS = (
  Layout("time-major-u16", (0, 1, 2)),
  Layout("token-axis-u16", (1, 2, 0)),  # Current compress.py byte layout.
  Layout("spatial-reversed-u16", (2, 1, 0)),
  Layout("temporal-delta-mod1024-u16", (1, 2, 0), delta_modulus=1024),
  Layout("token-axis-pack10", (1, 2, 0), bits=10),
  Layout("temporal-delta-mod1024-pack10", (1, 2, 0), delta_modulus=1024, bits=10),
)


@dataclass(frozen=True)
class Codec:
  name: str
  compress: Callable[[bytes], bytes]
  decompress: Callable[[bytes], bytes]


CODECS = {
  "lzma": Codec("lzma", lzma.compress, lzma.decompress),
  "bz2": Codec("bz2", lambda data: bz2.compress(data, compresslevel=9), bz2.decompress),
  "zlib": Codec("zlib", lambda data: zlib.compress(data, level=9), zlib.decompress),
  "gzip": Codec("gzip", lambda data: gzip.compress(data, compresslevel=9, mtime=0), gzip.decompress),
}


def chain(first: Codec, second: Codec) -> Codec:
  return Codec(
    f"{first.name}+{second.name}",
    lambda data: second.compress(first.compress(data)),
    lambda data: first.decompress(second.decompress(data)),
  )


@dataclass(frozen=True)
class Candidate:
  name: str
  layout: Layout
  codec: Codec
  solid: bool


def candidate_catalog() -> tuple[Candidate, ...]:
  lzma_codec = CODECS["lzma"]
  candidates = [
    Candidate("baseline/per-example/token-axis-u16/lzma", LAYOUTS[1], lzma_codec, False),
  ]
  candidates.extend(Candidate(f"solid/{layout.name}/lzma", layout, lzma_codec, True) for layout in LAYOUTS)
  candidates.extend(
    Candidate(f"per-example/token-axis-u16/{name}", LAYOUTS[1], CODECS[name], False)
    for name in ("bz2", "zlib", "gzip")
  )
  candidates.extend((
    Candidate("solid/token-axis-u16/bz2", LAYOUTS[1], CODECS["bz2"], True),
    Candidate("solid/token-axis-u16/zlib", LAYOUTS[1], CODECS["zlib"], True),
    Candidate("per-example/token-axis-u16/zlib+lzma", LAYOUTS[1], chain(CODECS["zlib"], lzma_codec), False),
  ))
  return tuple(candidates)


def run_candidate(candidate: Candidate, examples: list[dict]) -> dict:
  start = time.perf_counter()
  if candidate.solid:
    encoded_solid = b"".join(candidate.layout.encode(example["tokens"]) for example in examples)
    compressed = [candidate.codec.compress(encoded_solid)]
    materialized_bytes_bound = len(encoded_solid) + len(compressed[0])
    del encoded_solid
  else:
    compressed = []
    for example in examples:
      encoded = candidate.layout.encode(example["tokens"])
      compressed.append(candidate.codec.compress(encoded))
    materialized_bytes_bound = sum(map(len, compressed)) + candidate.layout.payload_bytes
  encode_seconds = time.perf_counter() - start
  start = time.perf_counter()
  restored_streams: Iterable[bytes]
  if candidate.solid:
    restored = candidate.codec.decompress(compressed[0])
    size = candidate.layout.payload_bytes
    if len(restored) != size * len(examples):
      raise RuntimeError("Solid stream has an invalid decoded length")
    restored_streams = (restored[offset:offset + size] for offset in range(0, len(restored), size))
  else:
    restored_streams = (candidate.codec.decompress(item) for item in compressed)
  for example, stream in zip(examples, restored_streams, strict=True):
    if not np.array_equal(candidate.layout.decode(stream), example["tokens"]):
      raise RuntimeError(f"Exact round trip failed: {candidate.name}/{example['name']}")
  decode_seconds = time.perf_counter() - start
  return {
    "name": candidate.name,
    "status": "exact",
    "compressed_bytes": sum(map(len, compressed)),
    "encode_seconds": encode_seconds,
    "decode_seconds": decode_seconds,
    "total_seconds": encode_seconds + decode_seconds,
    "materialized_bytes_bound": materialized_bytes_bound,
    "process_high_water_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
  }


def pareto(results: list[dict]) -> list[dict]:
  def dominates(left: dict, right: dict) -> bool:
    axes = ("compressed_bytes", "total_seconds", "materialized_bytes_bound")
    return all(left[axis] <= right[axis] for axis in axes) and any(left[axis] < right[axis] for axis in axes)
  return [result for result in results if not any(dominates(other, result) for other in results if other is not result)]


def benchmark(examples: list[dict], repeats: int = 3) -> dict:
  if not examples:
    raise ValueError("At least one example is required")
  first_pass = []
  for candidate in candidate_catalog():
    result = run_candidate(candidate, examples)
    first_pass.append(result)
    print(f"{candidate.name:56} {result['compressed_bytes']:10d} B  {result['total_seconds']:8.3f} s")
  initial_winner_names = {item["name"] for item in pareto(first_pass)}
  by_name = {candidate.name: candidate for candidate in candidate_catalog()}
  final = []
  for result in first_pass:
    if result["name"] in initial_winner_names and repeats > 1:
      trials = [result] + [run_candidate(by_name[result["name"]], examples) for _ in range(repeats - 1)]
      for key in ("encode_seconds", "decode_seconds", "total_seconds", "process_high_water_rss_kib"):
        result[key] = statistics.median(trial[key] for trial in trials)
      if len({trial["compressed_bytes"] for trial in trials}) != 1:
        raise RuntimeError(f"Nondeterministic compressed size: {result['name']}")
      result["repeat_count"] = repeats
    else:
      result["repeat_count"] = 1
    final.append(result)
  while repeats > 1:
    pending = [result for result in pareto(final) if result["repeat_count"] == 1]
    if not pending:
      break
    for result in pending:
      trials = [result] + [run_candidate(by_name[result["name"]], examples) for _ in range(repeats - 1)]
      for key in ("encode_seconds", "decode_seconds", "total_seconds", "process_high_water_rss_kib"):
        result[key] = statistics.median(trial[key] for trial in trials)
      if len({trial["compressed_bytes"] for trial in trials}) != 1:
        raise RuntimeError(f"Nondeterministic compressed size: {result['name']}")
      result["repeat_count"] = repeats
  winners = pareto(final)
  logical_bytes = len(examples) * VALUES * 10 // 8
  for result in final:
    result["logical_ratio"] = logical_bytes / result["compressed_bytes"]
  return {
    "schema": 1,
    "dataset": DATASET_NAME,
    "revision": DATASET_REVISION,
    "target_cases": TARGET_CASES,
    "subset_cases": len(examples),
    "subset_selection": "first N canonical rows",
    "logical_bytes_10bit": logical_bytes,
    "raw_storage_bytes_u16": len(examples) * VALUES * 2,
    "benchmark_process_high_water_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    "results": final,
    "pareto": sorted((item["name"] for item in winners)),
  }


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--cases", type=int, default=32)
  parser.add_argument("--repeats", type=int, default=3)
  parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
  args = parser.parse_args()
  artifact = benchmark(load_subset(args.cases), args.repeats)
  args.output.parent.mkdir(parents=True, exist_ok=True)
  args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
  print(f"wrote {args.output}")


if __name__ == "__main__":
  main()
