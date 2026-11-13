# General inductive lowering and shared loops

Complete target/data contract: target.md and pinned `inductive.cpp`, with
original raw cells96..100 in native-cells.md. No library names, constructor
field-count classes or host-derived positivity/index/recursor answers define
this implementation. Count branches are only source semantics (including Prop
elimination/K rules) or physical bounds. This document records the module
integration order, not a claim that an incomplete module admits a block.

1. Validate the raw block/universe/name vectors. Check every header as a closed
   type in the previous checked environment, BEFORE the temporary family overlay.
   Open shared parameters from the first header. For every other header reuse
   the SAME Local records, checking dependent domains in order; open all remaining
   indices with the same telescope/WHNF loop, ensure terminal Sort, and compare
   mutual result levels. Derive family descriptors with counts/templates.
2. Use a private provisional overlay, never publish raw headers as ordinary
   admitted dependencies. Check every constructor type. Consume the common
   parameters under the source-required policy, then traverse arbitrary remaining
   fields. Infer each domain universe, check its permitted result-level bound,
   check strict positivity and derive recursive descriptors before opening the
   field. Check the final owning family application, uniform parameters,
   universe levels and occurrence-free indices.
3. Strict positivity normalizes, calls a shared internal all-Expr current-family
   occurrence operation, rejects occurrences in Pi domains, opens its codomain
   with a fresh private Local, and loops. The terminal application validator
   walks the generic expression spine, matches a current family/level vector,
   exact shared parameter prefix, declared index count and occurrence-free index
   terms. Functional recursive arguments reuse the same telescope/spine loops;
   retain their prefix domains and abstract result indices. None of these results
   is an input bit or a host-produced answer.
4. Derive elimination/K permissions from the source rule; generate motives,
   minors, recursor types and reduction rules using shared context/open/fold/
   abstract/instantiate services. Rule argument positions/counts are derived
   data. Compare raw recursor claims with generated schemes rather than assume
   them. The full algorithm includes nested specialization's growing queue,
   copies of prior complete mutual blocks, restoration and rechecking. Publication
   is atomic only after the complete block and claims pass.
5. Generic iota/K/projection services consume checked derived descriptors and
   actual expression spines, using shared substitution and WHNF. Missing
   conversion/primitive services propagate GAP and cannot supply guessed answers.

Development spec already implements these block modules, including mutual/
indexed/functional recursion and nested restoration. It remains OFFLINE and
cannot supply native input answers. The weighted source driver now runs
the [private generic header phase](../../benchmarks/kernel-inductive-headers-stock/README.md)
then GAPs for missing constructor/generation/restoration stages; no header-only
analysis may turn that into ACCEPT.

Current weighted prerequisites: complete symbolic levels, all-Expr traversal/
substitution/scope/comparison, private checked environment, ordinary type/body
checking and general delta. [Shared telescope WHNF/dependent parameter reuse](../../benchmarks/kernel-dependent-telescope-stock/README.md)
is now lowered with exact stock operation evidence. The [current-family occurrence callback](../../benchmarks/kernel-internal-occurrence-stock/README.md)
is now composable and stock-validated: the earlier public OCCURS operation halts its whole top-level run on a
match and is therefore unsuitable as a positivity callback. The internal call
delimits its own private stack, returns a Boolean to its caller and retains
caller context windows on both early-match and full-traversal exits. Then lower
the family-application/positivity/recursive-descriptor callers above. This does
not change the complete block algorithm or select an easiest semantic class.

The next header-stage ABI uses output-only family161 `(indexCount,resultLevel,
rawFamilyRef)`, wrapped by scheme165 `(universeParams,INDUCTIVE_KIND,payload)`
and signature160 `(symbol,checkedHeaderType,scheme)`. These records are generated
ONLY after checking a header in the previous environment. A private linked list
collects them for duplicate checking and the subsequent provisional overlay.
Opening creates the shared parameter Locals; consuming reuses them for each
remaining family; opening indices derives counts, and context rolls back to the
shared parameter end after each family. The header list is separate from the
COMMITTED environment head and admitted-declaration count. Completing headers
must return to the block controller; until constructor/positivity/generation/
restoration checks are integrated that controller still reports GAP_INDUCTIVE.
A partial header list is never proof acceptance or an assumed public family.

