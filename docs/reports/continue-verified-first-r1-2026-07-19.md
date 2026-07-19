# Continue Verified-First — Round 1

**Date:** 2026-07-19  
**Round:** 1  
**Posture:** Godspeed; preserve only non-regressing, evidence-bearing moves.

## Planner Phase 0 baseline

Phase 0 began at `bbcfe8c` (`ci: update leaderboard tables`) on `master`, before the reproducibility delta. The baseline had no `compression/repro/` harness. Round 1 therefore treated branch safety, environment reproducibility, and one evaluator-compatible concrete round trip as prerequisites to codec optimization. The working frontier observed after those moves is `3037c38` on `leaderboard/codec-frontier`.

## Axes

1. **Repository safety** — prevent accidental pushes to the upstream repository and preserve fork-local work.
2. **Reproducibility** — pin the runtime and transitive dependency graph.
3. **Evaluator fidelity** — match the official extensionless archive and output-path contract.
4. **Evidence quality** — retain exact, inspectable proof and reject unsupported recommendations.
5. **Compression frontier** — survey codec improvements without trading away any verified axis.

The Round 1 Pareto filter retained a move only when it improved at least one axis and harmed none.

## Roster and xask targets

| Lane | Round 1 responsibility | xask target |
|---|---|---|
| Planner | Establish the Phase 0 baseline and verified-first ordering | Native WWKD planning; no xask gate |
| Repro executor | Land branch, environment, and evaluator-path proof moves | `codex` via `xask --spark --gs codex` |
| Codec scout | Survey codec candidates without bypassing the evidence gate | `codex` via `xask --spark --gs codex` |
| Artifact-contract scout | Survey a generalized artifact contract | `codex` via `xask --spark --gs codex` |
| Reviewer | Triage evidence, spoof flags, contradictions, and the blinded verdicts | `codex` via `xask --spark --gs codex`; complete |

## Observed commits

| Commit | Observation | Evidence-bearing delta |
|---|---|---|
| `3f6cc4d` | `repro: protect fork branch setup` | Adds `compression/repro/setup_fork.sh`, verifies the commaai fetch URL, disables upstream push, configures the VeigaPunk fork, and switches to `leaderboard/codec-frontier`. |
| `cf6187a` | `repro: lock baseline environment` | Adds the Python 3.11 project lock, `uv.lock`, a multiprocessing bound, and the generated-run ignore rule. |
| `3037c38` | `repro: prove extensionless one-case round trip` | Adds an evaluator-shaped archive/decompress path, a structural unit test, and a recorded concrete case whose source and rebuilt token SHA-256 are both `ad5be8abbcad55bc13e7e39d7c030d814e6262f15444ddb681d1c538e0ad3a4c`. |

## SYNTHESIS_READY moves

- **M001 — Land the first three reproducibility milestones.** Retain `3f6cc4d`, `cf6187a`, and `3037c38`: together they protect the fork workflow, lock the environment, and prove an evaluator-compatible extensionless one-case exact round trip.
- **M002 — Pin and gate the canonical dataset.** Direct inspection verified that the loading paths omit a dataset revision pin and explicit 5,000-unique-name gate. Accept the finding as a Round-2 implementation move; the observable has not improved until code and tests land.
- **M003 — Bound the integrity probe.** The exhaustive partial-artifact probe timed out without durable source-equality evidence. Reject the broad readiness claim and retain only the next move: an incremental, bounded, resumable verifier.

## SOURCE_MAP reveal

The source map was revealed only after blinded review:

- **M001** → execution proposal (`P1`).
- **M002** → correctness proposal (`P2`).
- **M003** → empirical proposal (`P3`).

## Dropped unevidenced moves

The following candidate proposals were removed before the synthesis-ready evidence audit:

1. **Codec recommendation.** Dropped because no benchmark command, output, ratio, runtime, or reproducible artifact accompanied the recommendation.
2. **Artifact-contract proposal.** Dropped because no concrete contract artifact, consumer test, or runnable compatibility result accompanied the proposal.

Neither proposal changes the frontier until it returns with exact evidence.

## Contradictions

- The codec route seeks immediate score improvement, while the verified-first ordering forbids adopting a codec recommendation before a reproducible evaluator path exists. Round 1 records the route but drops the recommendation.
- The artifact-contract route seeks generalization, while the concrete proof currently covers one case. Round 1 records the route but drops the proposal rather than presenting generality as verified.
- The audit line reports `0 dropped`, while this report records two dropped unevidenced proposals. The audit population is only M001–M003 after pre-audit proposal filtering; the two proposals are outside that three-move population.
- All three synthesis-ready moves were initially `spoof_flagged` even though repository artifacts existed. Blinded reviewer triage verified M001–M002 but found M003's broader support claim unsupported; only its bounded probe is retained.

## EVIDENCE AUDIT

`3 moves with evidence, 0 moves without, 0 dropped, 3 spoof_flagged`

**verified audit_hash:** `7847c3aab2aecb13b423c5f0f7f217b2a91b7af2a8631b9c41996defd7824e45`

## Reviewer triage

`M001 VERIFIED, M002 VERIFIED, M003 UNSUPPORTED`

## Final blinded verdicts

- **M001 — ACCEPT.** Preserve the three verified commits and remote durability.
- **M002 — ACCEPT as a Round-2 implementation move.** Add and test the shared revision/cardinality contract before claiming evaluator-scale correctness.
- **M003 — REJECT as unsupported; retain the bounded probe.** Do not claim full-artifact integrity until a resumable verifier records source equality.

## Fork safety state

- Alias `fork` points to `https://github.com/VeigaPunk/commavq.git` for fetch and push.
- `remote.pushDefault=fork` makes the VeigaPunk fork the default push destination.
- Origin fetch remains `https://github.com/commaai/commavq.git`; origin push is disabled as `no_push://commaai-origin-forbidden`.

## Optimization routes surveyed

- LZMA as the reproducible baseline and current one-case round-trip implementation.
- Alternative codec selection as a compression-ratio/runtime route; surveyed only, with the unevidenced recommendation dropped.
- Token-layout transforms, including the verified transpose/flatten ordering before compression.
- Compression-level and codec-parameter sweeps, contingent on evaluator-shaped benchmark evidence.
- Dataset-scale execution under bounded multiprocessing, contingent on preserving exact reconstruction.
- A generalized artifact contract for archive naming, decompressor placement, output naming, dtype, and shape; surveyed only, with the unevidenced proposal dropped.

## Commit delta

Relative to Phase 0 baseline `bbcfe8c`, the observed frontier is three commits ahead:

```text
3f6cc4d repro: protect fork branch setup
cf6187a repro: lock baseline environment
3037c38 repro: prove extensionless one-case round trip
```

Aggregate delta: **9 files changed, 872 insertions, 0 deletions**. The delta adds one fork-safety script, one locked Python environment, one evaluator-compatible decompressor, one concrete round-trip driver, one structural test, supporting documentation, and generated-run exclusion.

## Evidence note

`evidence: none — documentation artifact`
