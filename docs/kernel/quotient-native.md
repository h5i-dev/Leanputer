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
exported claims. The pinned kernel's insertion replaces existing bindings. Such replacement can
invalidate earlier original-block provenance and dependent declarations. The
current implementation explicitly GAPs if initialization would overwrite an
ordinary committed binding; whole-prefix invalidation/rechecking is unfinished.
Repeated claims after actual initialization remain idempotent. The private
overlay counts the newly added primitive names. All generated bindings and the initialization flag publish together
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
explicit helper/bootstrap/physical limits and Quot replacement boundary remain. The pinned 10.35B original-source STOCK smoke predates
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
