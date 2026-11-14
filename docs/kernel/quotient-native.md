# Genuine quotient primitive transaction and reduction

Authority: pinned `quot.cpp:check_eq_type, environment::add_quot`,
`quot.h:quot_reduce_rec`, `type_checker.cpp:reduce_recursor`, and
`Lean/Environment.lean:lean_environment_add`. Source hashes in `sources.json`.
This is the finite kernel quotient interface; ordinary inductives, constructor
names, parameters, fields and universe schemes remain checked data.

The original-source `quot_primitive` rows export claims about an `init_quot`
command. The first such claim runs the actual initializer in weights. Later
claims validate against the initialized bindings without republishing. No raw
row can set the initialized flag, insert a signature, or dispatch an internal
initialization/reduction task.

The weighted initializer interns canonical primitive names from bytes, looks
up the checked ordinary `Eq` inductive, requires its one universe and actual
sole constructor, and structurally compares both types as specified by
`check_eq_type`. The constructor is not required to have the library spelling
`Eq.refl`; nor is there a separate hardcoded Eq parameter-count rule. It builds
`Quot`, `Quot.mk`, `Quot.lift`, and `Quot.ind` types from fixed kernel syntax,
using checked scheme symbols as data. Their types are never supplied by the
exported claims. The initializer replaces existing bindings, as pinned
Kernel.Environment.add inserts map entries without rechecking the old dependency
prefix. The weighted Γ is a persistent map: newest signatures shadow historical
entries, and the public counter counts distinct names. No whole-prefix rewrite
or external rechecking step is invented. All five Nat/Bool/String binding cache
flags clear before the new private overlay is used.

Original-block origins remain historical immutable provenance. The nested
condition first checks that the CURRENT Γ signature is still an inductive;
a former family shadowed by a primitive cannot select an old container block.
Whole prior-mutual copying reads CURRENT family/constructor types and formal
universe vectors before specializing. Ordinary names/counts stay data.
If a surviving mutual family requires copying a group whose other member was
replaced, the pinned code asserts that all members remain inductives. This
metadata boundary remains an explicit GAP_PRIMITIVE; it is not silently copied
from stale raw declarations or described as full replacement coverage.

Repeated claims after actual initialization remain idempotent. All generated
bindings and the initialized flag publish together
after the current claim's name/interface, universe uniqueness/arity, scope,
type Sort and universe-specialized conversion checks. Failure preserves the
public environment, origins, raw cursor and initialized flag. Physical words
below ten bits report RESOURCE INDEX for this controller's program counter;
no control state is truncated into another instruction.

The reentrant reducer implements `quot.h`: lift major index5, ind index4,
function index3, enough arguments, WHNF major, exact three-argument `Quot.mk`,
then function applied to its payload followed by surplus arguments. Immutable
call frames preserve the original spine across recursive major reduction.
The existing WHNF pending-application bridge resumes beta/delta reduction after
consuming a successful application once. The checked primitive scheme and
initialization flag authorize this route. Partial and neutral expressions
remain neutral. No external code or host reduction runs at inference.

Independent executable SPEC constructs the declarations using locals and
abstraction, separately from the compiler's fixed de Bruijn syntax builder.
`test_kernel_quotient_source.py` admits original Eq source with a deliberately
renamed sole constructor, validates all four raw claims, compares every public
signature/rule against that independent SPEC, and checks direct/nested lift
computation in original source theorem conversion. Initial identity/direct
lift/nested lift runs DONE16277/21423/30890steps, heap1991/2414/3035includingnull.
An ind source definition also checks, followed by explicit runtime WHNF under
that source-admitted environment: ind plus surplus beta DONE155steps. The
source admission of this last definition alone does not require its value to
normalize. The extra runtime check is reported separately.
Four-source integration PASS1test73.714s,372selected Boolean transitions compare
ALL registers and banks. These are selected IR checks, not all execution steps,
not STOCK quotient evidence and not the small-model goal. Invalid binding/type/
arity/later claim and allocator-exhaustion tests preserve the committed prefix;
allocator failure is explicitly injected at the source transaction boundary.
The final combined regression is recorded in the checkpoint evidence log.

Subsequent [Nat](nat-arithmetic-plan.md) and [String](string-native.md) controllers
connect literal operations and primitive-aware canonical-form negatives. Their
explicit helper/physical limits and partially replaced mutual-group boundary remain. The pinned 10.35B original-source STOCK smoke predates
this code and does not satisfy the requested SMALL stock-transformer target.

Final checkpoint regressions PASS5tests284.526s (ordinary source, typed
conversion, existing recursor WHNF, nested transaction/atomicity). Failure-path
checks PASS1test15.774s, including5selected final Boolean transitions.
[Raw logs](../../benchmarks/kernel-quotient-ir/README.md) preserve exact scope.
The syntax exporter now includes Eq's original block as init_quot's implicit
source dependency even if the selected Quot type does not explicitly mention it.
A fresh pinned syntax export of `Quot.inductionOn` also passes independent SPEC
and whole-source transition reference, DONE16995steps/1994heap/7public signatures,
no assumptions. Every public scheme/RHS matches. Raw export and log are archived;
this additional exported case has no new selected Boolean or STOCK measurement.

## Current-map replacement checkpoint

Five original-source cases plus the ABI condition regression pass2tests176.848s,
369SELECTED all-state Boolean transitions in the source cases. Simple replacement
DONE18252steps/2233heap/8public signatures. Replacement followed by the full
original nested mutual-container transaction DONE208879/18129/20public and four
original origins, independently matching every public scheme/recursor RHS with
no assumptions. A bad replacement claim INVALID TYPE_MISMATCH preserves its
six-signature prefix. A former family head rejects an invalid recursive
occurrence through the current primitive (INVALID_INDUCTIVE_APPLICATION), with
no stale specialization map. A partially shadowed mutual group explicitly GAPs
while retaining11public signatures/two origins and the raw cursor.

A separate mixed source first performs String/Nat literal computation and
validates its helpers, then initializes Quot over old bindings. All four live
Nat/String flags change from1to0, with the untouched Bool flag0; one selected
Boolean transition compares ALL state at this boundary. The complete source
then DONE65570steps/6666heap/26public, every scheme/RHS independently matching,
no assumptions (PASS1test13.733s). This cache state is model-generated by checking
previous source, not a raw flag certificate. No Quot/combined-source STOCK run,
small model or full Boolean execution is claimed.

Coupled validation passes4tests176.589s: existing Quot initialization/runtime and
failure atomicity, original nested-source atomicity, and restored-owner K/structure
major preparation (372+130SELECTED transitions plus five terminal comparisons).
CLI2tests pass. Raw evidence: benchmarks/kernel-quotient-replacement-ir.
