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
Inference validates every limb/link/count and returns checked Nat using only
the checked monomorphic Type0 signature. The shared literal_type_rules.py
implements that type check for Nat and String. Constructor membership/signatures
are checked separately when preparation/arithmetic requires them. Preparation
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
Missing Nat type bindings GAP at literal typing. Empty/differently shaped Nat
inductives can still type a literal; their unsupported primitive constructor
interface GAPs when a reduction needs it. A twelve-bit physical-word predecessor borrow reports RESOURCE INDEX.
Four additional selected terminal transitions match the Boolean program.
This is source semantic/selected IR evidence, not Nat STOCK or full arithmetic.

## Nat arithmetic integration

The subsequent [native arithmetic controller](nat-arithmetic-plan.md) connects
all15pinned Nat operations and typed zero/successor offset conversion through
original-source WHNF and general conversion. Numeric candidates and exact arity
are recognized before requiring primitive bindings; ordinary declarations with
these names and neutral operands still reach their ordinary delta bodies.
Constant-headed canonical-form negatives no longer blanket GAP after the
completed Nat/Quot/offset paths. String paths are connected as described below.

`literal_reference.py` remains independent development SPEC, never a native
inference callback. Its Python integer/math operations supply expected semantics
only; weighted arithmetic uses arbitrary private bit/limb loops. Source/selected
IR evidence and physical/semantic limits are recorded with the controller.
No new Nat STOCK or SMALL-model evidence is claimed.

## String integration and remaining boundaries

The [String controller](string-native.md) connects original-byte scalar decoding,
checked helper signatures, typing, contextual projection/recursor preparation
and the pinned String.ofList conversion extension. No String layout or supplied
constructor certificate is trusted. The syntax exporter includes the implicit
Nat/String type and Char.ofNat/String.ofList helper dependencies. Unavailable or
incompatible expansion helpers remain explicit GAP when expansion is needed;
literal typing itself checks only String and permits helper bootstrap literals; the decoder requires at least a16bit physical word (otherwise RESOURCE).
Quot initialization overwriting already committed ordinary bindings explicitly
GAPs until dependent-prefix/registry invalidation is implemented; repeated claims
after actual initialization remain idempotent. Private metadata gaps remain
explicit. The compiler targets unmodified stock forward/cache with identity
feedback. The10.35B historical STOCK smoke does not meet the SMALL-model target.

The shared literal-type refinement and String integration pass the final targeted
7test542.320s run (benchmarks/kernel-string-ir/final-literals.log). Nat typing now
accepts an already checked empty or differently shaped Nat family without claiming
that its constructor interface supports primitive reduction. Five recursor-major
values pass241SELECTED all-state Boolean transitions; four type/missing/borrow
terminal transitions also match. Historical143selected counts above predate this
refinement. String helper-bootstrap typing is independently checked as described
in the linked controller. No additional STOCK evidence is implied.
