import json
import unittest
from pathlib import Path

import neural_codec_r4 as neural


class NeuralCodecR4Test(unittest.TestCase):
  def test_metadata_matches_executable_pins(self):
    metadata = json.loads((Path(__file__).parent / "neural-codec-r4-metadata.json").read_text())
    self.assertEqual(metadata["codec"]["commit"], neural.CODEC_COMMIT)
    self.assertEqual(metadata["dataset"]["revision"], neural.DATASET_REVISION)
    self.assertEqual(metadata["model"]["revision"], neural.MODEL_REVISION)
    self.assertEqual(metadata["model"]["sha256"], neural.MODEL_SHA256)
    self.assertEqual(metadata["model"]["bytes"], neural.MODEL_BYTES)
    self.assertEqual(tuple(metadata["probe_requirements"]), neural.PROBE_REQUIREMENTS)

  def test_documented_247_bpt_projection_counts_all_fixed_bytes(self):
    result = neural.full_projection(2.47, 1.0, 2.0, decoder_zip_bytes=4_374)
    self.assertEqual(result["tokens"], 768_000_000)
    self.assertEqual(result["logical_bytes_10bit"], 960_000_000)
    self.assertEqual(result["projected_bitstream_bytes"], 237_120_000)
    self.assertEqual(result["projected_headers_bytes"], 20_000)
    self.assertEqual(
      result["projected_self_contained_bytes_before_zip_framing"],
      237_120_000 + 20_000 + 4_374 + neural.MODEL_BYTES,
    )
    self.assertLess(result["projected_self_contained_ratio_upper_bound"], 1.13)
    self.assertLess(result["projected_external_model_ratio_upper_bound"], 4.05)


if __name__ == "__main__":
  unittest.main()
