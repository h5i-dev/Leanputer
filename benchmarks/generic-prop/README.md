Generic nullary Prop declarations: empty/singleton large elimination, arbitrary
constructor count for Prop-only elimination, and singleton K reduction on neutral
proofs. Rules depend on validated sort/count data, never declaration names.
Prop fields remain unsupported. Positive-Sort0/1-field support is retained.

Stock11case result6ACCEPT/4REJECT/1UNSUPPORTED exactly matches the spec's complete
input/config/names/outcomes/reasons/steps/heap counts/dependency counts/assumptions.
Three new actual Lean development sources exercise empty elimination, singletonK
and a two-constructor proposition. Two/three-constructor Prop large elimination
rejects. A Prop field is explicitly unsupported. Bool/Packet and wrong-field
behavior remain covered. Independent Lean accepts6/rejects5; weightedUNSUPPORTED
is distinct. Focused generic unit5PASS80.083s (30weighted full-state traces,
actual source export, independent Lean, unsupported-row preservation, renaming).

Actual mathlib source `Function.mt@[]` accepts805steps/90nodes, retaining all
3dependencies and no axioms: False as a generic inductive declaration, ordinary
Not definition and the checked opaque mt body. A claim-False mutation retains
that whole closure and rejects554steps/79nodes. This is1/1deliberately targeted
mathlib source smoke, selected because it needs the new generic empty Prop
family. It is not a representative sample, whole-population fraction or530proofs.
The established857source denominator/four-module population remains unchanged;
other856rows are NOT_RUN with this generic backend. Historical catalog syntax
530EXPORTED327UNSUPPORTED belongs to another compiler and is not reused here.

Pin: mathlibfabf563a7c95a166b8d7b6efca11c8b4dc9d911f/Lean4.31.0.
Export used `lake env lean --run tools/lean/ExportGeneric.lean` importing
Mathlib.Logic.Basic. Full ordered raw Expr dependencies and actual recursor
signatures are exported; no normalization/checking/certificates/hidden axioms.
Lean elaboration/replay are external evaluation/preparation only.

Bounds: heap128/stack16/context8/constants8/universe4/fuel1056.
Stock Qwen3.5 H1600/L69/FFN1024,m25;412,057,800BF16params/824,115,600weightbytes.
Compile8.066208s; fixed-fuel11case stockforward105.848930s;46boot+1058forwards.
CUDApeak925,078,016bytes,hostRSS1,694,003,200bytes. A10G/torch2.8.0+cu128/
transformers5.19.0 fallback kernels. Preparation wall time was not recorded for
this run; no zero-cost/cold-throughput assumption is made. Compilation and
reused-weight model costs are separate in the report. Every row still consumes
fixed batch fuel after it halts; these timings do not establish high throughput.
No matched speed comparison against other feature/capacity/batch checkpoints.

```bash
.venv/bin/python -m leanputer.preparation --generic \
  --source examples/GenericProp.lean --targets examples/generic-prop-targets.json \
  --output /tmp/generic-prop.jsonl
PYTHONPATH=. /mnt/scratch/leanputer-native-venv/bin/python -m leanputer.generic \
  --backend native --device cuda --input benchmarks/generic-prop/input.jsonl \
  --config benchmarks/generic-prop/config.json --batch-size 11 --report /tmp/generic-prop-stock.json
lean --run tools/lean/ValidateGeneric.lean benchmarks/generic-prop/input.jsonl /tmp/generic-prop-lean.json
.venv/bin/python -m unittest discover -s tests -p test_generic.py -v
```

No general inductive, symbolic-universe, formal-soundness or complete mathlib
coverage claim. Parameterized/indexed/recursive families are still unsupported.
