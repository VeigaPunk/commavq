import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from one_case_roundtrip import round_trip_case


class OneCaseRoundTripTest(unittest.TestCase):
  def test_extensionless_archive_round_trip_uses_evaluator_paths(self):
    tokens = (np.arange(1200 * 8 * 16, dtype=np.int32) % 1024).astype(np.int16).reshape(1200, 8, 16)
    name = "3b41c0fa8959aea6c118e5714f412a2e_13"

    with tempfile.TemporaryDirectory() as temporary_directory:
      archive_path, output_path = round_trip_case(tokens, name, Path(temporary_directory))

      self.assertEqual(archive_path.name, "compression_challenge_submission")
      self.assertEqual(archive_path.suffix, "")
      self.assertEqual(
        output_path,
        Path(temporary_directory) / "compression_challenge_submission_decompressed" / name,
      )
      self.assertTrue(output_path.is_file())
      np.testing.assert_array_equal(np.load(output_path), tokens)
      with zipfile.ZipFile(archive_path) as archive:
        self.assertEqual(sorted(archive.namelist()), [name, "decompress.py"])


if __name__ == "__main__":
  unittest.main()
