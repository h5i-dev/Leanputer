# Symbolic level algorithms and shared stock lowering

Authority: pinned Lean4.31.0 `src/kernel/level.cpp` at
`68218e876d2a38b1985b8590fff244a83c321783`, functions `operator==`,
`is_not_zero`, `to_offset`, `mk_max`, `mk_imax`, `is_norm_lt`, `normalize`,
`is_equivalent` and `is_geq_core`. These are fixed generic algorithms over all
five admitted level tags. Parameters remain symbolic. Source MVars are outside
the safe admitted input profile. No datatype/name/argument-count cases occur.

The complete target normalization algorithm strips outer successors; normalizes
IMax children using the smart constructor and restores successors; flattens
Max arguments, recursively normalizes and flattens them, sorts by a stable total
structural base order with offsets last, removes duplicate bases in favor of
the largest offset and discards explicit universes subsumed by another offset,
distributes outer successors, then right-folds the smart Max constructor.
Equivalence compares normalized structures. The pinned conservative greater-
or-equal predicate follows its own Max/IMax/offset recursive rules; it must not
be replaced by an unrelated sampled/numeric universe comparison. This full
normalization/equivalence/order target has an executable development spec in
`levels.py`. Stock normalization/equivalence is now integrated as described below;
conservative is_geq is also integrated as described below.

The shared weighted service now provides structural comparison, necessarily-
nonzero, successor separation and both COMPLETE smart constructors:

* Structural comparison traverses equal tags/payloads and every child. Address
  identity is a fast path only; native allocation is not generally hash-consed.
  Private continuation frames hold remaining pairs and short-circuit false.
  This operation is not universe equivalence: raw `max u 0` differs from `u`.
* Nonzero returns false for Zero/Param, true for Succ, short-circuit OR for Max,
  and follows IMax's right child. It never grounds symbolic parameters.
* Successor separation returns the remaining raw base and a checked word count.
  Physical overflow reports RESOURCE; it never wraps.
* Max handles zero/equal operands, direct Max-child absorption and equal bases
  with successor offsets, otherwise allocating the raw constructor. Both
  explicit numeric levels are the equal-Zero-base case. Structural equality
  and offset comparisons call the SAME shared services.
* IMax calls the nonzero service; a necessarily-nonzero right operand tail-calls
  Max. Otherwise right-zero, left-zero/one and equal-operand rules apply before
  raw allocation. This includes symbolic potentially-zero arguments.

The Boolean emitter `level_constructor_rules.py` emits no Python evaluator or
runtime reduction callback. Private continuations are derived in weights, not
loaded from proof data. A syntax-only packer relocates additional raw operand
roots; these roots are never comparison, normalization or admission answers.
A raw-substitution-then-comparison wrapper exercises allocation of duplicate
structures and calls the same comparator, without requiring input hash-consing.

Standalone wrappers return operation DONE/INVALID/RESOURCE. They do not run
proof/declaration admission. Dependent inference and checked environment callers are subsequent integration
work.
There is no additional native source theorem/mathlib coverage from these
operator contracts, and no full-kernel or formal-verification claim.

Source instantiation is now lowered separately from RAW substitution. Changed
Max/IMax children call the smart constructors; untouched source/replacement
syntax is not globally normalized. Both standalone levels and all-Expr scheme
callers share these routines. The total structural base/offset-last comparator
is also weighted and handles arbitrary nested Max/IMax bases with private pair
continuations. Its stable symbol-ID ordering can differ from Lean host name
ordering; canonicalization/equality must use the SAME order consistently within
an artifact. [Focused stock evidence](../../benchmarks/kernel-source-instantiation-stock/README.md).
Canonical normalization and equivalence now call these SAME shared operations.

The complete weighted normalizer now traverses all five admitted level tags
bottom-up. Normalized Max arguments use a reusable merge of sorted right chains
instead of host buffers/sort: structural-base matches retain the largest offset,
a deferred explicit argument is retained only when no nonexplicit offset
subsumes it, and a private reverse list reconstructs the canonical chain.
This is an implementation of the complete flatten/sort/deduplicate algorithm,
not a bound on argument count. Successor distribution preserves that order and
calls the same all-tag walker. IMax normalizes its children, calls the same smart
constructor and merges any resulting Max. Equivalence normalizes both sides
then calls the same structural comparator, including duplicate native DAGs.
No expected normal forms/equivalence answers enter native input.

[Focused stock normalization evidence](../../benchmarks/kernel-level-normalization-stock/README.md)
checks exact registers/cache and independently reconstructed outputs at the SAME
physical capacities/fuel as earlier services. HEAP/STACK/FUEL exhaustion remains
RESOURCE, never a negative semantic answer. The source conservative `is_geq_core` is now lowered as described below; typed
checking/environment/admission callers remain unfinished in weights.

The COMPLETE pinned conservative `is_geq/is_geq_core` now normalizes both sides
through the same normalizer before its pair traversal. Private AND continuations
handle right Max/IMax; left Max alternatives short-circuit on success and preserve
the source fallback to remaining IMax/offset rules on failure. Offset comparison
uses the same separator/structural equality and recursively compares bases when
both offsets are equal and positive. It does not substitute numeric assignments
for symbolic reasoning. [Focused stock evidence](../../benchmarks/kernel-level-geq-stock/README.md)
includes the nontrivial Max-to-IMax fallback and explicit fixed-fuel costs.
All these entries are operation services, not declaration admission answers.
