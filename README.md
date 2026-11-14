# Leanputer

Leanputer compiles a bounded proof checker into deterministic weights without
training. The [native backend](docs/native-backend.md) runs through stock
`Qwen3_5ForCausalLM.forward`, GatedDeltaNet cache and identity hidden-state
feedback. The compiler generates all weights for a standalone configuration.
The custom sparse circuit/attention-RAM implementation remains a reference.

Active development follows the [pinned general kernel contract](docs/kernel/target.md):
declarations are input data, and shared algorithms traverse arbitrary bounded
telescopes, indices, mutual blocks and recursive arguments. Field/name catalogs
and count-specific feature paths are no longer the development strategy.
The [full current source checker](benchmarks/kernel-full-source-stock/README.md)
now runs on the A10G with stock sparse parameter tensors and reusable compiled
weights. An original inductive, standalone recursor claim and identity proof
accept; a wrong proof rejects, with every register/cache row exact. The complete
fixed program with [byte controls](benchmarks/kernel-byte-controls-stock/README.md)
now has15.80B logical parameters despite219MB stored weights: the
small-model target remains unmet. [Whole-program accounting and runnable commands](docs/kernel/stock-delivery.md)
separate this current evidence from the historical checkpoints below.
The [shared traversal stock smoke](benchmarks/kernel-traversal-stock/README.md)
verifies lift/instantiation/abstraction/occurrence operations with one stock
model and exact output-cache comparison. It does **not** establish full
declaration admission or mathlib coverage. The same stock controller now runs
[typed universe normalization/equivalence](benchmarks/kernel-level-normalization-stock/README.md),
source scheme instantiation, [conservative level comparison](benchmarks/kernel-level-geq-stock/README.md)
and [dependent telescope opening/folding/parameter reuse](benchmarks/kernel-dependent-telescope-stock/README.md). The
[typed inference core](benchmarks/kernel-inference-core-stock/README.md) calls
those same weighted services. [Ordinary source transactions](benchmarks/kernel-source-transactions-stock/README.md)
now check raw dependency types/bodies before generating a private environment,
and constant inference instantiates only checked schemes. [Private general inductive-header analysis](benchmarks/kernel-inductive-headers-stock/README.md)
is now weighted. The [composed CORE rule pass](benchmarks/kernel-recursor-rules-stock/README.md)
checks constructor types/universes/positivity/functional recursive templates,
validates generated recursor names, privately declares constructors, derives
elimination/K permissions and builds all-family motives, all constructor minors/
functional IHs, closed recursor types and computation rules in stock weights.
It ends GAP before rule assembly/claims/restoration. Private grouped metadata/
signature assembly has subsequent IR evidence, outside that pinned stock report.
Original-source nested queue/restoration/rechecking/publication now has independent
semantic and selected Boolean integration evidence; it is outside the historical
stock report. General projection inference/reduction now also has selected source IR evidence.
[Typed conversion](docs/kernel/conversion-native.md) now has source/IR evidence
for proof irrelevance, binding/application congruence, eta and unit-like rules.
Nat/String/Quot source controllers now have targeted SPEC/selected IR evidence;
unavailable primitive bindings and private metadata remain explicit gaps.
An [original-source STOCK checkpoint](benchmarks/kernel-original-source-inductive-stock/README.md)
admits an empty inductive and checks its identity theorem; it uses10.35billion
parameters and does not meet the small-model goal or establish nested STOCK
coverage. An [original-scheme syntax interface](docs/kernel/input.md) is available for
general-kernel development via `leanputer.preparation --kernel-schemes`; syntax
export is separate from checking or native proof acceptance.

The production general-source CLI uses the syntax-only original-scheme loader
and stock model only. Install `.[native]` with Python3.11+, then run:

```bash
python -m leanputer.kernel_check \
  --input benchmarks/kernel-source-transactions-stock/input-id.jsonl \
  --device cuda --report /mnt/scratch/kernel-source-report.json
```

It retains every input row, explicit checked axiom assumptions, unavailable
bodies, malformed syntax, unsupported profiles, implementation gaps and physical
resource exhaustion. Default capacities are heap256/stack16/context8/rawbank4,
9-bit words and512fuel; dependencies AND target must fit. These are experimental
physical limits, not full-kernel support. At checkpoint e0db573, the source model used603.4M BF16
parameters/1.207GB weights. Matched15-case source checks took58.18s fixed GPU
forward or41.86s with native completion stopping; cold compile14.27s is separate.
Atbf7af13, the composed core-through-rules model uses3.807B parameters/7.614GB
weights; its two core operations take565.90s GPU forward plus79.49s cold
construction (heap512/stack16/context8/rawbank2,10-bit words,2048fuel).
Both end GAP before recursor generation, with exact all-register/all-bank
agreement. CPU development checks ran concurrently: these are operation smoke
costs, not isolated or steady-state theorem throughput. Current size changes with services and
capacities; these are historical measurements. No full-population native mathlib
evaluation or formal compiler verification is claimed. [Trust/algorithm contract](docs/kernel/target.md) states the target;
[typed input ABI](docs/kernel/native-cells.md) states the syntax boundary.

