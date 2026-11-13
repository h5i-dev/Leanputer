# Dependent input ABI and trusted components

`leanputer.dependent.v1` is a JSON object with `format`, `term`, `claim`, optional
`name`, ordered `environment`, and optional `provenance`. A corpus is JSONL or a
JSON array. The object grammar is:

```json
{
  "format": "leanputer.dependent.v1",
  "name": "polymorphic_identity",
  "environment": [],
  "term": ["lam", ["sort", 1], ["lam", ["var", 0], ["var", 0]]],
  "claim": ["pi", ["sort", 1], ["pi", ["var", 0], ["var", 1]]]
}
```

Expressions are `var(index)`, `sort(level)`, `const(name)`, or binary `pi`, `lam`,
`app` nodes, represented as tagged arrays. Indices/levels are unsigned integers;
index zero denotes the innermost binder. Domain annotations and claimed types
are untrusted syntax, checked by the weighted machine. Binder names and
implicit/explicit binder information do not affect kernel typing here.

Environment records have `name`, `type`, and `value` (null for an explicit axiom), and optional Boolean `opaque`.
Opaque values are checked but never delta-unfolded.
Dependencies must precede their users. Every declared type is checked to have a
sort; every definition value is independently inferred and compared with its
declared type. Future/self constant references fail. All assumptions are
reported. Supporting a declaration does not make its type an accepted axiom-free
theorem. Duplicate names and unknown external names are malformed input.

The external exporter traverses actual Lean Expr trees and the environment's
ConstantInfo. It retains applications and lambda terms requiring conversion;
it does not call inferType, whnf, isDefEq, or any checker to label the result.
Numeric level expressions are evaluated after syntactic universe parameter
instantiation. Unresolved levels, literals, metavariables and general
inductive/constructor/recursor/quotient declarations are explicitly unsupported.
The fixed primitive/projection exceptions are listed below. Unsupported exporter records are report entries, never
accepted judgments. Metadata nodes are erased because they have no typing role.

A successful check corresponds to the displayed *ground specialization* of the
source term, claimed type and entire exported environment. It does not establish
universal correctness for all universe parameter instantiations. The exporter
and format reader remain trusted for that correspondence. Lean replay rebuilds
Expr from the exported JSON and asks the actual kernel to add every declaration
and the target judgment. Nanoda replay emits equivalent ground NDJSON 3.1 and
checks it in an independently implemented Rust kernel. Both are evaluation-only.

| Component | Role / remaining trust |
| --- | --- |
| Lean preparation environment | Supplies elaborated expression/type syntax and constant bodies; source is checked externally, with no attached answer used at runtime |
| Exporter and document parser | Preserve binding, universe instantiation, annotations and complete assumptions; no type inference or reduction |
| DAG encoder | Syntax traversal/deduplication and binary packing only |
| Weighted initializer | Resets forged control, stacks, context and fuel; retains syntax and root/count metadata |
| Weighted transition compiler | Implements operational rules and guards; tested against full reference traces, not formally proved |
| Saturated attention | Exact binary address reads on tested float32 backend; underflow is a numerical assumption |
| Sparse ReLU arithmetic | Bounded Boolean/integer domain with explicit precision assumptions |
| PyTorch/backend/hardware | Executes fixed matrices; no formal runtime verification |
| Recursive/operational/Lean/nanoda references | Independent validation evidence; absent from runtime checking |

`SharedChecker.forward` is a transition on an intermediate machine state.
Arbitrary intermediate states are not proof inputs. `runner.run_states` always
applies the weighted canonical initializer before transitioning. All mutable
memory and control must originate there. Host shape/Boolean checks reject
nonbinary encodings without rounding. Raw heap pointer/arity/tag errors are
handled inside the weighted transition machine. New term allocation, lifting,
substitution, reduction, environment checks and outcomes are never precomputed
in the encoder.

