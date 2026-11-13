This checkpoint measures declaration-as-data, not catalog extension or mathlib coverage.

One bounds-only compiler invocation produced one standalone stock
`Qwen3_5ForCausalLM` model for all ten ordered input rows. The first three are
Bool-shaped, identically encoded under renaming, and three-constructor enums.
The next four test wrong iota result, constructor result, ordinal and recursor
type. The last three are unsupported constructor fields, indexed family type
and Prop family. Duplicate display names are preserved; row order identifies
mutations unambiguously.

Config: heap128, stack16, context8, constants8, universe4, fuel1056. Stock native
architecture H1408/L69/FFN1024, ballast22; 362,579,464 BF16 parameters,
725,158,928 weight bytes. Compile6.578620s; fixed-fuel stock execution108.394158s,
39 boot tokens +1058 forward calls; peak CUDA818,098,176 bytes and host
RSS1,699,545,088 bytes. A10G/PyTorch2.8.0+cu128/Transformers5.19.0.
No training, pretrained weights, external checker or datatype catalog at inference.
CPU implementation work overlapped; this is not a controlled throughput study.

Result: 3 ACCEPT, 4 REJECT, 3 UNSUPPORTED. Positive semantic steps804/804/991;
all native outcomes, steps and allocated nodes match the operational spec.
One identical compiled model handles all names and both constructor counts.
This is the matched generic example; historical full-catalog measurements use
other features/capacities and are not a matched size/speed baseline.
Independent Lean4.31.0 replay accepts the three positives and rejects all seven
mutations/boundary examples. The weighted unsupported outcomes remain distinct
from Lean rejection. Kernel replay evaluates fixtures, not compiler soundness.

Reproduce weighted CPU and stock CUDA reports:

```bash
.venv/bin/python -m leanputer.generic --backend circuit \
  --input benchmarks/generic-enum/input.jsonl \
  --config benchmarks/generic-enum/config.json --report /tmp/generic-cpu.json
PYTHONPATH=. /mnt/scratch/leanputer-native-venv/bin/python -m leanputer.generic \
  --backend native --device cuda --input benchmarks/generic-enum/input.jsonl \
  --config benchmarks/generic-enum/config.json --report /tmp/generic-native.json
lean --run tools/lean/ValidateGeneric.lean benchmarks/generic-enum/input.jsonl /tmp/generic-lean.json
.venv/bin/python -m unittest discover -s tests -p test_generic.py -v
```

Checker CLI exits1 when negative cases reject, or2 for unsupported/resource-only
nonaccept outcomes; this mixed fixture is intentionally expected to exit1.
No claim of general inductive/Lean support, formal verification or mathlib coverage.
