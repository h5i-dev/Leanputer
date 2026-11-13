Generic nonrecursive constructor fields, not a per-name catalog extension.

One fixed stock model checked all17ordered declaration fixtures:5ACCEPT,
8REJECT,4UNSUPPORTED. This retains the nullary slice and adds mixed zero/one-field
constructors, renamed copies, incorrect branch/field, invalid constructor return,
incorrect recursor minor, recursive field boundary, and carrier universe violation.
All native outcomes/reasons/steps/allocated nodes match the operational spec.
The focused unit test compares every full weighted state with the spec on these
17plus6metadata/bounds cases:3testsPASS51.010s. Independent Lean replay agrees
on all supported cases; weighted UNSUPPORTED is kept distinct from Lean rejection.

Heap128/stack16/context8/constants8/universe4/fuel1056, stock Qwen3.5 H1536/L69,
FFN1024, ballast6.395,580,040BF16params/791,160,080weightbytes.
Compile6.964121s; fixed-fuel17case forward107.157124s;46boot+1058stockforwards.
CUDApeak952,261,120bytes,hostRSS1,695,817,728bytes. A10G/torch2.8.0+cu128/
transformers5.19.0. New syntax/features differ from the prior nullary checkpoint;
there is no matched performance comparison. No pretrained weights are used.

Source evidence originates in actual elaborated `examples/GenericInductives.lean`:
Bool, three-way Signal and mixed nullary/unary Packet. Generic syntax-only
preparation retains fullΓ4/5/7 and no axioms. `source-check-input.jsonl` includes
all3source rows plus one post-export wrong-field mutation. Independent Lean and
CPU weighted checker both yield3A1R810/998/964/1007steps. Export and CLI category
tests2PASS2.288s. The input is not normalized or prechecked for inference.
These are development sources, not a mathlib population/coverage estimate.

```bash
.venv/bin/python -m leanputer.preparation --generic \
  --source examples/GenericInductives.lean --targets examples/generic-targets.json \
  --output /tmp/generic-source.jsonl
.venv/bin/python -m leanputer.generic --backend circuit \
  --input benchmarks/generic-fields/source-check-input.jsonl \
  --config benchmarks/generic-fields/config.json --report /tmp/generic-fields.json
PYTHONPATH=. /mnt/scratch/leanputer-native-venv/bin/python -m leanputer.generic \
  --backend native --device cuda --input benchmarks/generic-fields/input.jsonl \
  --config benchmarks/generic-fields/config.json --batch-size 17 --report /tmp/generic-stock.json
lean --run tools/lean/ValidateGeneric.lean benchmarks/generic-fields/input.jsonl /tmp/generic-lean.json
```

The restricted class requires each field carrier to be a literal earlier constant
with a literal Sort type, no higher than the positive family Sort. Parameters,
Prop families, recursive/indexed/multiple/dependent fields remain unsupported.
No supplied positivity flag, field arity or reduction rule is trusted. The weighted
checker derives recursor minor types and iota field application from constructor
ASTs. Broad validation and formal whole-checker soundness remain outstanding.

Stock source4 COMPLETE:3A1R, all names/config/status/reason/steps/heap counts,
Γ and assumptions match weighted CPU. Same395,580,040parameter architecture.
Compile7.202323s; forward106.627494s. These are dependency-checked native source
results, not merely exported syntax. `source-native-report.json` records the full
cold/steady costs and peak memory. No broad native campaign was run.
