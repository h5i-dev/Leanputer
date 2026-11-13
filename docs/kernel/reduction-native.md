# Checked-environment weak-head reduction

Target authority: pinned `type_checker.cpp:whnf_core, is_delta,
unfold_definition_core, unfold_definition, whnf` and
`declaration.h:constant_info::has_value`. This is one general module in the
complete target, not a declaration-shape or selected-name extension.

The existing private argument stack walks application spines. Metadata is
transparent; Let and applied Lam use the shared capture-avoiding instantiation.
For a Const under a checked environment, use the SAME private environment lookup
and universe-arity zip as constant inference. Select its checked body according
to the source kind: definitions AND theorems have values; opaque declarations
and axioms do not unfold. Source `constant_info::has_value()` includes theorems.
For an unfoldable entry, instantiate the original body universe parameters with
the SAME all-Expr source-instantiation walker, restore the caller's context
window, then resume weak-head traversal with the SAME pending application spine.
Repeated aliases/beta/zeta are a data-controlled loop; no supplied reduction
schedule, specialized type or inferred answer enters memory.

An opaque/axiom head returns neutrally; unknown names fail the typed source
checking path. Missing definition bodies cannot be published by the source
driver. Public standalone beta/zeta operations start without a checked
environment and cannot access supplied raw declarations. Fuel/heap/stack/context
exhaustion is RESOURCE. All checked signatures/bodies are immutable and input
cannot encode checked records.

This module does not complete WHNF/conversion. Recursor/K/Quot/projection/literal
reduction and complete typed proof-irrelevance/eta/conversion remain target
modules with explicit GAP callers. Inductive block admission/generation remains
unfinished. Generic header/telescope/positivity/index/recursive-argument callers
reuse this service rather than introduce field-count/name-specific reductions.

Implementation: the SAME constant_machine/constant_rules lookup+zip now dispatch
on the private caller task (inference/type or WHNF/allowed checked body).
[Native4 exact-state/cache evidence](../../benchmarks/kernel-checked-delta-stock/README.md)
covers generic delta, opacity, application spines and symbolic universe zip.
The preceding ordinary-source benchmark is pinned e0db573 with beta/zeta only.

The shared [native binder integration](../../benchmarks/kernel-dependent-telescope-stock/README.md)
implements two different source operations. Opening a telescope creates fresh private Locals and checks its
WHNF before every binder; a bounded prefix returns its tail without opening
extra binders. Consuming a shared parameter telescope reuses the SAME previously
derived Local records: expose Pi, compare its domain against that Local's type,
instantiate the body with the existing Local, advance a data count. Each shared
parameter is checked in order so later domains see the earlier substitutions.
Universe symbol slots and Local slots have explicit context windows. The caller
owns context lifetime; the operation restores windows and never treats symbol
slots/raw types as Local assumptions. Header/constructor callers choose the
source-required normalization policy, not a supported shape class. Missing
conversion propagates GAP. Both loops must call the existing weighted services,
not copy a host telescope or precomputed uniformity result.

The subsequent semantic-IR update matches `is_delta` failure behavior: a missing
entry or wrong universe arity is neutral for WHNF; typed inference still rejects
those constants. This matters for generic core predicates working under staged
family data, and does not authorize using raw types as inferred answers. New
core module tests cover it; the stock report above is pinned539b84f.

## Runtime recursor algorithm and shared application representation

The complete target is pinned `inductive.h:to_cnstr_when_K`,
`to_cnstr_when_structure`, and `inductive_reduce_rec` (lines30–117), with
`inductive.cpp:mk_nullary_cnstr`, `expand_eta_struct`, `get_rec_rule_for`.
This determines the operation before testing instances:

1. Split the recursor expression into head and arguments; require a checked
   recursor signature and a present major at
   `nparams + nmotives + nminors + nindices`.
2. For the metadata K flag, infer/WHNF the major's type, require its owner family,
   build that family's first constructor at the type's universe arguments and
   parameter prefix, infer its type, and compare the two types before replacing
   the major. There are no expression metavariables in the exported target.
3. WHNF the major. Kernel Nat/String primitives use their source literal
   expansion; other majors use structure expansion only under the source
   predicate (one constructor, no indices, nonrecursive), checked owner type,
   and non-Prop type. Construct all projections in a counted field loop.
4. Split the resulting major and search the derived rule vector by constructor
   identity. Missing rule/major/insufficient actual fields or wrong recursor
   universe arity means no reduction, not a rejected proof.
5. Instantiate the selected closed RHS's universe scheme. Apply the first
   `nparams + nmotives + nminors` recursor arguments, then the **trailing**
   `nfields` actual major arguments, then arguments after the major. Constructor
   and recursor parameter counts can differ after nested restoration. Do not
   use either count as a shape restriction or substitute the parent's indices
   for a recursive subvalue's indices.
6. Resume the shared WHNF controller on this expression. Neutral return must
   preserve the caller's pending application stack; successful return consumes
   the spine exactly once. Recursive WHNF/inference/conversion calls require
   immutable per-call state retained by continuations, not unprotected global
   scratch registers.

`APPLICATION_SPINE` is now implemented in the development reference and Boolean
IR as a pure reusable operation. It allocates an immutable output-only
`APPLICATION_SPINE(headExpr, argumentVector, 0)` record (tag183); arguments are
in application order. `get_app_fn` stops at a metadata wrapper exactly as the
source syntax helper does; transparency belongs to WHNF. `APPLY_VECTOR_SLICE`
validates `(start,take)` against a reference-vector length without word overflow,
then allocates the corresponding application chain. Both preserve context,
environment and stack and have no checking/reduction authority. These operations
serve runtime reduction, K/structure expansion and projection traversal without
field-count/name branches. Their current evidence is focused exact-state IR,
not a native reduction or theorem-acceptance result.

The remaining composition is explicit: select/instantiate/apply derived rules;
K/structure/literal preparation with the shared checked services; reentrant WHNF
integration; full original-source nested staging/restoration and publication.
Missing checked conversion/primitive/projection services must GAP, not supply
admission answers. This decomposition is of the complete source algorithm,
not a supported datatype-class ladder.
