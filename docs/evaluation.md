# Evaluation and diagnosis

The runtime checker never invokes references. The evaluation harness first
compiles configuration-only weights and completes every weighted model run,
including reused-weight repetitions. Only then does it invoke the independent
operational specification, recursive oracle, actual Lean kernel, and optional
nanoda. References cannot choose proof inputs, resource bounds, forward steps or
weights. They are validation instruments rather than a runtime trust shortcut.

## Corpus generation

```bash
python -m leanputer.preparation --source examples/DependentCorpus.lean \
  --targets examples/dependent-targets.json \
  --output /mnt/scratch/leanputer-runs/real.jsonl
python -m leanputer.corpus --real /mnt/scratch/leanputer-runs/real.jsonl \
  --seed 814732 --synthetic 96 --mutations 256 --fuzz 256 \
  --exhaustive-small --resource-cases \
  --output /mnt/scratch/leanputer-runs/corpus.jsonl
python -m leanputer.evaluation --input /mnt/scratch/leanputer-runs/corpus.jsonl \
  --config config.json --output /mnt/scratch/leanputer-runs/evaluation \
  --device cuda --execution cuda_graph --memory-update attention_delta \
  --batch-size 32 --lean --nanoda /path/to/nanoda_bin --traces 8 --repeats 0
```

The synthetic recipes include ground polymorphic identity, dependent families,
beta wrappers, and conversion-required claims. They construct syntax without
running inference, normalizing or asking an oracle. Mutations alter annotations,
indices, child order, subtrees and claimed types. **A mutation is not automatically
an invalid judgment**; independent checking determines its actual outcome.
Untyped fuzz uses bounded random Sort/Var/Pi/Lam/App trees. The exhaustive small
suite covers every depth-at-most-one term over four leaves (Sort0, Sort1, Var0,
Var1), all three binary constructors, and every leaf claim: 52×4=208 judgments.
It is an exhaustive bounded set, not exhaustive testing of the calculus.
Resource cases are valid judgments that can exceed universe, stack or input
heap budgets. Corpus rows contain provenance, never expected checker labels.

Results report source constants, unique syntax judgments and total selected
rows separately. Repeated variants do not establish new source-theorem coverage.
`UNSUPPORTED`, malformed input, preparation/encoding exhaustion, runtime
`RESOURCE`, `REJECT` and `ACCEPT` remain distinct. Resource exhaustion does not
establish invalidity; unsupported screening is not proof checking. A recursive
oracle may finish when the bounded machine exhausts resources.

## Differential evidence and counterexamples

Every encoded final state has a canonical SHA256 digest compared to the
operational specification's entire state, including heap, stacks and registers.
The optional trace mode compares every bit after every semantic step and reports
the first mismatch, prior control registers and differing banks/cells. This is
instrumentation outside checking. Tracing large cases is expensive and is
reported by count, never implied for an entire corpus from a sample.

A discrepancy triggers a bounded syntax/environment minimizer. It removes
subtrees/declarations only when the original disagreement predicate remains
true, writing the reduced input and attempt count. Trace diagnostics are also
tested by injecting a faulty transition. A minimized discrepancy still requires
human analysis; no minimized output is silently relabeled as correct.

Lean replay rebuilds every environment declaration and target in a fresh empty
kernel environment. Nanoda uses equivalent ground NDJSON 3.1. Its adapter
retains exit code, stdout and stderr: nonzero exits currently map to REJECT,
including expected checker panics for invalid terms. A process/tool crash must
be audited from those logs; this mapping is not itself proof that every failed
process established logical rejection. Timeouts raise an evaluation failure.
The complete kernel/compiler/float32 correspondence remains unproved.

## Timing and scaling

`evaluation.json` retains compile/device-placement, syntax encoding/H2D,
initializer, graph setup and fixed forward costs. All CUDA timings synchronize
before completion. The forward interval includes initialization and host fixed
loop overhead. Reused repeats retain raw forward and total-batch times, median
and nearest-rank p95. With only three samples the reported p95 equals the
maximum and is descriptive rather than a statistical tail estimate.

The [mathlib protocol](mathlib-evaluation.md) preserves denominator and dependency
boundaries and provides a fresh-process full-pipeline harness. No theorem
verification cache exists. Reusing weights/graphs does not reuse proof answers.
Peak device memory is PyTorch allocated bytes, not driver memory; host peak RSS
is the complete evaluation process including references. Weight bytes count
fixed buffers, including sparse index storage, not only nonzero float values.

```bash
python -m leanputer.scaling --capacities 32,64,128,256 --batches 1,8,32 \
  --devices cpu,cuda --lowerings optimized --fuel 128 --repeats 3 \
  --memory-update attention_delta --execution cuda_graph \
  --output /mnt/scratch/leanputer-runs/scaling.json
```

Scaling replicates one STLC identity relative to P:Prop, and compares the shared
checker to the original circuit baseline. It is a controlled shape workload,
not a diverse corpus or mathlib coverage measurement. The shared checker also
validates P:Prop and the environment, which the nominal-atom baseline assumes.
Report the baseline's different scope. `--memory-update logic` and
`--lowerings reference,optimized` provide compiler ablations. Captured pools are
cleared between shapes, one cold run precedes steady measurements, and the
strict fuel schedule is the same for every item in a batch.
