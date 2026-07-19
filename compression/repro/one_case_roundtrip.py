#!/usr/bin/env python3
"""Prove one commaVQ case through evaluator-compatible archive paths."""

import argparse
import hashlib
import importlib.util
import shutil
import zipfile
from pathlib import Path

import lzma
import numpy as np
from datasets import load_dataset


HERE = Path(__file__).resolve().parent
ARCHIVE_NAME = 'compression_challenge_submission'
OUTPUT_NAME = 'compression_challenge_submission_decompressed'

DATASET_NAME = 'commaai/commavq'
DATASET_REVISION = '795c839a57b3c4eebd1a28b1ec04eb56d6000e81'
DATA_FILES = {'train': ['data-0000.tar.gz', 'data-0001.tar.gz']}
TARGET_CASES = 5000


def compress_tokens(tokens: np.ndarray) -> bytes:
  transposed = tokens.astype(np.int16).reshape(-1, 128).T.ravel().tobytes()
  return lzma.compress(transposed)


def _load_archived_decompressor(path: Path):
  spec = importlib.util.spec_from_file_location('commavq_submission_decompress', path)
  if spec is None or spec.loader is None:
    raise RuntimeError(f'Cannot load {path}')
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


def round_trip_case(tokens: np.ndarray, name: str, workspace: Path) -> tuple[Path, Path]:
  """Archive, extract, and reconstruct one case exactly where evaluate.py reads it."""
  if Path(name).name != name:
    raise ValueError(f'Evaluator case name must be a plain filename: {name!r}')

  workspace.mkdir(parents=True, exist_ok=True)
  staging = workspace / 'staging'
  output_dir = workspace / OUTPUT_NAME
  archive_path = workspace / ARCHIVE_NAME
  if staging.exists():
    shutil.rmtree(staging)
  if output_dir.exists():
    shutil.rmtree(output_dir)
  staging.mkdir()
  output_dir.mkdir()

  # ensure deterministic, evaluator-compatible extensionless output paths
  (staging / name).write_bytes(compress_tokens(tokens))
  shutil.copy2(HERE / 'decompress.py', staging / 'decompress.py')
  with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(staging / name, name)
    archive.write(staging / 'decompress.py', 'decompress.py')

  with zipfile.ZipFile(archive_path) as archive:
    archive.extractall(output_dir)
  decompressor = _load_archived_decompressor(output_dir / 'decompress.py')
  rebuilt = decompressor.decompress_bytes((output_dir / name).read_bytes())
  output_path = output_dir / name
  decompressor.save_tokens(output_path, rebuilt)
  np.testing.assert_array_equal(np.load(output_path), tokens)
  return archive_path, output_path


def validate_dataset_contract() -> None:
  dataset = load_dataset(
    DATASET_NAME,
    split='train',
    data_files=DATA_FILES,
    revision=DATASET_REVISION,
  )
  if len(dataset) != TARGET_CASES:
    raise RuntimeError(f'Expected {TARGET_CASES} cases, got {len(dataset)}')
  names = [row['json']['file_name'] for row in dataset]
  if len(set(names)) != TARGET_CASES:
    raise RuntimeError('Expected 5,000 unique file names in canonical split')


def load_one_case(index: int, data_file: str) -> tuple[str, np.ndarray]:
  dataset = load_dataset(
    DATASET_NAME,
    split='train',
    num_proc=1,
    data_files={'train': [data_file]},
    revision=DATASET_REVISION,
  )
  row = dataset[index]
  return row['json']['file_name'], np.asarray(row['token.npy'], dtype=np.int16)


def sha256(data: bytes) -> str:
  return hashlib.sha256(data).hexdigest()


def main(index: int, data_file: str, workspace: Path) -> None:
  validate_dataset_contract()
  name, tokens = load_one_case(index, data_file)
  archive_path, output_path = round_trip_case(tokens, name, workspace)
  rebuilt = np.load(output_path)
  print(f'case={name}')
  print(f'tokens_sha256={sha256(tokens.tobytes())}')
  print(f'rebuilt_sha256={sha256(rebuilt.tobytes())}')
  print(f'archive={archive_path.resolve()}')
  print(f'output={output_path.resolve()}')
  print('round_trip=exact')


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--data-file', default='data-0000.tar.gz')
  parser.add_argument('--index', type=int, default=0)
  parser.add_argument('--workspace', type=Path, default=HERE / 'run' / 'one-case')
  arguments = parser.parse_args()
  main(arguments.index, arguments.data_file, arguments.workspace)
