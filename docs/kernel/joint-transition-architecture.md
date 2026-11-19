Immediate delivery milestone (explicit user instruction, 2026-11-19): approximately 4,000 TOTAL stock forwards per original source case is acceptable, with <=48,290,654 dense parameters and unchanged generic rules/input domain. This supersedes the previous ~2,300 hard forward gate. Delivery requires an emitted complete model and actual matched GPU accept/reject, with boot/check/total counts and measured latency separate. Offline estimates and standalone operators are not delivery.

# Joint target and present conclusion

The authoritative gate is <=48,290,654 logical dense parameters and approximately
<=2300 stock forward calls for the same original-source batch, including syntax
boot. The actual anchor is d3250a9:48,290,654 parameters,230432 checking forwards.
The existing word-controller backend cannot meet this gate. Its larger80M
preflight candidate is diagnostic and its integrated source prefix FAILED at
forward19 (stockPC37966/reference37965). No speed or source-admission result is
claimed for it. No further such model emission or long run is scheduled.

The proposed replacement executes checker transitions, not scalar instructions.
Arithmetic shape/step allowances fall below the joint limits, but do not yet
describe an implemented schedule. Full-rule feasibility has NOT been established.
The conservative complete-register layout below exceeds the forward allowance;
the earlier2077/2141figures must not be cited as achievable checker counts.
This is not a promised100x result.

# Fixed shared checker datapath

Use stock Qwen3.5 forward/cache, with no pretrained model, host dispatch,
normalization, admission answers, proof-specific program pruning or CPU/Boolean
instruction executor. The host transports unchanged original syntax and applies
identity feedback. All names, declaration counts/shapes, universes and AST tags
remain data. Existing word16/heap512/stack32/context8/constants4/fuel8192 bounds
remain the semantic domain; scratch-layout changes must not restrict that domain.

A compiler-owned semantic phase PC selects an immutable descriptor for a kernel
transition. It carries operand routing, constants, predicates, simultaneous
field/row updates, checked successors and abstract fuel cost. It does not fetch
one descriptor per16bit comparison, register move or dirty-field commit.
Descriptors are generated from ALL kernel algorithms before reading input syntax.
The complete program has a4096-descriptor/256-bit design budget. The current4757
(family,guard) effect groups are NOT these descriptors and cannot establish that
budget. There must be a verified full-rule lowering or this design fails.

Reuse a small hardware set: tagged AST/level row access and construction;
context/environment/block-transaction rows; vector/name/scheme iteration;
inference/WHNF/conversion/recursor rule predicates; continuation call/return;
and bulk masked word/row updates. These are shared kernel operations over data,
not per-declaration/type/name circuits. Complex rules continue through the same
general traversal/call mechanisms. Existing semantic GAPs are not closed by this
architecture proposal and must not become silent acceptance.

Keep procedure state in model-owned activation rows, up to28words per frame
INCLUDING continuation metadata, at depth32. Four GDN value heads share one
one-hot frame key and return/write four7word rows together. A shared global bank
has a224bit design allowance. A source-CFG liveness/ownership proof must establish
both bounds for every routine. Observed28-field updates do not prove a live bound.
If either bound fails, repack/revise within the SAME parameter cap or reject the
architecture; do not narrow the input domain or omit rules.

Use three active GDN key layers, each with four value heads and128x128 state:
heap512 (four pages); activation RF (four word-vector pages); and disjoint
stack32/declaration4/context8 coordinates. Heap, activation and one small-bank
write can commit together. Small-bank frame/context collisions use a model-owned
flush subphase, with the original transition's atomicity and fuel cost retained.
Multiple small-bank reads require a bounded multi-key query plus in-weights
binary rounding; numerical correctness is an UNVERIFIED operator gate.

All frame data is fetched/updated as vectors. One masked Boolean update uses
`mask * (new_bit - old_bit)` in one SwiGLU unit, instead of a sequence of scalar
MOVE/merge/append/commit instructions. Old pending packets die after their heads
consume them; their physical columns are reused by descriptor/ALU scratch and
then by new output packets. This requires explicit SSA/cyclic boundary allocation
and correct write/read timing, not CSR storage or assumed host-side updates.

