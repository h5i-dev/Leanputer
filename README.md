# Leanputer

Leanputer's first milestone is a bounded checker for the simply typed lambda
calculus (STLC), compiled directly into deterministic Transformer-style weights.
There is no training. At inference, fixed sparse attention and ReLU feed-forward
matrices compute the acceptance bit; no recursive type checker, CPU/RISC-V
emulator, Lean process, or external proof service decides it.

This is an experimental foundation for a future dependent-type checker. The
current checker supports variables, annotated lambdas, and applications over a
finite vocabulary of atomic types and arrows. It checks closed terms and exact
claimed types. It does **not** implement the Lean kernel, Lean export/import,
dependent products, universes, constants, inductives, recursors, definitional
equality, or proof irrelevance. There is no formal verification of the compiler
or its floating-point implementation.

Install and run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m leanputer --device cpu
.venv/bin/python -m leanputer --device cuda  # optional CUDA-capable PyTorch
.venv/bin/python -m unittest discover -s tests -v
```

The editable install also provides a `leanputer` command. On a CPU-only machine,
install a CPU build of PyTorch before installing this package. Development was
validated with Python 3.9, PyTorch 2.8.0+cu128, and an NVIDIA A10G. NumPy is not
required; this environment's PyTorch emits a NumPy initialization warning without
it. CPU CI uses Python 3.11 and PyTorch 2.8.0. CUDA and Lean integration tests skip
when their tools are unavailable; CPU CI does not establish those results.

The default demo accepts ten identities, application/composition, projections,
and a beta-redex example. It rejects a wrong statement, a free variable, and
application of an atomic value. Corresponding manually written Lean theorems
live in [examples/Proofs.lean](examples/Proofs.lean). An optional test invokes Lean
on that file and on a negative example. This is independent fixture validation;
it is not proof translation or an inference dependency.

Check a term or save/load weights

```bash
.venv/bin/python -m leanputer --check examples/identity.json
.venv/bin/python -m leanputer --save /mnt/scratch/leanputer-runs/checker.pt
.venv/bin/python -m leanputer --load /mnt/scratch/leanputer-runs/checker.pt \
  --check examples/identity.json --device cuda
```

`--check` reads one JSON object containing exactly `term` and `claim`. Atoms are
nonempty strings; an arrow is a two-element array, with arrows associating as
explicitly nested. For example, `P -> Q -> P` is `["P", ["Q", "P"]]`.

```json
{
  "term": ["lam", "p", "P", ["var", "p"]],
  "claim": ["P", "P"]
}
```

The term grammar is `["var", name]`, `["lam", name, domain, body]`, or
`["app", function, argument]`. Names are strings and may shadow outer names.
JSON results contain `ACCEPT`, `REJECT`, or `RESOURCE_LIMIT`; exit codes are 0,
1, and 2 respectively. Malformed syntax/configuration also exits 2 with a parser
error. A demo exits 0 only if all its expected decisions match.

`--config path.json` compiles a different fixed configuration, e.g.
`{"nodes": 8, "types": ["P", ["P", "P"]]}`. It is mutually exclusive with
`--load`. The vocabulary must contain every arrow's domain and codomain, without
duplicates. Configuration changes generate new weights; they do not increase a
loaded checker's capacity during inference.

Artifacts contain configuration and sparse tensors, with a format version.
Loading uses `torch.load(..., weights_only=True)` and compares **every** tensor
against deterministic recompilation. Modified weights are rejected. Loading is
therefore not a compilation cache, and configuration/compiler changes can
invalidate older artifacts. Choose configuration and artifact provenance as you
would for compilation input: the loader does not bound the cost of compiling an
arbitrarily large configuration. Large generated artifacts belong on scratch
storage, not in the repository.

Supported fragment and limits

Both `Config()` and the CLI use 16 AST slots and these 16 fixed types; `->`
below associates to the right:

| IDs | Types |
| --- | --- |
| 0–2 | `P`, `Q`, `R` |
| 3–6 | `P -> P`, `P -> Q`, `Q -> R`, `P -> R` |
| 7–9 | `Q -> Q`, `R -> R`, `Q -> P` |
| 10 | `(Q -> R) -> P -> R` |
| 11 | `(P -> Q) -> (Q -> R) -> P -> R` |
| 12 | `(P -> Q) -> P -> Q` |
| 13–15 | `P -> Q -> P`, `P -> P -> P`, `P -> Q -> Q` |

STLC inference uses lexical scope and structural equality of types. Every
subterm's inferred type must fit the vocabulary, including a lambda inside a
beta redex whose intermediate type does not appear in the final statement. No
beta normalization is needed for STLC arrow typing.

`ResourceLimit` from the encoder means the AST/depth, annotation, or statement
does not fit the compiled capacities. This says nothing about logical validity.
Within the model, a separate resource bit detects a lambda whose representable
domain/body would form an arrow missing from the vocabulary. That bit is a
conservative signal of incomplete checking; a different part of the term may
also be ill typed. It does not certify that the term is well typed. The CLI
reports this signal as `RESOURCE_LIMIT` instead of presenting it as a definitive
logical rejection. `ACCEPT` requires a structurally valid tree, correct scope,
and an inferred root type equal to the one-hot claim.

Python API and trusted boundary

```python
from leanputer import App, Config, Lam, Var, compile_checker, encode

