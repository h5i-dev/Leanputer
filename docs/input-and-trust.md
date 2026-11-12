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

Environment records have `name`, `type`, and `value` (null for an explicit axiom).
Dependencies must precede their users. Every declared type is checked to have a
sort; every definition value is independently inferred and compared with its
declared type. Future/self constant references fail. All assumptions are
reported. Supporting a declaration does not make its type an accepted axiom-free
theorem. Duplicate names and unknown external names are malformed input.

The external exporter traverses actual Lean Expr trees and the environment's
ConstantInfo. It retains applications and lambda terms requiring conversion;
it does not call inferType, whnf, isDefEq, or any checker to label the result.
Numeric level expressions are evaluated after syntactic universe parameter
instantiation. Unresolved levels, lets, projections, literals, metavariables,
inductive/constructor/recursor/quotient declarations and opaque dependencies are
explicitly unsupported. Unsupported exporter records are report entries, never
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
the currently implemented calculus and can differ from full Lean conversion.
