# Typed symbolic memory and shared stock services

One stock model now consumes the [typed raw-memory ABI](../../docs/kernel/native-cells.md)
for both symbolic universe scope and Pi/Lam open/fold calls. The level service
traverses Zero/Succ/Max/IMax/Param and checks parameter-vector membership in
weights. Input names preserve string/numeric segments and UTF-8. Universes are
original symbolic DAGs, never host-grounded. The typed syntax packer imports no
inference/normalization/admission code; offline generated artifacts are excluded.

Eight focused operation probes:5DONE/3INVALID(UNIVERSE). All registers and every
materialized heap/stack/context cache row match the independent spec exactly.
These include unbound/empty/numeric-versus-string-name contexts, renamed Unicode
parameters and Pi/Lam callers on the SAME typed heap/model. DONE means operation
completion, **not full typing, declaration admission or theorem acceptance**.
The full weighted source driver/normalization/conversion remain unfinished.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --device cuda \
  --report /mnt/scratch/leanputer-runs/typed-symbolic-services-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_native_cells tests.test_kernel_level_transition -v
```

Exact inputs/config/results: [report.json](report.json).
Stock `Qwen3_5ForCausalLM.forward`/GatedDeltaNet cache, generated weights, no
pretrained model/custom forward/emulator/runtime external checker.
97,222,484BF16params/194,444,968bytes; H1024/L43/FFN512;
128heap/16stack/8context/2raw-declaration cells,8-bit words/fuel128.
Compile3.736426s, GPU8.566312s including63boot+130forwards;
CUDApeak234,743,296bytes, hostRSS1,676,771,328bytes. Cold run; no steady-state
or complete-checker speed claim. No weights saved or broad evaluation run.
Compile/forward timings exclude Python imports and offline validation; no
complete process/source-preparation timing or steady-state claim is made.

Focused transport contracts verify role-alias safety (identical source tuples
used as level references and literal limbs), original-input identity after an
offline spec run generated new rules/types/names, missing-scope data preserved
for weighted checking, arbitrary bounded name numerals and physical exhaustion.
Full source dependency admission remains separate; this is no new mathlib
theorem denominator or coverage estimate.
