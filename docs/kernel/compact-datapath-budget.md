# Current bounded stock result and open delivery gate

The corrected full current-rule model at d3250a9 has actual matched original-source
accept/reject evidence: 48,290,654 dense parameters, 230432forwards/800.1316s, and
all951registers/allbanks equal to SPEC checked after inference. Inputs/code/runtime
are pinned in [the audited evidence](../../benchmarks/kernel-control-speed/README.md).
The proposed100M dense size ceiling is met for word16/heap512/stack32/context8/
constants4/fuel8192. **Practical latency is not delivered: 13.3minutes for this tiny
pair is unacceptable.** No repeat without materially improved projected cost.
General semantic GAPs and larger/nested-source native coverage remain open; the
historical statements below are superseded only for this bounded stock result.

# Current emitted whole-rule budget (2026-11-15)

The proposed <=100M logical dense gate is met by the current fixed program at
**48,290,654 parameters**, H768 / I256 / L65, 755 allocated residual channels.
This is within the intended 10–50M working range for the current bounded domain;
it does not establish larger-domain coverage or close semantic gaps. Weight
parameters occupy 96,581,308 bytes in BF16, before model buffers and native caches.

All 73 rule families / 6,454 effects map into 46,608 fixed 112-bit records:
39,210 body records, 7,200 indexed entries and 198 alignment records. PC width is
16 bits. The source/namespace/shape/count data are not compiler selection keys.
The model has 22 byte-page ROM stages, 7 byte decoder stages, 19 active GDN memory
layers, the shared operator/commit computation, scratch clearing and one inert
final feedback boundary. Active memory heads may share layers with FFN work;
these counts are not additive. The remaining 46 layers use tiny stock attention
with zero outputs. All stock FFN operations remain present.

With H=768 and I=256, the exact logical count is
19*(3HI+644H+1666) + 46*(3HI+12H+4) + 129H.
The global term includes both 64-token embedding/output matrices and final norm.
This counts every dense parameter, including zeros, without CSR discounts.

The semantic domain remains word16 / heap512 four-word rows / stack32 six-word
rows / context8 / constants4 six-word rows / fuel8192. It is the same domain as
the matched original-source baseline, not a reduced proof-specific domain.
The RF has 512 rows per read copy, 126 binary payload bits per row and 3 coherent
copies (12 GDN heads). Seven arena heads serve heap/frame/context/declarations.
Main and shadow use 136 rows each, 136 rows hold the unique-field dirty queue,
101 rows hold compiler/source temporaries and three rows hold arena write buffers.
There are 707 physical temporary words, with 11 source-port padding words and
696 usable indexed words. Field merges take one forward for an already dirty
field or two for a new field; commit takes two forwards per dirty field plus exit.
The dirty-row commit alternative was tested and preserved but is not selected:
its ~1.8% forward saving did not justify the additional protocol complexity.

The two original source cases have exact OFFLINE all-state counts of
225,506 / 230,425 native forwards (1,316 / 1,355 semantic steps). A 128-forward
actual stock prefix exactly matches eager hidden/cache tensors/logits and runs at
288.39 forwards/s, with 138.91s setup. The longer current projection is ~799s of
decoding plus setup/build/prefill. This is conditional, not whole-source evidence.
A cold production-run hook-installation compilation error was found before any
decoding and fixed with a restored eager stock warmup; its cold-prefix check is
pending. Whole small-stock source acceptance/rejection remains unvalidated here.
The inference runner reports actual parameter/cache tensor bytes and boot packet
counts from the instantiated stock model, separately from these analytical counts.

Earlier design assessment follows and is historical where it differs.

# Compact checker datapath: current result and original assessment

Superseding implementation evidence: [typed-control-store.md](typed-control-store.md).
The full current bounded controller now emits64192native records into an actual
83,727,386 dense stock model (H768/I256/L77),768/768channels used. OFFLINE full
native-record execution matches both complete original-source traces. Actual
stock module checks pass; full-source stock run is ongoing, not validated yet.
The proposed100M dense SIZE gate is met for this emitted current-domain artifact;
practical LATENCY is not: observed~9.2forwards/s and1.22M required forwards imply
~37hours if that rate persists. This is not delivery of the requested small,
practical general tool. Semantic gaps and larger operating bounds remain explicit.

