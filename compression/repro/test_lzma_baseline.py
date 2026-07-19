import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compress import (  # noqa: E402
  DATASET_REVISION,
  compress_tokens,
  resume_rows,
  validate_dataset_contract,
)


def row(name: str, value: int = 0) -> dict:
  tokens = np.full((1200, 8, 16), value, dtype=np.int16)
  return {"json": {"file_name": name}, "token.npy": tokens}


class DatasetContractTest(unittest.TestCase):
  def test_revision_is_canonical_and_contract_requires_exact_unique_plain_names(self):
    self.assertEqual(DATASET_REVISION, "795c839a57b3c4eebd1a28b1ec04eb56d6000e81")
    self.assertEqual(validate_dataset_contract([row("a"), row("b")], 2), ["a", "b"])
    for invalid in ([row("a")], [row("a"), row("a")], [row("../a"), row("b")]):
      with self.subTest(invalid=invalid):
        with self.assertRaises(RuntimeError):
          validate_dataset_contract(invalid, 2)


class ResumeTest(unittest.TestCase):
  def test_validates_existing_and_atomically_repairs_only_invalid_payloads(self):
    rows = [row("a", 1), row("b", 2)]
    with tempfile.TemporaryDirectory() as temporary_directory:
      output = Path(temporary_directory) / "payloads"
      progress = Path(temporary_directory) / "progress.jsonl"
      output.mkdir()
      valid = compress_tokens(rows[0]["token.npy"])
      (output / "a").write_bytes(valid)
      (output / "b").write_bytes(b"corrupt")

      stats, manifest = resume_rows(rows, output, progress)

      self.assertEqual(stats, {"pre_existing": 2, "validated": 1, "repaired": 1, "written": 1})
      self.assertEqual((output / "a").read_bytes(), valid)
      self.assertEqual(len(manifest), 2)
      self.assertEqual(len(progress.read_text().splitlines()), 2)
      self.assertFalse(list(output.glob("*.tmp")))

  def test_failed_repair_preserves_existing_artifact(self):
    rows = [row("a", 1)]
    with tempfile.TemporaryDirectory() as temporary_directory:
      output = Path(temporary_directory) / "payloads"
      output.mkdir()
      artifact = output / "a"
      artifact.write_bytes(b"corrupt-but-preserved")

      with mock.patch("compress.compress_tokens", side_effect=RuntimeError("stop")):
        with self.assertRaises(RuntimeError):
          resume_rows(rows, output, Path(temporary_directory) / "progress.jsonl")

      self.assertEqual(artifact.read_bytes(), b"corrupt-but-preserved")
      self.assertFalse(list(output.glob("*.tmp")))


if __name__ == "__main__":
  unittest.main()
