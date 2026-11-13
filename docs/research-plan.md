# Research tool work plan

The primary runtime is a standalone, compiler-generated stock
Qwen3_5ForCausalLM with native GatedDeltaNet cache and identity hidden feedback.
No pretrained backbone, custom forward, CPU emulator or inference-time external
checker is used. The sparse circuit/attention-RAM engine remains a reference.
Research quality and formal soundness remain goals, not established labels.

| Slice | Current evidence / remaining work |
| --- | --- |
| Dependent calculus | Ground sorts/Prop, Pi/Lam/App/let, capture avoidance, beta/delta/zeta, typed eta and proof irrelevance; all environment types/values checked |
| Native compilation | Stock RMSNorm/SwiGLU/GDN/forward/cache; generated BF16 weights, tested bounded binary domain; broad numerical correspondence still pending |
| Layout | Matched downsizing completed:4.021B→668.6Mparameters, same capacities/fuel/outcomes; GPUforward372.825→315.196s, far from efficient |
| Fixed kernel constructs | False, True, And/Iff, Eq/HEq, Nonempty/Exists/Or, Quot primitives, Decidable, Subtype, Bool, Option, Zero/One, bounded Nat, OfNat and PUnit; selected targeted native checks |
| One-field record slice | Inhabited/Mul/Add/Subsingleton:103phases/58intrinsics; weighted20cases16A4R; native12cases9A3R including a new source proof; targeted Lean agrees |
| Bounded Nat | Raw literal/constructor/recursor paths:109phases/68intrinsics, native13cases9A3R1numeric-resource; ordinary OfNat still separate |
| Real Lean input | Syntax-only Expr export, full supported dependency closure, explicit genuine axioms, opaque bodies checked, independent kernel replay |
| Mathlib denominator | Same857public source theorems/four modules/pin, one ground instance each. Latest112phase syntax refresh408EXPORTED449UNSUPPORTED; not408proofs. Complete native population NOT_RUN |
| Evaluation | Old custom-backend834case differential and61test checkpoint passed; latest native features have targeted checks. Broad native/differential campaign explicitly deferred |
| Release tooling | CLI, reference artifact fingerprints, stock model serialization prototype, CI and compact evidence. Full research release criteria incomplete |

The one-field native checkpoint passed all12cases9A3R, matching planned steps,
including actual Function.injective_of_subsingleton(2643steps/three checked
dependencies/noaxioms). The independent Option source Function.IsPartialInv.eq
also accepted4930steps/three checked dependencies/noaxioms. These are selected
source judgments, not a new full-population coverage fraction. Preserve exact
input/config/model measurements; full native checking of857rows is unrun.

OfNat now passes native12cases9A3R, including ordinary numerals with their two
checked instance definitions and an independent label3/value5 instance. PUnit now passes native13cases11A2R, preserving its Prop0/data distinction.
Bool.involutive_not only plans at43989steps/3407nodes; a larger native run is
impractical without further resource work. Pause feature expansion at this
safe checkpoint for a minimum bank-layout reduction with a matched small Eq
comparison and unchanged feature set/capacities/stock forward/cache. Nat.succ_injective only plans at~25ksteps/~2.8knodes and has
not been checked natively. Other remaining first blockers:
Monoid/AddMonoid require multiple-field/inherited records; several Mul/Add
closures now expose cancellation-property classes. General recursive/indexed
inductives and Nat need separate rules. Fixed catalog support is not arbitrary
input declaration admission. Symbolic universes remain unsupported.

Stock fallback latency and eager allocation/environment rechecking are material
limits: an individual small native source proof can take minutes. After a safe
feature checkpoint, any required efficiency work must preserve stock architecture,
full semantics, capacities and trust boundaries, with a matched small comparison.
Do not replace checking with cached host answers or erase dependencies. The
completed layout campaign is documented separately; avoid indefinite tuning.

A full proof-coverage fraction requires one frozen native compiler/configuration
and outcomes for all857rows, retaining unsupported/resource categories and
cold/steady boundaries. Syntax export counts and independent spec plans cannot
satisfy that criterion. Schedule that broader validation only after the user's
feature-first phase; do not rerun large campaigns after every feature.

