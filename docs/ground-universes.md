# Ground-universe tuples and fixed pair records

This work extends fixed primitive schemas to three ground universe parameters,
needed by PProd/Prod recursors. It does not solve symbolic universe constraints
or admit arbitrary inductive declarations. The input JSON syntax stays unchanged.

The internal heap still has four words per node. For builtin nodes, `a` holds
all universe levels in fixed-width little-endian lanes, `b` is zero and `v` is
the fixed primitive code. Lane width is max(1, universe_bound.bit_length()),
leaving room to represent an out-of-bound level at the bound itself. Public
syntax packing rejects only scalars that cannot fit a lane. Validation inside
the weights checks every lane against the exclusive primitive universe bound,
checks unused high bits and checks b=0. Thus an invalid level cannot carry into
another level and silently select a different type. Word width includes the
largest primitive universe arity times lane width. Small model shapes can grow
when a new arity requires more bits; this is explicit feature capacity, not a
matched downsizing claim. Existing heap512/1024 configurations have enough bits.

Schema recipes contain fixed compiler-authored universe tuples and max/successor
expressions. BUILTIN_TYPE resolves these with Boolean arithmetic and builds
types inside weights. Syntax preparation does not infer or normalize types.
The runtime retains the stock Transformer forward/cache and identity feedback.
Old raw operational states use a different internal encoding; public documents
are repacked, and artifact source fingerprints must match the compiler.

PProd has `Sort (max (max 1 u) v)`, so it is always data, including at 0/0.
Prod has `Type (max u v)`. Both fixed records have two uniform parameters and two fields.
Projection inference verifies the exact family; conversion checks both exact
record types and both fields. Neutral data recursion uses both projections.
This differs from Subtype's proof field, which can use typed proof irrelevance.

Eleven actual Lean source fixtures match independent
Spec/recursive Oracle acceptance; four negative field/family/universe judgments
match all three references. Focused weighted9cases5A4R passed193.218s, including
Eq K and PUnit eta retention. The base state/weight-sharing trace passed21.800s.
A focused lane boundary test passed3.586s, including each over-bound lane,
nonzero b, unused padding and unrepresentable syntax. The native shape preflight
regression passes1.276s before any state/model allocation.

The stock native batch passes19cases14A5R, including pair fixtures, field/family/
universe negatives, previous Eq3/PUniteta2/Subtype neutral recursion and actual
Function.uncurry_def@[1,1,1]. The source accepts4295steps, checking four definitions
without axioms. All reported outcomes/reasons/steps/heap counts match Spec.
At heap1024/stack32/context16/constants8/fuel4352:85boot+4354stock forwards
657.889s,compile39.508s,2,063,527,628BF16parameters/4,127,055,256weightbytes,
hidden5376/103layers/FFN1024. Peak forward CUDA allocation4,524,193,280bytes;
processRSS1,786,871,808bytes. CPU development checks/syntax export overlapped;
this is not a controlled speed comparison with other batches. Evidence:
benchmarks/native/pairs-*. Broad native validation and formal soundness remain
pending; finite targeted correspondence is not a proof for all inputs.

Native RAM uses one128-dimensional value head, including two reference lanes.
The largest bank payload is the six-word stack frame, so word width must be
at most21. The compiler rejects a larger width before allocating state/model
tensors. The default ground-universe bound4 and tested heap512/1024 models
remain within this limit.