`leanputer.report.v1` lists per-case outcomes, assumptions, input/allocated heap
nodes and actual semantic steps; runtime includes fixed applied steps, elapsed
forward time and CUDA peak allocated bytes. Model data includes all capacities,
shared FFN/attention stages, buffer bytes/nonzeros and trainable parameter count.
These are measurements, not soundness certificates. `RESOURCE` is incomplete;
`UNSUPPORTED` is outside the current syntax/conversion scope; `REJECT` concerns
the implemented ground calculus; complete correspondence with Lean remains a
validation target rather than a formally verified result.

Source names in export provenance carry structured `source_name_parts` (string
and numeric Lean Name components), plus displayed `source_constant` and ground
levels. Target selection accepts `name_parts` when display parsing is ambiguous.
Monomorphic environment names are opaque identifiers to the JSON checker and
both replay adapters; dots/quotes are never reparsed as namespaces there. The
exporter verifies an imported axiom was originally an actual axiom; unavailable
bodies of theorem/definition dependencies produce UNSUPPORTED. These checks
prevent accidental dependency weakening, but remain trusted exporter code.

Evaluation reports retain final whole-state SHA256 digests compared against the
independent operational specification. A digest comparison is compact
experimental evidence, not a proof of collision-free semantic equivalence.
Host peak RSS includes evaluation references and is labeled process-wide;
CUDA peaks measure PyTorch allocations only. The runtime has no dependency
verification cache. Reused artifacts/graphs reuse compiled weights, never prior
proof answers or unchecked theorems.

## Empty proposition primitive slice

The input grammar now includes `["builtin","False"]` and
`["builtin","False.rec",u]` for a concrete unsigned universe u. These are fixed
kernel primitives, distinct from user environment constants. Their typing rules
are `False : Prop` and
`False.rec.{u} : (motive : False → Sort u) → (t : False) → motive t`.
False has no constructors and its eliminator has no iota branches. This does
not implement arbitrary user inductive declarations or unchecked environment
assumptions. The eight-node dependent eliminator type is allocated by weighted
transitions from a compiled schema. Preparation does not infer it as a proof
certificate or inject an axiom declaration. Source exports preserve the actual
False/False.rec occurrences. User declarations remain checked in order.

This slice has targeted native/reference/Lean smokes; final broad differential
validation is deferred until architecture/feature implementation is complete,
as requested. The nanoda syntax adapter has not yet been extended for these
intrinsics; existing nanoda evidence applies to the earlier lambda-Pi fragment.

## Fixed proposition structures

The intrinsic catalog additionally contains `Iff`, `Iff.intro`, `And`, and
`And.intro`, with their standard closed positive typing schemas. User-supplied
arbitrary datatype declarations are not admitted. Projection syntax is
`["proj","Iff",0,term]` (mp), index1(mpr), or `And` indices0/1(left/right).
The weighted machine checks the projected term's inferred family and parameters,
lifts dependent codomains, and reduces a projection of its matching constructor.
Unary substitution/shift traverses the projected term. Conversion retains
proof-irrelevance fallback when structural bases differ. Fixed Iff.rec and And.rec rules are described below; recursors outside
the explicit catalog remain unsupported. Ordinary projection definitions remain in the checked
dependency closure. They are not replaced by unchecked environment assumptions.


## Equality primitive slice

`["builtin","Eq",u]`, `["builtin","Eq.refl",u]` and
`["builtin","Eq.rec",u,v]` preserve concrete universe parameters. Eq.rec's
order is **result universe, carrier universe**, matching Lean. Both parameters
participate in syntax validation and conversion. Its full dependent type is
constructed inside weighted transitions from a fixed compiled rule schema;
input documents do not supply type certificates. Eq.ndrec, Eq.mp and other
ordinary definitions are exported with checked bodies rather than admitted
as new primitive axioms.

Fully applied, well-typed Eq.rec reduces to its minor when the anchor and
endpoint are definitionally equal. This includes constructor iota and Lean's
K reduction with an opaque or neutral equality proof; it uses existing proof
irrelevance and typed conversion. A hypothesis `a=b` does not by itself make
distinct endpoints definitionally equal. The implementation relies on the
checker's typed weak-head-normalization invariant, as does its existing
conversion algorithm. No formal proof of that invariant or whole-compiler
soundness is claimed. Internally derived head/arity registers track partial
recursor applications; they are not input certificates or heap annotations.
General indexed inductive definitions, HEq and quotient rules remain unsupported.


