# Full current source checker on stock Qwen3.5

The entire general source program at semantic commit 127751c is compiled,
including nested transactions, Nat/String/Quot and standalone recursor claims.
Compilation uses physical bounds only; neither witness selects rules or weights.
This is a small source integration check, not all-Lean or native nested coverage.

`source-stock.json` records actual CUDA BF16 inference through unmodified stock
`Qwen3_5ForCausalLM.forward` and cache with identity hidden-state feedback:

| Original source input | Stock result | Semantic steps |
|---|---|---:|
| Empty Prop E, standalone E.rec claim, identity proof | DONE/NONE |1,316|
| Same declarations, wrong proof body | INVALID/TYPE_MISMATCH |1,355|

Both use no assumptions and retain two public environment signatures. Every one
of the 951 logical registers and every row of all seven native RAM partitions
matches the offline transition reference. References were computed only after
model inference. `source.jsonl` contains both exact inputs; `config.json` fixes
word16/heap512/stack32/context8/constants4/fuel8192. Names, expressions and
declaration shapes remain raw syntax data.

The latest model has hidden22,528/layers603 and **21,471,112,926 logical
parameters** (42,942,225,852 BF16 dense-equivalent bytes). **It is not small.**
Standard sparse CSR parameter tensors store 288,206,120 parameter/index bytes,
including 1,153,323 nonzero values, without replacing any stock module. Actual
peak CUDA allocation was 426,602,496 bytes, excluding framework/driver memory.
The two-case forward took 1,221.760s using stock fallback kernels. Compilation
plus artifact saving took 142.003s. These are integration costs, not throughput.

`latest-plan.json` is the reproducible whole-program meta plan: 7,913 persistent
channels, 21,864 allocated slots, 137,494 logic FFN units. Its parameter breakdown
shows 20,865,613,824 MLP parameters. Earlier matched plans show why direct dense
allocation was blocked; they are plans, not native admission evidence. The
logical small-model target and practical runtime remain substantive blockers.

The compiled artifact remains on scratch, outside git; `artifact.json` records
its path and hashes. Production inference, with no SPEC or host checker:

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m leanputer.kernel_check \
  --load-model /mnt/scratch/leanputer-runs/current-full-stock/compiled-source-efficient \
  --input benchmarks/kernel-full-source-stock/source.jsonl \
  --batch-size 2 --device cuda --report /mnt/scratch/leanputer-runs/current-full-stock/cli-report.json
```

The CLI returns exit1 because this fixture deliberately includes a rejection.
The complete admission report here used NativeMachine.check directly after
compilation/save; a separate complete CLI load-and-admit run was not repeated.
The preceding all-linear artifact passed every-parameter/ABI roundtrip and a
loaded two-transition all-register probe. The latest artifact also loaded and
matched all 951 registers for two source transitions in 10.460s; see
`loaded-probe.json`. This is not a second admission run. `environment.json` pins the environment.

Reproduce the meta-only plan without allocating GPU weights:

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m tools.kernel_stock_delivery \
  --plan --config benchmarks/kernel-full-source-stock/config.json \
  --report /mnt/scratch/leanputer-runs/current-full-stock/replanned.json
```

For targeted development validation, the same tool accepts `--input`,
`--config`/`--load-model`, `--device` and `--report` without `--plan`; it compares
all registers and cache rows after inference. It is separate from production.
`delivery-check.log` records seven focused compiler/RAM/CLI checks, not a broad
campaign. Sparse stock inference uses no_grad because this Torch build raises
`Cannot set version_counter for inference tensor` with CSR under inference_mode.

Larger/nested original-source native admission remains unproven. Explicit
semantic gaps include partially replaced prior mutual groups, incompatible or
unavailable primitive bindings/private metadata and conservative neutral
failure classifications. See [delivery accounting](../../docs/kernel/stock-delivery.md).
