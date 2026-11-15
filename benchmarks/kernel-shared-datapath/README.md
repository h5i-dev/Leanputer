# Actual compact shared stock module

The module uses30,509,368 DENSE logical parameters, H768/I256/L28, one ROM
layer and nine active GDN RF heads (three coherent read replicas,384rows each).
Weights encode an eight-record word program and all operand selection, arithmetic,
branching and writeback. The two rows carry identical operands and different
runtime claims. MOVE, unsigned modular ADD/SUB, EQ/LT branching and stop execute
with identity hidden feedback. All RF replicas match exactly after the run.

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m unittest tests.test_kernel_stock_datapath
```

This is a shared operator/RF/ROM implementation check, NOT original declaration
admission or a complete kernel. The full current typed program still exceeds
budget, and additional checker/arena/shadow/continuation actions are not emitted.
No proof-dependent program pruning, pretrained backbone, RV/Boolean emulator,
host instruction dispatch, cache replacement or custom forward is used.

All-GDN stock caches require explicit position/mask arguments in the installed
Transformers: tests pass constant shape-only position_ids and mask mappings
through the existing API. Otherwise the stock cache's automatic get_seq_length
raises because no full-attention layer exists. No runtime code is patched.

[report.json](report.json) records shape/scope; [check.log](check.log) records
actual checks, including full-source SPEC/typed-capture correspondence separately.