Formal typing/compiler/floating-point soundness is not proved. Limited gate and
mask lemmas and differential traces are evidence only. Integration with a base
LLM and full Demo A remain separate, last/optional work.

The notes below are historical checkpoint records, not current pending states.

Primary provenance (accessed 2026-11-12):

- [Qwenputer](https://github.com/divagr18/qwenputer): the repository describes a
  compiled RISC-V design using Gated DeltaNet memory and eleven inserted layers.
  That architecture motivates explicit accounting of memory and repeated
  execution; Leanputer is not implementing its CPU or downloading Qwen weights.
- [nanoda_lib](https://github.com/ammkrn/nanoda_lib): independent Rust Lean kernel
  used for algorithmic comparison and planned differential reference, not a
  source-to-weights translation. The exact checkout revision is recorded in run
  logs before integration.
- [Lean universes](https://lean-lang.org/doc/reference/latest/The-Type-System/Universes/):
  ground sorts are noncumulative, Sort 0 is Prop, and Pi uses impredicative Prop
  and maximum levels otherwise. Symbolic universe expressions and parameters
  need explicit handling or unsupported outcomes.
- [lean4export](https://github.com/leanprover/lean4export): existing elaborated
  environment export interface to inspect for compatible preparation tooling.

Initial supported-calculus target: ground numeric universe levels, de Bruijn
variables, Pi, annotated Lam, App, and acyclic monomorphic environment constants.
First conversion uses beta/delta structural comparison; eta and proof irrelevance
need separate rules or explicitly restricted coverage. Passing a restricted
checker is meaningful only with a precise correspondence to Lean judgments.

Checkpoint 1 evidence: addressed attention passes all positions at capacities
2–256 on CPU/CUDA; 4-bit arithmetic is exhaustive. All 32 explicit operational
phases have full-state matching weighted traces, including environment, beta,
delta, capture-avoiding shift/substitution and resource/invalid inputs. Five
limited integer/Boolean lemmas compile in Lean without axioms. Full suite is
being run before committing; a public canonical runner, Lean ingestion,
conversion coverage, corpus and systematic evaluation are still required.

Checkpoint 2 progress: public fixed-budget runner and weighted initialization
prevent forged terminal/control/mutable-state inputs. Elaborated Lean Export
traversal retains beta/delta work and complete supported dependencies. Six
source judgments and four post-export mutations agree across weighted,
operational, recursive and actual Lean kernel checks; sampled nanoda replay also
agrees. Batch JSON reports, compiler-fingerprinted artifacts and CLI are tested.
Current gaps: eta/proof irrelevance/opaque constants, larger real corpus, fuzz
minimization, systematic scaling measurements and broader formal invariants.

Conversion extension: 49 phases now implement contextual Pi/Lam comparison,
proof irrelevance via inferred proposition typing, and typed eta expansion with
weighted lifting/allocation. Opaque bodies are checked and remain opaque. New
positive/negative cases agree with actual Lean and nanoda. A real elaborated eta
type needs 617 steps and therefore legitimately exhausts a 512-step checker;
resource outcomes must remain separate in evaluation. Next architecture work
will measure/factor memory writes and parallelize address arithmetic, preserving
exact traces; then run the broader corpus/fuzz/scaling program.

Optimized lowering validation: full suite 48 tests passed in 69.667s. Same
49-phase semantics and state ABI, with reference lowering retained. At 128
cells, constant folding, parallel borrow/carry, liveness and bank-write factoring
reduce shared stages 92 -> 41 and buffer bytes 8,882,256 -> 2,101,556. These
static reductions are measured; end-to-end performance still needs controlled
corpus evaluation and CPU/GPU/reference comparisons.

User priority update: pinned real-mathlib theorem coverage and checking speed
are now primary evaluation axes. Enumerate an explicit selected population before
feature filtering; retain all export/encoding/unsupported/resource/reject counts.
Report source theorem counts separately from repeated ground instantiations.
Dependency-closed checking is the primary mode; any trusted-library experiment
must name its entire unchecked basis and remain a separate result. Report cold
export/encoding/compilation/initialization/check costs, steady reused-weight
model costs and amortized environment costs. A zero-accept mathlib sample must
be published honestly and used to prioritize missing features, not filtered out.
Discovery of actual pinned mathlib/toolchain/cache availability is underway.

Mathlib sampling protocol is now concrete: pin mathlib v4.31.0 commit
fabf563a7c95a166b8d7b6efca11c8b4dc9d911f / Lean 4.31.0. Owner modules are
Mathlib.Logic.Basic, Mathlib.Logic.Function.Basic, Mathlib.Algebra.Group.Defs,
and Mathlib.Data.Nat.Basic. Enumerated 1,033 original theorem declarations,
857 public noninternal/nonprivate declarations, all with bodies available.
Choose 200 by lowest SHA256("814732/module/name"), before inspecting/filtering
expressions, with one all-ones universe specialization per source theorem.
Publish population/selection manifests and all 200 outcomes. These figures
concern this four-module population/sample only, not all of mathlib.

## Current user priority: feature expansion and architecture assessment

Broad corpus repetition/profiling is deferred after the 834-case foundation.
The unsupported full population's first blockers include Eq130, Decidable109,
Iff41 (+Iff.intro22), Exists35, False15 and And14. These are first failures, not
complete closure requirements. Current implementation work order:

1. Empty proposition False and dependent empty eliminator: fixed primitive
   typing rules, no invented axiom assumptions, syntax-only export and actual
   kernel replay. Target `Function.mt` from the measured unsupported population.
2. Nonrecursive singleton Prop structures Iff/And, constructors, native
   projections and appropriate eliminator typing/reduction.
3. Equality with refl and dependent elimination, then other measured blockers.

Each slice needs targeted positive/negative/full-state tests and a small real
mathlib smoke, then commit/push; full expensive campaigns wait for substantial
checkpoints. The semantic machine/IR must survive backend replacement.

The current sparse circuit plus custom attention/RAM updates is **not a standard
Transformer architecture**. A matched dense ReLU lowering prototype and concrete
standard recurrent-block assessment are required, without asserting unchanged
compatibility with normalization, SwiGLU or optimized attention. Custom delta
memory is nonstandard. Existing fixed schedule wasted95.54%of corpus item-steps
on absorption; mathlib large budget wasted69.66%. GPU placement or100%device
utilization does not establish efficiency. Architecture assessment accompanies
feature work; it does not replace expanding supported judgments.

## Authoritative execution order (latest user instruction)

1. Compile the actual checker into a SMALL existing Transformer and use stock
   forward; no full pretrained backbone. Initial complete bounded STLC native
   Qwen3.5 path is implemented and smoke-tested; dependent native DeltaNet RAM
   migration is next. See native-backend.md for actual sizes and scope.
2. Expand constructs on that native backend to improve pinned-mathlib coverage.
3. Run broad differential testing/evaluation only after architecture migration
   and intended feature expansion. During implementation use minimal smokes.

This order supersedes prior feature-first/profiling campaign notes. No further
broad corpus, profiling or plotting runs are active. The semantic specification
is retained; the old custom sparse engine is a reference, not the final claimed
architecture. Stock normalization/activation/cache compatibility must be tested,
not replaced or renamed. Full Qwen natural-language integration remains optional.

Native architecture checkpoint d3a146d compiles the shared machine into stock
Qwen3.5 GatedDeltaNet cache/SwiGLU with CPU/CUDA identity/unbound smokes. Native
BAll.imp_left also accepts in a banked256-cell configuration. False/False.rec
are now implemented as intrinsic rules plus weighted type-schema construction;
new real source Function.mt accepts through stock native forward (802steps),
alongside a universe1eliminator and a wrong-claim rejection. Only the15old
False-first blockers were re-exported;14still expose Eq/Iff/Exists/Decidable.
No new full857coverage result or broad differential campaign is claimed.
Next implement Iff/And constructors, native projections and eliminators on this
existing native lowering, then equality. Compiler residual liveness/dense-zero
parameter overhead remains substantial and must not be called efficient.

Iff/And checkpoint: fixed positive families/constructors and field projections
implemented through real export,60-phase spec/compiled/native execution. Stock
GPU Imp.swap accepts1232steps, Iff.mp/And.left fixtures accept, wrong-family
projection rejects. Twelveof77old blockers now syntax-export; only Imp.swap
new real theorem was checked natively in this slice. GeneralIff.rec/And.rec
are not supported yet. Next actual priority is Eq family/refl/dependent recursor.
User explicitly approved feature-first; record model memory/time and fix sizing
only when it blocks continued development. Compression/profiling/broadvalidation
remain deferred. No graph unit-budget compression was applied.

Eq family/refl/dependent recursor is implemented through syntax export,
66-phase IR and fixed intrinsic schemas. Ground universe pairs are preserved
in typing/conversion. Targeted weighted and actual Lean tests cover unequal
recursor universe parameters, typed K conversion under an explicit equality
hypothesis, and rejection of reflexivity at unequal endpoints. The native
source/K/negative check is recorded in native-backend.md after completion.
Next measured syntax blocker is let (16first failures in the old Eq130subset):
preserve annotation/value/body and perform checking plus zeta in weights.
No corpus-wide rerun or model compression campaign is scheduled in this phase.


Let74-phase implementation now preserves annotation/value/body, validates the
annotation and value even if unused, performs zeta substitution inside weights,
and traverses its binder in shift/substitution. Targeted weighted5cases and
actual Lean agree. Two previously let-blocked mathlib closures now export but
exhaust2048heap in planning; no proof acceptance claim for them. True/True.intro
also implemented, with a small real source native smoke recorded separately.
Next expand fixed nonrecursive positive families and recursors (True, And/Iff,
Nonempty, Exists, Or), guided by recorded unsupported closures. No arbitrary
user inductive declaration admission or new unchecked-axiom substitution.


Latest user override: downsize native compiler layout now, preserving Eq and
the implemented let/True boundary. Matched baseline: benchmarks/native/let-true-
input.jsonl and let-true-config.json,81layers/H13312/inter1024/4.021B BF16
parameters;3A1R2U, including new source iff_mpr_iff_true_intro. First concrete
compiler issue: full FFNs leave no handover units, so dead residual channels
cannot be reused and global dense width grows. Reserve handover capacity,
measure slot/layer/weight cost and run exactly the same few cases. Other
positive recursor work is preserved but paused. Resume features after a
material sustainable reduction; broad validation remains deferred.


Downsizing main matched result passed:3A1R2Uidenticalwithsame74-phasefeature
set/capacities/fuel. Factored data selection + affine NOT + reserved handover
units reduce4.021B→668.6Mparameters(6.013x),hidden13312→2560,layers81→70.
GPUforward372.825→315.196s(only1.183x); high-throughput execution remains
unsolved. Eq retention and small matched CPU/GPU fixtures finish the targeted
checkpoint, then resume preserved positive-construct work. No broad campaign.


After downsizing checkpoint 9c66c72, positive-construct expansion resumes on
compact stock layers. Nonempty/Exists/Or with dependent Prop elimination and
True/And/Iff recursors are implemented in an 81-phase IR. Six exported recursor
types plus five iota and two negative cases pass targeted weighted checking.
A prototype neutral And/Iff data reduction failed an actual Lean check and was
removed before checkpoint; the retained constructor-only rules match that
boundary. Native smoke is two small new mathlib proofs plus relative feature
fixtures; 37/80 syntax re-exports are candidates only. Subsequent Quot support
is under design because it blocks funext/let-dependent closures; Quot.sound
must remain a genuine explicitly reported axiom dependency, not a fabricated
replacement. Broader differential/coverage evaluation remains deferred.

Positive checkpoint native10cases passed8A2R:two new actual mathlib judgments
BEx.intro@[1]/exists_apply_eq@[1,1],both noaxioms;relativecases preserve
explicitassumptions. Model802.35M BF16params/H3072/70layers,318.306s for
3074forwards at512heap. Full native857coverage stillunmeasured. Nextfixed
quotientprimitives are chosen to unlock funext-dependent closures; no broader
differential campaign or renewed layout tuning is planned now.


Fixed Quot/Mk/Ind/Lift now share the existing 81-phase recursor framework.
Ground universe order is checked against actual Lean aliases, including
Quot.lift.{0,1}/{1,0}. Targeted weighted tests reject invalid respectfulness,
neutral-quotient reduction and large Ind elimination. Thirteen of 23 current
Quot-first blockers now syntax-export; no new native mathlib acceptance claim
for this slice. Full funext dependency closure planning takes ~41k transitions
and ~6.5k nodes for two source theorems, exceeding current small native smoke
budgets. Keep those resource costs visible. Next constructive Decidable slice
uses its two constructors and dependent data recursor, chosen from 109 original
first blockers; broad verification/evaluation remains deferred.


Decidable family/isFalse/isTrue/dependent recursor now uses the same 81-phase
native framework. Two data branches and neutral/bad-evidence rejection pass
native stock forward at heap256/fuel1536. Actual Lean replay required its closed
Not definition when rebuilding the standard inductive type; this is checked,
not an axiom. Of133current Decidable-first blockers,29syntax-export. One real
source Decidable.or_not_of_imp is running at heap1024/fuel5504 against a5390step
plan; no broad theorem replay. The earlier ~41kfunext closures remain outside
this targeted budget. Next subtype projections/constructor semantics are under
assessment from the remaining blockers, with current feature work preserved.


Subtype milestone:91semantic phases, fixed data family universe floor,
dependent projections, constructor reduction and typed record/recursor eta.
Native11case9A2Rmatchesweighted/Lean, model671.2MBF16params at256heap. Of95
currentfirstSubtypeblockers11syntax-export;two inspected classicalclosures
need~20ksteps/~3knodes andexplicitClassical.choice,notnativeacceptedcounts.
Next core feature candidate HEq is measured among14oldEq-subsetblockers.
Broader validation remains deferred; high eager substitution/environment cost
and nativefallbacklatency remain concrete research limitations.

HEq fixed family/refl/rec now has explicit carrier+value K checks, seven-arg
spines and per-head arity guards(98phases). Weighted seven cases and actual
Lean agree on K/iota and rejection when either index differs. Native small
check active. Complete syntax refresh retains all857names:236EXPORTED,
621UNSUPPORTED; not236proved. Bool is now largest first blocker(142), so it
supersedes generic-record work as the next coherent feature slice. Preserve
exact source/trust/resource boundaries. No broad expensive differential run
has occurred in this syntax refresh.

Bool checkpoint:42fixed primitives/99phases, both nullary branches and neutral
major boundary pass native8case6A2R. Same full857syntax denominator now362
EXPORTED/495UNSUPPORTED; no full-population native proof result. Complete
assumption/dependency/node metadata and unknown unsupported closures retained.
The largest remaining first blockers are Monoid32/AddMonoid31/Mul29/Add29;
Inhabited18 and Option/Prod are smaller coherent next data slices. New Bool
classical closures have at least72dependencies, so native resource costs are
material. Keep broad differential/profiling deferred; choose the next slice
from actual closure structure rather than counting syntax export as proof.

Option100phase milestone adds Type-universe successors and zero/one-field
constructor-dependent elimination. Targeted weighted/native11case8A3R and
actualLean agree. Of12Option-first blockers4now syntax-export; one new actual
Function.IsPartialInv.eq proof is undergoing native checking at1024heap/f4992
against4930planned steps/three checked dependencies, not an acceptance yet.
Next assess a reusable fixed one-field record slice (Inhabited, Subsingleton,
Mul/Add), preserving typed data eta versus Prop constructor-only elimination.
No arbitrary user inductive admission or unchecked dependency assumptions.
