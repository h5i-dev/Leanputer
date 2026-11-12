# Leanputer

Leanputer is an experimental bounded dependent-type checker whose semantic
transitions are compiled directly into fixed Transformer weights. There is no
training, CPU emulator, or external checker in its runtime checking path. It
uses actual attention to read syntax/context/continuation memory, and sparse
ReLU FFNs to perform typing, capture-avoiding substitution, beta reduction,
conversion, and state updates. The same weights are reused at every step.

The research program is in progress. Current support is a ground-universe Lean
lambda-Pi subset: Sort, de Bruijn variables, dependent Pi, annotated Lam, App,
and acyclic axiom/transparent-definition dependencies. Numeric universes use
Lean's impredicative Prop rule. Current conversion is beta/delta structural
conversion. Symbolic universe constraints, eta, proof irrelevance, opaque
dependencies, inductives, recursors, quotient rules, lets and projections are
not yet supported. A restricted-calculus rejection need not be a Lean rejection.
The tool does not claim a complete Lean kernel, formal soundness verification,
or conference-level results from the current test count.

Installation and validation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

CPU-only installations can install a CPU PyTorch wheel first. Development uses
Python 3.9, PyTorch 2.8.0+cu128, Lean 4.31.0, and an NVIDIA A10G. CPU CI has no
Lean/CUDA/nanoda and skips those integrations explicitly. NumPy is optional.
`LEANPUTER_NANODA_BIN` enables the independent nanoda integration test; Lean and
nanoda are evaluation tools, never weighted-checker runtime dependencies.

Real elaborated Lean input

Create a targets file containing fully qualified declaration names and concrete
universe instantiations, for example:

```json
[
  {"name": "LeanputerCorpus.dependent_id", "levels": [1, 1]},
  {"name": "LeanputerCorpus.use_library_id", "levels": [1]}
]
```

Then prepare expressions externally and check the resulting syntax:

```bash
.venv/bin/python -m leanputer.preparation \
  --source examples/DependentCorpus.lean --targets targets.json \
  --output /mnt/scratch/leanputer-runs/corpus.jsonl
.venv/bin/python -m leanputer.research \
  --input /mnt/scratch/leanputer-runs/corpus.jsonl --device cuda \
  --report /mnt/scratch/leanputer-runs/report.json
```

Preparation imports Lean's elaborated environment, traverses Expr directly,
specializes universe parameters syntactically, and exports the full supported
constant dependency closure in order. It does not infer proof types, normalize
expressions, generate correctness certificates, or attach checker answers.
The original declared type is the claim. Unsupported expressions/dependencies
produce explicit `UNSUPPORTED` records. Source compilation is external Lean
elaboration/validation, separate from checking the exported input in weights.
Post-export mutations are independently replayed through Lean in tests.

The source corpus includes polymorphic functions, dependent families and
application, propositional proofs, beta/delta conversion and standard-library
constants. Integration tests compare exported judgments and invalid/capture/
environment mutations against the weighted engine, two Python references, the
actual Lean kernel and sampled nanoda replay. They no longer rely only on
manually paired Lean/Python examples.

Using the shared checker

```bash
# Compile an artifact without checking a proof.
.venv/bin/python -m leanputer.research \
  --save /mnt/scratch/leanputer-runs/shared.pt
# Check a JSON document, JSON array, or JSONL corpus in batches.
.venv/bin/python -m leanputer.research \
  --load /mnt/scratch/leanputer-runs/shared.pt --input corpus.jsonl \
  --batch-size 16 --device cpu --report report.json
```

`--config` accepts the fixed capacities `heap`, `stack`, `context`, `constants`,
`universe`, and `fuel`. Memory capacities are powers of two. A configuration
change compiles new weights. The default is 128 heap cells, 32 continuations,
32 context entries, 16 constants, maximum sort level 4, and 1,024 fuel steps.
Every input passes a weighted canonical initializer, followed by exactly
`fuel+1` shared transitions. Finished states absorb all further steps. This
strict schedule avoids host semantic branching but wastes work on short proofs;
reports distinguish applied steps from the steps each proof actually needs.

The CLI reports `ACCEPT`, `REJECT`, `RESOURCE`, `UNSUPPORTED`, and `MALFORMED`
separately. Exit codes are 0 for all accept, 1 if any reject, and 2 for other
incomplete/unsupported/malformed outcomes. Resource exhaustion never accepts.
Axiom assumptions are listed explicitly in each result: acceptance is a
judgment relative to that checked environment, not a claim of axiom freedom.

Artifacts contain fixed tensors, configuration, an ABI format and compiler
fingerprint. Loading performs weights-only deserialization and exact comparison
against deterministic recompilation, including attention weights. Artifacts
from changed compiler sources are rejected. This is compatibility/integrity
checking, not a compilation cache. Store generated weights and reports on
scratch, outside the repository.

Architecture, trust and evidence

[Architecture documentation](docs/shared-engine.md) describes state layout,
addressed memory, semantic phases, recurrence and numerical assumptions.
[Input and trust documentation](docs/input-and-trust.md) defines the format and
correspondence to exported Lean expressions. [The research plan](docs/research-plan.md)
tracks acceptance criteria and remaining work. The original 126-layer STLC
unrolling remains available for comparison through `python -m leanputer` and is
documented in [the baseline notes](docs/stlc-baseline.md).

In the tested 128-cell configuration, the shared machine has 92 sequential
stages per semantic step and roughly 6.4 MB of buffers. A dependent-family
identity took 297 semantic steps. These are intermediate measurements, not a
claim of efficiency or fewer than eleven layers. Systematic corpus/scaling
measurements are still in progress. Singleton identity attention has been
replaced in the shared engine; computation remains sequential and bounded.

Exact reads rely on saturated float32 softmax underflow on the supported binary
address domain, verified at every address for tested CPU/CUDA capacities. ReLU
logic relies on bounded exact integer arithmetic. This is not exact selection
over real-number softmax and is not a backend-independent proof. Autocast is
disabled and dtype-cast weights are rejected. Input parsing, external exporting,
compiler implementation, runtime/backend arithmetic and hardware remain trusted.

`proofs/Logic.lean` proves limited binary integer-domain gate, masked-write and
absorbing-state lemmas without axioms. It does not verify the complete circuit
compiler, attention implementation or typing machine. Full-state differential
traces, seeded tests and external replay provide evidence, not formal soundness.
