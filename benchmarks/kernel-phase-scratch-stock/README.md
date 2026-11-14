# Owner-scoped scratch, complete fixed general source checker

Actual stock CUDA BF16 execution passes the SAME bounds and source cases as
[f05dc32](../kernel-banked-controls-stock/README.md): original E block + standalone
E.rec claim + identity proof DONE/NONE1316steps; wrong proof INVALID/TYPE_MISMATCH
1355steps. No assumptions; two public signatures. Every951logical register and
every row of all17native cache partitions matches the post-inference SPEC.
No rule, declaration/name/shape, numeric word or expression tag is pruned.

The compiler derives conservative owner domains from the full Boolean program,
including native word-operation dependencies. Local results are gated in stock
FFNs. Reads crossing into shared computation use guarded shared exports.
Local lifetimes allocate into one overlapping owner window, with conditional
slot clears. Guard lifetimes are tracked even when the guard only participates
in a clear. No host dispatch, custom executor or inference semantic processing
is introduced. Feedback stays the unchanged model hidden state.

| Whole fixed program | f05dc32 | Scoped scratch |
|---|---:|---:|
| Logical parameters |12,010,486,994|9,066,086,190|
| Hidden width / layers |18432/413|10240/564|
| Persistent channels |1380|1380|
| Allocated slots |17574|10036|
| Logic FFN units |88913|127570|
| Nonzero parameter values |917271|1073704|
| Stored CSR bytes |164772060|130917126|
| Two-case stock forward seconds |856.180|1161.105|

Width and logical size improve, but depth and runtime **regress**. The model
is **not small or practical**. Storage bytes do not establish a small dense
architecture. The first phase plan reports8641shared slots +1395owner-window
slots;127570logic FFN units include gating/export costs. `preliminary-plan.json`
predates final predicate/guard-liveness corrections; actual evidence is
`source-stock.json` and its layout_statistics. Compilation190.394s excludes
saving; peak CUDA205054976bytes. Static CPU compiler analysis also ran during
part of this development validation; this is not isolated throughput evidence.

Two focused stock boundary tests pass3.467s: actual overlapping physical slots,
conditional clears and shared exports through FOUR model-driven owner changes,
plus scoped17bit arithmetic/mux at carry/partial-digit boundaries. There was no
broad differential/fuzz/scaling campaign. These numerical tests are separate
from the full source acceptance/rejection above.

The complete artifact is
`/mnt/scratch/leanputer-runs/current-full-stock/compiled-source-phase/`.
Production inference uses --load-model with that path and the source.jsonl in
kernel-full-source-stock. A separate complete load-and-admit run was not repeated.
The saved geometry needs no compiler or SPEC during inference.

Development reproduction:

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m tools.kernel_stock_delivery \
  --config benchmarks/kernel-full-source-stock/config.json \
  --input benchmarks/kernel-full-source-stock/source.jsonl \
  --bank-control --native-word-ops --phase-scratch --device cuda \
  --report /mnt/scratch/leanputer-runs/current-full-stock/reproduced-phase.json
```

The next layout correction reclaims boot-only channels and clears scratch in
stock FFNs at the end of the forward, reducing reserved clearing-prefix padding.
It has separate pending evidence. The general semantic gaps, larger/nested
native source coverage and SMALL/practical delivery remain unfinished.
