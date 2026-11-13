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
General indexed inductive declarations remain outside the fixed catalog.
The later HEq and quotient slices are documented below.


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


## Fixed Subtype records

Subtype and Subtype.mk take one carrier universe u; Subtype.rec takes result
universe then carrier universe. The family lands in Sort(max 1 u), including
when the carrier is Prop. The weighted schema constructor computes that numeric
universe floor. Projection syntax accepts Subtype indices0(val)/1(property).
Val has carrier type; property has predicate(val), constructed inside weights.
Projection substitution/shift preserves binding, and constructor iota selects
the corresponding field.

Subtype is data. Unlike And/Iff proofs, a neutral subtype value supports record
eta, and its recursor may expand the data major through its projections.
Conversion first identifies the left subtype and checks that the right value
has the same subtype, then compares their vals. The proof fields follow by typed
proof irrelevance. Different data vals reject. Non-Subtype fallback probes
return false rather than aborting outer proof-irrelevance comparisons. General
record declarations remain unsupported; this is a fixed checked catalog slice.

## Fixed heterogeneous equality

HEq and HEq.refl take one carrier universe; HEq.rec takes result then carrier
universe. Its motive quantifies over the endpoint's carrier and value. The
seven-argument recursor's K-like reduction first compares carrier types, then
values. Both must be definitionally equal before returning the minor. An assumed
heterogeneous equality does not make distinct carriers or values definitionally
equal. The same typed-normalization premise as Eq applies. Per-head arity bounds
protect partial-spine metadata. The controller has98phases; this remains a fixed
bounded fragment, not general inductive checking or formal soundness verification.

## Bool and Option data

Bool uses two nullary constructors and a dependent recursor with a result
universe. A normalized constructor selects its minor; a neutral Bool stays
neutral, even with identical branches. Option adds a type parameter and
zero/one-field constructors. Option.{u} expects Type u, represented as numeric
Sort(u+1); its recursor universes are result then carrier. Successor levels are
computed inside weighted primitive-schema construction. Using a Prop as that
Type carrier or a wrong some-field rejects. Neither type receives data eta.

## Fixed one-field record slice (provisional)

The catalog contains Inhabited, Mul, Add and Subsingleton, each with its actual
constructor and dependent recursor. Their projection index is exactly zero.
Inhabited accepts Sort u and lands in Sort(max 1 u); Mul/Add take and return
Type u; Subsingleton takes Sort u and returns Prop. Its field is a proof of
forall a b, Eq a b, which does not change definitional equality of those data.

Projection inference identifies the matching family and instantiates its fixed
constructor schema with the actual carrier by weighted substitution. The field
type is the resulting binder domain. This handles dependent binding without
an input field-type certificate or host type inference. Constructor reduction
checks the actual family/constructor spine. Typed data eta first checks the
same record type on both sides, then compares their projections. Data recursors
may expand a neutral Inhabited/Mul/Add through that field. Subsingleton is Prop
and retains constructor-only data reduction, matching the targeted actual Lean
boundary. General user record/inductive admission remains unsupported. Current
validation is targeted and provisional; the whole checker is not formally proved.

## Bounded natural literals and recursion

The literal node is ["nat",n], with unsigned n stored in one scalar word. Its
weighted inferred type is Nat. Nat.zero normalizes to literal0; Nat.succ on a
literal uses a guarded in-weight addition. Literal input bounds are the scalar
encoding bounds; for heap512 the10bit word represents literals0..1023.
Forced normalization of succ1023 produces RESOURCE/NATURAL, never wraparound.
Constructor expressions can still be well typed without forcing that numeric
normalization. The bounds concern the checking representation and computation,
not a claim that Lean's mathematical naturals are bounded.

Nat.rec builds the step application and recursive call inside weights. It
handles both literal majors and Nat.succ n with a neutral n; a neutral major
stays neutral. Shift/substitution treat literals as closed atoms. Zero/One use
the fixed one-field data-record path. General recursive inductive admission,
arithmetic primitive optimizations remain outside this slice. Ordinary numeral
notation retains its OfNat dependency and its actual instance definition;
preparation never rewrites it to a literal to evade environment checking.
The raw-literal fixture uses nat_lit syntax explicitly.

## OfNat and uniform record parameters

OfNat has two uniform parameters:the Type-u carrier and a Nat label. Its single
field has the carrier type and may differ from that label. For example an
OfNat Nat3 instance may store5. Constructor projection returns5, never3.
The ordinary instOfNatNat definition that stores the label itself is exported
and checked as a definition, not assumed or applied by the encoder.

