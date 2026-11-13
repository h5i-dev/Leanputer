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
normalization/equivalence/order target already has an executable development
spec in `levels.py`, but its stock integration remains unfinished.

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
proof/declaration admission. Canonical normalization/equivalence, dependent
inference and checked environment callers are subsequent integration work.
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
Canonical normalization and equivalence are still subsequent integrations.
