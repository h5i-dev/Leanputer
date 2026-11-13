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

## Shared semantic-IR core modules and composed stock evidence

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
with the development reference, plus independent source operations. They were
IR-only unit evidence at23ecc55/a3b1008. The [composed stock controller](../../benchmarks/kernel-typed-core-stock/README.md)
now runs the operations from raw syntax through typed constructor checking. Unit control-state setup is
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

The next typed CORE controller follows check_constructors/declare_constructors
as separate phases. Constructor type inference sees a provisional header overlay
ONLY after all headers have checked in the previous environment. Earlier
constructors must NOT become assumed types while checking later constructor
schemes. A separate private pending-name/metadata list detects duplicates and
retains each checked constructor's derived field-Local snapshots/recursive
descriptors; the typing overlay still contains only headers and the prior Γ.
Every field checks its inferred Sort universe, source result-level bound,
positivity and recursive descriptor before opening the next binder. The final
application must return the owning family with uniform parameters and valid
indices. Counts drive all loops. All constructors must pass before later
constructor declaration/recursor generation. Private field snapshots are kernel
derivations, never raw assumptions; the final recursor type/rule generator must
abstract all their Locals before publication.

A CORE-operation entry will invoke this pipeline on raw core declarations and
report missing recursor generation as GAP. It is a kernel-function API, not a
claim that original nested declarations have been transformed or checked. The
production original-source entry remains GAP before missing nested staging.
No supplied "nested checked"/typing/admission flag is accepted from raw syntax;
operation selection is a fixed loader/controller entry, as with other kernel
operation APIs. No proof target may be accepted by this diagnostic core entry.

Current typed core controller: `constructor_machine/rules` follows all families/
constructors/fields with count-driven traversal, provisional HEADER-only typing
and a separate pending-name registry. Record168 holds pending ctor symbol/type/
analysis;169 holds a derived Local record/recursive descriptor/field ordinal;
170 retains family/field-vector/result arguments. All are output-only private
metadata. Header list prefixes share the prior Γ tail; `header_seen` delimits
current families for occurrence. Constant inference selects the scoped typing
head; committed Γ remains separate. No pending ctor can type a later ctor.

`core_transition` selects the typed core operation with pure syntax input and an
inert rejecting axiom sentinel, never a proof target. The original-source entry
cannot set that entry flag from JSON; it remains GAP before missing nested
staging. After constructor checks the current core controller privately declares
constructors and derives elimination/K metadata, then GAPs before recursor
generation and type-claim checks. The historical stock report below predates
the name, constructor-declaration and elimination/K stages.
The [stock2 evidence](../../benchmarks/kernel-typed-core-stock/README.md) derives
ALL private state from raw syntax in normal forward/cache; no native metadata
seeding or external checking. Generated recursor names/claims remain untrusted.

Recursor-name checking uses the pinned mk_rec_name rule `I + name("rec")`.
Family/candidate names are raw structured-name DATA, not a lookup catalog. A
shared name-path lookup traverses the symbol table, then a count-driven prefix
comparison uses the SAME byte/limb vector comparator for string/numeral segments
and checks the final string segment's bytes. A raw recursor symbol can be reused
only AFTER that relation and declaration-name uniqueness pass. Its supplied type
remains a claim compared against the GENERATED recursor scheme. The raw block
format already carries the recursor-name claim; no host expected-name/type
answer is inserted. Generic fresh-name interning for nested specialization is
still a separate subsequent operation.

Private constructor declaration walks verified family/name records and each
ORIGINAL raw constructor vector, deriving source ctor ordinals by a counter.
It looks up the fully checked pending ctor record, verifies its owner/type
association, then creates constructor162 `(familySignature,fieldVector,ordinal)`,
scheme165 `(universeParams,CTOR_KIND,constructorInfo)` and signature160. Only
now may these constructor types enter the PRIVATE typing head. Committed Γ and
raw input cursor stay unchanged until all generation/restoration is complete.
Result arguments/typed field snapshots remain in pending analysis for the
recursor builder; none are input-derived checking answers.

Elimination/K follows `inductive.cpp:475–570` in the pinned source. The complete
decision first uses necessarily-nonzero on the result universe; otherwise mutual
predicates and predicates with multiple constructors eliminate only to Prop,
empty predicates eliminate to any universe, and a singleton constructor loops
over **all** fields. Each field must either have a type in Prop or be directly
one of the constructor result application's arguments. Nested occurrence inside
an index does not satisfy direct equality. K applies exactly to a single
predicate family with one constructor and no fields. These are source semantic
conditions, not support limits on family/constructor/field counts. Header,
field-universe and K `is_zero` checks use the source's **raw level tag**;
normalization/equivalence to zero is a different kernel operation.

`elimination_machine/rules` restores the internally derived field Local records
one by one before inferring dependent field domains under the private checked
environment. No supplied universe/Prop/K classification enters inference. A
generic search chooses a fresh nonzero universe-symbol identity outside the
old parameter set. This alpha-renames Lean's fresh `u`, `u1`, … binder; generated
recursor types/claims must compare universe binders by substitution, not by the
spelling chosen for that binder. The weighted transition shifts the live
universe/parameter scope right once, preserving the derived Local identities,
and prepends the fresh symbol to the recursor universe vector, as
`get_rec_lparams` does. Immutable family/constructor schemes keep their original
universe lists. Output172 contains `(elimLevel,recursorUniverseVector,Kflag)`.
Heap/context/fuel exhaustion is RESOURCE, not a restricted semantic class.

The following generation stages are still required: rebuild all family index
telescopes; form each motive over its indices and major; traverse all constructor
fields to form minors and functional induction hypotheses; collect motives and
minors in declaration order; generate each recursor's closed type and rules with
the shared telescope abstraction/substitution services; check raw type claims
against generated schemes. Nested transformation/restoration must surround the
core stages before an original declaration can be published. The standalone
core-operation entry remains diagnostic and cannot accept a theorem.
