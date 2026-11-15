# Full typed rule capture and first control store

Development correspondence, NOT stock admission. All73 current rule-family
entry points are captured with source hashes into word/guard IR. The guarded
control store preserves field OR merges and deferred addressed arena writes.
Both existing original-source fixtures match every SPEC register/bank at every
semantic transition. The report explicitly separates capture/lowering from
unimplemented native actions.

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m tools.kernel_control_store \
  --config benchmarks/kernel-full-source-stock/config.json \
  --report /mnt/scratch/leanputer-runs/architecture-budget/store.json \
  --offline-verify benchmarks/kernel-full-source-stock/source.jsonl
```

[report.json](report.json) is the measured complete store, not a per-proof
program. Its46K records FAIL the16K/100M budget; the estimated1.8M forwards per
witness FAIL latency. It is not emitted. Phase-specific control dispatch is the
next compiler correction. Coverage of the CURRENT rule families does not remove
the semantic gaps documented in kernel/target.md.
