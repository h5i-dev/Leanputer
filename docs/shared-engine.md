# Shared dependent transition engine

The baseline circuit is preserved in `checker.py`. `transition.py` is a separate
implementation of the explicit machine in `machine_spec.py`, with a separately
structured recursive oracle in `dependent.py`. The compiler takes configuration
only, never a proof or its expected answer.

State has an immutable postorder DAG for syntax, a declaration environment, an
explicit context stack, continuation frames, control/result registers, heap
allocation pointer, fuel, and absorbing outcomes. Variable indices are de Bruijn
indices. Context lookup lifts a stored type by index+1. Shift and substitution
traverse syntax using continuation frames and allocate new nodes. Beta WHNF
substitutes an argument into a lambda body; transparent constants delta-unfold.
Conversion compares WHNFs recursively. Lambda, Pi, application, and declaration
checks have dedicated semantic phases; there is no general CPU instruction set.

Ground universe typing uses Sort u : Sort (u+1) and Lean's numeric imax rule:
Pi has level zero when its codomain is in Prop, otherwise the maximum domain and
codomain levels. Universe overflow is a resource outcome. The current machine has contextual eta and proof irrelevance, but no symbolic
universe equations, inductives or recursors. Tests of these rules do not establish correspondence
with all Lean terms, and a restricted-calculus rejection need not be a Lean
rejection.

Each semantic step applies exactly the same module objects and weight tensors:

1. Compiled Boolean FFNs produce addresses for current expression, second
   expression, result, validation cursor, return continuation, and declaration.
2. Softmax attention reads their memory tokens using fixed positional keys.
3. Compiled FFNs produce context and constant addresses from the first reads.
4. Addressed attention reads context/constant memory.
5. Compiled FFNs implement guarded semantic transitions, masked memory writes,
   return-stack changes, fuel accounting, and absorbing outcomes.

A binary address query is projected by fixed diagonal weights 256 and bias
-128, with positional keys encoded as +/-1 bits. A matching token beats every
other token by at least 256. Float32 max-subtracted softmax underflows the
nonmatches to zero on tested CPU/CUDA backends, giving an exact read of Boolean
payloads. This is a numerical domain assumption and is not exact softmax
selection over the reals. Address capacities are powers of two. Semantic guards
reject invalid pointer domains before interpreting read results. Unused read
ports can read a harmless cell; all branches are masked in compiled logic.

Attention therefore performs actual addressing; it is not the baseline's
singleton identity attention. The `logic` backend writes memory using Boolean FFNs. The
`attention_delta` backend uses a register-only FFN controller plus addressed
attention writes: read old payload, gate the address distribution by write-enable,
and apply the rank-one delta of new minus old payload. Intermediate deltas can
be negative; completed machine state remains Boolean. All update arithmetic
executes inside the fixed module. Fixed Python loops/slices in `forward` wire modules together; they do not
infer types, perform substitution, choose semantic operations, or update state
outside module outputs. Shape/Boolean validation and syntax preparation remain
outside the weights. A proof-checking runner must initialize control and mutable
memory canonically; arbitrary intermediate machine states are not proof inputs.

The compact smoke configuration (heap=32, stack/context=8, constants=4, fuel=256)
compiled in 0.230s to 1,281 state bits and 75,860 sparse nonzeros. Address FFNs
have depths 18 and 24; transition FFNs have depth 36, plus two sequential
attention stages: 80 shared stages per semantic step. One exact 50-step trace
ran in 0.291s on CPU. These are development samples, not benchmark results.
The shared stack is not a claim of fewer than eleven layers, and repeated
execution can cost substantially more than the baseline's single unrolling.

Tests compare every state bit at every step for eight positive dependent,
conversion-required, environment and capture cases, plus malformed/negative
and resource cases. All 49 current operational phases are covered by the expanded tests. CPU/CUDA traces
match the independent operational specification; terminal states absorb further
steps; buffer storage identities remain fixed across execution. The recursive
oracle separately checks expected judgments and seeded generated terms.

`proofs/Logic.lean` proves binary integer-domain NOT/AND/OR formulas, masked
writes, and the absorbing-state pattern without axioms. These are limited core
lemmas. They do not verify arbitrary fan-in compilation, the transition machine,
PyTorch float32 arithmetic, attention underflow, or typing soundness.

Conversion extension (after 268573a): the machine now has 49 phases. Structural
comparison under Pi/Lam extends/restores context. Failed comparison invokes
inferred-type proof irrelevance and then typed function eta expansion. Eta lifts
the neutral function and allocates its application to a fresh de Bruijn variable
inside the weighted machine. Opaque constants have checked values and a separate
kind that prevents delta unfolding. Recursive, operational, weighted, actual
Lean and nanoda checks agree on eta/irrelevance positives and wrong-eta,
different-proposition and forbidden opaque-delta negatives. These tests do not
constitute a formal proof of conversion soundness.

Two additional Lean lemmas prove OR and bounded AND arithmetic for arbitrary
integer counts. Their standard Lean axioms are propext and Quot.sound; there is
no sorryAx. Float32 realization and the full checker remain unverified.

## Register-only control and execution capture

The attention-write backend keeps wide memory out of register-control FFNs.
At heap256/stack32/context32/constants16/fuel2048, state width is 11,820 bits,
controller work width 5,627, buffers 694,332 bytes and sparse nonzeros 25,938.
Two address FFNs have depths 5 and 9, the transition FFN depth is 24, and
accounting includes two read rounds plus write-address attention, a write gate
and a rank-one update: 43 logical stages per semantic step. The one-time
initializer is another stage. This count describes sequential operations, not
an asserted equivalence to a conventional language-model block.

CUDA graph replay captures the same forward pass and an identity copy to the
next input. Graphs are cached per model/batch/device, invalidated by changed
buffer identities/addresses, and absent from saved artifacts. Canonical weighted
initialization resets each new batch. The host applies exactly fuel+1 graph
replays with no semantic dispatch or early termination. Graph capture costs and
steady reused execution are reported separately. Compilation remains proof
independent. Graph execution is tested against eager full-state traces.
