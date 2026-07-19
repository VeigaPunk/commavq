# commaVQ Neural Codec — Round 4

**Date:** 2026-07-19  
**Branch:** `leaderboard/codec-frontier`  
**Axes:** compression, losslessness, runtime, portability, reproducibility,
external standing, and resource durability

## Claim

The pinned upstream core exactly round-trips the canonical first case through
22 frames on CPU and CUDA, but commit `5bc967f` is not a reproducible evaluator
package and a 5,000-case score above 4.0 is not achievable with the measured
implementation and available host resources.

## Immutable inputs

- Codec: `ykstorm/commavq-lossless-codec` at
  `5bc967f218c551eeb74387b5ce016586baed77a2`.
- Dataset: `commaai/commavq` at
  `795c839a57b3c4eebd1a28b1ec04eb56d6000e81`, files 0000 and 0001.
- Case: `3b41c0fa8959aea6c118e5714f412a2e_13`, canonical row zero.
- Model: `commaai/commavq-gpt2m` at
  `12f0a5e31c22b492dc391aa348cbe422139e3087`, `gpt2m.onnx`,
  614,166,933 bytes, SHA-256
  `d2ee2bd95bc09811404938359395ce78a6dd59a540a44d781f838219752d6cd0`.
- CPU probe dependencies are version-pinned in
  `compression/repro/neural-codec-r4-metadata.json`.

`neural_codec_r4.py fetch` detached the external checkout, installed the pinned
probe environment, downloaded the revision-qualified model URL, and rejected a
model whose size or digest differed. Neither external checkout nor model is
committed.

## Upstream tests

With the model and canonical case at the paths expected by the checkout:

```text
$ time -p .venv/bin/python -m pytest codec/tests -q
..................................................                       [100%]
50 passed in 52.16s
real 52.66
user 1369.87
sys 14.02
```

The README's 47-test badge is stale; the pinned tree contains 50 passing tests.

## Exact bounded probes

Both probes use the same provider for encode and decode. `bpt` includes range
coder termination bytes. RSS is process high-water RSS and excludes GPU VRAM.

| Provider | Frames | Context boundary | Bytes | bpt | 10-bit ratio | Encode s | Decode s | Wall s | Peak RSS KiB | Exact |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| CPU | 3 | no | 197 | 4.104167 | 2.436548 | 14.990 | 12.228 | 28.651 | 3,676,848 | yes |
| CPU | 22 | yes | 570 | 1.619318 | 6.175439 | 249.649 | 390.311 | 641.648 | 7,423,696 | yes |
| CUDA | 22 | yes | 570 | 1.619318 | 6.175439 | 45.703 | 45.878 | 92.205 | 2,429,936 | yes |

The CPU 3-frame bitstream SHA-256 is
`ed06cc000d81a6bb427844f1d4bef95e0da52ce8185dacedb78e4727ca9f3eb0`.
The CPU 22-frame bitstream SHA-256 is
`b35c1df60d524f4d269e6a10c840c5ffc8316c3bbc90001f9242ca3d05b30472`.
The 22-frame result crosses the 19-frame sliding-context boundary and proves an
autoregressive inverse without spending an estimated 80+ minutes on one full
1,200-frame GPU round trip. Its unusually easy first-clip rate is not used as a
dataset-wide score.

CUDA required local CUDA 12/cuDNN 9 runtime wheels; the installed RTX 5070 has
12,227 MiB. A first attempt without those libraries fell back to CPU, so provider
availability was checked from the actual session before retaining CUDA timing.

## Decoder, model, and package bytes

The five source files selected by upstream packaging total 9,090 bytes. A
deterministic deflated archive of those files is 4,374 bytes. The public model is
614,166,933 external bytes. Python, ONNX Runtime, dataset, and Hugging Face
dependencies are also external and are not counted in the 4,374-byte archive.

Using upstream's advertised but not dataset-reproduced 2.47 bpt gives this
transparent 5,000-case arithmetic:

| Component | Bytes |
|---|---:|
| Projected bitstreams, 768,000,000 tokens | 237,120,000 |
| 5,000 four-byte frame headers | 20,000 |
| Deterministic decoder zip | 4,374 |
| External-model package subtotal, before ZIP entry framing | 237,144,374 |
| Public ONNX model, if made self-contained | 614,166,933 |
| Self-contained subtotal | 851,311,307 |

The corresponding optimistic bounds are 4.048167 with the model downloaded and
1.127672 with the model included. Actual ZIP framing, dependency availability,
and any rate above 2.47 bpt only lower these figures. Thus 4.0 has very little
unmeasured packaging margin and is not established by the first-case probe.

## Package blockers at the pinned commit

The upstream package cannot pass the canonical evaluator unchanged:

1. `np.save(OUTPUT_DIR / name, out)` creates `name.npy`; the evaluator loads the
   extensionless `name`.
2. Model and dataset downloads are not revision-pinned.
3. `submission_compress.py` resolves copy sources under a nonexistent
   `compression/codec` directory for this flattened checkout.
4. Compression prefers CUDA while shipped decompression forces CPU, violating
   the codec's own same-provider determinism condition.
5. Runtime dependencies are neither shipped nor pinned.

These are package failures, not failures of the bounded range-code inverse.

## 5,000-case feasibility

There are 6,000,000 frames. Linear extrapolation from the 22-frame CUDA proof is
144.3 encode days plus 144.8 decode days for one process. The CPU measurements
are slower and reached 7.1 GiB RSS. Parallelism is constrained by the single
12-GB GPU, while upstream's implementation processes one segment and token at a
time. No full-case or 5,000-case run was started after the bounded context probe.

The external 4.04 standing remains an upstream assertion: this round verifies
the mechanism and one canonical prefix, not the full score.

## RED / GREEN

RED before adding the reproduction test:

```text
ModuleNotFoundError: No module named 'compression/repro/test_neural_codec_r4'
Ran 1 test in 0.000s
FAILED (errors=1)
```

GREEN after adding pinned metadata, acquisition/probe logic, and projection
checks, together with all prior reproduction tests:

```text
Ran 10 tests in 1.271s
OK
```
