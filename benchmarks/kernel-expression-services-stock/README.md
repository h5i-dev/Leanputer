# Shared expression services and internal calls

The recorded controller/evidence is pinned at commit `fe97d14`.

This extends the general traversal controller with the source's syntactic
beta/zeta/metadata weak-head subservice. Beta and literal Let reduction call
the SAME capture-avoiding substitution walk through private continuations.
An explicit application spine handles curried beta and neutral heads.
Internal control frames and single-substitution entry are never proof input.

One stock model processes the eight earlier operation probes and three new
capture/Let/spine probes:10DONE and1RESOURCE(INDEX). Every register and every
heap/stack/operand cache row matches the independent small-step spec exactly.
DONE is operation completion, **not proof or declaration acceptance**.
This is not complete WHNF: checked-environment delta, local-let lookup,
recursor/projection/K/eta/literal/Quot integration remain separate operations.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_operation_smoke.py --device cuda \
  --report /mnt/scratch/leanputer-runs/general-expression-services-stock/report.json
```

Evidence: [report.json](report.json), including exact raw syntax/operand inputs.
Stock `transformers.models.qwen3_5.modeling_qwen3_5.Qwen3_5ForCausalLM`,
66,107,980 BF16 parameters/132,215,960weight bytes; H768/L39/FFN512;
64heap/16stack/8operand cells/8-bit words/fuel128.
Compile3.309404s; GPU7.868765s,23boot+130stock forwards;
CUDApeak177,651,200bytes; hostRSS1,679,708,160bytes. Cold compilation/run;
no steady-state throughput or complete-checker speed comparison. Stock fallback
kernels were used; no weights saved. No host reduction/checker is called inside
native operation inference. Spec execution and cache decoding are offline
validation only. Broad differentials and mathlib population runs remain deferred.