# Dense shape and layer/column budget

Primary budget: H1536/I192/L44, three active GDN layers,1key/4value heads,head128;
other layers are ordinary zero-output stock attention with head_dim2. RMS ballast
m24 gives m/H=1/64; native norm/activation exactness and any rounding must be tested.
The entire dense shape is counted, including zeros:

GDN layer = 3HI + (258+386V)H +1152+514V =3,655,816.
Other layer =3HI+12H+4 =903,172.
Global embeddings/head =129H =198,144.
Total =3*3,655,816 +41*903,172 +198,144 =48,195,644.
This is95,010 below the actual baseline cap. It is a SHAPE formula, not emitted
full-checker evidence or a discount for sparsity/shared storage.

For4096 descriptors of256bits, byte ROM has32pages and33columns/page including
validity:1056units. At I192 it needs6ROM layers +7decode +1low decoder =14layers.
Early activation/heap heads overlap those ROM stages; small-bank access follows
context-address calculation. A provisional44-layer reservation is14ROM/decode,
3address/memory,3binary-rounding/predicate,11shared-operator,5bulk-feedback,
4scratch-clear, and4dependency/handoff/inert-boundary layers. Each slot must be
scheduled from actual circuits. Operator capacity is2112 physical FFN units
(1848 after reserving24handoff units/layer), not an unlimited operation.

A provisional peak is1534columns:224global +448old RF packet +74heap packet +
103small packet +32control +20deferred-context +448incoming working frame +
128ROM low decoder +32ROM byte accumulators +25ballast/tau. Later phases must
release old packets and descriptor bytes before wider row/ALU values arrive.
There is almost no slack. Actual lifetimes, initialization, residual cancellation,
write forwarding and peak columns must be checked; this bound is not verified.

# Step budget: measured abstract work versus conditional native work

The original sources have1316/1355 reference checker transitions. Existing syntax
boot has692packets/item, packed32tokens/call:22stock prefill calls, NOT692calls.
The actual old execution has five additional setup model calls (hook warmup,
three capture warmups and graph capture). Report those separately too.

A full-transition operator at one forward per old semantic step would need
1316/1355 checking calls, before overhead. The measured longer trace has317stack
write steps,16context writes, seven simultaneous stack+context steps, and a
maximum28register updates. The shorter has308stack writes and eight conflicts.
These are whole-trace costs, not a source-selected operator catalog.

Allow at most two additional spill/restore forwards per stack-write step, one
per small-bank conflict, and one per extra7word update chunk. The measured update
histograms give91/88 wide-update allowances. Conditional totals are:

short:1316+616+8+91=2031; observation rounded32 ->2048check calls.
long:1355+634+7+88=2084; rounded32 ->2112check calls.
Add22boot +5setup +2initialization/publication:2077/2141combined calls.
The longer has159calls of remaining budget. These are CONDITIONAL upper budgets;
there is no implemented full-rule scheduler establishing them. Additional
unaccounted operand fetches, descriptor dispatches, validation or commits must be
charged. If they exceed159calls, or any operator cannot fit its layer/column
budget, the joint design gate FAILS. Reference counts are not stock speed.

Abstract fuel decrements per original semantic transition, not per auxiliary
flush/spill. Publication occurs only after all pieces of a split transition.
The scope/activation-state correspondence must cover all live logical state,
heap/context/environment/stack and outcomes, including RESOURCE/GAP and rollback.
Inactive private fields can be abstracted only after a full CFG liveness proof;
not merely because a particular sample did not use them. All-state/declared
semantic correspondence is checked only AFTER inference against independent
source semantics. The current old951-register equality remains preserved evidence.

# Next substantive gate

First implement/test the shared28word continuation-row protocol (arbitrary word
payloads, depth32, reentrant call/return, previous-packet write timing) with one
stock forward per operator and one-unit masked bulk updates. A few tiny matched
operator tests may establish hardware feasibility, not checker completion.
In parallel implementation order, derive full-rule live-in/out frame contracts
and semantic-transition descriptors from the complete source CFG; enumerate all
73families/6454effects without treating guard groups as macro coverage. Refuse
full model emission until descriptor, frame, layer, column and source-step gates
are explicit and satisfied. No new workers/model changes or broad campaigns.

