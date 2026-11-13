Generic one-field projections, with a fixed family/constructor-table interpreter.
No datatype-specific circuit or trusted field/reduction answer is supplied.

Two actual elaborated source theorems from `examples/GenericRecords.lean` retain
fullΓ6/noaxioms each. Projection iota accepts341steps/35nodes; neutral
projection under beta/substitution accepts451/44. Wrong field/family and
projection from a nonrecord enum reject. Different neutral records' projections
reject; same record accepts. Renaming leaves the complete encoded state identical.
Nonzero field index is explicitly unsupported by this slice.

Weighted/independent Lean unit2PASS28.518s. Every full state matches the spec for
12cases, including retained PropK/actualFunction.mt/mixed-field recursor. Tests
assert projection substitution/rebuild and neutral comparison phases are visited.
Independent Lean replay agrees on supported outcomes. Input and metadata retain
all12rows and complete dependencies; no mathlib population estimate follows.

```bash
.venv/bin/python -m leanputer.preparation --generic \
  --source examples/GenericRecords.lean --targets examples/generic-record-targets.json \
  --output /tmp/generic-records.jsonl
.venv/bin/python -m unittest discover -s tests -p test_generic_projections.py -v
PYTHONPATH=. /mnt/scratch/leanputer-native-venv/bin/python -m leanputer.generic \
  --backend native --device cuda --input benchmarks/generic-projections/input.jsonl \
  --config benchmarks/generic-projections/config.json --batch-size 12 --report /tmp/generic-projection-native.json
```

Scope remains monomorphic, positive-Sort zero/one-field nonrecursive inductives
and nullary Prop families with restricted elimination. Projections require one
constructor/one independent field. Parameters, recursive/indexed/multiple or
dependent fields, generic record eta and symbolic universes are not implemented.
No formal whole-checker/numerical equivalence or broad native validation claim.

Stock12 COMPLETE:7ACCEPT/4REJECT/1UNSUPPORTED. All row fields/config match
the operational spec, including retained full Function.mt closure.
428535560BF16params/857071120weightbytes, H1664/L69;
compile7.305504s, fixed-fuel forward107.750904s;
CUDApeak957429248bytes, hostRSS1705431040bytes.
46boot+1058stockforwards. A10G/torch2.8.0+cu128/transformers5.19.0.
Preparation wall time is unrecorded. Different features/batch from earlier
checkpoints, so this is not a matched speed comparison.
