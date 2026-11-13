# Expression representation comparison and conversion callers

Source authority is pinned Lean4.31 `src/kernel/expr_eq_fn.cpp:expr_eq_fn::apply`
and `type_checker.cpp:is_def_eq_core`. Comparison traverses finite Expr tags;
children, names, vector lengths and indices are data. Native allocation is not
hash-consed, so pointer identity can only be a fast path.

The compiler representation erases binder names, metadata payloads and the Let
nondep optimization flag. Its comparator checks representation equality, not
byte-for-byte original Lean Expr identity. Binder info is ignored as in source
`expr_eq_fn<false>`. This is a positive equality test for conversion; a false
result NEVER establishes definitional inequality. The full conversion caller
must continue through reduction, typed proof irrelevance and eta rules.

Complete algorithm to lower: compare tags; BVar/Local compare identity words;
Sort calls the SAME structural level comparator; Const compares symbol and
universe vector; App/Pi/Lam compare all children using private pair continuations;
Let compares all three children; Proj compares symbol/index and its expression;
MData compares its represented child; Nat/String compare every limb/byte. Typed
vectors compare length/role and stream corresponding cells, calling the SAME
level comparator for universe entries. No host equality/normal-form/admission
answer is transported, and no argument-count/name/field-count paths are added.

All comparison frames are private state produced in weights. Syntax capsules
transport raw expression roots only. This service is now lowered through the shared stock controller, with
[focused exact-state evidence](../../benchmarks/kernel-expression-comparison-stock/README.md).
It is not full typed inference, conversion, declaration admission or theorem coverage.

A composed source-instantiation/comparison wrapper creates fresh result syntax
and invokes the SAME comparator. The second raw operand root is preserved across
smart-constructor calls; no equality result is supplied. This checks duplicate
runtime level/vector structures as well as mismatches. Complete conversion may
use true as a positive shortcut but must never turn false into a rejection.
