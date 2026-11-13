# Target kernel algorithms and representation

This is the implementation contract, not a claim that the target is implemented.
The earlier per-name catalog and the newer restricted `generic_*` checker are
preserved reference work. Neither determines this target's semantics. In
particular, field count, parameter count, constructor count, mutual-block size
and recursive function arity are data traversed by shared loops. They do not
select different supported inductive classes or different compiled algorithms.

## Pinned authority and target boundary

The authority is Lean4.31.0 commit
`68218e876d2a38b1985b8590fff244a83c321783`, matching the installed executable.
The algorithmic cross-reference is nanoda_lib commit
`0da9f98feadd3a0a2ef4b3dbcf52a298a6fef929`. File hashes and source links are in
[sources.json](sources.json). Nanoda is a reference, not code to translate wholesale.
Where its behavior differs, the pinned Lean kernel decides the target behavior.

The target is the safe declaration/expression kernel at that pin: symbolic
universes; dependent Pi/Lam/App/Let; definitions/theorems/opaque bodies; general
inductive blocks including dependent fields, indices, mutual and nested
inductives; generated recursors and projections; conversion including the
kernel's function/structure eta, proof irrelevance and unit-like rules; and the
kernel's literal/Quot primitives. All of these belong in the design now.
No field-count or parameter-shape restrictions are part of the target.

Unsafe/partial declarations and mutual unsafe definitions are outside this safe
profile. The pinned kernel itself rejects safe mutual-definition declarations
(`environment.cpp:add_mutual`); ordinary safe recursive library functions arrive
as checked acyclic definitions using recursors/fixpoint constructions. Unresolved
metavariables and externally supplied free locals are invalid closed declarations.
An explicit goal context is allowed only when its declarations are themselves
checked and reported as assumptions.

`Lean.reduceBool`/`Lean.reduceNat` invoke native compiled code in the pinned
kernel. That execution path is outside the user's authorized inference model
and is rejected explicitly. It will not be silently treated as an axiom, run on
the host, or implemented by a CPU emulator. Kernel Nat/String literal operations
and Quot are genuine finite primitive interfaces; ordinary Eq, Nat inductive
formation, structures and their eliminators are not a growing primitive catalog.
Primitive bindings and required signatures must be checked before literal/Quot
rules use them. Symbolic universe normalization and integer arithmetic run in
weights; the host does not precompute their answers.

## Source-to-operation map

All paths below are relative to the pinned repositories. The named functions,
not a selected theorem, specify each operation.

