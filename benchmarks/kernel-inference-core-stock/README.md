# General typed core through shared stock services

The inference controller first runs complete expression scope, then derives
Sort/Pi/Lam/App/Let/Local types through the SAME universe constructors,
telescope opening, capture-avoiding substitution, abstraction and beta/zeta
services. Private Local/type records are created only after domain checking;
raw universe-symbol slots are outside the Local lookup window. Binder scope is
restored after the resulting type is derived. All names/counts remain data.

Full checking is UNFINISHED. Constants require a checked environment callback;
projection/literals require general checked metadata/genuine primitive services.
Those paths return GAP. The conversion callback establishes only positive
representation/beta/zeta equality or complete Sort-universe equality; other
cases GAP. Representation mismatch never becomes definitional inequality.
The complete target remains [the native inference contract](../../docs/kernel/inference-native.md).

Seventeen focused stock inputs complete7DONE/5INVALID/5GAP, exact ALL registers
and every materialized heap/stack/context cache row. DONE types independently
convert to KernelServices results. Inputs include the actual original id type/
body, dependent binder shadowing, App/Let, definite type errors, free-variable
errors and explicit missing callbacks. A RAW axiom signature does NOT become a
trusted inferred type: that case remains GAP_ENVIRONMENT/admitted0. Focused
module/shared-caller4tests PASS8.591s also checks STACK/CONTEXT/FUEL exhaustion.
No host inferred types/checking answers are packed.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --group inference --device cuda \
  --report /mnt/scratch/leanputer-runs/general-inference-core-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_inference_transition -v
```

[Exact report/inputs](report.json). Heap128/stack16/context8/8-bit words, FUEL160
for the137-transition nested binder input; traces1..137steps/free27..52. Stock
Qwen3_5ForCausalLM forward/cache, generated BF16weights, no pretrained model or
custom forward. 342,631,476parameters/685,262,952weight bytes; H2624/L59/FFN512;
compile7.383776s/GPU14.427619s;40boot+162forwards;
CUDApeak814,410,240bytes/hostRSS1,692,897,280bytes.
Fixed-fuel unused work is included; imports/offline validation excluded. No
matched-speed/compression or steady/full-source throughput claim. No saved
weights or broad differential campaign.

DONE is INFERENCE OPERATION completion, not source/declaration/theorem admission.
The checked environment, complete conversion/primitives and general weighted
inductive admission/generation/whole-source driver are unfinished. No new native
mathlib theorem coverage or formal-verification claim.

Evidence is pinned to `8d9a76d`; later ABI revisions add raw declaration reads.
