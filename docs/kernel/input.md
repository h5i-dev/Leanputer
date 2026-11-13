# Original-scheme syntax interface

`tools/lean/ExportKernel.lean` and `leanputer.kernel.syntax.SyntaxCodec` transport
raw source declarations for the [general kernel contract](target.md). This is
an experimental syntax interface, **not a full native admission/import path**.
The native proof-checker CLI still implements its documented earlier fragment.

```
.venv/bin/python -m leanputer.preparation --kernel-schemes --module Init \
  --targets /path/to/targets.json --output /mnt/scratch/kernel-source.jsonl
```

Targets are objects with `name` (or exact structured `name_parts`), without a
`levels` grounding request. The exporter preserves each original scheme's
universe parameters and all symbolic universe arguments. It reads available
bodies, including opaque/theorem bodies, with full dependency closure. Genuine
axioms are explicit; an unavailable non-axiom body is not turned into an axiom.
Unsafe/partial declarations are outside the safe profile.

One JSONL row is retained for every requested target. EXPORTED describes syntax
availability only. Unavailable rows have status/reason and null declarations/
target; unknown dependency counts must remain unknown. Parsing them raises
`SourceUnavailable`, not kernel rejection or a fictitious empty environment.

The format is `leanputer.kernel-source.v1` with ordinary declarations and
complete `inductive_block` groups in dependency order. Blocks contain original
universe parameters, a checked-later parameter annotation, all mutual family
and constructor signatures, recursor names and recursor TYPE claims. Derived
indices, field counts, positivity, recursion, elimination/K and computation RHSs
are not exported as answers. The checker generates those internally. Recursor
claims are inferred as types and compared to generated schemes modulo bound
universe renaming, never used to select the elimination permission.

Structured names preserve string versus numeric segments. `SymbolTable` interns
them injectively and records a bounded generic-vector representation. Symbolic
levels support zero/succ/max/imax/param. Expressions support BVar, Sort, Const,
App, Pi/Lam with binder annotations, Let, arbitrary-index Proj, Nat/String
literals and inert metadata wrappers. Numeric literals are decimal syntax
encoded into little-endian 16-bit limbs; strings use UTF-8 bytes. Decimal limb
conversion is literal encoding, not evaluation of a Lean arithmetic term.
No INFER/WHNF/CONV or admission operation runs in this codec/exporter. The
exporter omits the semantically inert metadata payload, retaining its inner
expression. No declaration scheme or term is normalized/ground-specialized.

Quot has a separate actual-kernel-primitive interface declaration. Its signature
and required bindings must be validated by the kernel driver before use. It is
not an admitted axiom or a precedent for an ordinary named primitive catalog.

`tests/fixtures/kernel-source-smoke.jsonl` has three standard-library source
exports (`id`, `Prod.fst`, `Eq.symm`) and one deliberately unavailable target.
The core-phase test independently infers/checks the Prod and Eq block data,
derives their recursors and compares the supplied symbolic schemes. It does not
check the full target bodies or earlier ordinary declarations. This is neither
native proof coverage nor a new mathlib denominator. The executable spec now
connects nested processing and atomic transactions, with explicit GAP for
incomplete conversion/projection/primitive services. The weighted full-source
driver remains unfinished; see [the nested spec evidence](../../benchmarks/kernel-nested-spec/README.md).
