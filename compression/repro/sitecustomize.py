"""Bound official CommavQ multiprocessing on memory-constrained hosts."""

import multiprocessing
import os


if limit := os.environ.get("COMMAVQ_NUM_PROC"):
  multiprocessing.cpu_count = lambda: int(limit)