| Kernel operation | Lean authority | nanoda cross-reference | Shared transition/data operation |
|---|---|---|---|
| Declaration scope, safety, values | `src/kernel/environment.cpp:check_constant_val, add_axiom, add_definition, add_theorem, add_opaque, add_mutual` | `src/tc.rs:check_declar, check_declar_info` | checked environment lookup, scoped overlay, type/value comparison, atomic publication |
| Universe syntax/equality/order | `src/kernel/level.cpp:normalize, is_equivalent, is_geq_core, is_not_zero`; `type_checker.cpp:check_level` | `src/level.rs:simplify, leq_core, eq_antisymm` | level-DAG traversal, parameter membership, substitution, canonicalization and comparison |
| Instantiation/abstraction | `src/kernel/instantiate.cpp`, `abstract.cpp`, `local_ctx.cpp` | `src/expr.rs:inst, abstr, abstr_telescope` | binder-depth expression walk, fresh local IDs, capture avoidance, telescope fold |
| Expression typing | `src/kernel/type_checker.cpp:infer_type_core, infer_constant, infer_app, infer_lambda, infer_pi, infer_let, infer_proj` | `src/tc.rs:infer, infer_app, infer_lambda, infer_pi, infer_let, infer_proj` | typed recursive calls through explicit continuation/scope frames |
| Conversion/reduction | `type_checker.cpp:whnf_core, whnf, is_def_eq_core, lazy_delta_reduction, try_eta_struct_core, is_def_eq_proof_irrel` | `src/tc.rs:whnf, def_eq, proof_irrel_eq, try_eta_struct_aux` | normalize/apply/compare service, typed eta and proof checks, environment-epoch caches |
| Block headers and indices | `src/kernel/inductive.cpp:check_inductive_types` | `src/inductive.rs:check_inductive_specs, check_inductive_spec_0th, check_inductive_specs_mutual1` | open shared parameter telescope, compare domains, traverse each index telescope, compare result levels |
| Occurrences/strict positivity | `inductive.cpp:has_ind_occ, is_valid_ind_app, check_positivity, is_rec_argument` | `inductive.rs:has_ind_occ, is_valid_ind_app, check_positivity1, is_rec_argument` | symbol-set DFS, application-spine view, local-parameter identity, functional recursive descriptor |
| Constructor admission | `inductive.cpp:check_constructors, declare_constructors` | `inductive.rs:check_ctor, mk_ctors_env_ext` | generic parameter/field telescope traversal and checked universe constraints |
| Nested elimination/restoration | `inductive.cpp:elim_nested_inductive_fn, restore_nested, environment::add_inductive` | `inductive.rs:specialize_nested_aux, replace_if_nested, restore_and_check` | work queue of auxiliary block members, substitution/rewrite map, recheck restored declarations |
| Elimination universe/K eligibility | `inductive.cpp:elim_only_at_universe_zero, init_elim_level, init_K_target` | `inductive.rs:large_elim_test, large_elim_test_aux, init_k_target` | derive flags from checked fields/result arguments and symbolic levels, never supplied flags |
| Motives/minors/rules | `inductive.cpp:mk_rec_infos, mk_rec_rules, declare_recursors` | `inductive.rs:mk_motives, mk_minors1group, handle_rec_args_minor, mk_rec_rule1, mk_recursor_aux` | binder/vector folds over all families, constructors, fields and recursive descriptors |
| Runtime recursor reduction | `src/kernel/inductive.h:to_cnstr_when_K, to_cnstr_when_structure, inductive_reduce_rec` | `src/tc.rs:to_ctor_when_k, iota_try_eta_struct, reduce_rec` | derived rule lookup, universe instantiation, generic vector application, beta reduction |
| Dependent projections | `type_checker.cpp:infer_proj, reduce_proj_core` | `src/tc.rs:infer_proj, reduce_proj_core` | instantiate parameters then all preceding dependent fields using projections; select requested field |
| Genuine primitives | `src/kernel/quot.cpp`; `type_checker.cpp:reduce_nat, reduce_pow`; `inductive.cpp:nat_lit_to_constructor, string_lit_to_constructor` | `src/quot.rs`; `src/tc.rs:reduce_quot, try_reduce_nat` | fixed primitive registry with validated bindings and bounded limb/byte algorithms |

## Shared data model

The input format must preserve original declaration schemes. Ground goals may
instantiate them, but admission must not first ground-specialize a polymorphic
inductive: whether a symbolic result universe can be Prop changes elimination
eligibility. The old ground-specialized interface cannot decide that property
for the original scheme and is not the complete target representation.

Use immutable, indexed DAGs and separate raw and derived environment banks:

* Expression row `(tag,a,b,c)`: BVar, internal Local, Sort, Const, App, Pi, Lam,
  Let, Proj, NatLit, StringLit, MData. Const carries symbol and universe-vector
  references; Sort carries a level reference; Let uses three expression children;
  Proj carries a family symbol, arbitrary field index and value. Binder metadata
  is syntax, not an inferred type. Local expressions are internal only.
* Level row `(tag,a,b)`: Zero, Succ, Max, IMax, Param. Declaration universe-parameter
  vectors bind Param symbols. No input metavariables. Constant universe arguments
  are expressions over that same DAG, not host-evaluated integers.
* Vector headers/cells store bounded lists of references. Parameters, indices,
  fields, motives, minors, block members, local function arguments and rule lists
  all use this representation. Length is data. A loop ends at the vector/telescope
  boundary, not at a compiled field-count case.
* Local rows contain a fresh identity and declared type/optional let value.
  Opening a binder instantiates its body with a fresh Local. Folding abstracts
  those identities back into de Bruijn binders. Scope marks restore active locals;
  generated closed outputs are checked for escaped locals before publication.
* Raw declaration rows describe schemes, bodies and complete inductive blocks.
  `numParams` is a checked declaration annotation. Index/field counts, recursive
  flags, reflexivity, elimination permissions, K and recursor descriptors are
  derived inside the checker. Exported values for these are claims to compare,
  never trusted admission answers.
* A validated block descriptor references shared parameters, per-family indices
  and result levels, constructor telescopes, result-index templates and recursive
  argument descriptors. A recursive descriptor names a target family and the
  dependent function telescope before it, plus its result indices. It is not a
  boolean `recursive` flag and is not restricted to direct self fields.
