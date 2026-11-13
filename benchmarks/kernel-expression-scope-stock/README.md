# Shared closed-expression and universe scope in stock layers

The complete scope traversal checks BVar depth, rejects raw free Locals, and
calls the SAME symbolic level-membership service at every Sort/Const universe
argument. It covers all twelve Expr tags with generic vectors/private return
frames. Empty declared universe contexts are checked rather than treated as
identity substitution. Names/counts remain data; no host scope/type answers.

Eight focused stock inputs complete4DONE/2INVALID_UNIVERSE/2INVALID_SCOPE, with
exact ALL registers and every materialized heap/stack/context cache row. They
include original exported id type/body, the all-tag syntax traversal, undefined
Sort/Const universes, free BVar/Local and an empty universe context. Independent
`check_scope` agrees; three focused caller/regression tests PASS3.008s.
The accepted all-tag input is deliberately only a SCOPE example, not a well-typed
proof: constant/projection existence and signatures belong to later typing.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --group scope --device cuda \
  --report /mnt/scratch/leanputer-runs/typed-expression-scope-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_level_transition.SymbolicLevelTransitionTest.test_complete_expression_scope_reuses_symbolic_level_scope -v
```

[Exact report/inputs](report.json). Same128heap/16stack/8context/8-bit/f128;
stock Qwen3_5ForCausalLM forward/cache, generated BF16weights.
272,606,636parameters/545,213,272weight bytes; H2240/L55/FFN512;
compile6.331548s/GPU10.818216s;65boot+130forwards;
CUDApeak610,238,464bytes/hostRSS1,695,739,904bytes.
No pretrained weights/custom forward, saved weights or broad campaign. Timing
excludes imports/offline checks; no matched-speed/compression or steady/full-
source throughput claim. The geq report uses DIFFERENT fuel512.

Scope DONE establishes no typing, declaration admission, theorem or mathlib
coverage. The checked environment and full typed checking driver are unfinished.

Evidence is pinned to `7882037`; later shared programs add operations.
