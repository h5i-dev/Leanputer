# Generic typed core through motive generation in stock layers

Tested compiler commit **72cd7a0**. [Report](report.json).

Two raw core-operation inputs: the exported Eq header/constructor and a positive
functional recursive field. The stock Qwen3_5ForCausalLM forward/cache derives
header and constructor checks, recursive descriptors, verified recursor names,
private constructor signatures, elimination/K metadata, and motive types with
index/major snapshots. All metadata comes from raw syntax in weights. No host
checking/reduction/admission answer or generated-record bootstrap enters native
inference. Offline reference/cache decoding is diagnostic validation only.

Both operations reach **GAP_RECURSOR_GENERATION**, with **exact agreement in
all registers and every heap, stack, constants and context cache row**. Public
environment/admitted declarations remain zero. Eq block analysis is not Eq.symm
proof checking. Original-source nested staging, minor/recursor type/rule
construction, restoration and full conversion remain incomplete. No new
mathlib coverage/throughput fraction is asserted (source denominator remains857).

| Measurement | Value |
|---|---:|
| BF16 parameters | 2,129,074,346 |
| Weight bytes | 4,258,148,692 |
| Hidden size / layers | 6400 /150 |
| Heap / stack / context / raw constants | 256 /16 /8 /2 |
| Word bits / fuel cap | 9 /1024 |
| Cold compilation | 44.235124s |
| GPU forwards, two cases batched | 204.749126s |
| Bootstrap tokens / applied forwards | 110 /945 |
| Semantic steps, Eq / functional | 941 /576 |
| CUDA peak allocated bytes | 4,307,555,328 |
| Host process peak RSS bytes | 1,800,151,040 |

Early halt observes model halt bits every8steps and performs one stock completion
flush. Timing includes this batched forward run; it is not steady-state theorem
throughput. Transformers used its correct PyTorch fallback kernels for missing
causal-conv1d/FLA extensions. This report changes semantic work relative to older
core reports; it is not a matched performance comparison. Weights fit the A10G
and were not saved/downloaded. Subsequent raw recursion-flag and shared-window
changes are not included in this pinned native report.

Command: see `command` in the report. Targeted IR contracts for this code passed:
all-family motives/independent telescope types (Eq, functional, dependent mutual
indices) and the existing zero-base telescope round trip,2tests52.803s.
