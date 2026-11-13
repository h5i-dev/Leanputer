# Generic computation rules in stock Transformer weights

Tested compiler **bf7af13**. [Report](report.json).

Same two raw kernel-function inputs: exported Eq header/constructor and a positive
functional recursive field. Stock Qwen3_5ForCausalLM forward/cache derives all
private typing/universe/positivity/name/flag checks, constructor signatures,
motives/minors/functional IHs, closed recursor types and **closed computation
rules**. Rules use shared context restoration, generic dependent prefix/index
reopening, generated recursor universe schemes, motive/minor vector application,
and lambda folding. No checked state, inferred type or host answer is loaded.

Both end **GAP_RECURSOR_GENERATION**, with exact agreement in **all registers
and every heap/stack/constants/context cache row**. Public Γ/admitted declarations
remain zero. The missing grouping/claim/nested restoration and full runtime
conversion/reduction stages still prevent original declaration/theorem admission.
Eq block analysis is not Eq.symm checking. Later assembly IR work is not part of
this pinned stock result. No mathlib coverage/formal compiler verification claim.

| Measurement | Value |
|---|---:|
| BF16 parameters / weight bytes | 3,806,862,228 /7,613,724,456 |
| Hidden size / layers | 8448 /203 |
| Heap / stack / context / raw constants | 512 /16 /8 /2 |
| Word bits / fuel | 10 /2048 |
| Cold compilation | 79.491515s |
| GPU forward run (two cases batched) | 565.896489s |
| Bootstrap / applied forwards | 110 /1921 |
| Semantic steps, Eq / functional | 1917 /1474 |
| Allocated heap rows excluding null, Eq / functional | 333 /228 |
| CUDA peak allocated bytes | 7,677,385,216 |
| Host peak RSS bytes | 1,835,638,784 |

Halt observation every8steps plus one stock completion flush. Correct PyTorch
fallbacks for unavailable causal-conv1d/FLA extensions. CPU development/IR checks
ran concurrently: observed smoke costs, not isolated or steady-state throughput.
Semantic work changes across reports; no matched speed comparison. Fits A10G;
weights not saved/downloaded. Source denominator857 unchanged, no native fraction.

Focused IR RHS/order/arity/scope comparisons with the independent source builder
passed1test100.973s: Eq, functional fields with fresh elimination universes,
mixed ordinary/functional/direct multi-constructor fields, empty indexed mutual
block. One entire raw-entry functional trace was compared stepwise. Later
assembly/grouped-count/private-visibility contracts passed1test7.624s separately.
Command is in report.json; offline reference/cache decoding is diagnostic only.
