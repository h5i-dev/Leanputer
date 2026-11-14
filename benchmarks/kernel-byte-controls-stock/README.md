# Lossless byte controls, same complete fixed source checker

The complete fixed source program is unchanged from 127751c. All bounds and
inputs match [18902c7's evidence](../kernel-full-source-stock/README.md):
word16/heap512/stack32/context8/constants4/fuel8192, original E block + standalone
E.rec claim + identity proof, and the wrong-proof mutation. Nothing is pruned
by proof, name, shape or task. No kernel semantics run on the host.

Two-bit physical digits are replaced by bytes0..255. Stock FFNs decode bits
using bounded threshold/remainder operations. The logical words remain16bits,
including symbolic syntax. Pending native RAM writes remain binary. Host
encoding/decoding is serialization only; feedback is the model's hidden state
unchanged. Older two-bit artifacts still load with their saved configuration.

| Matched full program | 18902c7 | Byte controls |
|---|---:|---:|
| Logical parameters |21,471,112,926|15,799,810,694|
| Hidden width / stock layers |22,528 /603|17,408 /581|
| Persistent residual channels |7,913|2,207|
| Allocated slots |21,864|17,283|
| Logic FFN units |137,494|131,934|
| Nonzero values |1,153,323|1,236,359|
| Stored CSR parameter/index bytes |288,206,120|219,396,384|
| Two-case stock forward seconds |1,221.760|1,197.032|

This is a materially smaller logical layout, **still not a small Transformer**.
Runtime barely improves. The nonzero count increases despite smaller padded
shapes. CPU-only compiler analysis also ran during part of this development
run; these timings are integration costs, not an isolated throughput comparison.

Actual CUDA BF16 execution passed DONE/NONE at1,316semantic steps and
INVALID/TYPE_MISMATCH at1,355. Both use no assumptions and preserve two public
signatures. Every register and every native cache row matches the SPEC computed
only after inference. Peak CUDA allocation327,577,088bytes; compilation123.910s
excludes subsequent artifact saving. `source-stock.json` is actual evidence;
`plan.json` is the matching meta-only plan. Three focused compiler tests pass,
including all256byte values, max255/carry/wrap, overlapping guards and repeated
identity feedback. No broad differential/fuzz/scaling campaign was run.

Reusable weights remain on scratch in
`/mnt/scratch/leanputer-runs/current-full-stock/compiled-source-byte/`.

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m leanputer.kernel_check \
  --load-model /mnt/scratch/leanputer-runs/current-full-stock/compiled-source-byte \
  --input benchmarks/kernel-full-source-stock/source.jsonl \
  --batch-size 2 --device cuda --report /mnt/scratch/leanputer-runs/current-full-stock/byte-cli.json
```

The fixture intentionally rejects one row, so the CLI returns exit1. The
admission report used the same NativeMachine.check after compilation/save;
a separate full load-and-admit run was not repeated. New source compilations
default to byte controls; --control-digit-bits2 reproduces paired controls.

Larger/nested-source native admission and the general semantic gaps remain
unproven/unresolved as documented in the pinned kernel target. Continued work
must compact phase/scratch lifetimes and preserve caller state, without host
dispatch or a custom executor. This checkpoint does not complete that goal.
