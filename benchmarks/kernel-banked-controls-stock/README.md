# Cache-backed private controls and native bounded-word lowering

The complete fixed general source program and numeric bounds match
[b8ad63e](../kernel-byte-controls-stock/README.md). No proof, declaration, name,
task rule or syntax tag is pruned. Logical words remain16bits and original
symbolic schemes remain input data. The Python SPEC runs only after inference.

The compiler derives private-control ownership by conservative Boolean
may0/may1 analysis. It covers normal execution, empty-stack return, caller-frame
return, and the invalid task domain. Address and dispatch inputs stay shared.
566registers belong to one effective owner;385stay shared.66owner groups use
a shared74word scratch window backed by native cache. On a return the model
reads frame.task; it preserves the caller's private state while helpers execute.
All bank queries, pending writes, initial syntax transport and feedback are
model operations or byte/bit serialization. No host dispatch or checking occurs.

Unsigned add/subtract, comparison, variable equality and word selection retain
their original Boolean definitions. Compiler provenance permits stock FFNs to
implement the same operations with bounded digits. Arithmetic propagates
carry/borrow across nibbles; comparison propagates a bit across bytes. No full
16bit integer is stored as a BF16 scalar. The focused tests include wraparound,
borrow-in,17bit partial digits and the comparison threshold256.

Arbitrary-byte GDN cache storage FAILED exactness:7 read6.96875 in a stock BF16
row stress. `rejected-byte-cache.log` preserves the failure. Private cache
storage is **binary**, with10new native partitions; residual/pending digits
remain bytes. The binary codec test covers all126row columns and preserves an
inactive owner. There is no rounding repair or inference host semantic step.

| Same full source program | Paired controls18902c7 | Byte b8ad63e | Banked/native words |
|---|---:|---:|---:|
| Logical parameters |21,471,112,926|15,799,810,694|12,010,486,994|
| Hidden width / layers |22528/603|17408/581|18432/413|
| Persistent channels |7913|2207|1380|
| Allocated slots |21864|17283|17574|
| Logic FFN units |137494|131934|88913|
| Native cache partitions |7|7|17|
| Nonzero values |1153323|1236359|917271|
| Stored CSR parameter/index bytes |288206120|219396384|164772060|
| Two-case forward seconds |1221.760|1197.032|856.180|

The model is materially smaller but **still not small or practical**. Sparse
bytes are not logical parameters. Temporary liveness/padding still dominates:
1380persistent channels become17574allocated slots. Qwenputer's cited P2 chip
has11layers/hidden2816/~1.04Mnonzeros; a similar nonzero count does not imply
our current padded shape is necessary. Its merged backbone and alternate
executor are different measurements, not stock checker throughput evidence.

Actual CUDA BF16 inference passes the same source witnesses: original E block,
standalone E.rec claim and identity proof DONE/NONE1316steps; wrong proof body
INVALID/TYPE_MISMATCH1355steps. No assumptions; two public signatures. All951
registers and all17native cache partitions exactly match the reference computed
after inference, including every private-owner row and unused padding.
Compilation69.289s excludes artifact saving; forward856.180s; CUDA peak248931840
bytes. These are integration timings, not a broad throughput campaign.

Eight focused compiler/control/CLI checks pass3.206s. A fresh artifact load
checks its first two source transitions, all951registers including private
cache/pending serialization, PASS7.978s including loading/boot. That probe is
not a second complete admission. The full admission report used the same
NativeMachine.check after compile/save. Artifact hashes are in artifact.json;
weights remain on scratch.

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m leanputer.kernel_check \
  --load-model /mnt/scratch/leanputer-runs/current-full-stock/compiled-source-bank-words \
  --input benchmarks/kernel-full-source-stock/source.jsonl --batch-size 2 \
  --device cuda --report /mnt/scratch/leanputer-runs/current-full-stock/bank-cli.json
```

The intentional rejection makes the CLI return exit1. New source compilation
defaults to byte controls, private banking and native word lowering. Explicit
--no-bank-control/--no-native-word-ops retain the preceding layout choices.
`tools.kernel_stock_delivery --plan --bank-control --native-word-ops` reproduces
the whole-program meta plan without GPU weight allocation; use the same config
as kernel-full-source-stock/config.json. `plan.json` separates this planning
evidence from actual `source-stock.json` inference.

Next work is reuse of temporary scratch across mutually exclusive kernel
owners/phases. It must handle conditional writes, slot clearing and reads of
inactive values correctly; a phase name alone does not justify overlapping
live slots. Larger/nested native source admission and the documented semantic
gaps remain separate, explicit blockers. No new semantic features or broad
campaigns were added.
