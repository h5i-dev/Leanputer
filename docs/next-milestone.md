# Next milestone: reusable transitions, then a dependent calculus

The current result establishes that a bounded STLC acceptance predicate can be
compiled to fixed sparse residual attention/ReLU weights. It does not establish
that the same architecture scales to dependent types. The next milestone must
address both state reuse and computational type equality.

First, specify a reusable STLC transition system. Its state should contain a
bounded immutable syntax table, traversal/work stack, lexical binder/type
storage, result registers, validity flags, and a step-budget counter. Use
syntax-specific operations such as entering a lambda, checking an application,
and returning a type. Compile the transition relation directly into Boolean
circuits and then weights; do not introduce a general-purpose instruction set,
CPU emulator, or a runtime call to the Python oracle.

One shared block (or a small fixed sequence of blocks) should update that state
on every step. Gate activity and memory updates with explicit masks. Completed
and failed states should be absorbing. Fuel exhaustion must produce a separate
resource outcome and never acceptance. Reusing layers with a bounded host loop
is acceptable as an intermediate design if the loop only applies the same
weights and all semantic decisions remain in the state. Document that recurrence
explicitly; it is not present in the first milestone.

Before adding syntax, validate transition traces against an independent STLC
machine on exhaustive small inputs and seeded generated inputs. Check binder
scope, stack bounds, step accounting, invalid-table rejection, shared weight
identity across steps, and CPU/CUDA agreement. Compare circuit size, activation
memory, steps, and wall-clock cost across capacities. The acceptance criterion is
identical STLC behavior on representable inputs with an explicit resource result
at every bound; speed improvement is a measurement, not an assumption.

Then implement a small predicative lambda-Pi calculus with de Bruijn indices:

- `Sort u`, variables, dependent `Pi A B`, annotated `Lam A body`, application.
- A finite explicit universe range, `Sort u : Sort (u+1)`, and predicative
  products using the maximum universe level. Universe overflow is a resource
  outcome. Lean's impredicative `Prop` is deferred.
- Context lookup with index shifting, capture-avoiding substitution, weak-head
  beta reduction, and conversion checking. Operations on term/type syntax must
  be computed in the weighted transition system, rather than in the encoder.
- Explicit bounds for syntax allocation, context, evaluation stack, reduction
  steps, and equality work. A missing normal form within fuel gives a resource
  outcome; it never establishes equality or inequality by default.

Specify beta conversion with alpha handled by de Bruijn indices. Eta conversion
and universe cumulativity are deferred; the initial calculus has its own
explicit rules before any correspondence with Lean is claimed.

Start with a separately reviewed executable specification and trace format.
The parser may encode syntax and indices; it may not pre-normalize terms,
precompute substitutions, supply inferred types, or attach correctness labels.
The first dependent fixture should include polymorphic identity
`fun (A : Sort 0) (x : A) => x`, whose type is
`Pi (A : Sort 0), Pi (x : A), A`, with the corresponding de Bruijn shifts.
Follow with applications whose types agree only after beta reduction, dependent
codomain instantiation, nested shadowing, and negative capture/shift cases.

Completion requires independent differential tests, bounded exhaustive
substitution/conversion checks, exact arithmetic tests on CPU/CUDA, and tests
showing that increasing fuel can resolve resource outcomes without changing a
previously established acceptance/rejection. Publish all bounds and trusted
components. Formal verification remains a separate deliverable.

Only after that should a Lean subset be specified: environment/constants and
universe instantiation, Lean's sort and conversion rules, and subsequently
inductives and recursors. Keep each unsupported kernel feature explicit. The
nanoda_lib kernel can guide algorithm choices, but wholesale translation is not
the architecture. Lean export ingestion, correspondence to actual Lean
expressions, integration with a language model, and full Demo A each need their
own interface, validation fixtures, and completion criteria.
