# Nested algorithm executable-spec checkpoint

This is OFFLINE SPEC evidence, not native checking or mathlib coverage.
The source `KernelAlgorithms.nestedIdentity` uses a nested inductive whose
container is a prior TWO-member mutual block. The current block has two
parameters (including a term parameter); the prior container has one.

The general driver checks the whole dependency closure, specializes/copies the
entire prior mutual block through a growing queue, checks the expanded block,
derives all recursors/rules, restores prior family/constructor names and public
auxiliary recursors, checks restored types/RHSs and input claims, and publishes
atomically. There is no container catalog or supplied positivity/elimination/
admission answer. Complete conversion/primitives and native lowering of this
driver are still gaps. The Python spec never feeds semantic answers to a model.

```
.venv/bin/python -m leanputer.preparation --kernel-schemes \
  --source examples/KernelAlgorithms.lean --module KernelAlgorithms \
  --targets /mnt/scratch/leanputer-runs/kernel-nested-source/targets.json \
  --output /mnt/scratch/leanputer-runs/kernel-nested-source/input.jsonl \
  --workdir /mnt/scratch/leanputer-runs/kernel-nested-source/preparation
.venv/bin/python -m unittest tests.test_kernel_environment tests.test_kernel_nested -v
```

Target array: `[{"name":"KernelAlgorithms.nestedIdentity"}]`.
Source preparation compiled the Lean module to scratch, then exported syntax
without grounding/checker calls. Recorded source:
[kernel-nested-source.jsonl](../../tests/fixtures/kernel-nested-source.jsonl).
The [spec report](report.json) records ACCEPT, both input blocks checked,
12derived declarations admitted, no axioms, zero residual scope. Kernel93618
spec work ticks and syntax583ticks are development counters, **not native tokens
or timing/throughput measurements**. No GPU run was performed for this driver.

Focused contracts also check closure rejection on an otherwise well-typed
nested signature that depends on field locals, scope/transaction rollback,
trailing-field reduction when constructor/recursor parameter counts differ,
and explicit GAP/RESOURCE outcomes. Earlier assumptions remain visible; partial
block headers/constructors/recursors are never published on failure or gaps.
