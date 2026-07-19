#!/usr/bin/env python3
"""LZMA baseline decompressor that preserves extensionless evaluator paths."""

import multiprocessing
import os
from pathlib import Path
import lzma

import numpy as np
from datasets import load_dataset


HERE = Path(__file__).resolve().parent
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", HERE / "compression_challenge_submission_decompressed"))


def decompress_bytes(data: bytes) -> np.ndarray:
  tokens = np.frombuffer(lzma.decompress(data), dtype=np.int16)
  return tokens.reshape(128, -1).T.reshape(-1, 8, 16)


def save_tokens(path: Path, tokens: np.ndarray) -> None:
  with path.open("wb") as output:
    np.save(output, tokens)


def decompress_example(example):
  name = example["json"]["file_name"]
  path = OUTPUT_DIR / name
  tokens = decompress_bytes(path.read_bytes())
  save_tokens(path, tokens)
  np.testing.assert_array_equal(tokens, example["token.npy"])


if __name__ == "__main__":
  num_proc = multiprocessing.cpu_count()
  dataset = load_dataset(
    "commaai/commavq",
    num_proc=num_proc,
    data_files={"train": ["data-0000.tar.gz", "data-0001.tar.gz"]},
  )
  dataset.map(decompress_example, desc="decompress_example", num_proc=num_proc, load_from_cache_file=False)
