# Declaration-as-data kernel

The per-name primitive backend is a historical experiment. Increasing its
catalog was the wrong direction: ordinary inductives belong in checked input
data, not in generated semantic branches. Its syntax-export counts do not
measure generic kernel coverage.

The new path supports monomorphic nonrecursive inductives in positive numeric
Sorts, with zero or one independent field per constructor, and nullary Prop
families. Bool-shaped and three-way enums must use one identical compiled
model. The compilation API takes bounds only; declaration names, constructor
counts and recursor signatures arrive as input data.

An inductive header supplies its type and constructor count. Fixed weighted
rules require a literal Sort, a complete contiguous constructor block,
correct owners and ordinals, and each constructor's literal result type equal
to its own family. A field domain must be a literal reference to an earlier
checked carrier whose type is a literal Sort no higher than the family Sort. Parameters, multiple/dependent fields, indices and recursive occurrences are
explicitly unsupported. Since a field is an earlier closed carrier and no
constructor domain can mention the current family, positivity follows from
this restricted shape; it is not a supplied flag.

A recursor supplies a family reference, ground result universe and claimed
type. The checker constructs the expected dependent type inside weights:
`(motive : F → Sort v) → minor₀ → … → (x : F) → motive x`.
A nullary minor is `motive c`; a one-field minor is
`(a : A) → motive (c a)`, derived from the checked constructor AST.
It checks the supplied type and compares it with this derived type. Arity and
minor selection come from validated family/constructor data. Generic iota
reduction checks the major's constructor owner and selects its corresponding
minor and applies its actual field when present; neither constructor names nor user-provided reduction answers are used.
Nullary Prop families can eliminate into Prop with any constructor count.
Large elimination is admitted only for empty or singleton families. Singleton
K reduction selects the sole minor even on a neutral proof major. These rules
come from validated sort/count data, not family names. Prop constructor fields
remain explicitly unsupported; no proof/data elimination flag is trusted.

The reusable foundation is the catalog-free dependent core at `4da2515`:
Sort/Pi/Lam/App, de Bruijn operations, beta/delta, typed proof irrelevance and
function eta, and checked acyclic ordinary declarations. New operational and
Boolean-lowering modules separate semantics from the stock Qwen3.5 backend.
The standard forward/cache requirement remains in force.

Focused acceptance criteria are constructor and recursor checking, Bool
elimination, renaming invariance, three-way selection, and rejection of wrong
owners/results/ordinals/recursor signatures. Unsupported class boundaries must
also be tested. A small matched example must report actual size and step costs;
generic interpretation is not assumed faster. No broad campaign is required
for this initial slice.

Uniform parameters, multiple/dependent constructor fields, strict positivity for recursive
arguments, indexed results and generic recursor derivation for those larger
classes remain explicit subsequent work. This design is not a soundness proof
or a claim of general Lean support.

The implemented modules are `generic_syntax` (untrusted parser and declarations),
`generic_spec` (small-step operational semantics), `generic_transition` (Boolean
lowering), and `generic_layout` (state serialization). The existing stock backend
accepts a semantic-program interface, leaving its historical default intact.
The generic compiler does not import the primitive catalog or inspect proof data.
The native facade still imports its historical default for backward compatibility;
that catalog is not compiled when the generic program is selected.

Input format `leanputer.generic.v1` carries ordered `environment`, `term` and
`claim` fields. Expressions are tagged arrays: var, sort, const, pi, lam, app.
Declaration kinds are axiom, definition, opaque, inductive, constructor, recursor.
Inductive rows carry `constructors`; following constructor rows carry `family`
and zero-based `index`; recursor rows carry `family` and ground result `level`.
There are no supplied positivity flags, reduction tables or accepted judgments.
Ordinary declaration bodies are checked before use; named axioms are explicit
and reported, with no catalog hidden as library assumptions. Syntax preparation
only resolves names, deduplicates identical syntax and encodes bounded integers.

Heap, stack, context and constant capacities are powers of two. Universe and
fuel limits are configuration fields. Exceeding syntax encoding capacity reports
RESOURCE before inference. In-weights heap/stack/context/universe/fuel limits
also report RESOURCE. Semantic class restrictions return UNSUPPORTED;
well-formed supported claims can ACCEPT or REJECT. Bounds are part of the model,
so different proofs/constructor counts fitting the same bounds reuse its weights.
A zero-constructor positive-Sort family is representable; empty elimination has
no constructor iota case. Neutral inductive eta is not implemented.

The Boolean specification uses exact bits. The stock model evaluates their
compiled realization in BF16 using normalization compensation, gated MLPs and
GatedDeltaNet cached memory. The ten-case observed correspondence does not prove
floating-point equivalence for all bounds/inputs. Models remain large and slow:
see the exact [focused evidence](../benchmarks/generic-enum/README.md).
The active milestone after this slice is generic one-field projections and
uniform parameters, then multiple/dependent fields and recursive/indexed
admission with real positivity and elimination checks. No per-name constructors should be added to obtain them.


Actual elaborated Lean input is available through:

```bash
.venv/bin/python -m leanputer.preparation --generic \
  --source examples/GenericInductives.lean --targets examples/generic-targets.json \
  --output /tmp/generic-source.jsonl
```

`ExportGeneric.lean` traverses raw Expr syntax and ordered dependency closures.
It groups actual constructor declarations into input blocks and exports the
actual specialized recursor type; the weighted checker independently validates
both. It does not call inferType/whnf/isDefEq, emit kernel answers, normalize
terms or export supplied recursor rules. Name dispatch is only identity lookup.
The initial exporter rejects polymorphic/mutual/nested families and unsupported
expression syntax rather than promoting dependencies to axioms. All source rows
are retained, including UNSUPPORTED rows with unknown dependency counts.

The source smoke contains three real elaborated declarations using Bool, a
three-way enum and a mixed nullary/one-field datatype. Complete checked closures
contain4/5/7declarations, with no axiom assumptions. These are explicit development
sources, not a mathlib sample or a population coverage estimate.


The [Prop checkpoint](../benchmarks/generic-prop/README.md) also checks an actual
mathlib source target, `Function.mt@[]`, through a three-declaration closure
containing the empty Prop family, an ordinary negation definition and a checked
opaque theorem body. No names receive special compilation rules. This targeted
1/1 smoke is not a full857population result or a generic coverage estimate.
