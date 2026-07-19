# Continue Verified-First — Round 2

**Date:** 2026-07-19

**Branch:** `leaderboard/codec-frontier`

**Canonical dataset:** `commaai/commavq@795c839a57b3c4eebd1a28b1ec04eb56d6000e81`, train files `data-0000.tar.gz` and `data-0001.tar.gz`

## Axes and verdict

The retained frontier improves losslessness, evaluator compatibility,
reproducibility, resource evidence, and interruption durability without changing
the LZMA token transform. **Pareto verdict: retain.** All 2,895 prior payloads
were source-validated before reuse; all 2,105 absent cases were written through
fsynced temporary files and atomic replacement. Exactly 5,000 unique plain names
were packaged and evaluated.

## RED / GREEN

RED, before the resumable API existed:

```text
$ .venv/bin/python -m unittest -v test_lzma_baseline.py
ImportError: cannot import name 'resume_rows' from 'compress'
FAILED (errors=1)
```

GREEN:

```text
$ .venv/bin/python -m unittest -v test_lzma_baseline.py test_one_case_roundtrip.py
Ran 4 tests in 0.023s
OK
```

The tests cover the pinned revision, exact cardinality, unique/plain names,
validation and repair accounting, exact retained bytes, temporary cleanup, and
preservation of an existing artifact when replacement generation fails.

## Encode and incremental recovery

```text
$ .venv/bin/python ../compress.py --num-proc 4
progress=1/5000 status=validated
...
progress=5000/5000 status=written
pre_existing=2895 validated=2895 repaired=0 written=2105
encode wall-time=566.078629229 s
user CPU=552.59 s; system CPU=3.57 s; available peak ru_maxrss=1919704 KiB
```

Progress was durably flushed to `compression/repro/run/compression_progress.jsonl`
after each case. A crash leaves completed final paths valid and any hidden
temporary path unreferenced; rerunning revalidates every final path, removes a
failed temporary, and atomically repairs only invalid/missing cases. Generated
payloads, archive, decoded arrays, and run logs remain ignored.

## Deterministic package

```text
archive entries=5001 (5000 extensionless payloads + decompress.py)
unique entries=5001
archive bytes=601812420
logical numerator=960000000
compression ratio=1.5951814354379725
manifest/payload/archive hash equality=5000/5000
```

Hashes:

```text
066b6af1e05e327d4f27391a3a940b3ba7c38c440875a48d27c937d75811540a  compression/repro/lzma-5000-manifest.json
e39f943448836950002bd8a46a32133607f6ba9aa06539f2b0ccebc6756ab55d  compression/compression_challenge_submission.zip
```

The archive uses sorted names, fixed ZIP timestamps and modes, and stored ZIP
members because each payload is already LZMA-compressed.

## Fresh decode and exact evaluator pass

The archive was extracted only after deleting and recreating the decode output.
The archived `decompress.py` then reconstructed extensionless NumPy files in
place, exactly where the evaluator reads them.

```text
Decoded exact cases: 5000/5000
Decode wall-time: 269.54 s
Decode user CPU: 437.87 s; system CPU: 2.51 s
Decode available peak ru_maxrss: 2043912 KiB

Compression rate: 1.6
Exact array equality: 5000/5000
Evaluation wall-time: 306.92 s
Evaluation user CPU: 213.50 s; system CPU: 0.38 s
Evaluation available peak ru_maxrss: 2040928 KiB
```

Commands are documented in `compression/repro/README.md`; the evaluator was
run with `PACKED_ARCHIVE`, `UNPACKED_ARCHIVE`, and `COMMAVQ_NUM_PROC=4` against
the fresh output.

## Failures and recovery

The required first `xask --spark --gs codex` call timed out after 120 seconds
with no stdout, so execution continued in-session. `/usr/bin/time` was absent;
the scripts' `perf_counter`, CPU accounting, and `resource.getrusage` evidence
were used instead. Neither failure modified a final payload. Four workers were
retained as the conservative bound on a 30 GiB host with swap already occupied.

## Rejected alternative

Skipping validation of the 2,895 existing paths was rejected: it would reduce
runtime but could silently preserve artifacts from a different source revision.