The weighted record-parameter scan traverses the inferred family spine, checks
the expected fixed family head, builds its fixed constructor schema, and uses
stacked substitutions to instantiate all parameters in order. The resulting
field-binder domain is the projection type. Conversion first checks the whole
record type, including its label, before typed data eta. OfNat.rec carries
result/carrier universes and may expand a neutral data record through its field.
No arbitrary indexed inductive declaration admission is provided by this rule.

## PUnit's Prop/data distinction

PUnit.{u} has sort u and no data fields. Its recursor universes are result then
carrier. At carrier0, values are proofs and convert by typed proof irrelevance,
but a neutral major cannot reduce a data-valued recursor. Constructor iota still
applies. At positive carrier universes, empty-record data eta permits neutral
recursion. Typed equality first checks the exact PUnit type; different universes
do not merge. This distinction is checked against actual Lean rfl judgments.

## Fixed relation and pair records

LT/LE store α→α→Prop over a Type-u carrier. They use typed data eta; different
relation values are not proofs and cannot collapse by proof irrelevance.
PProd/Prod have two uniform parameters and two fields. PProd has
Sort(max(max1u)v), always data; Prod has Type(maxuv). Their recursor universe
order is result, left carrier, right carrier. Conversion checks both exact
record types and both fields; a mismatched family or either distinct field
rejects. General input structure declarations remain unsupported.

The [ground-universe encoding](ground-universes.md) changes only the internal
state ABI. Public builtin arrays retain each ground level separately. The
encoder packs scalar lanes without inference or reduction, and weighted
validation enforces lane bounds, unused padding and reserved zeros. Fixed
schema max/successor calculations run inside weights. Symbolic universe
constraints are still unsupported; targeted Lean/native agreement is not a
formal proof of the compiler or the typed normalization invariant.

Membership has two uniform Type parameters and field γ→α→Prop, in that order.
Its family/constructor carry element/container universes; its recursor carries
result/element/container universes. The fixed schema uses the definitionally
equal normalized form of the standard outParam annotation. Source aliases and
ordinary projection definitions still export their actual specialized outParam
dependencies for checking. Lean replay adds the standard polymorphic outParam
definition by kernel-checked declaration before adding Membership's genuine
inductive declaration. It does not add an axiom. Different carriers, reversed
field arguments or arbitrary distinct relation values cannot be identified.

HAdd/HMul have three uniform Type parameters and field α→β→γ. Family/constructor
levels are left/right/result-carrier; recursor levels are motive-result followed
by all three carrier levels. The fourth level is stored separately and checked
with the others inside weights, including zero padding for lower arities.
Field inference instantiates all three parameters and preserves the result type.
Typed data eta checks the exact family/type before comparing fields; a swapped
argument, wrong result carrier or changed fourth universe rejects in targeted
Lean/native checks. These remain fixed declarations, not generic user records.

The fixed inherited law-record slice covers Semigroup/AddSemigroup and
CommMagma/AddCommMagma. Each has one Type-valued carrier parameter and two
stored fields: a Mul/Add parent and a dependent associativity/commutativity
proof. Their family and constructor have one numeric universe parameter, their
recursor has two. The compiler schema expresses operations through the parent's
projection; this is definitionally equal to Lean's ordinary HMul/HAdd aliases.
Those aliases and instance definitions still appear as checked input dependencies.

Law projection inference constructs the fixed constructor type, substitutes the
actual carrier, then substitutes the projection of the actual stored parent.
The syntax encoder never supplies an inferred field type. A proof about a
left-projection operation cannot construct a record whose operation is right
projection. Typed record eta compares exact record types and their data parents;
the remaining law fields inhabit Prop and use definitional proof irrelevance.
The fixed two-field recursor applies its minor to both stored projections,
including a neutral major. This does not admit arbitrary user structures.

Conversion remains incomplete within resource budgets. Comparing two distinct
neutral law records currently cycles between projection congruence and typed
record eta until STACK exhaustion. The targeted negative is rejected by actual
Lean but reported as RESOURCE by this bounded engine. The recursive evaluation
oracle also reaches its recursion limit. No acceptance or semantic rejection is
claimed for that case; broad numerical/semantic correspondence remains pending.

Evaluation can select the actual mathlib replay basis with `--lean --lean-module
Mathlib.Algebra.Group.Defs`, invoked inside the pinned checkout's `lake env`.
The Python `lean_replay(..., module=...)` adapter exposes the same option.
This only changes the independent offline reference, never model inference.
