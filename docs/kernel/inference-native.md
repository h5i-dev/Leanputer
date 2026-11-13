# General native inference integration

The inference core and ordinary declaration driver are implemented; complete
conversion/inductive/primitive services remain unfinished. Authority
is pinned Lean4.31 `src/kernel/type_checker.cpp:infer_type_core, infer_lambda,
infer_pi, infer_app, infer_let, infer_constant, infer_fvar, infer_proj` and the
complete conversion/reduction contract in target.md. All Expr tags have fixed
source rules; declarations, telescope lengths, indices and names are data.

A public raw-scheme inference entry must first run the shared all-Expr closure/
universe-scope traversal. It starts with no supplied Local types or checked
signatures. Raw dependencies remain raw until the weighted declaration driver
checks them. A supplied claimed type must never be used as an inferred answer.

Inference uses private continuations and the SAME operations already lowered:
Sort creates Succ/Sort; FVar searches internally derived Local/type records;
Pi/Lam first check the domain's inferred type is a Sort, open one binder with
the shared telescope operation, infer the opened body, then restore scope.
Pi combines inferred universes with the SAME IMax; Lam abstracts the private
Local with the SAME abstraction service and builds its Pi type. App infers and
WHNF-exposes Pi, checks the argument with complete conversion, and calls the
SAME capture-avoiding instantiation for the result. Let checks annotation and
value, then infers the zeta-instantiated body. Metadata is transparent.

Constants must look up a PRIVATE CHECKED signature and instantiate its original
symbolic scheme after arity/scope checks. Projection must infer its major and
use checked generic inductive/constructor metadata and the source parameter/
field telescope loop, including Prop-to-Type restrictions. Literal/Quot rules
are justified actual kernel primitives, not a library-name expansion strategy.
The full target includes these operations and typed proof-irrelevance/eta/
conversion/reduction; missing implementations must report GAP and cannot return
negative or positive semantic answers on behalf of the unfinished operation.

Universe parameter slots precede scoped private Local records in the shared
context. Inference records its Local base on entry; raw symbol argument slots
are never mistaken for assumed Local declarations. New locals are allocated
only after the domain checks, uniquely identified by immutable allocation and
removed from the live context after the binder result is derived. Raw free
Locals are rejected by the public scope entry. Intermediate service completion
is not proof/declaration acceptance, and no new theorem coverage follows until
the whole source driver and complete required checking services are integrated.

Current implementation: `inference_machine.py` is the explicit development
transition reference; `inference_rules.py` emits the matching Boolean IR to the
SAME stock forward/cache program. The raw entry runs scope before inference.
The source Sort/FVar/Pi/Lam/App/Let/metadata call chain is lowered, with checked
binder domains and scoped private records. The current conversion callback is
only a positive shortcut (representation equality, beta/zeta then equality,
Sort-universe equivalence). Unhandled conversion cases report GAP, not false.
Checked constants now use weighted private lookup/universe instantiation after
source publication. A standalone operation entry still GAPs environment access;
projection/literal and remaining primitive services GAP. Raw signatures never
supply their inferred answers.

[Focused stock evidence](../../benchmarks/kernel-inference-core-stock/README.md)
checks the complete state/cache and independently inferred output types. This
is not full Lean checking. [Ordinary source transactions](environment-native.md)
now integrate checked-environment access/publication through weighted type/body
checking. Full inductive generation, complete typed conversion and primitive
callbacks remain unfinished. No field-count/name classes define that work.
