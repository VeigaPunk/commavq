# commaVQ Codec Frontier — Round 3

**Date:** 2026-07-19  
**Branch:** `leaderboard/codec-frontier`  
**Dataset:** `commaai/commavq@795c839a57b3c4eebd1a28b1ec04eb56d6000e81`  
**Axes:** compression, losslessness, runtime/trials per hour, portability,
reproducibility, and resource durability

## Claim

On the fixed first-256-case subset, solid LZMA with the current token-axis byte
order is the compression-axis qualification winner: it is exact, reduces the
current per-example payload total from 30,632,528 to 28,456,416 bytes (7.10%),
and raises logical ratio from 1.604569 to 1.727273. It trades runtime and retained
materialization for that gain, so this report promotes it only to full-5,000
qualification, not directly to the evaluator archive.

The baseline subset total exactly equals the first 256 entries of the committed
5,000-case manifest. All candidates use only Python's standard library and NumPy
after token loading, and every measured decode was array-equal to its source.

## RED / GREEN

RED, before the benchmark test existed:

```text
$ .venv/bin/python -m unittest -v test_codec_frontier_benchmark.py
ModuleNotFoundError: No module named 'test_codec_frontier_benchmark'
Ran 1 test in 0.000s
FAILED (errors=1)
```

GREEN, including prior reproducibility tests:

```text
$ .venv/bin/python -m unittest -v test_codec_frontier_benchmark.py test_lzma_baseline.py test_one_case_roundtrip.py
Ran 8 tests in 1.335s
OK
```

Coverage includes deterministic/exact round trips for every ordering, modulo
delta, and packing transform; 10-bit range, truncation, and padding rejection;
unique catalog names; every codec round trip; deterministic compressed sizes;
and strict Pareto dominance.

## Fixed-subset benchmark

Command:

```text
.venv/bin/python codec_frontier_benchmark.py --cases 256 --repeats 3 \
  --output run/codec-frontier-r3.json
```

Logical numerator: 49,152,000 bytes (the evaluator's 10-bit convention).
Available process high-water RSS: 1,503,992 KiB, including the cached dataset.
`Bound MiB` is deterministic retained input/output materialization, excluding
dataset and codec-internal allocation. Times are medians for Pareto candidates;
non-frontier probes are single trials. `Trials/h` is `3600 / total seconds`.

| Candidate | Bytes | Ratio | Enc s | Dec s | Total s | Trials/h | Bound MiB | Runs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline/per-example/token-axis-u16/lzma` | 30,632,528 | 1.604569 | 11.219 | 0.759 | 11.967 | 300.8 | 29.5 | 3 |
| `solid/time-major-u16/lzma` | 35,293,880 | 1.392649 | 62.437 | 1.672 | 64.109 | 56.2 | 108.7 | 1 |
| `solid/token-axis-u16/lzma` | 28,456,416 | 1.727273 | 35.635 | 0.680 | 36.310 | 99.1 | 102.1 | 3 |
| `solid/spatial-reversed-u16/lzma` | 28,585,908 | 1.719449 | 103.520 | 1.836 | 105.356 | 34.2 | 102.3 | 1 |
| `solid/temporal-delta-mod1024-u16/lzma` | 35,335,096 | 1.391025 | 125.503 | 4.516 | 130.019 | 27.7 | 108.7 | 1 |
| `solid/token-axis-pack10/lzma` | 34,746,468 | 1.414590 | 40.992 | 6.905 | 47.897 | 75.2 | 80.0 | 1 |
| `solid/temporal-delta-mod1024-pack10/lzma` | 35,890,204 | 1.369510 | 33.957 | 5.385 | 39.341 | 91.5 | 81.1 | 1 |
| `per-example/token-axis-u16/bz2` | 31,916,885 | 1.540000 | 3.810 | 1.418 | 5.247 | 686.1 | 30.7 | 3 |
| `per-example/token-axis-u16/zlib` | 37,987,346 | 1.293905 | 2.528 | 0.268 | 2.785 | 1,292.7 | 36.5 | 3 |
| `per-example/token-axis-u16/gzip` | 37,990,418 | 1.293800 | 2.525 | 0.257 | 2.782 | 1,293.9 | 36.5 | 3 |
| `solid/token-axis-u16/bz2` | 30,097,571 | 1.633089 | 3.875 | 2.373 | 7.430 | 484.5 | 103.7 | 3 |
| `solid/token-axis-u16/zlib` | 37,945,261 | 1.295340 | 2.733 | 0.291 | 3.026 | 1,189.6 | 111.2 | 3 |
| `per-example/token-axis-u16/zlib+lzma` | 38,004,556 | 1.293319 | 7.128 | 0.272 | 7.399 | 486.5 | 36.5 | 1 |

Exact Pareto set over compressed bytes, median total time, and deterministic
materialized-byte bound: baseline per-example LZMA; per-example BZ2, zlib, and
gzip; solid token-axis BZ2, zlib, and LZMA. Every final winner has three runs.

Linear qualification estimates for solid token-axis LZMA are about 709 seconds
and 1.95 GiB retained materialization at 5,000 cases. Those are planning bounds,
not full-run evidence; evaluator packaging still needs deterministic case offsets
and a fresh 5,000-array equality pass.

## Rejected alternative

Promoting 10-bit packing or modulo temporal delta was rejected: both are exact
and portable, but every packed/delta LZMA variant is strictly dominated on this
subset. Packing shrinks the pre-compression stream yet disrupts the byte patterns
that LZMA exploits; temporal differencing likewise increases compressed bytes.

The required first `xask --spark --gs codex` call timed out after 120 seconds and
produced no stdout, so the implementation and measurements proceeded in-session.

## Round 3 evidence audit

`EVIDENCE AUDIT: 0 moves with evidence, 4 moves without, 2 dropped, 2 spoof_flagged`

Audit hash `d39f382c0fba657f5958378d8010801a32b9c99c84f4f6e56e8481f54966fb76`
matched the source-map reveal after blinded scoring. The empty required xask
payload invalidated the executor's proposal at intake, so a separate reviewer
re-ran the tests and deterministic 256-case comparison. It reproduced
`30,632,528 → 28,456,416` bytes (`7.103926%`) and verified local/remote commit
`715b171a94ed8b5fc7c39f9a91d5fcc26e2b87d9`.

**Final verdict:** accept the benchmark harness because it improves repeatable
frontier observability without changing submission behavior. Do not promote the
solid-LZMA candidate: its measured runtime is roughly three times baseline and
it lacks full-package evidence. Carry the pinned public 4.04 arithmetic-codec
reproduction route into Round 4.
