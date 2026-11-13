# Complete conservative symbolic universe comparison

The pinned `is_geq/is_geq_core` algorithm is compiled into the SAME stock
controller as normalization, structural equality and successor separation.
Both inputs are normalized; Max/IMax recursive AND/OR paths, offset comparisons,
equal-positive-offset recursion and fallback after both left-Max alternatives
fail use private continuations. No numeric grounding, sampled assignments,
parameter-name rules or host semantic comparison runs at inference.

Twelve focused inputs complete DONE with exact ALL registers and every
materialized heap/stack/context cache row. True/false results independently
match LevelOps. Targeted shared-service module11tests PASS16.621s. The important `max u v >= imax u v` path succeeds through the
IMax fallback after both Max alternatives fail; treating that point as false
would incorrectly change the source predicate. This is generic rule evidence,
not a new datatype/shape class or theorem coverage.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --group geq --device cuda \
  --report /mnt/scratch/leanputer-runs/typed-level-geq-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_level_transition -v
```

[Exact report/inputs](report.json). Same heap128/stack16/context8/8-bit words,
FUEL512 (increased from128 for the301-transition fallback trace). Stock
Qwen3_5ForCausalLM forward/cache, generated BF16weights, no pretrained model.
272,615,596parameters/545,231,192weight bytes; H2240/L55/FFN512;
compile6.277654s/GPU41.019125s;45boot+514forwards;
CUDApeak625,400,320bytes/hostRSS1,694,937,088bytes.
Semantic traces need11..301steps, but this runner still executes the fixed fuel
plus two flush forwards. The timing INCLUDES that unused work; it is not a
steady-state/full-source throughput figure or a matched speed/compression
comparison with earlier fuel128 services. Imports/offline validation excluded.
No weights saved and no broad evaluation campaign.

Source symbolic universe services are now available for typed inference and
admission callers. Those callers and complete typed conversion/primitives remain
unfinished; operation DONE is not native proof/declaration acceptance. No added
native mathlib coverage or formal-verification claim.

Evidence is pinned to `1447eae`; later shared programs add operations.