* Generated recursor records store schemes, major position, rule vectors and
  derived eligibility flags. Each rule contains a constructor ID, derived field
  arity and a generated lambda RHS. Reduction applies that RHS generically rather
  than dispatching to a hand-written rule for a field layout.

Only physical arena/vector/context/stack/symbol/limb capacity and fuel are model
configuration. Exhausting them is RESOURCE. Missing implementation of a whole
operation is recorded separately from an invalid declaration; it must not be
hidden as acceptance or a trusted library declaration.

## Complete admission and recursor algorithm

1. Validate closed raw syntax, symbols, universe parameters and prior dependency
   visibility. Start a block transaction; nothing is published on partial success.
2. Eliminate nested occurrences using a growing queue as in the pinned kernel.
   For a prior inductive application whose parameter arguments contain current
   block families, require the source's closure condition, specialize all members
   of its prior mutual block, deduplicate specialization templates and append
   auxiliary declarations. Rewrite constructors until the queue is exhausted.
   Retain the auxiliary-to-original map for restoration and rechecking.
3. Check every family type. Open the first family's declared shared parameters;
   compare the other families' parameter domains definitionally in that shared
   context. Traverse each remaining index telescope to a Sort, and require
   equivalent result levels across the mutual block. Parameters can be terms and
   domains can depend on previous binders; literal Sort domains are not required.
4. Install a private family-header overlay. For each constructor, check its type,
   consume the shared parameters with checked domain equality, then traverse ALL
   remaining dependent binders. For each field infer its domain's Sort; require
   its level below the family result unless the result is Prop. Apply the generic
   strict-positivity algorithm below. Finally require the owning family applied
   to unchanged shared parameters and well-typed indices, with no block-family
   occurrence inside any index expression. Derive field arity from the telescope.
5. Derive recursion/reflexivity and elimination metadata. A provably nonzero
   symbolic result allows large elimination. A possibly-Prop mutual block or
   multiple constructors restricts elimination to Prop. For a singleton, each
   non-Prop field must occur as an actual argument in its result application;
   empty predicates allow large elimination. These are the pinned semantic rules,
   not arbitrary implementation dispatch on convenient constructor shapes.
6. K eligibility is exactly the source predicate: a single inductive predicate,
   one constructor, no fields after parameters. K execution still requires that
   the constructor prototype's inferred type converts to the actual major type;
   singleton status alone must not erase incompatible indices.
7. Install the private constructor overlay. For each family build
   `motive : Π indices, family params indices → Sort elimLevel`.
   For every constructor open ALL fields. Let its result be `I params js` and
   constructor value `c params fields`. Its minor result is
   `motive_I js (c params fields)`.
8. For each recursive field `u : Π xs, J params ks`, derive an IH
   `Π xs, motive_J ks (u xs)`. The minor binds ALL constructor fields first,
   then ALL IHs in recursive-field order. This ordering is in both pinned sources;
   it is not an interleaving chosen separately for each field count.
9. Build each recursor type as
   `Π params, Π motives, Π allMinors, Π ownIndices, Π major, motive ownIndices major`.
   Build each computation RHS as a lambda over parameters, motives, minors and
   constructor fields, applying the selected minor to all fields followed by
   `λ xs, rec_J params motives minors ks (u xs)` for each recursive field.
   Check/compare supplied recursor schemes and RHS claims against these generated
   records. The rule is generated data, not trusted input or compiler constants.
10. Restore nested names/schemes/rules with the retained substitution map, recheck
    restored declarations and their association with the original block, and
    atomically publish the checked block. Restore every temporary local/overlay
    scope before checking subsequent declarations or the goal.

Strict positivity itself is one algorithm: WHNF the field type; return if no
current-block constant occurs; for Pi require no block occurrence in the domain,
open the binder and continue in its body; otherwise require a saturated valid
application of a family in the same block. Nested occurrences are first handled
by step2, not accepted through an unproved positive-functor flag.

## Expression operations and reduction

The shared operations are spine traversal, scoped telescope open/fold, expression
and level substitution, occurrence DFS, dependent vector application, INFER,
WHNF, and typed conversion. Their implementations are independent of the number
or names of datatypes using them.

