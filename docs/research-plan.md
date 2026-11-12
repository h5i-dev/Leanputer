# Research tool work plan

Baseline: commit 0fd6b5e. Research quality is an evaluation target, not a claim.
The baseline STLC circuit remains a comparison implementation.

| Slice | Measurable acceptance criterion | State |
| --- | --- | --- |
| Shared execution substrate | Fixed FFNs and actual attention reads; exhaustive bounded-address reads; exact CPU/CUDA; state updates in weights; shared module identities across steps | Implementing |
| Dependent operational specification | Explicit heap/context/continuations; Sort/Var/Pi/Lam/App; beta conversion; shift/substitution; ground Lean universe rules; absorbing failures and explicit bounds; independent recursive differential oracle | Implementing |
| Compiled semantic transitions | Every specification transition matched by fixed weights; no host semantic operations; resource boundaries and adversarial traces | Pending |
| Real Lean input | Export elaborated Expr and complete supported dependencies; no pre-normalization or checker answers; unsupported features explicit; judgments compared against Lean | Pending |
| Corpus and evaluation | Real/generated/mutated/dependent/conversion/resource cases; reproducible JSON reports; CPU/CUDA, exhaustive/fuzz tests and trace minimization | Pending |
| Scaling and trust | A10G and CPU measurements vs baseline/reference; weights/memory/depth/steps/time; trusted-component table; machine-checkable core lemmas | Pending |
| Research release | Documented schemas, versioned artifacts, batch CLI, CI, exact reproducibility and gap table; reviewed checkpoint commits | Pending |

Each validated coherent slice is committed and pushed, followed immediately by
implementation of the next slice. Tests alone do not establish soundness.

Architecture under investigation: immutable AST and mutable continuation/context
memory tables, binary-address queries, fixed positional keys, saturated float32
softmax attention, and compiled Boolean FFNs for control and masked writes. The
same modules are reused on every step. This trades the baseline's many distinct
layers for sequential execution; total steps and memory must be measured.
Saturated softmax exactness is a platform-tested floating-point property, not an
identity over real arithmetic. Invalid addresses must never access unchecked
memory or produce acceptance.

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