The assessment below is HISTORICAL7831b13. Its flat-ROM16K ceiling,384row RF plan,
static commit-list proposal and662channel subtotal were superseded by paged byte
weight-ROM,512row RF, dynamic dirty queue, separate pending packet and measured
lifetime allocation. Do not use that preliminary table as current accounting.

# Compact checker datapath: architecture feasibility gate

This is an analytical design, not an implemented small checker. Stop further
large candidate emission. Keep validated 4d4c063 and all pending failed-layout
edits. The proposed engineering ceiling is **100M logical dense parameters**,
with 10–50M desirable where feasible; these are assessment budgets, not an agreed
requirement or a demonstrated result. This design does not substantiate10M.

The present all-phase combinational lowering should be retired as the primary
small-model path. Keep its general kernel algorithms, source mapping, Boolean
correspondence tests and source-validated stock baseline. Packing, CSR storage
and local allocation changes do not establish the required roughly 82-fold
reduction from the 8.128B validated model.

## What to learn from Qwenputer

Inspected the actual MIT-licensed checkout at
`/mnt/scratch/leanputer-references/qwenputer`, commit
`0cab57038a8b218dabe481f994174c3437405e3d`:
`experimental/riscv/chipformer/rv/core.py`, `rv/spec.py`, `rv/ref.py`,
`q35/emit.py`, and `docs/rv32.md`. In `core.py`, control/PC precedes ROM fetch,
three register-file read ports feed a common ALU, RAM follows, and writeback
commits a record. Division and digit operations span multiple tokens. We
vendored its emitter utilities; our present controller did not adopt this
shared datapath/time decomposition. That was a substantive architecture miss.

The documentation attributes the 11-layer/H2816/1,040,595-nonzero P2 circuit to
3c33d0f. That old commit object is absent in this checkout; the inspected source
is0cab570. The same document reports a stock standalone P2 model of 2,112M
parameters, including its large vocabulary and target widths. Neither its
nonzeros nor11 layers prove a100M dense architecture. Its Triton executor and
host snapshot/reference machinery are not proposed Leanputer inference paths.

## Fixed kernel-specific machine

Compile the pinned general Lean algorithms into an immutable typed kernel
control store. Expressions, universe schemes, names, declarations and their
sizes remain input data. The control store contains only the checker program;
it cannot be supplied or changed by a proof. It is not RV firmware or a generic
CPU/gate interpreter. Scalar arithmetic supports kernel operations; it does not
introduce an application ISA. No trusted typing, normalization, recursor or
admission result is input metadata.

Use one16 bit add/subtract/carry lane, one equality/order lane, bitwise Boolean
and one-bit shift lanes, and a shared row/word selector. Kernel-specific actions
reuse these for AST/tag inspection and construction, arena bounds/allocation,
context access, continuation frames, register-delta merging, branch/service
control and checked publication. Variable shifts and larger literal operations
use bounded micro-record loops. The source algorithms still determine all
universe, conversion, inductive, literal and Quot behavior; no operator implements
a name/shape catalog. Eight functional groups are budgeted, with at most 64
encoded action/variant values. A complete mapping to those groups is NOT done.

The model owns phase PC, microstage, predicates, carries and pending writes.
The host loads syntax, then repeats the same unmodified stock Qwen3.5 forward
with its cache and identity hidden feedback. It may observe model completion;
it never fetches/decodes a control record, selects a semantic circuit, runs an
ALU, checks a type, or initializes a program-specific cache snapshot.

## State and memory budget at the current matched bounds

Preserve word16, heap512 four-word cells, stack32 six-word frames, context8,
constants4 six-word declarations and semantic fuel8192. Original arbitrary-size
Nat values remain vectors of 16 bit limbs limited by arena space. This is the
existing small integration domain, not native admission of the larger nested
fixture or all Lean inputs. Growing these bounds requires new accounting.

All native cache payloads are binary. One128-by128 GatedDeltaNet head uses two
ballast columns and at most 126 data bits per row:

