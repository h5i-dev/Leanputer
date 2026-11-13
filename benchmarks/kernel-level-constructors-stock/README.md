# Shared symbolic constructors in stock layers

The COMPLETE pinned Lean `mk_max`/`mk_imax` algorithms call the SAME generic
structural equality, necessarily-nonzero and checked successor-offset services.
See [algorithm/source mapping](../../docs/kernel/level-services.md). Declarations,
names/counts and symbolic parameters remain data. No new datatype catalog.

Twelve focused stock operation inputs completed DONE. They include allocation
of structurally identical levels at distinct addresses followed by comparison,
symbolic IMax nonzero handling, successor separation, both-side Max absorption,
equal-base offsets, raw construction and IMax calling Max. Every register and
every materialized heap/stack/context cache row matches the development spec.
The CPU contract additionally checks all constructor branches and overflow,
compares output syntax to independent LevelOps, and retains prior typed-call
contracts:8tests PASS4.580s. No host comparison answers enter native input.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --group constructors --device cuda \
  --report /mnt/scratch/leanputer-runs/typed-level-constructors-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_level_transition tests.test_kernel_native_cells -v
```

[Exact report and inputs](report.json): same128heap/16stack/8context/8-bit/f128
capacities, stock Qwen3_5ForCausalLM forward/cache, compiler-generated BF16weights.
194,800,036parameters/389,600,072weight bytes; H1728/L51/FFN512;
compile5.169027s, GPU10.085165s;59boot+130forwards;
CUDApeak458,844,672bytes, hostRSS1,689,321,472bytes.
Timings exclude imports/offline validation; no matched speed/compression or
steady-state/full-source throughput claim. No weights saved or broad campaign.

DONE is OPERATION completion, not proof acceptance. Canonical normalization,
conversion, native inference and full declaration admission are still unfinished.
Structural comparison is not definitional universe equivalence. No added native
theorem/mathlib coverage or formal-verification claim follows from these probes.
