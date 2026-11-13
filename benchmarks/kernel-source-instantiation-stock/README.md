# Shared source instantiation and total level ordering

Pinned source instantiation uses the same all-tag level/expression traversal and
binding/vector machinery as raw substitution, calling the smart Max/IMax
constructors only on CHANGED children. Replacement arguments remain simultaneous
and unchanged raw syntax is retained, as in source `update_max`. A complete
Sort/Const scheme caller uses those SAME private services. No host reduction.

The total canonicalization order strips successors with the same offset service,
compares bases structurally, recursively orders unlike bases, then compares
successor counts when bases match. It returns equal/less/greater and whether the
OUTER bases match. Parameter symbol IDs supply an artifact-local total order;
they are data, not a compiled name list. No host sorting/order answers enter input.

Twelve focused stock operation inputs all completed DONE, with exact ALL registers
and every materialized heap/stack/context cache row. These include changed and
unchanged level instantiation, nested constructor updates, a whole scheme call,
base/offset and nested-child ordering. CPU module8tests PASS5.716s additionally
retains the earlier typed scope, raw operations, telescope and constructor paths.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --group instantiation --device cuda \
  --report /mnt/scratch/leanputer-runs/typed-source-instantiation-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_level_transition -v
```

[Exact report/inputs](report.json). Stock Qwen3_5ForCausalLM forward/cache with
compiler-generated BF16weights, no pretrained download/custom forward.
Same128heap/16stack/8context/8-bit/f128 physical capacities.
205,948,646parameters/411,897,292weight bytes; H1792/L52/FFN512;
compile5.319256s/GPU10.553859s;54boot+130forwards;
CUDApeak486,464,000bytes/hostRSS1,688,301,568bytes.
Timing excludes imports/offline checks. No speed/compression or steady/full-source
throughput claim, weight artifacts or broad campaign.

Ordering/instantiation completion is not native proof/declaration acceptance.
Full canonical normalization/equivalence, inference and source admission are still
unfinished. No added native mathlib theorem coverage or formal-verification claim.

Evidence is pinned to `c8affa8`; later shared programs add operations.
