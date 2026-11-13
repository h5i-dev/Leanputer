Direct strictly-positive recursive fields are declaration data, not named Nat
rules. A constructor domain may be an earlier checked closed carrier or exactly
its positive-Sort family. Other function/nested/indexed/dependent recursive shapes
remain unsupported. Prop fields remain unsupported. Zero or one field per ctor.

Weights derive the recursive minor `(a:F)→M a→M(c a)` from the constructor AST
and validate the supplied recursor signature. Generic iota constructs
`minor a (rec motive minors a)` in weighted heap memory. No recursive flag,
induction hypothesis, normalization result or per-name reduction table is trusted.

Real Lean source `examples/GenericRecursive.lean` includes arbitrary Tally,
renamed, nested and actual Nat constructor/recursor judgments. Nat encodes
IDENTICALLY to Tally; one compiled model handles both. This is constructor-only
Nat, with no generic raw literal or optimized arithmetic support. FullΓ4 and
no axioms per recursive source. One-level recursion accepts1227steps/97nodes,
two-level1355/102. Missing IH type rejects345/66. A wrong recursive result rejects;
negative function domains remain UNSUPPORTED. A one-constructor recursive
projection agrees with the actual Lean kernel.

A12deep well-typed example returns STACKresource1148steps/95nodes under the same
bounds; independent Lean accepts it. An initial fixture accidentally changed only
the claim annotation; independent replay caught it, both term/claim annotations
were corrected, and focused tests reran. This was a fixture correction; no failed
run is counted as success. The full focused unit2PASS42.875s (14weighted every-step
full-state cases + independent Lean); actual Nat identity test1PASS separately.
Retained actual Function.mt closure, neutral projection, PropK and nonrecursive
Packet recursor remain covered. No broad campaign or population estimate.

```bash
.venv/bin/python -m leanputer.preparation --generic \
  --source examples/GenericRecursive.lean --targets examples/generic-recursive-targets.json \
  --output /tmp/generic-recursion.jsonl
.venv/bin/python -m unittest discover -s tests -p test_generic_recursive.py -v
PYTHONPATH=. /mnt/scratch/leanputer-native-venv/bin/python -m leanputer.generic \
  --backend native --device cuda --input benchmarks/generic-recursive/input.jsonl \
  --config benchmarks/generic-recursive/config.json --batch-size 15 --report /tmp/generic-recursive-native.json
```

Bounds heap128/stack16/context8/constants8/universe4/fuel1408. Model/runtime metrics
are recorded after the actual stock run. Preparation elapsed time was not recorded.
No claim of general strict positivity, indexed families, uniform parameters,
formal whole-checker/numerical equivalence, or broad mathlib coverage.

Stock15 COMPLETE:9ACCEPT/3REJECT/2UNSUPPORTED/1STACKresource.
All input names/config/outcomes/reasons/steps/allocations/Γ/assumptions match
the spec. Actual Nat accepts1227steps/97nodes/Γ4/noaxioms in the SAME model.
445040968BF16params/890081936weightbytes,H1728/L69;
compile7.321626s, fixed-fuel stockforward143.97165s.
CUDApeak1031423488bytes,hostRSS1705951232bytes;
58boot+1410stockforwards. A10G/torch2.8.0+cu128/transformers5.19.0.
Different features/fuel/batch from earlier checkpoints, not a matched speed claim.
