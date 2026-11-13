# Extended differential corpus result

At checkpoint 8883252's weight semantics, the CUDA attention-write engine checked
834 selected judgments with a 256-cell heap, 32 continuations/context entries,
16 constants, maximum sort level 4 and fuel 2,048. Batches have up to 32 items;
all 2,049 fixed transitions execute for each encoded item. The deterministic
seed is 814732. Corpus SHA256 and full machine/compiler provenance are retained
in the compact benchmark summary.

| Family | Selected | ACCEPT | REJECT | RESOURCE | UNSUPPORTED |
| --- | ---: | ---: | ---: | ---: | ---: |
| Elaborated Lean targets | 15 | 14 | 0 | 0 | 1 |
| Dependent-family recipes | 24 | 24 | 0 | 0 | 0 |
| Polymorphic identities / redex wrappers | 72 | 72 | 0 | 0 | 0 |
| Syntax mutations | 256 | 6 | 250 | 0 | 0 |
| Untyped bounded fuzz | 256 | 17 | 239 | 0 | 0 |
| Exhaustive depth-one / leaf-claim pairs | 208 | 3 | 205 | 0 | 0 |
| Valid resource-boundary judgments | 3 | 0 | 0 | 3 | 0 |
| **Total** | **834** | **136** | **694** | **3** | **1** |

There are 600 unique syntax judgments, not 834 distinct source theorems. The
15 elaborated targets are hand-authored source fixtures, separate from the
[857-name real mathlib population](mathlib-evaluation.md). Mutations and fuzz
are checked rather than labeled invalid by construction: six mutations and
17 fuzz judgments are valid. The unsupported target depends on Nat. The three
resource cases exceed the universe bound, continuation stack and input heap
respectively; none is a logical rejection.

No discrepancies were found among weighted outcomes, the independent operational
specification, recursive oracle, actual Lean kernel or nanoda on completed
ACCEPT/REJECT judgments. All 830 such judgments were independently replayed in
nanoda. Every encoded final whole-state digest agrees with the operational
specification, including runtime resource states. Eight actual source-case
traces were compared at every step; all 49 specification phases occur in the
corpus. Additional unit tests compare full traces covering all phases and test
forged state, binding/capture errors, numerical domains, resource absorption,
invalid annotations/environments, opacity, eta and proof irrelevance.

These are bounded differential results. They establish neither full Lean
compatibility nor formal soundness. Nanoda invalid judgments often use Rust
assertion panics; exit codes/stderr are retained for audit. Signal failures are
classified as tool errors in the current adapter. No failed reference process
is hidden as an unsupported proof. No mismatch required minimization in this
run; the minimizer and first-fault diagnostics have separate injected-fault tests.

Initial validation-run fixed forward time was 184.191 s, with compile+check
191.066 s; no repeated latency estimate is claimed for that run. Real Lean
replay took 1.182 s including the helper process/frontend and all selected JSON
rows, excluding source elaboration. This reference timing has a different
boundary from reused-weight forward time. CPU reproduction and shape scaling
are reported separately. See [the evaluation guide](evaluation.md) for exact
commands, depth-one enumeration, generation rules and timing boundaries.
