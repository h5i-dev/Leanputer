# Ordinary source transactions in stock Qwen3.5 weights

Historical checkpoint e0db573; subsequent reduction changes have separate evidence.

The source loader packs ORIGINAL raw schemes/dependencies/body syntax only.
The weighted controller starts with an empty checked environment. It checks
names/unique universe parameters/scopes, infers type Sort and body type, checks
conversion and only then links a private checked signature. Constant inference
traverses that checked list and instantiates the original universe scheme with
the SAME weighted services. No supplied type/admission answer is trusted.
The target requires a checked body and is never published as an assumption.

Fifteen focused source cases produce4DONE/9INVALID/1GAP_UNAVAILABLE_BODY/
1UNSUPPORTED_PROFILE. All registers and all materialized heap/stack/raw-bank/
context cache rows match the development transition reference. The independent
source spec checks the semantic outcomes separately, outside inference. These
are module contracts, not broad differential validation or mathlib coverage.
Original exported `id` is a definition. The polymorphic dependency alias, pure
proof and explicit-axiom proof are synthetic source cases. The latter reports
its two checked dependency axioms; missing definitions never become axioms.

```bash
PYTHONPATH=$PWD /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_source_smoke.py --device cuda --report /mnt/scratch/source-fixed.json
# Same15inputs/capacities/weights, stop on model-produced completion:
PYTHONPATH=$PWD /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_source_smoke.py --device cuda --early-stop \
  --report /mnt/scratch/source-early.json
.venv/bin/python -m unittest tests.test_kernel_source_transition \
  tests.test_kernel_inference_transition tests.test_kernel_name_transition \
  tests.test_kernel_check_cli -v
```

Heap256/stack16/context8/rawbank4/word9/fuel512/FFN512.
Generated standalone BF16weights; stock
`transformers.models.qwen3_5.modeling_qwen3_5.Qwen3_5ForCausalLM`, unmodified
forward/cache and identity state feedback; no pretrained weights/host checker.
603,445,270parameters/1,206,890,540weight bytes; hidden3584/layers76.

| Measurement | Fixed fuel | Native completion |
|---|---:|---:|
| Cold compilation seconds |14.274001|14.270413|
| GPU forward seconds |58.180480|41.855290|
| Stock forwards after boot |514|369|
| Boot tokens |55|55|
| CUDA peak allocated bytes |1,369,549,824|1,369,549,824|

[Fixed report](report.json), [matched completion report](early-stop-report.json).
Completion observes only output status bits every8steps. One extra stock forward
flushes pending cache writes. The hard fuel cap remains. No host proof semantics
or answers enter the loop. Exact all-state/cache matches include pending-write
flush behavior. The native forward uses correct PyTorch fallback kernels when
optional FLA/causal-conv kernels are unavailable. Imports/syntax/reference checks
are outside model timings; this is not a steady-state throughput claim.

The [production CLI report](production-cli-report.json) checks the original
[id source row](input-id.jsonl): ACCEPT/no assumptions,200semantic steps,
201stock forwards,28boot tokens; cold compilation14.566215s/GPU22.142330s.
During that single run `SpecMachine.step`, `KernelServices.infer`,
`KernelServices.convert` and `EnvironmentDriver.check` were replaced with
functions raising AssertionError. None was called; process exit0.

```bash
PYTHONPATH=$PWD /mnt/scratch/leanputer-native-venv/bin/python -m leanputer.kernel_check \
  --input benchmarks/kernel-source-transactions-stock/input-id.jsonl \
  --device cuda --report /mnt/scratch/production-source.json
```

The general target remains unchanged. Inductive/recursor admission/generation,
Quot/literal/projection services and complete typed conversion/reduction are
still GAP callbacks. Positive conversion supports erased representation equality,
beta/zeta and complete Sort-universe equivalence; unhandled mismatches GAP.
This is experimental bounded ordinary checking, not full Lean, full mathlib,
formal compiler verification or a real mathlib coverage fraction. All857source
population rows remain the evaluation denominator; no broad rerun was made.
