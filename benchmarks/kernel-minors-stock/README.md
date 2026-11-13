# Generic core through minor/functional IH generation in stock layers

Tested compiler **a9fc5ab**. [Complete report](report.json).

Same two raw core inputs: exported Eq header/constructor and a positive
functional recursive field. Normal stock Qwen3_5ForCausalLM forward/cache
performs header/constructor typing, universe/positivity/index checks, functional
recursive descriptor derivation, name validation, private constructor declarations,
raw recursion/reflexivity flags, elimination/K, all motives, and all constructor
minor types/functional induction hypotheses. Generic dependent prefix reopening,
substitution, family-to-motive lookup, list application and scoped Pi folding
run inside the generated weights. No supplied checked metadata or host answers.

Both end **GAP_RECURSOR_GENERATION** after minors, with **exact agreement in
all registers and every heap/stack/constants/context cache row**. Public Γ and
admitted declarations remain zero. This is not Eq.symm proof checking, original
nested declaration admission, full conversion, or mathlib coverage. Closed
recursor types/rules, claims and nested restoration/publication are subsequent
stages; later type-pass IR evidence is not part of this pinned stock result.

| Measurement | Value |
|---|---:|
| BF16 parameters / weight bytes | 2,719,944,788 /5,439,889,576 |
| Hidden size / layers | 7168 /171 |
| Heap / stack / context / raw constants | 256 /16 /8 /2 |
| Word bits / fuel | 9 /1024 |
| Cold compilation | 56.073746s |
| GPU forward run (two cases batched) | 248.867828s |
| Bootstrap / applied forwards | 110 /1001 |
| Semantic steps, Eq / functional | 997 /766 |
| CUDA peak allocated bytes | 5,702,578,176 |
| Host peak RSS bytes | 1,813,471,232 |

Early-stop observation every8steps plus one stock completion flush. Correct
PyTorch fallbacks were used for unavailable causal-conv1d/FLA extensions.
CPU development/IR checks ran concurrently: these are observed smoke costs,
not isolated or steady-state theorem throughput. New stages change semantic
work, so older reports are not matched speed comparisons. No weights saved or
pretrained weights downloaded; memory fits the A10G. Source denominator857
remains unchanged and no native coverage fraction is asserted.

Targeted IR checks: ordered constructor vector12.818s; generation helpers1.562s;
all-state minor types versus independent closed recursor telescopes96.600s,
covering Eq, multiple constructors with mixed nonrecursive/functional/direct
fields, and an empty dependent indexed mutual block. Command is in report.json.