The preserved restricted checker is [declaration-as-data](docs/generic-kernel.md).
Its compiler takes resource bounds only. Family names, constructor blocks and
claimed recursor signatures are input data, validated by fixed weighted rules.
One stock model checks two- and three-constructor enums, including arbitrary
renamings. Its current class is ground-universe declarations with uniform type parameters and zero or one field per
constructor in positive numeric Sorts; each field is an earlier checked carrier
a type parameter, or a direct uniform recursive occurrence. It also supports nullary Prop families with checked
elimination restrictions. Zero-parameter single-field projections use validated constructor
data, including neutral comparison and substitution. Parameterized recursors are derived and checked; parameterized projections,
term parameters, indices and Prop constructor fields remain
unsupported. The checker derives dependent recursor types inside weights and
performs generic constructor iota reduction. This is experimental, with no
whole-checker soundness proof or generic mathlib coverage claim.

```bash
.venv/bin/python -m leanputer.generic --backend circuit \
  --input benchmarks/generic-enum/input.jsonl \
  --config benchmarks/generic-enum/config.json --report /tmp/generic-report.json
# Stock architecture: install .[native] in Python >=3.11, then select:
# --backend native --device cuda
```

The first nullary-only ten-case stock run produced 3 ACCEPT, 4 REJECT and 3 UNSUPPORTED
outcomes using 362,579,464 BF16 parameters (725,158,928 weight bytes).
Compilation took 6.58s and fixed-fuel checking took 108.39s on the A10G.
These are small declaration/proof fixtures, not real mathlib throughput.
Input, configuration and measured evidence are in
[benchmarks/generic-enum](benchmarks/generic-enum/README.md).
A syntax-only generic Lean exporter is available with
`python -m leanputer.preparation --generic`; see
[the declaration format and source example](docs/generic-kernel.md).
The independent Lean replay constructs actual inductives and checks their generated recursors.
It is an evaluation tool, never invoked by inference.

Generic Prop support also checks actual mathlib `Function.mt` with all three
input dependencies checked and no axioms. Its False-claim mutation rejects.
This is one targeted source smoke; the complete857source population has not been
checked with this backend. The [eleven-case Prop evidence](benchmarks/generic-prop/README.md)
reports6ACCEPT/4REJECT/1UNSUPPORTED using412.1M BF16 parameters and105.85s GPU
forward time. Actual constructor-only Nat uses the same data/rules as an arbitrary recursive
Tally type, with no Nat-specific compilation. The
[recursive stock batch](benchmarks/generic-recursive/README.md) yielded
9ACCEPT/3REJECT/2UNSUPPORTED/1RESOURCE using445.0M BF16 parameters
(890.1MB weights) and143.97s GPU execution at1408fuel. Raw literals, general inductives,
Eq and general indexed elimination still require
further generic rules.

The remainder documents the **historical per-name catalog backend**, retained
for reproducibility. Its syntax-export counts and feature list do not describe
the new generic backend. Expanding that catalog is no longer the implementation
strategy.

[Layout improvements](docs/native-downsizing.md) reduced an earlier matched 512-cell
model from 4.021 billion to 668.6 million BF16 parameters, with identical
outcomes on targeted checks. GPU forward remains slow: 372.83s → 315.20s for
the fixed development batch. These results establish a size reduction, not
high proof throughput or broad correctness.

With the newer 74-primitive fragment frozen, a second matched layout change
reduces 1.356B to 1.221B parameters at the same capacities and fuel; latency
remains about 159s for three Eq judgments. All execution still uses stock layers.

The supported ground-universe fragment includes Sort, de Bruijn variables,
dependent Pi, annotated Lam, App, checked acyclic dependencies and let
expressions. Fixed kernel primitives provide False and its eliminator, Iff/And
constructors, projections and dependent recursors; True/True.intro/True.rec;
Nonempty, Exists and Or with their fixed constructors and recursors; and
Eq/refl/dependent Eq.rec and HEq with carrier/value K checks. Decidable provides its two constructors and dependent
data recursor. Subtype includes dependent fields and typed record eta.
Std.Symm retains a Sort-valued carrier and an actual binary relation, including
Prop carriers, with targeted stock native confirmation. The commutativity slice preserves Std.Commutative as a proof class and the actual
operation instances in IsMul/IsAddCommutative, with targeted native checks.
Bool includes its two nullary constructors and dependent data recursor.
Option includes its zero/one-field constructors and dependent data recursor,
with successor universes for its Type-valued carrier.
Fixed one-field records cover Inhabited, Mul, Add and Subsingleton, including
dependent field typing. Zero and One use the same fixed data-record path.
LT and LE add relation-valued fields, preserving typed data eta and family checks.
Membership retains both carrier types and its container-first relation field.
HAdd and HMul retain three carrier types and four recursor universe parameters.
Semigroup/AddSemigroup and CommMagma/AddCommMagma retain a Mul/Add parent and
its dependent associativity/commutativity proof. Projection typing substitutes
the actual parent; typed eta compares the data parent and uses proof irrelevance
for the law field. These are four fixed schemas, not general structure support.
Four cancellation Prop classes retain their actual Mul/Add instance as a uniform
parameter and check left/right translation injectivity; singleton data recursion
reduces on genuine constructors.
PProd and Prod add two-field records with typed eta and dependent recursors;
[ground-universe tuples](docs/ground-universes.md) retain all three recursor levels.
Bounded raw Nat literals, zero/successor normalization and dependent Nat.rec
are also supported. OfNat retains both uniform parameters and the stored
field, so ordinary numerals check their actual instance definitions.
PUnit distinguishes Prop0 constructor-only data reduction from positive-universe
data eta/recursion. Data records support typed eta; the Prop-valued
Subsingleton keeps constructor-only data reduction.
Fixed Quot/Mk/Ind/Lift rules include checked
relation respectfulness for lifting.
Numeric universes use Lean's impredicative Prop rule. Conversion includes
beta/delta/zeta, function eta and definitional proof irrelevance. Opaque values
are checked while opacity is preserved.

