#!/usr/bin/env python3
"""LZMA baseline decompressor that preserves extensionless evaluator paths."""

import multiprocessing
import os
import resource
import time
from pathlib import Path
import lzma

import numpy as np
from datasets import load_dataset


HERE = Path(__file__).resolve().parent
OUTPUT_DIR = Path(os.environ.get('OUTPUT_DIR', HERE / 'compression_challenge_submission_decompressed'))

DATASET_NAME = 'commaai/commavq'
DATASET_REVISION = '795c839a57b3c4eebd1a28b1ec04eb56d6000e81'
DATA_FILES = {'train': ['data-0000.tar.gz', 'data-0001.tar.gz']}
TARGET_CASES = 5000


def decompress_bytes(data: bytes) -> np.ndarray:
  tokens = np.frombuffer(lzma.decompress(data), dtype=np.int16)
  return tokens.reshape(128, -1).T.reshape(-1, 8, 16)


def save_tokens(path: Path, tokens: np.ndarray) -> None:
  with path.open('wb') as output:
    np.save(output, tokens)


def load_dataset_rows(num_proc: int):
  dataset = load_dataset(
    DATASET_NAME,
    split='train',
    num_proc=num_proc,
    revision=DATASET_REVISION,
    data_files=DATA_FILES,
  )
  if len(dataset) != TARGET_CASES:
    raise RuntimeError(f'Expected {TARGET_CASES} cases, got {len(dataset)}')
  names = [row['json']['file_name'] for row in dataset]
  if len(set(names)) != TARGET_CASES:
    raise RuntimeError('Expected 5,000 unique file names in canonical split')
  return dataset


def decompress_example(example):
  name = example['json']['file_name']
  path = OUTPUT_DIR / name
  tokens = decompress_bytes(path.read_bytes())
  save_tokens(path, tokens)
  np.testing.assert_array_equal(tokens, example['token.npy'])


if __name__ == '__main__':
  num_proc = int(os.environ.get('COMMAVQ_NUM_PROC', min(4, multiprocessing.cpu_count())))
  start = time.perf_counter()
  self_before = resource.getrusage(resource.RUSAGE_SELF)
  children_before = resource.getrusage(resource.RUSAGE_CHILDREN)
  dataset = load_dataset_rows(num_proc)
  dataset.map(decompress_example, desc='decompress_example', num_proc=num_proc, load_from_cache_file=False)
  self_after = resource.getrusage(resource.RUSAGE_SELF)
  children_after = resource.getrusage(resource.RUSAGE_CHILDREN)
  print(f'Decoded exact cases: {len(dataset)}/{TARGET_CASES}')
  print(f'Decode wall-time: {time.perf_counter() - start:.2f}')
  print(f'Decode user CPU seconds: {(self_after.ru_utime - self_before.ru_utime) + (children_after.ru_utime - children_before.ru_utime):.2f}')
  print(f'Decode system CPU seconds: {(self_after.ru_stime - self_before.ru_stime) + (children_after.ru_stime - children_before.ru_stime):.2f}')
  print(f'Decode available peak ru_maxrss KiB: {max(self_after.ru_maxrss, children_after.ru_maxrss)}')
