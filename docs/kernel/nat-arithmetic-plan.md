# Native Nat arithmetic and offset conversion

Authority: pinned `type_checker.cpp:569–687,943–970`, `inductive.cpp` literal
preparation, and the existing source/generic recursor algorithms. This file began
as the integration plan; the algorithms below are now connected. Evidence is
semantic/selected Boolean IR, outside the frozen STOCK reports.

The genuine C++ interfaces are exactly Nat.succ/add/sub/mul/pow/gcd/mod/div/beq/
ble/land/lor/xor/shiftLeft/shiftRight. A fixed structured-name byte trie recognizes
these intrinsic hooks and Nat.zero's numeric-operand role. Ordinary names,
declaration counts/shapes and all nonprimitive operations remain data. Nat.zero
is never dispatched as an arithmetic opcode. Const universe vectors must be
empty; arity is exactly1for successor and2otherwise.

`nat_bridge_rules.py` intercepts checked constant WHNF before ordinary delta.
`nat_reduce_rules.py` first checks arity, normalizes and recognizes numeric
candidates, then validates the required checked Nat/Bool/function signatures.
An ordinary declaration named Nat.add over propositions, with no Nat datatype,
still checks and unfolds normally. This is required by the pinned algorithm;
name classification alone cannot impose a primitive declaration catalog.

Parent arguments, checked signature, operation and converted operands survive
recursive WHNF in immutable owned records. The gather bridge saves an immutable
ordinary fallback(scheme,type,head). A successful primitive consumes its pending
application once. A neutral result restores the original checked lookup frame,
all pending arguments and ordinary delta. The semantic pow cap behaves this way;
it is never confused with a zero result or physical resource failure.

`nat_bits_rules.py` uses canonical arbitrary little-endian bit vectors and16bit
limb transport. Counted scans implement add/borrow/saturated subtraction,
comparison, bitwise operations, shifts and conversion; low-bit pushes share
higher tails. `nat_high_rules.py` implements shift/add multiplication, MSB binary
long division, Euclid and repeated squaring. Parent loop records remain immutable
across recursive child arithmetic. No external integer answer, proof-supplied
instruction tape, generic CPU/RISC-V emulation or pretrained backbone is used.
These fixed operations lower through the same Boolean/compiler/stock backend.
Output-only cells207..211 and arithmetic internal tasks are never raw input.

Division by0returns0; modulus by0returns the dividend. Exponents above1<<24
return neutral so ordinary delta may proceed. Shift counts are arbitrary Nat
vectors: a count larger than the physical word yields0for right shift,0for left
shift of0, otherwise RESOURCE INDEX because the nonzero result cannot fit.
All other heap/word/stack/fuel failures remain RESOURCE; no wrapped result is an
accepted value. Operand precision is limited only by physical capacities.

`nat_offset_rules.py` implements typed literal/zero/successor offset comparison.
It validates the finite Nat interface, compares literal predecessors recursively,
and decides checked zero/successor disjointness. General conversion still owns
proof irrelevance, binder/app congruence, function/structure eta, projections,
unit-like equality and context restoration. Completed Nat/Quot reductions and
offset rules precede final canonical-form negatives. The subsequent
[String controller](string-native.md) connects String cases; unavailable private
metadata still propagates GAP.

The original-source test checks general Nat/Eq/Bool blocks, ordinary function
bindings and genuine Quot initialization/claims before target checking. Function
bindings have simple checked bodies intentionally: pinned reduce_nat takes
precedence on numeric operands, while neutral/capped applications still use the
ordinary body. This is synthetic original source, not exported Std implementation
body admission. Sources require all arithmetic operations, mixed Quot/Nat/generic
Bool recursor normalization, true/false predicates, multi-limb multiply/divide,
semantic pow-cap fallback and zero/literal equality. Every public scheme/RHS
matches independent SPEC and no assumptions are used. Selected Boolean checks
compare every register and bank, including owned returns. Negative offset proofs
reject; enormous shifts return either correct0or explicit physical RESOURCE.
Raw logs and exact counts are archived in the checkpoint benchmark directory.
No complete-step Boolean or Nat STOCK evidence is claimed.

Remaining: String helper bootstrap/unavailable bindings (see linked controller);
nested copying of a partially replaced mutual family after Quot initialization
(explicit metadata GAP; ordinary replacement now follows the pinned map rules);
private metadata boundaries;
SMALL-model architecture and full nested-source STOCK capacity. The historical
10.35B source STOCK smoke is not the requested small model. No broad corpus,
fuzzing/profile or optimization campaign, coverage percentage or ETA is claimed.