Environment lookup will take an explicit private list head. Ordinary inference
passes the committed head; provisional constructor checking later passes the
source-staged overlay; header duplicate checks can search previous private
headers WITHOUT exposing them to header type inference. This removes accidental
ambient-environment mutation and preserves the source staging requirement.

Occurrence calls borrow a TEMPORARY symbol window at the current context end.
Weights copy the checked-header symbols into that window, leaving the live
Local-context length unchanged, save the caller's universe/count/window state,
run the composable occurrence service, then restore the caller state. The window
is rebuilt before each call. Subsequent fresh Local allocation may overwrite the
dead scratch symbols. Thus functional-prefix growth cannot overwrite a live
family set, and inference never mistakes family symbols for Local/type records.
The space check is physical `liveContext + familyCount <= capacity`, with no
field/parameter-count semantic classes or host-generated occurrence answers.

Current header implementation scope: family-symbol validation/duplicate checks,
raw universe scope/type checking in the previous environment, shared dependent
parameter reuse, generic index opening and result-universe comparison are
lowered. Generated recursor-name construction/validation and constructor-name
checks belong to the remaining source block staging; raw recursor names/claims
are not yet treated as checked results. The header output retains raw-family
references for those later checks. Neither a private header signature nor
header-phase completion is full inductive admission.

## New semantic-IR core modules (stock validation pending)

`family_occurrence_machine/rules` copies only current checked-header symbols
into a temporary window after live Locals, calls the existing composable
occurrence service and restores the caller's universe/window state. Its real
source continuation and live Local prefix survive early/no-match returns.

`formal_levels_machine/rules` generates an ordered Param-level vector IN WEIGHTS
from the validated universe-symbol window. Header analysis now retains that
private vector. `family_application_machine/rules` walks an arbitrary application
spine, validates current-family membership, derived total arity, exact Const
universe-vector syntax with the SAME vector/level comparator, uniform parameter
Locals with the SAME expression comparator and every index with shared family
occurrence. Returns a private family signature reference or0. Raw declarations
never supply those signatures or an application-validity answer.

Pinned is_valid_ind_app uses exact Const equality, not definitional level
equivalence. The earlier development spec's permissive level callback was
removed to match that source predicate; raw `max(u,0)` syntax differs from raw
`u` here. General conversion/normalization are distinct operations. The codec
preserves raw level DAG syntax; no host canonicalization answer is inserted.

`positivity_machine/rules` lowers the complete strict-positivity CORE loop:
weighted WHNF, shared occurrence, rejection of family occurrences in Pi domains,
shared single-binder opening and repetition, then the same family-application
predicate. It restores the caller's Local scope on semantic completion/failure.
Missing/wrong-arity delta targets are neutral in WHNF, as pinned is_delta; typed
constant inference still rejects unknown/wrong-arity constants.

These are general finite kernel operations. Unit contracts seed internal calls
AFTER real weighted header/Local derivation and compare every Boolean-IR state
with the development reference, plus independent source operations. They are
IR evidence ONLY until composed stock validation. Unit control-state setup is
not a production inference path. No supplied typing/admission/positivity answers
are packed or used by the production source loader.

The full-source pipeline must run nested specialization BEFORE core positivity,
and check constructor typing under the staged header environment. Raw original
blocks still stop GAP after headers. Do NOT connect original raw nested fields
directly to this core and report their core rejection as a Lean declaration
rejection; the missing prior transformation must remain an implementation gap.
Functional recursive descriptor generation, full nested lowering, recursor
generation/restoration and complete conversion/primitives remain unfinished.

Functional recursive-descriptor lowering uses two additional generic services.
Local-window abstraction copies UIDs from derived Local/type records into a dead
context window past the live end, invokes the SAME multi-Local abstraction, and
restores the caller's level/count/window state. A private counted-list reversal
builds immutable object-reference vectors. The descriptor loop normalizes, opens
arbitrary dependent Pi prefixes, abstracts each domain over preceding functional
Locals, validates the terminal current-family application, then abstracts its
indices over the complete functional prefix. Output-only166 references
`(familySignature,prefixVector,indexVector)`; prefix record167 holds
`(domain,binderInfo,0)`. Both vectors are generated in weights. A nonrecursive
argument returns0. Caller constructor Locals remain in scope; the later generic
recursor builder must abstract them before any declaration publication. This
operation alone is neither positivity nor admission and does not bypass nested
specialization/type checking.
