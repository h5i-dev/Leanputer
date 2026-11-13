# General kernel-operation stock smoke

This verifies four reusable operations: all-tag capture-avoiding lift and
instantiation, internal-Local abstraction, and symbol occurrence traversal.
It is **not declaration admission, proof acceptance, or mathlib coverage**.
This original controller/evidence is pinned at commit `e756db2`; the current
source adds internal beta/zeta calls, with separate
[extended evidence](../kernel-expression-services-stock/README.md).
The same capacities/weights process all eight raw syntax/operand inputs stored
in [report.json](report.json). All registers and every heap/stack/operand cache
row match the independent transition specification exactly. One unsigned-word
overflow is RESOURCE/INDEX; the remaining seven operations complete.

Source-defined operations: Lean4.31.0 `instantiate.cpp`, `abstract.cpp`, binder
traversal in `replace_fn.h`, and occurrence checking in `inductive.cpp`.
The broader source/target contract and remaining kernel gaps are documented in
[target.md](../../docs/kernel/target.md).

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_operation_smoke.py --device cuda \
  --report /mnt/scratch/leanputer-runs/general-traversal-stock/report.json
```

Stock class: `transformers.models.qwen3_5.modeling_qwen3_5.Qwen3_5ForCausalLM`.
No custom forward, pretrained weights, CPU interpreter, host syntax reduction,
or supplied traversal schedule enters native execution. Python reference runs
and cache decoding are posthoc development checks, not input answers.

64,419,786 BF16 parameters / 128,839,572 weight bytes; H768, 38 layers,
FFN512; 64 heap / 16 stack / 8 vector cells, 8-bit words, fuel128.
Compilation3.260405s; GPU forward7.766392s including23boot tokens and130
transition forwards. CUDA peak163,671,040bytes; host process peak
1,670,524,928bytes. This is a cold compilation/run, with no steady-state speed
claim or comparison to a complete checker. Stock fallback kernels were used.
No weights were saved.

The first attempt passed register comparison but failed posthoc inspection
because the diagnostic accessed a cache dictionary as a tensor. Correcting that
inspection to the stock cache's `[0]` recurrent-state entry produced the recorded
passing rerun. The model/controller was unchanged by that correction.