INFER follows the finite expression-tag rules: variables/locals through checked
contexts; Sort via successor; Const via checked universe substitution; App by
checking its argument against a Pi domain then instantiating; Lam/Pi by opening
binders, checking domains/codomains and applying imax; Let by checking the value
and instantiating; Proj by the generic constructor-telescope procedure. Metadata
is inert. Literals use validated kernel primitive bindings.

WHNF implements beta/zeta, transparent delta, derived recursor RHS application,
projections and justified literal/Quot reductions. Recursor reduction computes
its major position from descriptor lengths, performs valid K/structure expansion,
normalizes the major, looks up its constructor rule, specializes rule universes,
applies parameters/motives/minors and actual constructor fields, then surplus
arguments. It never assumes a recursive subvalue has the parent's indices.

Projection inference instantiates the constructor's parameter binders, then
walks all fields preceding the requested index, substituting earlier projections
when the remaining telescope depends on them. It enforces the pinned Prop/data
restriction. Projection reduction selects constructor argument `numParams+idx`.
The existing zero/one-field implementation is reusable traversal code, not the
specification of this operation.

Conversion follows the pinned typed algorithm: universe equality, beta/delta/
zeta/iota, binder congruence, application/projection comparison, function eta,
nonrecursive structure eta, unit-like comparison, and proof irrelevance only
after checking proposition/type compatibility. Cache keys include environment
and local/universe context epochs. A resource failure is not inequality; a false
result from an incomplete module is not a certificate that Lean rejects a term.

## Execution and lowering contract

Each general operation uses explicit work stacks, vector cursors and scope
frames. Calls to WHNF/INFER/CONV are internal kernel service calls in that same
machine, never callbacks to an external checker at inference. A reference
executable spec may implement these services in Python for development; it is
not an inference path until the corresponding operations are lowered.

The finite controller program and its typed semantic operations are compiled
into stock Qwen3.5 Transformer blocks and cache. There is no user-supplied CPU
instruction stream, RISC-V emulator or native code execution. Proof data cannot
write control frames. Input/derived banks are distinct; word overflow, vector
bounds, stale scopes and escaped locals are checked explicitly. Physical row
payloads can reference auxiliary records instead of growing a stock value head
past its width. No custom forward or custom attention is substituted.

## Current implementation and module order

The target above is complete; this table states implementation gaps, not future
semantics to invent from examples.

| Module | Current reusable implementation | General work required |
|---|---|---|
| Arena/syntax/scopes | `kernel/arena.py`: immutable all-tag Expr/Level/vector arenas and scoped Local identities; `environment.py`: private overlay/rechecking and atomic publication (spec) | integrated native ABI/lowering |
| Original-scheme input | `ExportKernel.lean` and `kernel/syntax.py`: syntax-only complete-tag/scheme/mutual-block transport, explicit recursor claims and unavailable rows | integrate the complete checked-environment/native driver; see [input.md](input.md) |
| Physical native input | `native_cells.py`: typed vector/name/level/raw-declaration packing, excludes offline generated artifacts; `level_transition.py`: stock symbolic scope, raw/source all-Expr instantiation, constructors, normalization/equivalence and typed telescope calls, with argument windows | checked-environment/inference callers and full weighted admission; see [native-cells.md](native-cells.md) |
| Substitution/traversal | `kernel/operations.py`, `telescope.py`: iterative all-tag lift/instantiate/abstract, symbolic-level substitution, scope/occurrence checks, dependent telescope open/fold (spec); `traversal_transition.py`: stock traversals, beta/zeta, Pi/Lam telescope opening/folding through shared substitution/abstraction/private calls | connect checking/generation callers and full kernel |
| Expression/universe checking | `kernel/levels.py`: symbolic normalization/equality/order/nonzero; `services.py`: dependent inference/reduction with explicit conversion gaps (spec); `inference_rules.py`: shared stock Sort/Local/Pi/Lam/App/Let core with private typed scope and explicit callback GAPs | complete typed conversion, projection/K/eta/literal/Quot services and stock integration |
| Declaration admission | `kernel/positivity.py`, `admission.py`: general core checks; `nested.py`: queue/mutual specialization/closure/template and restoration operations; `environment.py`: checking/rechecking/private staging and atomic publication (spec) | complete internal conversion/projection/K/primitive services and stock integration |
| Recursor generation/reduction | `kernel/recursor.py`: general motives/minors/rules for private checked descriptors; constructor-headed rule application (spec) | admission integration, checked K/structure/literal major handling; stock lowering |
| Stock lowering | stock forward/cache emitter and memory ABI | lower the shared general operations; remove count-specific semantic paths |
| Evidence | targeted restricted traces/native/source replays | targeted module contracts first; broad differentials remain deferred |

