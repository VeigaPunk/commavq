# Compression reproducibility milestones

## M00: protected fork branch

`./setup_fork.sh` verifies the commaai fetch URL, disables its push URL, configures
the VeigaPunk fork, and switches without resetting work to
`leaderboard/codec-frontier`. Push explicitly with:

```bash
git push -u veigapunk HEAD:refs/heads/leaderboard/codec-frontier
```

## M01: locked environment

Python 3.11 and all transitive packages are frozen by `pyproject.toml` and
`uv.lock`:

```bash
uv sync --frozen
uv lock --check
```

`COMMAVQ_NUM_PROC=4` activates `sitecustomize.py` to bound the official scripts
on memory-constrained hosts.

## M02: one-case evaluator path

```bash
uv run --frozen python -m unittest -v test_one_case_roundtrip.py
uv run --frozen python one_case_roundtrip.py --data-file data-0000.tar.gz --index 0
```

The concrete case is `3b41c0fa8959aea6c118e5714f412a2e_13`; source and
reconstructed token SHA-256 are both
`ad5be8abbcad55bc13e7e39d7c030d814e6262f15444ddb681d1c538e0ad3a4c`.
The archive and reconstructed token filename are intentionally extensionless,
matching `evaluate.py` exactly. Generated proof artifacts live under `run/`.

Failure traps: Hugging Face access is needed when the shard is not cached;
excessive worker counts can exhaust memory; and `np.save(path, tokens)` silently
appends `.npy` to extensionless case names. The submitted decompressor writes
through an open file handle to preserve the evaluator's exact path.