| Store | Physical layout | Heads per port |
|---|---|---:|
| Heap |512 rows ×64 bits |4|
| Semantic stack |32 rows ×96 bits |1|
| Context |8 rows ×16 bits |1|
| Raw declarations |4 rows ×96 bits |1|
| Checker register file |384 rows,7×16 bit words +7 dirty bits per row |3|

RF rows0–135 hold all 951 current semantic words,136–271 hold shadow words,
and 272–383 provide784 temporary words. Padding is explicit. Three RF read ports
replicate this complete RF: source A, source B and destination row. Writes are
broadcast to all three copies using model-owned pending packets. Thus9 RF heads
plus 7 arena heads require16 active memory layers. There is no uncounted host
register file, continuation stack or write queue.

Use a compiler-produced commit list per semantic phase instead of a dynamic
queue. Every active field assignment merges into its shadow word with the
original bitwise-OR semantics, initializing from zero on its first dirty write.
The commit tail reads the shadow and old destination, patches the main RF row,
then clears the dirty flag. Unchanged fields retain their old word. No next
semantic phase can read partially committed state. The current algorithms'
public-environment commit fence and failure behavior remain required. Proving
complete commit lists and alias-safe operand scheduling is an open compiler
obligation, not trusted metadata.

Proposed residual allocation at H768:

| Resident purpose | Channels |
|---|---:|
| Phase PC and microstage |20|
| Status/reason output |32|
| A/B/result words, byte aliases and carry flags |62|
| Shared read/modify/write row and pending address/control |142|
| Control record and valid bit |113|
| Predicates and transaction flags |16|
| Query page/row/word address |14|
| Operator temporaries |128|
| Bootstrap control |19|
| Public result pointer |16|
| **Data subtotal** |**662**|
| Ballast12 and reserved tau1 |13|
| **Unassigned margin** |**93**|

Row reads and writes share one buffer at different microstages. Source RF ports
project only their selected word; the destination port supplies the full row.
Address one-hot tests are direct q/k projection forms as in upstream, not128
persistent Boolean wires per port. The662-channel plan is not a proven live-range
allocation. If it requires H1024, the 16K-record design rises to 131.86M and fails
this gate. Spilling or an extra microstage must be accounted rather than silently
increasing width or narrowing data.

## Control store in weights and exact dense shapes

A112 bit record can contain a6 bit action, three12 bit physical RF operand addresses,
a16 bit immediate, two16 bit successors,6 flag bits,3memory-space bits and 13 reserved
bits. An RF address is page2/row7/slot3; unassigned slots are invalid. Long
operations and compound actions occupy additional records, which count.

ROM uses ordinary SwiGLU comparators against the model's16 PC bits. Each record
has one exact match unit; down projections write its constant112 bits and valid
bit. There are256 records per MLP layer. Only one record matches; invalid PCs
must fault explicitly. All program information is compiler-generated weights,
with no host ROM lookup, program cache initialization or proof specialization.

Budget22 datapath layers: RF A pages1–3, B4–6, destination7–9; heap10–13,
stack14, constants15, context16; final arithmetic/guards/writeback17–22. ALU work
can overlap the earlier destination/RAM stages when operands are ready. Add four
protocol/reset layers and one final output layer. This schedule and the 256-unit
MLP capacity still need an actual emission proof.

Use stock Qwen3_5ForCausalLM with H768, intermediate256, one128-dimensional key
and value head,64 output vocabulary rows, untied embeddings, no backbone.
**All layers are GatedDeltaNet**, including inactive ROM/protocol heads. This
counts their parameters and avoids accumulating full-attention KV history over
long microprogram runs. A custom executor/cache is not assumed.

For N records, L=ceil(N/256)+27. The local installed stock model constructors
confirm the complete logical count on meta tensors:

`P = L × (3HI + 644H + 1666) + 129H`.

The644H includes all GDN projections and two layer norms;1666 includes depthwise
convolution, GDN norm and decay parameters. The last term counts both embedding
matrices and final norm. Zeros count in full.

| Control records | Layers | Logical dense parameters | BF16 parameter bytes |
|---:|---:|---:|---:|
|4,096|43|46,800,598|93,601,196|
|6,144|51|55,489,254|110,978,508|
|8,192|59|64,177,910|128,355,820|
|16,384|91|98,932,534|197,865,068|
|17,920|97|105,449,026|210,898,052|

