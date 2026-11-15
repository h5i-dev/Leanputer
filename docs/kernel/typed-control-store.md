# Typed kernel control store and shared stock datapath

Implementation is continuing from7831b13. The all-phase Boolean backend remains
reference evidence. The current implementation adds an input-independent typed
front end by injecting a word builder into the existing general RuleCompiler;
all73 included rule families execute their existing generators. No kernel rule,
name/shape condition, universe scheme or16bit data domain is pruned by a proof.

`control_ir.py` retains words, zero extension, checked-width arithmetic,
selections, slices/splices and structured guards. `control_capture.py` records
register and arena effects with source provenance. `control_store.py` compiles
short-circuit WORD branches, field-merge descriptors and arena chunks; it has no
Boolean-gate or RV opcode. `control_reference.py` and
`control_store_reference.py` are development-only correspondence tools, never
inference callbacks. They are not imported by `stock_datapath.py`.

The complete current capture has6454 grouped effects. All are represented in
control lowering; all73 source family hashes are recorded. Both original-source
fixtures match every register and arena row through the full1316/1355-step
SPEC runs. This is typed IR/reference evidence only. Current full semantic GAPs
remain exactly that; capturing their explicit outcomes does not implement them.

The first complete store required110375records. Factoring common guards,
short-circuit control and bounded three-assignment/three-row-word descriptors
reduces it to46245records, with118 temporary RF words including17ports and32
frozen guard values. The current queue layout provides175 temporary words:
136 main rows +136 shadow rows +87 dirty-queue rows +25 temporary rows =384.
Each queue row holds eleven11bit physical field references. Native queue/merge
microstages and descriptor encoding still need implementation; they are not
trusted host bookkeeping. Multi-item descriptors explicitly count their extra
forwards rather than claiming a free batch of writes.

**Both size and latency FAIL.** The record budget is16384; current software
control execution visits about1.77M/1.82M records for the two source fixtures,
with estimated1.80M/1.85M model forwards after commit work. Walking all phases'
guards is not a practical compact checker. The complete store is not emitted.
Current work is exhaustive kernel-control dispatch/cofactoring over task, mode,
continuation and private-PC fields, including invalid16bit control values.
AST tags, declarations, names, counts and constructor shapes are DATA and are
not specialization keys. The source programs remain input-independent.

The first actual shared hardware module is `stock_datapath.py`:30,509,368 dense
stock parameters,H768/I256/L28, ROM in weights, nine active RF heads, one nibble
adder shared by add/sub/order, equality, and weighted branch/writeback control.
An eight-record fixed program with arbitrary operand/claim data executes in two
items with unchanged stock forward/cache and identity feedback. Word wrap/borrow
and all three RF replicas pass. It is an operator implementation, NOT native
original-source checking or a complete Lean kernel. The real allocation is606
channels (476 fixed features,117 operator scratch,13 ballast/tau);22 datapath
layers suffice for this module. Additional native actions remain explicit.

Two design details are now concrete. First, all-GDN stock calls require explicit
constant shape-only position_ids and mask mappings; automatic cache sequence
length inference otherwise raises. This uses supported stock arguments without
patching modules/cache. Second, the previous RF write packet must remain separate
from the destination read/modify/write row until every RF replica consumes it.
The prototype includes a separate136-channel binary pending packet. A single
shared buffer would overwrite writes partway through the read-port sequence.

The original budget table's listed data rows summed to562, not662. The model
must count the separate136-channel pending packet and queue/control latches
explicitly; H768 remains a constraint to prove, not a width to increase silently.
All FFN intermediate sums as well as residual values need exactness bounds;
arbitrary-byte GDN state and unsafe signed same-MLP handovers remain excluded.

Evidence: [full typed program](../../benchmarks/kernel-typed-control-store/README.md)
and [actual stock module](../../benchmarks/kernel-shared-datapath/README.md).
These are coherent integration checkpoints, not task completion. Next is compact
phase dispatch, complete native action/encoding coverage, then the SAME original
source accept/reject through the small fixed stock model with full state checks.