Symbolic universe constraints, general inductive declarations/recursors,
higher Quotient/Setoid structures and arbitrary structure projections remain
unsupported. The
fragment and native numerical correspondence are experimental. Whole-checker
formal soundness and broad native differential validation remain outstanding.

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
  --memory-update attention_delta --execution cuda_graph \
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

Using the native checker

With Python3.11+ and the native extra installed, check prepared JSON/JSONL:

```bash
python -m pip install -e '.[native]'
python -m leanputer.native_machine --input corpus.jsonl --config capacities.json \
  --device cuda --batch-size 4 --report native-report.json
```

The same capacity fields below apply. Reports retain unsupported, malformed
and resource outcomes and separate compilation from fixed forward time. Dense
model sizes are substantial; consult the measured native checkpoints before
selecting capacities. This path uses stock layers and cache, with no external
checker at inference. Broad native validation remains pending.

Using the shared reference checker

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
An optional `atom_pool: true` configuration reserves a validated prefix of
canonical Var/Sort leaves for reuse inside weights. It trades a fixed syntax
prefix for fewer runtime allocations; default false retains the original policy.
Every shared-reference input passes a weighted canonical initializer, followed by exactly
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
correspondence to exported Lean expressions. [The 834-judgment corpus result](docs/corpus-results.md) records 136 accept,
694 reject, three resource and one unsupported outcome, with zero differential
mismatches. [The evaluation guide](docs/evaluation.md) documents generation, replay,
minimization and timing. [The research plan](docs/research-plan.md)
tracks acceptance criteria and remaining work. The original 126-layer STLC
unrolling remains available for comparison through `python -m leanputer` and is
documented in [the baseline notes](docs/stlc-baseline.md).

With `--memory-update attention_delta`, the shared reference engine combines
two dependent attention read rounds, compiled register-control FFNs, and
attention-addressed gated rank-one writes. Stage depth depends on the compiled
fragment and capacities and is reported in model statistics. The default
`logic` backend retains Boolean masked writes for comparison. CUDA graph replay
(`--execution cuda_graph --device cuda`) reuses the same forward operations and
fixed schedule; it does not move semantic work into the host loop.

[The initial reference-backend mathlib evaluation](docs/mathlib-evaluation.md) retains all **857
public theorem declarations from four pinned modules**. Four ground instances
are exportable and accepted at heap2048/fuel16384; 853 are unsupported. This is
4/857 (0.467%) for that population, with a 59.16-second fixed CUDA batch in an
initial single run. At heap256/fuel2048, one accepts and three exhaust heap in
6.27 seconds. These are low coverage and low throughput results, with explicit
limits, not a fraction of all mathlib or a GPU speedup claim. All four exported
judgments have empty dependency environments and agree with Lean and nanoda.
The sequential fixed-fuel design remains a major performance limitation.

Custom reference-backend reads rely on saturated float32 softmax underflow on the supported binary
address domain, verified at every address for tested CPU/CUDA capacities. ReLU
logic relies on bounded exact integer arithmetic. This is not exact selection
over real-number softmax and is not a backend-independent proof. Autocast is
disabled and dtype-cast weights are rejected. Input parsing, external exporting,
compiler implementation, runtime/backend arithmetic and hardware remain trusted.

`proofs/Logic.lean` proves binary integer-domain gates, masked writes and absorbing
states without axioms. It also proves bounded n-ary gate arithmetic using Lean
standard axioms (`propext`, `Quot.sound`), with no admitted lemmas. It does not verify the complete circuit
compiler, attention implementation or typing machine. Full-state differential
traces, seeded tests and external replay provide evidence, not formal soundness.


The current complete syntax refresh retains all 857 selected public theorems:
530 export and 327 remain unsupported. EXPORTED is not proof acceptance; a
new full-population native check has not been run. The [complete syntax
outcomes](benchmarks/mathlib-v4.31.0/current-fragment/syntax-summary.json) retain
assumptions, input sizes and every unsupported row. Monoid is the largest current
first blocker (32 rows). This refresh is separate from the earlier 4/857
reference-backend proof result.
