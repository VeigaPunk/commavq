import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codec_frontier_benchmark import (  # noqa: E402
  LAYOUTS,
  SHAPE,
  benchmark,
  candidate_catalog,
  pack10,
  pareto,
  unpack10,
)


def tokens(seed: int = 7) -> np.ndarray:
  return np.random.default_rng(seed).integers(0, 1024, size=SHAPE, dtype=np.int16)


class TransformTest(unittest.TestCase):
  def test_every_layout_is_exact_and_deterministic(self):
    source = tokens()
    for layout in LAYOUTS:
      with self.subTest(layout=layout.name):
        first = layout.encode(source)
        self.assertEqual(first, layout.encode(source))
        self.assertEqual(len(first), layout.payload_bytes)
        np.testing.assert_array_equal(layout.decode(first), source)

  def test_pack10_rejects_out_of_range_truncation_and_nonzero_padding(self):
    with self.assertRaises(ValueError):
      pack10(np.array([1024], dtype=np.uint16))
    payload = pack10(np.arange(5, dtype=np.uint16))
    np.testing.assert_array_equal(unpack10(payload, 5), np.arange(5, dtype=np.uint16))
    with self.assertRaises(ValueError):
      unpack10(payload[:-1], 5)
    with self.assertRaises(ValueError):
      unpack10(payload[:-1] + bytes([payload[-1] | 0x80]), 5)


class HarnessTest(unittest.TestCase):
  def test_catalog_names_are_unique_and_all_candidates_round_trip(self):
    catalog = candidate_catalog()
    self.assertEqual(len({item.name for item in catalog}), len(catalog))
    examples = [{"name": "fixed", "tokens": tokens()}]
    first = benchmark(examples, repeats=2)
    second = benchmark(examples, repeats=2)
    self.assertEqual(
      [(item["name"], item["status"], item["compressed_bytes"]) for item in first["results"]],
      [(item["name"], item["status"], item["compressed_bytes"]) for item in second["results"]],
    )

  def test_pareto_requires_a_strict_axis_improvement(self):
    a = {"name": "a", "compressed_bytes": 10, "total_seconds": 2, "materialized_bytes_bound": 3}
    duplicate = {"name": "duplicate", "compressed_bytes": 10, "total_seconds": 2, "materialized_bytes_bound": 3}
    dominated = {"name": "dominated", "compressed_bytes": 11, "total_seconds": 2, "materialized_bytes_bound": 3}
    self.assertEqual({item["name"] for item in pareto([a, duplicate, dominated])}, {"a", "duplicate"})


if __name__ == "__main__":
  unittest.main()
