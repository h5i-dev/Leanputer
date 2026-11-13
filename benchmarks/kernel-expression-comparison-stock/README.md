# All-tag expression and typed-vector comparison in stock layers

The complete erased-syntax comparator covers all twelve Expr tags, private
pair/Let-third continuations and length-driven level/limb/byte vectors. Sort and
Const universe entries call the SAME structural level comparator. Binder info
is ignored, as in pinned expr_eq_fn<false>; the codec already erases binder names,
metadata payloads and Let nondep optimization flags. See [source/representation
contract](../../docs/kernel/expression-comparison.md).

Thirteen focused stock operation inputs complete DONE with2true/11false results.
Every register and every materialized heap/stack/context cache row matches the
development transition reference. Independent erased-syntax comparison agrees.
Focused comparison/shared-caller regression3tests PASS3.733s.
The composed source-instantiation-then-comparison calls create fresh vector/level
allocations matching an existing root; the true case establishes comparison
without assuming pointer identity, and the late mismatch is also tested. No host
inferred types, normalization/equality or admission answers enter input.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --group comparison --device cuda \
  --report /mnt/scratch/leanputer-runs/typed-expression-comparison-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_level_transition.SymbolicLevelTransitionTest.test_all_tag_representation_comparison_and_runtime_duplicate_vectors -v
```

[Exact report/inputs](report.json). Same128heap/16stack/8context/8-bit/fuel128,
semantic traces3..86steps/free45..84. Stock Qwen3_5ForCausalLM forward/cache,
compiler-generated BF16weights, no pretrained model/custom forward.
306,727,664parameters/613,455,328weight bytes; H2432/L57/FFN512;
compile6.897743s/GPU11.288353s;85boot+130forwards;
CUDApeak718,756,352bytes/hostRSS1,698,910,208bytes.
Timing excludes imports/offline checks; no matched speed/compression or steady/
full-source throughput claim. No weights saved or broad campaign.

FALSE is representation mismatch, NOT a proof of definitional inequality. Future
conversion must continue through reduction, typed proof irrelevance and eta.
DONE is an operation outcome, not native proof/declaration acceptance or mathlib
coverage. General typed checking and source admission remain unfinished.

Evidence is pinned to `c6b8884`; later programs add typed inference.
