# Analytical stock datapath budget

No small checker was emitted or admitted here. Stock meta parameter counts and
static/SPEC accounting support the conditional design in
[compact-datapath-budget.md](../../docs/kernel/compact-datapath-budget.md).

Run from the repository root with the native Python environment:

```bash
/mnt/scratch/leanputer-native-venv/bin/python benchmarks/kernel-datapath-budget/account.py
PYTHONPATH=. /mnt/scratch/leanputer-native-venv/bin/python benchmarks/kernel-datapath-budget/source_account.py
```

The first command uses meta tensors only; no GPU model weights or inference.
The second compiles the fixed source rules and accounts the two existing source
fixtures in development SPEC. It supplies no model inference answers.

[stock-shapes.json](stock-shapes.json) includes every stock parameter group,
not CSR/nonzero storage. [source-account.json](source-account.json) records the
existing source-controller choices and changed-state counts. These neither
prove a microcode translation nor a numerical/operator/liveness bound.
