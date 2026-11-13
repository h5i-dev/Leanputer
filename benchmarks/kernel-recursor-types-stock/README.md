# Closed generic recursor types in stock forward/cache

Tested compiler **86659f7** (semantic codeee251ab). [Report](report.json).

Two raw kernel-function inputs: exported Eq header/constructor and a positive
functional recursive field. Stock Qwen3_5ForCausalLM forward/cache derives all
private header/constructor checks, raw flags, elimination/K, motive/minor/functional
IH metadata and **closed recursor types**, then checks generated Expr/universe
scope. No inferred/checked metadata or admission answers are loaded. Offline
reference/cache decoding is diagnostic and never supplies inference inputs.

Both end **GAP_RECURSOR_GENERATION**; **every register and every heap/stack/
constants/context cache row matches exactly**. Public Γ/admitted declarations
remain zero. Eq block analysis is not Eq.symm checking. Claims, computation
rules, nested restoration/admission and complete conversion/reduction remain
subsequent stages. Later shared-restoration/rule IR work is outside this pinned
stock result. No full-kernel, mathlib coverage or formal verification claim.

| Measurement | Value |
|---|---:|
| BF16 parameters / weight bytes | 3,562,559,238 /7,125,118,476 |
| Hidden size / layers | 8192 /196 |
| Heap / stack / context / raw constants | 512 /16 /8 /2 |
| Word bits / fuel | 10 /2048 |
| Cold compilation | 71.298418s |
| GPU forward run (two cases batched) | 456.680433s |
| Bootstrap / applied forwards | 110 /1601 |
| Semantic steps, Eq / functional | 1593 /984 |
| Allocated heap rows, Eq / functional (excluding null) | 287 /170 |
| CUDA peak allocated bytes | 7,187,927,552 |
| Host peak RSS bytes | 1,838,112,768 |

Eq needs288heap slots including null, exceeding the previous256capacity; this
is a physical capacity increase, not a new syntax class. All four512-heap cache
banks and every other bank are verified in the report. Halt observation every8
steps plus one completion flush. Correct PyTorch causal-conv1d/FLA fallbacks.
CPU development/IR checks ran concurrently; these are smoke costs, not isolated
or steady-state theorem throughput. Capacity and semantic work differ from old
reports, so no matched speed comparison. Fits A10G; weights not saved/downloaded.
The857-source denominator is unchanged; no native coverage fraction is asserted.

Focused closed-type/8bit task-control/raw-flag isolation IR contracts passed:
3tests95.838s. Subsequent shared restore callers passed3tests119.969s; closed
rule RHS comparisons passed1test100.973s, each separately scoped as IR evidence.
Command is in report.json.
