# Declaration-as-data kernel

The per-name primitive backend is a historical experiment. Increasing its
catalog was the wrong direction: ordinary inductives belong in checked input
data, not in generated semantic branches. Its syntax-export counts do not
measure generic kernel coverage.

The new path supports ground monomorphic inductives in positive numeric
Sorts, with zero or one independent field per constructor, and nullary Prop
families. Bool-shaped and three-way enums must use one identical compiled
model. The compilation API takes bounds only; declaration names, constructor
counts and recursor signatures arrive as input data.

An inductive header supplies its type and constructor count. Fixed weighted
rules require a literal Sort, a complete contiguous constructor block,
correct owners and ordinals, and each constructor's literal result type equal
to its own family. A field domain must be a literal reference to an earlier
checked carrier whose type is a literal Sort no higher than the family Sort,
or a literal reference to its own family. The latter is a direct strictly
positive recursive field. Parameters, multiple/dependent fields, indices and
other recursive shapes are explicitly unsupported. Function domains and nested
applications cannot smuggle negative occurrences into this class. Positivity
is checked by this restricted AST shape; it is not a supplied flag.

A recursor supplies a family reference, ground result universe and claimed
type. The checker constructs the expected dependent type inside weights:
`(motive : F → Sort v) → minor₀ → … → (x : F) → motive x`.
A nullary minor is `motive c`; a one-field minor is
`(a : A) → motive (c a)`, derived from the checked constructor AST.
For a direct recursive field it is instead
`(a : F) → motive a → motive (c a)`. The induction-hypothesis binder and its
de Bruijn indices are built inside weights, not supplied by a trusted schema.
It checks the supplied type and compares it with this derived type. Arity and
minor selection come from validated family/constructor data. Generic iota
reduction checks the major's constructor owner and selects its corresponding
minor and applies its actual field when present. For a recursive field it
also constructs the recursive recursor application as the induction hypothesis; neither constructor names nor user-provided reduction answers are used.
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
`claim` fields. Expressions are tagged arrays: var, sort, const, pi, lam, app, and
`["proj", familyName, 0, inner]` for the restricted one-field projection.
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
The next milestone is uniform parameters and a reusable constructor-telescope
interpreter for multiple fields, followed by indexed admission. Direct-self
recursion is implemented; nested/functional recursion remains unsupported. No per-name constructors should be added to obtain them.


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


Generic projection support is restricted to a validated positive-Sort family
with one constructor and one supported field. Inference checks the projected
term has that family and returns the constructor domain. Reduction checks the
actual constructor owner/ordinal and unary shape before selecting its field.
Neutral projections compare the record terms, with proof/eta fallback; identical
field identities alone do not establish equality. Projection syntax participates
in de Bruijn shift/substitution. Other projection indices are UNSUPPORTED.
This does not implement generic record eta or arbitrary structure inheritance.


The [direct recursion checkpoint](../benchmarks/generic-recursive/README.md)
uses actual arbitrary Tally/renamed/Nat declarations and generated recursor
signatures. Tally and actual constructor-only Nat inputs encode identically.
Recursive iota builds the IH application in weighted AST memory; ordinary beta
and generic recursor reduction evaluate it. One- and two-level tests demand
that IH is used. Missing IH signatures reject, negative function domains remain
unsupported, and a deeper valid term exhausts the configured stack. Raw numeric
literals and optimized Nat arithmetic are not implemented by this generic path.

Identifiers in a JSON document designate its supplied theory. Provenance fields
are annotations, not authentication of an installed Lean library. The external
syntax extractor is the correspondence boundary for actual elaborated sources;
weighted inference checks the encoded declarations/judgment. Extraction does not
normalize or check proofs for the model, and all declarations' types/bodies and
the restricted inductive/recursor data are validated by the weighted machine.