# Implemented checkpoint and measured limits

The continuation protocol is now implemented in `continuation_operator.py`.
An emitted stock CPU module passes seven fixed forwards on a batch with recursion
depths0/1/3 and stack-overflow rejection. It restores all28arbitrary words and
matches every written memory row across all four value heads after inference.
Actual shape:22,820,572dense parameters,H1536/I192/L22,18graph layers plus3scratch
clear and1inert boundary;2017FFN units,1029allocated channels. A first probe set
Qwen residual RMSNorm gain incorrectly; it failed and was corrected. This is
hardware protocol evidence ONLY, with no source verdict or speed claim.

`transition_contracts.py` now accounts for all73families/6454effects through
2406family-factored regions and125dispatch nodes. Their2337alpha-renamed DAG
templates are compiler IR, NOT a full-transition descriptor count or circuits.
Maximum state inputs are13words; the largest input/update union is33words and
the largest captured region DAG has373nodes. Alternative data guards contribute
to those unions. They do not establish cross-transition liveness or ownership.
One attempt at the Cartesian whole-body control partition hit its45second
diagnostic cap, with no completed root or native result; no repeat is scheduled.

`transition_layout.py` implements a conservative alternative to lifetime-based
erasure: retain ALL951logical words in distinct permanent storage,14feedback
words and34RF rows of28words. Placement is generated from all control regions
BEFORE reading either source. There is no per-proof pruning, aliasing or host
semantic state. This removes the need to assume private stale fields are dead,
but adds row-access work that must be lowered and charged.

On the existing fixed native-control reference, the first frequency-based
global layout requires3895/3972conditional row-access calls, or3932/4008with
boot/setup/conflict/publication allowances. A fixed controller/address global
layout requires5149/5266, or5186/5302combined. Neither meets2300. These are OFFLINE
access accounts, not native schedules or model timing: old word-control guard
initialization still reads inactive private control fields. The reference's
eager all-register preflight dictionary and bounds-latch oracle are excluded;
the actual nine-word weighted gathers are included. Failed dictionary-inclusive
counts and timed-out typed-reference diagnostics remain in scratch logs.

The next joint gate is a checked semantic phase PC and operand-gather schedule
that removes those inactive-control reads while preserving every state word and
all original prefix/body outcomes. A shared selective row-read operator can
reduce gather width, but its ROM controls, write coherence, layer/column peak
and required extra forwards must be accounted together. Until that lowering
exists, the full checker has NO established plan meeting both limits. No large
model is emitted on the basis of the illustrative2077/2141allowances.

## Nov19 resumption audit

The complete source-operator IR retains all73rule families and6454effects. Its
matched original-source runs check every951registers and every bank at each
1316/1355semantic step. This is IR/word-reference correspondence, not stock
inference. The source-derived28private control words share one16bit selector;
explicit carry/update/clear/reload accounting needs no reload on these samples.

The paged RF primitive writes112bits to one selected seven-word physical page,
retains all four value-head pages and supports three/four independent read
replicas. Four saved module/projection checks passed after the Nov19 interpreter
repair (5.967s, CPU); Torch2.8.0+cu128/Transformers5.19.0 and the A10G are available.
Python is now system3.12.15 because the previous3.12.16 interpreter vanished;
the venv package set was preserved. The original failure and symlink/config
backup are saved under architecture-budget/nov19-venv-before.json.

The relaxed4k milestone favors three RF read ports: candidate dense shape
H1152/I128/L78 with6active GDN layers =48,123,600parameters. Prior three-port
conditional access accounts (2461/2525, or2365/2429 with the all-program16global
layout) fit that numerical allowance. They assume a neural transition and page
commit schedule which is NOT implemented. Complete neural kernel-body lowering,
control/descriptor binding, scratch allocation, atomic page commit and original
source GPU validation remain required. No full candidate is emitted merely
because these conditional counts fit. No new stock admission/speed is claimed.
