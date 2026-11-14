# Nat/String literal algorithms and native integration

Authority: pinned `Lean/Expr.lean:Literal.type`,
`inductive.cpp:nat_lit_to_constructor,string_lit_to_constructor`, and
`type_checker.cpp:reduce_nat,reduce_pow`. These genuine kernel interfaces are
finite. Ordinary inductive source still follows the complete general transaction;
there is no ordinary per-name/field-count admission rule.

## Current connected implementation

`nat_literal_rules.py` connects original Nat literal inference and generic
recursor-major preparation. It content-interns the genuine Nat/zero/succ names,
requires checked signatures and zero-universe arities, compares their required
types through the general conversion service, and checks family provenance and
constructor membership. An unavailable/incompatible primitive binding GAPs; an
ordinary inductive with a different constructor shape is still checked normally.
The source environment is immutable after publication except the disjoint genuine
Quot initialization, so validated Nat bindings can be reused in that source run.
Source initialization resets the cache; input cannot provide it.

The literal is a canonical little-endian vector of arbitrary16bit limbs.
Inference validates every limb/link/count and returns checked Nat. Preparation
maps0to the checked zero constructor, otherwise computes the predecessor by a
generic borrow scan, removes a leading zero limb, reverses the accumulated vector
and constructs the checked successor application. No host integer or inference
answer is loaded. A required65535limb that cannot fit a narrow physical word
reports RESOURCE INDEX. Only capacities bound operand length.

The original-source test forms Nat with the general inductive transaction and
checks a literal-bearing generated recursor computation at0,1,65536,2^160, and
2^128+17. It covers repeated borrow, highest-limb removal and carry termination
inside an arbitrary vector. Independent EnvironmentDriver accepts all five and
all public schemes/RHS match;143SELECTED Boolean transitions compare every
register/bank. Initial four-case pass was22.565s/141selected; the final integrated
regression log records the five-case test plus Quot/restored-owner regressions.
Missing, empty and differently shaped ordinary Nat bindings GAP only at literal
use. A twelve-bit physical-word predecessor borrow reports RESOURCE INDEX.
Four additional selected terminal transitions match the Boolean program.
This is source semantic/selected IR evidence, not Nat STOCK or full arithmetic.

## Nat arithmetic integration

The subsequent [native arithmetic controller](nat-arithmetic-plan.md) connects
all15pinned Nat operations and typed zero/successor offset conversion through
original-source WHNF and general conversion. Numeric candidates and exact arity
are recognized before requiring primitive bindings; ordinary declarations with
these names and neutral operands still reach their ordinary delta bodies.
Constant-headed canonical-form negatives no longer blanket GAP after the
completed Nat/Quot/offset paths. String literal cases still GAP.

`literal_reference.py` remains independent development SPEC, never a native
inference callback. Its Python integer/math operations supply expected semantics
only; weighted arithmetic uses arbitrary private bit/limb loops. Source/selected
IR evidence and physical/semantic limits are recorded with the controller.
No new Nat STOCK or SMALL-model evidence is claimed.

## Remaining integration

String literal binding/type, UTF8 scalar decoding and Char/List/String helper
construction, projection preparation and literal conversion remain GAP. Their
bootstrap/helper dependencies are being audited against pinned safe original
sources. No supplied String constructor certificate is accepted. Syntax export
currently records the implicit Nat/String type dependency from Literal.type;
String construction will also need the genuine implicit helper closure.
Quot initialization overwriting already committed ordinary bindings explicitly
GAPs until dependent-prefix/registry invalidation is implemented; repeated claims
after actual initialization remain idempotent. Private metadata gaps remain
explicit. The compiler targets unmodified stock forward/cache with identity
feedback. The10.35B historical STOCK smoke does not meet the SMALL-model target.
