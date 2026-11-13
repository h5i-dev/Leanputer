# Research tool work plan

Baseline: commit 0fd6b5e. Research quality is an evaluation target, not a claim.
The baseline STLC circuit remains a comparison implementation.

| Slice | Measurable acceptance criterion | State |
| --- | --- | --- |
| Shared execution substrate | Fixed FFNs, actual attention reads/writes, exhaustive bounded-address checks, exact CPU/CUDA, shared weights | Implemented/tested; backend numerical assumptions remain |
| Dependent operational specification | Explicit heap/context/continuations, dependent lambda-Pi, capture avoidance, beta/delta/eta/proof irrelevance, ground Prop/universe rules and bounds | Implemented; expanded to60phases with proposition structures |
| Compiled semantic transitions | Every phase matched by fixed weights, no host semantic work, adversarial/resource traces | Implemented/tested, no complete formal proof |
| Real Lean input | Elaborated Expr, complete supported dependency closure, explicit unsupported, independent actual kernel replay | Implemented, quoted-name and unavailable-body boundary tests |
| Corpus and evaluation | Real/generated/mutated/fuzz cases, reproducible reports, CPU/CUDA, trace mismatch minimization | Harness implemented; larger controlled runs in progress |
| Mathlib coverage and speed | Pinned prefilter population, all rows retained, source/instance distinction, closure and cold/steady costs | 857-name population measured: 4 accepted/853 unsupported at large budget; repeated timings pending |
| Scaling and trust | A10G/CPU measurements vs baseline/reference, memory/depth/steps/time, trust table/core lemmas | Core lemmas and tests implemented; controlled scaling in progress |
| Research release | Schemas, artifact compatibility, batch CLI/CI, exact reproducibility and explicit gaps | Usable checkpoint; research requirements still incomplete |

Each validated coherent slice is committed and pushed, followed immediately by
implementation of the next slice. Tests alone do not establish soundness.

Current architecture: syntax heap and mutable continuation/context banks,
binary-address attention queries with fixed positional keys, saturated float32
softmax, compiled Boolean register-control FFNs, and optional gated rank-one
attention writes. The same modules are reused each step. This trades the
baseline's many distinct layers for sequential execution. Report all logical
stages and applied/semantic steps; no claim of fewer than eleven layers.

Current measured gaps and next acceptance criteria:

| Gap | Evidence / next checkpoint |
| --- | --- |
| Inductives/constructors/recursors/quotients | 853/857 selected mathlib theorems unsupported; first failures dominated by these dependencies. Add a reviewed declaration/eliminator specification and invalid-declaration cases before advertising support. Never replace them by unchecked axioms. |
| Symbolic universes | Only one ground instance/name tested; no universal theorem coverage claim. Symbolic level equivalence/constraints need separate semantics. |
| Fresh allocation / fixed fuel overhead | Largest accepted instance takes 12,332 steps and 1,620 allocations; the batch runs 16,385 steps for every item. Investigate syntax interning/reusable conversion work without host semantic assistance. |
| Controlled evidence | Run real-population repeat timings and mixed corpus, preserve complete denominator and negative results. Add capacity/batch/device ablation with raw samples and peak memory. |
| Formal assurance | Limited gate/mask/absorption lemmas exist; compiler, attention floating behavior and dependent typing soundness remain unproved. Tests are differential evidence. |
| Qwen integration | Not implemented; standalone checker correctness/coverage/performance take priority. No base weights needed. |

See [mathlib evaluation](mathlib-evaluation.md) for pins, exact reproduction,
source population, supported theorem names, budget tradeoff and trust boundary.
Historical checkpoint notes below record development, not current pending states.

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
