#!/usr/bin/env python3
from __future__ import annotations

import multiprocessing
import os
import resource
import time
from pathlib import Path

import numpy as np
from datasets import load_dataset


archive_path = Path(os.environ.get('PACKED_ARCHIVE', './compression_challenge_submission.zip'))
unpacked_archive = Path(os.environ.get('UNPACKED_ARCHIVE', './compression_challenge_submission_decompressed/'))

DATASET_NAME = 'commaai/commavq'
DATASET_REVISION = '795c839a57b3c4eebd1a28b1ec04eb56d6000e81'
DATA_FILES = {'train': ['data-0000.tar.gz', 'data-0001.tar.gz']}
TARGET_CASES = 5000


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


def compare(example):
  name = example['json']['file_name']
  tokens = np.load(unpacked_archive / name)
  gt_tokens = example['token.npy']
  assert np.all(tokens == gt_tokens), f'decompressed data does not match original data for {name}'


if __name__ == '__main__':
  num_proc = int(os.environ.get('COMMAVQ_NUM_PROC', min(4, multiprocessing.cpu_count())))
  start_wall = time.perf_counter()
  start_cpu = os.times()
  start_self = resource.getrusage(resource.RUSAGE_SELF)
  start_children = resource.getrusage(resource.RUSAGE_CHILDREN)

  ds = load_dataset_rows(num_proc)
  ds.map(compare, desc='compare', num_proc=num_proc, load_from_cache_file=False)

  elapsed_wall = time.perf_counter() - start_wall
  end_cpu = os.times()
  end_self = resource.getrusage(resource.RUSAGE_SELF)
  end_children = resource.getrusage(resource.RUSAGE_CHILDREN)

  rate = (len(ds) * 1200 * 128 * 10 / 8) / archive_path.stat().st_size
  print(f'Compression rate: {rate:.1f}')
  print(f'Exact array equality: {len(ds)}/{TARGET_CASES}')
  print(f'Evaluation wall-time: {elapsed_wall:.2f}')
  print(f'User CPU seconds: {end_cpu.user - start_cpu.user:.2f}')
  print(f'System CPU seconds: {end_cpu.system - start_cpu.system:.2f}')
  print(f'Available peak ru_maxrss KiB: {max(end_self.ru_maxrss, end_children.ru_maxrss)}')