Implementation proceeds by these general operations, not by another selected
record or another field count. Tests vary dependent telescope lengths, nesting,
indices and names against the pre-existing algorithm. Documentation and reports
must keep design, executable-spec coverage, native coverage and trust assumptions
separate. No completion percentage or generic mathlib fraction is established.

The Python algorithm modules under `leanputer/kernel/` are **not a kernel
inference path**. They are not imported by the proof checker's native syntax
loader. The separate `traversal_transition` program compiles the shared
LIFT/INSTANTIATE/ABSTRACT/OCCURS operations to stock forward/cache; its loader
reconstructs raw syntax/operand vectors only. The matched eight-operation
[stock smoke](../../benchmarks/kernel-traversal-stock/README.md) verifies exact
registers and output cache rows. DONE means operation completion, not proof
acceptance. These operations are not yet integrated into full admission.
The [extended eleven-operation smoke](../../benchmarks/kernel-expression-services-stock/README.md)
also verifies beta/literal-Let/metadata reduction through the same substitution
walk and private continuation stack. Checked-environment/local-let lookup,
recursor/projection/K/eta/literal/Quot rules are not part of that subservice.
The [sixteen-operation stock smoke](../../benchmarks/kernel-telescope-stock/README.md)
also verifies closed-variable scope and declared dependent telescope opening/
prefix consumption. Local/type/binder-info records are produced inside weights.
This scope subservice checks BVars/Locals; universe membership and type checking
remain separate unfinished weighted services. No field-count semantic dispatch
or supplied inferred types enter the operation.
The [twenty-operation stock smoke](../../benchmarks/kernel-telescope-fold-stock/README.md)
adds reverse folding through the same abstraction walk, dependent prefix
open/fold, both Pi/Lam kinds and cross-kind reconstruction. It checks returned
closed ASTs and restored scope without accepting proof-supplied control frames.
The [typed symbolic stock smoke](../../benchmarks/kernel-typed-symbolic-stock/README.md)
loads the physical name/level/vector representation and checks symbolic level
parameter membership inside the same stock controller as Pi/Lam callers.
It does not supply or check full source admission; standalone operation reports
must not be counted as theorem coverage.
The [twelve-operation substitution smoke](../../benchmarks/kernel-level-substitution-stock/README.md)
adds simultaneous raw symbolic substitution on all level tags with typed
bindings, missing/empty mappings and preserved caller context. Canonical normalization remains separate. The
[seventeen-operation expression substitution smoke](../../benchmarks/kernel-expression-levels-stock/README.md)
adds raw universe instantiation throughout all twelve Expr tags, including the
original exported `id` body. Sort/Const use the SAME level substitution routine;
universe vector length is data. This is still operation evidence, not native
typing or admission.
`BetaZeta` implements
only its named WHNF subservice. Positivity and generation call internal services
whose complete checking implementations are still missing; their focused unit
tests supply structural equality or the beta/zeta subservice to test isolated
module contracts. `test_kernel_admission` instead runs the actual internal
inference/level services for the general core phase; it still does not certify
complete declaration admission. Test-generated
recursor types/rules are scoped and exercised for mutual indexed functional
recursion, including fields-before-IHs and nested-restoration parameter arity.

Source details preserved in the core: constructor **declared** Pi telescopes
are traversed syntactically (unlike family headers, which are WHNF-ed).
Recursive/reflexive block flags derive from source syntactic occurrences,
separately from normalized recursive-argument descriptors. All members share
those global flags. Neither flag is trusted input.

`examples/KernelAlgorithms.lean` independently checks dependent fields and
the mutual indexed functional recursor type/computation law. It also directly
invokes the raw pinned kernel on a symbolic `Sort u` inductive. Lean's command
elaborator rejects possibly-Prop result universes, but its raw kernel admits
them with the derived elimination restriction. The complete target follows the
kernel; its schemes cannot be ground-specialized before admission. This replay
is development evidence and is never part of inference.