The intended10–50M range requires roughly 4K records under this plan. The100M
ceiling permits 16K;17.9K fails. These are independently counted stock **meta
shapes**, not generated datapath weights or successful native checks.

At91 layers, recurrent FP32 cache is5,963,776 bytes per item, plus about279,552 bytes
of BF16 convolution state, activations and framework workspaces. Inactive heads
are still included. Cache size does not grow with microstep history.

Numerical assumptions remain explicit: stock RMSNorm uses 12 ballast channels
at 2^40, so H/m=64 gives a power-of-two scale; integer SiLU tests use K128.
GDN rows retain the existing two2^24 ballast columns and binary data scaled
by2^7. Arbitrary-byte cache storage is excluded: the earlier local codec read7
as6.96875. Words remain binary or bounded digits, never a16 bit floating scalar.
Every projection, GLU product, MLP sum and residual addition needs an exactness
bound, including slot clears. A representable final word does not certify its
intermediates, as the failed327-to 328 handover demonstrated. These conventions
have baseline evidence; the new width/ports/schedule still need native evidence.

## Forward/commit budget and feasibility limits

An ordinary record fetches its own control, reads A/B/destination through the
three ports, operates and prepares a pending write in ONE stock forward. The
next forward flushes that write before reads. The22-layer schedule is a design
constraint, not measured execution. Effects requiring several row accesses,
large literals or carry/shift loops expand into explicit records; they cannot
be counted as one unbounded "kernel operation".

For a semantic transition let Q be its executed ordinary records, C the number
of candidate words in its compiled commit list, and W the deferred arena row
writes. The proposed upper budget is `Q + 2C + 2W + 2` stock forwards, plus syntax
boot and final flush. Counts include model-owned skips/guards and commit cleanup.
No new semantic RESOURCE cutoff is authorized to make this budget hold.

| Hypothetical Q/C/W | Forwards per old semantic step | Good witness1316 steps | Bad witness1355 steps |
|---|---:|---:|---:|
|8 /4 /1|20|26,320|27,100|
|32 /16 /3|72|94,752|97,560|

These are scenarios, NOT a measured or proven translation. The latter budget
would mean589,824 forwards at semantic fuel8192. This may be too slow under
stock fallbacks; fitting100M is not by itself practical delivery. No ETA or
speedup is inferred from Qwenputer's alternate executor.

Static accounting of the complete current source controller gives 951 semantic
words,13,243 field assignments (13,237 distinct guard/word choices),719 heap,
679 stack and 11 context write choices, and 145,449 Boolean gates. Literal
assignment translation already needs13.2K records before guards/arithmetic.
Literal Boolean-gate microcode exceeds the 16K budget and is not the proposed
kernel-specific lowering. Structured service/phase lowering and shared calls
must demonstrably reduce this, with all general rules retained.

For the two already-validated source fixtures, SPEC accounting after that
baseline finds means3.90/3.88 changed register words per transition, max12 each,
and at most 3 changed arena rows. Changed values do not count active assignments,
guard evaluation, commit-list candidates or micro-records. They do not prove the
20/72-forward scenarios or full-kernel worst cases.

The old model's1122 persistent and 9778 allocated channels exceed H768. Moving
state into RF and actually reusing operators is essential; these old lifetimes
cannot simply be overlaid unchanged. There is currently no evidence that every
kernel phase fits784 RF temporaries, the 662 resident channels,16K records and
the proposed latency budget simultaneously. Code/control growth, spills,
compound-field operations and two-batch numeric exactness are precise open gates.

## Next permitted checkpoint

Before another complete model: produce the typed control-store representation
and input-independent full-program record/operand/commit accounting; explicitly
identify unmapped rules. Then one short general AST/context/stack operation
prototype may test RF three-port coherence, ROM fetch, byte arithmetic bounds,
shadow OR updates and continuation/writeback through unchanged stock forward.
It must use operands/names as data and compare acceptance/rejection or full
operation states after inference, including the two-item case that broke the
current candidate. No full-size retry, unrelated feature or broad campaign is
needed for this gate. Do not claim a small full checker until both mapping and
matched whole-source evidence exist.

Reproducible counts: [budget data and scripts](../../benchmarks/kernel-datapath-budget/README.md).