model = compile_checker(Config()).eval()  # takes no proof or expected label
term = Lam("p", "P", App(Lam("q", "P", Var("q")), Var("p")))
bits = encode(model, term, ("P", "P"))
accept, resource, *root_types = model(bits)[0].tolist()
assert (accept, resource) == (1, 0)
```

The encoder parses syntax, copies annotations and claims, lays out an AST in
postorder, and resolves lexical names to binder node IDs. It does **not** infer
or compare proof types. Unknown names become self-binder references so the
weights reject them. This name resolution and AST encoding remain a trusted
syntax boundary: the weights validate the resulting nameless tree, not the
relationship between its binder IDs and the user's original name strings. The
separate recursive `infer`/`reference_check` functions in `terms.py` are testing
oracles; the compiler and inference path never call them.

The fixed binary input is a single state token, exposed as a batch of vectors
of shape `[batch, 1104]` with the default configuration. Ordered names are
available as `model.input_names`. For `n` nodes and `k` types, it has
`4n + 3n² + nk + k` bits:

- `tag/i/{pad,var,lam,app}`: exactly one tag per slot.
- `a/i/j`, `b/i/j`: unary/body or binary/application child pointers.
- `bind/i/j`: a variable's explicit lexical binder pointer.
- `ann/i/t`: a lambda's domain annotation.
- `claim/t`: exactly one claimed root type.

The encoder left-pads and puts the root at `n-1`. The circuit checks tag/field
arity, one-hot constraints, children preceding parents, unique parents, active
rows connected to the root, unreferenced padding, and lexical binder ancestry.
Raw tables may have gaps in padding; active rows must still form one tree. The
model rejects disconnected nodes, shared children, cycles, forward child
pointers, non-ancestor/non-lambda binders, and unused metadata. Host-side shape
and Boolean-value checks reject nonbinary values rather than rounding them;
these boundary checks are outside the weights. The output is
`[accept, resource, root_type_0, ...]`. Type bits are diagnostic and must not be
used as acceptance bits for malformed raw inputs.

Architecture and arithmetic

`circuit.py` shares Boolean subexpressions, groups gates by dependency depth,
and lowers each depth to one residual block. Each wire has a dedicated state
coordinate, plus a scratch bank:

1. Single-token self-attention has constant `Q = K = 0`, so its attention matrix
   is exactly `softmax([0]) = [1]`. The sparse value projection copies operands
   to scratch through a residual update.
2. A fixed sparse FFN implements `NOT(x) = ReLU(1-x)`,
   `AND(x_1,...,x_m) = ReLU(sum(x)-m+1)`, and
   `OR(x_1,...,x_m) = ReLU(sum(x))-ReLU(sum(x)-1)`.
3. The FFN adds new wire values and clears scratch for the next block. Earlier
   wire values remain in the residual state. Empty AND/OR implement true/false.

The default checker has **126 distinct, unrolled layers**, residual width
**60,738**, and **254,817 sparse weight nonzeros** after tree validation was
strengthened. It uses frozen buffers, no learned parameters, no layer norm,
no positional encoding, and no dropout. Python orchestrates a fixed sequence of
sparse matrix operations; no input-dependent checker algorithm executes there.
The singleton attention is deliberately degenerate: computation is carried by
FFNs. This is not evidence of a scalable multi-token Transformer architecture.

On Boolean inputs, residual wires are Boolean at layer boundaries and scratch
returns to zero. FFN hidden values may be larger integers. Exactness relies on
float32's exact representation of integers through `2^24`, unit/signed-unit
weights, integral biases, and gate fan-in at most `2^24`, which the builder
checks. Inputs initialize all non-input wires to zero. This is an arithmetic
argument for this construction on the supported domain, not a proof of every
PyTorch backend. CPU/CUDA tests check exact 0/1 outputs; no tolerance or output
threshold is used. Autocast is disabled inside inference, and casting model
weights to half/bfloat16 is rejected. Quantization, altered weights, mixed
precision, and arbitrary nonbinary embeddings are outside this contract.

The model materializes all circuit wires for every batch item. Its sparse
weights do not make the residual state sparse. Larger node/type vocabularies
increase compilation size and batch memory rapidly, and every inference runs
all 126 blocks. The implementation is a bounded circuit unrolling, not a
recurrent micro-operation checker, a Qwen integration, or full Demo A. It
neither imports an existing language model nor demonstrates an efficient Lean
kernel on general proofs.

Validation and next step

Tests cover the ten examples and wrong claims, lexical shadowing and free
variables, application errors, malformed raw tables, every single-bit mutation
of a compact valid encoding, exhaustive binder assignments on a branching AST,
large-fan-in gates under autocast, scratch cleanup, resource exhaustion,
independently generated successes and random differential cases, artifact
round-trip/tampering, CLI statuses, exact CPU/CUDA agreement, and optional Lean
fixture checks. These tests provide evidence, not formal soundness or
completeness proofs. GPU timing on this small batch is not a performance claim.

[The next milestone](docs/next-milestone.md) first replaces per-proof-capacity
layer unrolling with reusable STLC transition layers, then adds a bounded
predicative dependent calculus with explicit substitution, weak-head reduction,
and conversion checking in weights. Each phase has separate correctness and
resource-limit criteria before approaching a Lean kernel subset.
