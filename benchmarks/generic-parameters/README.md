Uniform type-parameter admission, not a catalog of named parameterized datatypes.

The fixed validator checks the annotated parameter count against literal-Sort
family binders, matching constructor parameter domains, and exact unchanged
parameter variable applications in constructor results. Constructor tails are
typechecked with a scoped self-family permission; later constants stay unavailable.
Fields remain0/1, either closed carriers, parameter variables or direct uniform
self-reference. No supplied typing/uniformity/positivity answer is trusted.

Actual source `examples/GenericParameters.lean` uses Option constructors and an
arbitrary two-parameter Either. FullΓ6/noaxioms each; weighted source steps703/1078,
allocated51/70nodes. The actual parameterized Option.rec is exported withΓ7 but
explicitly UNSUPPORTED in weights. Parameterized projections also remain
unsupported. This checkpoint does not claim full Option elimination/structures.

Focused unit2PASS51.824s:15full-state/every-step weighted cases + independent Lean
replay. Swapped uniform arguments, mismatched binder domains, excessive metadata,
wrong constructor argument reject; an index reinterpretation, Prop field and
parameterized recursor remain unsupported. Renaming produces identical encoded
states. A valid9parameter declaration exceeds context8 and reports CONTEXTresource;
independent Lean accepts it. Retained nested recursion/projection/PropK and complete
Function.mt closure accept. Zero-parameter extended-ABI unit3PASS43.428s and actual
source-export regression1PASS2.559s. No broad campaign or coverage estimate.

Declaration ABI now has6words, adding validated parameter count. This fits the
existing native boot/value-head payload; no stock forward/cache change is needed.
Opcode width derives from fixed rules/bounds. Family/constructor universe tuples
are specialized syntactically; recursor owner/result universes are read from its
actual instantiated motive syntax, without name-specific ordering or normalization.

```bash
.venv/bin/python -m leanputer.preparation --generic \
  --source examples/GenericParameters.lean --targets examples/generic-parameter-targets.json \
  --output /tmp/generic-parameters.jsonl
.venv/bin/python -m unittest discover -s tests -p test_generic_parameters.py -v
PYTHONPATH=. /mnt/scratch/leanputer-native-venv/bin/python -m leanputer.generic \
  --backend native --device cuda --input benchmarks/generic-parameters/input.jsonl \
  --config benchmarks/generic-parameters/config.json --batch-size 15 --report /tmp/generic-parameters-native.json
```

Bounds128heap/16stack/8context/8constants/universe4/fuel1536. Prep wall time was not
recorded. Native metrics follow after actual stock confirmation. Mathlib's complete
857source population is still NOT_RUN on this generic backend; Function.mt remains
one targeted development smoke. No full strict-positivity/general inductive,
formal-soundness, numerical-equivalence or broad native validation claim.

Constructor tails are now typechecked, adding semantic steps to older zero-
parameter cases. One former negative at1056fuel exhausts that budget; the focused
legacy unit budget is1152 and this batch uses1536. No capacity/fuel-preserving
speed or outcome comparison is claimed against older checkpoints.

Stock15 COMPLETE:7ACCEPT/4REJECT/3UNSUPPORTED/1CONTEXTresource.
All input names/config/outcomes/reasons/steps/allocations/Γ/assumptions match
the spec; parameterized recursor remains UNSUPPORTED, never counted as support.
461577096BF16params/923154192weightbytes,H1792/L69;
compile8.214015s,fixed-fuel GPU157.347091s.
CUDApeak1054575104bytes,hostRSS1704464384bytes;
59boot+1538stockforwards.A10G/torch2.8.0+cu128/transformers5.19.0.
No matched speed comparison with prior feature/fuel/batch checkpoints.
