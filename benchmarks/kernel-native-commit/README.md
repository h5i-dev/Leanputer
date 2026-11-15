# Shared stock shadow merge and dirty commit

Extends the fixed stock module; this is NOT original-source admission. No host
micro-op dispatch, checker answer, cache mutation, CPU ISA or proof specialization.
The kernel source generators and data domain remain unchanged.

Native actions now include16bit bitwise AND/OR/XOR and one-bit shifts; a fixed
three-assignment field descriptor; idempotent OR-shadow updates; a model-owned
unique dirty-field queue; and queued publication with dirty-bit clearing. One
new field takes2forwards, an already-dirty field1, commit2per dirty field plus
one exit. All simultaneous expressions read the immutable old main state.

The three RF read copies now each have512rows (four heads): even/odd rows0..271
interleave136 main/shadow rows,272..407 hold136 queue rows with seven16bit entries,
408..508 provide707 temporary words,509..511 are reserved for pending arena
buffers (not integrated yet). Only951 fields can enqueue; references are11bit
logical main word addresses. Payloads and counter updates are binary, not rounded
large packed residuals. The heap512/stack32/context8/constants4/word16 bounds stay
unchanged. Source public environment transaction semantics remain in the rules.

Actual small module shape H768/I256/L48 =52,231,008 dense parameters,737channels
(511features+213scratch+13ballast/tau),39occupied graph layers in35data stages.
The proposed100M ceiling has not been established for a full checker. At49,275
records the same partial shape would be76,124,812parameters/L70; complete native
encoding, wide operands, bitfields, arena buffering, source address prologue and
final outcome publication still have to fit. No stock original-source result yet.

queue.log tests two runtime claim items, OR duplicate assignments, unique queue
entries crossing seven-entry row boundaries,8dirty fields, two transactions,
all RF replicas and preservation of old main values. bits.log checks the shared
word bit/shift lanes. Previous arithmetic/ROM/arena checks remain applicable and
were rerun only because these paths changed. These are targeted module checks,
not a broad kernel differential campaign. Whole-program latency remains a blocker.