## Let and true proposition

`["let",type,value,body]` retains all three subexpressions. Only body is under
one new binder. All three pointers must precede the parent in the syntax DAG.
The weighted machine checks that type has a sort, infers value and compares
its type to the annotation, then substitutes value into body and infers the
result. An unused invalid value or annotation still rejects. Shift/substitution
traverse annotation and value at the current cutoff/depth, incrementing it only
for body. Weak-head normalization performs zeta by the same weighted substitution.
No external zeta reduction or inferred body type is supplied by preparation.

`["builtin","True"]` and `["builtin","True.intro"]` add the fixed positive
rules True:Prop and True.intro:True. True.rec is now supported with its fixed dependent type and K-like unit rule.


## Fixed positive families and recursors

The catalog now includes Nonempty/Nonempty.intro/Nonempty.rec and
Exists/Exists.intro/Exists.rec, each with one ground carrier universe, plus
Or/Or.inl/Or.inr/Or.rec with no universe parameters. True.rec, And.rec and
Iff.rec have one ground result universe. These are fixed built-in schemas,
not user-supplied inductive declarations or inferred input certificates.

Nonempty.rec, Exists.rec and Or.rec motives land in Prop. Eliminating these
propositions into arbitrary data is rejected. And.rec and Iff.rec may target
Sort u, and their matching constructor arguments select the minor's fields
in order. The machine normalizes the major premise, checks its constructor
spine, and applies the appropriate minor. A neutral major stays neutral.
In particular, **an opaque And/Iff proof does not trigger data reduction**.
A targeted regression preserves this actual Lean behavior. True.rec has a
separate K-like unit rule, consistent with Lean's primitive recursor metadata.

Proof irrelevance remains a typed conversion fallback; it does not license
arbitrary recursor reduction in data-valued contexts. The native controller
implements all 81 phases from the same semantic IR. Type aliases from actual
Lean exports exercise each closed schema; focused iota/negative cases exercise
field order, Or branch choice, the Prop elimination boundary and opaque majors.
General recursive, indexed, mutual or user inductive definitions remain outside
this fixed catalog. The nanoda intrinsic adapter is still deferred; no new
nanoda evidence is claimed for these constructs.


## Fixed quotient primitives

`Quot`, `Quot.mk` and `Quot.ind` each carry one carrier universe.
`Quot.lift` carries **carrier universe, result universe**, in that order.
Their fixed kernel typing schemas are built inside weights. Lift checks its
function and the full relation-respectfulness proof before accepting an
application. Ind's motive lands in Prop. Both reductions normalize the major,
require a matching Quot.mk, and apply the minor/function to its representative.
Opaque or neutral quotients do not trigger representative selection.

`Quot.sound` is a genuine Lean axiom. It is exported as an ordinary explicit
environment axiom with its entire type checked, and is listed in assumptions
where used. It is not synthesized as a replacement for unavailable bodies.
Lean replay adds the kernel's actual quotDecl for the four quotient primitives;
that declaration does not add Quot.sound. Higher Setoid/Quotient structures
remain unsupported until implemented separately. Broad native/nanoda quotient
correspondence validation is still deferred.


## Fixed Decidable data

Decidable is a fixed family Prop → Type, with isFalse carrying p → False and
isTrue carrying p. Its dependent recursor has one result universe, two minors
in false/true order, and may return Sort u. The major must normalize to the
matching constructor before branch selection. Neutral decision values stay
neutral; they are data, not proof-irrelevant evidence. Both branches and two
negative cases are targeted in native execution.

Lean replay includes the actual closed Not definition before reconstructing
the standard Decidable inductive declaration, whose isFalse type refers to Not.
The weighted rule expands that definition as p → False. Neither side introduces
an axiom for negation, and ordinary exported Not dependencies remain checked.