`environment.py` now connects ordinary declaration checking, the nested queue,
core checks, generated recursors, restoration/rechecking and atomic publication
as a development specification. Missing conversion/primitive services produce
GAP, never false rejection or a trusted input answer. Actual `id` and `Eq.symm`
source bodies/closures pass this spec; `Prod.fst` explicitly reports the missing
projection service. A source nested/mutual/term-parameter
[transaction smoke](../../benchmarks/kernel-nested-spec/README.md) admits12derived
declarations/noaxioms and checks its complete source body. These are not native
proofs or generic mathlib coverage. The weighted driver is still unfinished.

The [shared symbolic constructor smoke](../../benchmarks/kernel-level-constructors-stock/README.md)
checks structural comparison (including duplicate runtime allocations), nonzero,
offset and complete smart Max/IMax operations inside the stock controller.
The [level algorithm map](level-services.md) distinguishes these reusable rules
from the subsequent normalization/equivalence integration and typed admission still pending.

The [source instantiation/order smoke](../../benchmarks/kernel-source-instantiation-stock/README.md)
connects changed Max/IMax updates to the SAME constructor services in standalone
levels and all-Expr schemes. The generic base/offset-last order is lowered for
canonical merging; normalization/equivalence now use that comparator. Admission
remains unfinished.

The [ten-operation canonicalization smoke](../../benchmarks/kernel-level-normalization-stock/README.md)
verifies complete symbolic normalization/equivalence through the shared services,
with no host sort/equality answers. Typed inference/conversion and integrated admission remain gaps. No native source theorem coverage follows
from operation DONE.

The [twelve-operation conservative geq smoke](../../benchmarks/kernel-level-geq-stock/README.md)
completes the pinned symbolic-level comparison service, including Max failure
fallback and IMax/offset recursion. Typed checking/environment/admission callers
remain unfinished; operation DONE adds no native source theorem coverage.

The [eight-input full expression scope smoke](../../benchmarks/kernel-expression-scope-stock/README.md)
connects BVar/Local closure and all Sort/Const universe positions to the SAME
weighted membership service. Raw scope data does not establish constant existence,
signature arity, typing or admission. Those remain subsequent typed callers.

The [all-tag expression comparison smoke](../../benchmarks/kernel-expression-comparison-stock/README.md)
connects typed vector streaming and the SAME structural level comparator. The
[representation contract](expression-comparison.md) records erased annotations
and the distinction from full conversion; false is NOT definitional inequality.
Composed source instantiation creates duplicate runtime levels/vectors before
comparison. Full typed/environment/admission callers still remain unfinished.

The [typed-core stock smoke](../../benchmarks/kernel-inference-core-stock/README.md)
connects [inference callers](inference-native.md) to the SAME private telescope/
substitution/abstraction/level services. Raw signatures are not checked answers;
missing environment/projection/literal/full-conversion paths return GAP. DONE
returns an inferred type, not source theorem/admission acceptance.

The [read-only raw declaration port smoke](../../benchmarks/kernel-environment-abi-stock/README.md)
verifies all four cache banks before [checked-environment/source transaction
integration](environment-native.md). A separate raw cursor address is available;
advancement and publication remain unfinished. Transport is not admission.

## Current integration status (supersedes historical operation-stage notes above)

The [ordinary source driver](environment-native.md) now scope/type/body checks
dependencies before generating private signatures in weights, and checks its
target without assuming it. Original schemes feed the SAME constant lookup and
universe instantiation. [General checked delta](reduction-native.md) now unfolds
source-permitted definition/theorem bodies on that environment. Raw-bank cursor
advancement/publication and ordinary inference are implemented. Complete typed
conversion and general inductive/recursor generation/restoration, Quot/literal/
projection/K/eta services remain unfinished explicit GAPs. Ordinary native source
evidence is distinct from earlier operation DONEs and offline inductive specs.
No complete857-source native rerun/mathlib fraction is claimed.

The [core-through-motives stock report](../../benchmarks/kernel-motives-stock/README.md)
at72cd7a0 now derives all private header/constructor checks, functional recursion
descriptors, recursor-name relations, constructor signatures, elimination/K and
all-family motive types from raw syntax, with exact register/cache agreement.
It ends GAP before minors/recursor types/rules. The original-source controller
still GAPs before missing nested staging; this explicit kernel-function operation
cannot certify an original nested declaration or theorem. Subsequent IR modules
scan raw recursion/reflexivity flags and reopen generic dependent recursive
prefix/index templates using shared context-window substitution/snapshots.
These later modules are not part of that pinned stock measurement. The complete
generation/restoration/reduction algorithms above remain the implementation
target, not a supported shape catalog.
