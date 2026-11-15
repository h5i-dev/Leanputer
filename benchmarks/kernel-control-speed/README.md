# Latency diagnosis and experimental bundles (not selected)

The completed48.29M/800.13s baseline remains the validated source result below.
No full source run was repeated. A bounded32forward stock sample plus8profile
replays measured11096CUDA kernels (~1387perforward); GEMM/split-K reductions,
attention/cache and pointwise launches dominate. The native negative case spends
55728forwards on body LT dispatch and36039on validation LT checks. Detailed
region/operation counts and the standard PyTorch kernel profile are preserved.

An input-independent global mode partition, followed by bundles of2or3pure
word comparisons, maps all73families/6454effects and matches every source state
OFFLINE at175953/180686forwards (50960records). Full16bit operand values and both
continuations remain; byte-immediate encoding limits fall back to the original
word comparisons. Declaration names/shapes/counts are not specialization keys.

The stock bundle has three RF read ports, AND/OR groups, conditional returns,
parallel full-word carry, and RF reads scheduled before arena lanes reuse them.
Wider stock configs retain exact RMS ballast ratio m/H=1/64; logical parameters
include all dense zeros. The complete experimental model actually emits/loads
**64,099,378dense parameters**, H960/I256/L70,905allocatedchannels. Its256forward
original-source prefix passes ALL eager/replay hidden/cache-tensor/logit checks
and146native-PC boundaries per item after inference. Rate253.52forwards/s,
setup126.19s. The longer reference count projects to~713s of decoding: **insufficient
for the seconds-scale requirement, so this is opt-in, not the selected backend**.
There is no full stock source acceptance claim for this candidate.

The native source driver exposes --bundled-controls for bounded development; its
default retains the validated48.29M layout. Plan-only emission counts the actual
whole graph/ROM/bounds before weight allocation. Standard Torch Triton GEMM
autotuning hit its240s cap before producing timing and is not selected/extended.
This is not a performance delivery claim. Further coarsening of source/validation
operations is required; minor gains and repeated13minute checks do not meet the goal.

Earlier evidence follows.

# Completed small-model source check; latency NOT delivered

The corrected run at **d3250a907f19948f46f414887ea2374e2dfc3b71** completed with
exit 0. The original Empty block, alpha-renamed recursor claim and identity target
are accepted (DONE/NONE/result1); the matched invalid target is rejected
(INVALID/TYPE_MISMATCH/result0). Both cases match **all 951 registers and all
arena banks**, checked by SPEC only after stock inference terminates.

Actual: **230,432 forwards / 800.131630s** decoding; build15.033756s,
syntax prefill12.622695s, capture47.113022s. The completed artifact has
**48,290,654 logical dense parameters**, H768/I256/L65, all73rule families /
6454effects, 46608 fixed records. Weights96,581,308bytes; native cache tensor
storage2,608,208bytes for2items. Domain: word16/heap512/stack32/context8/constants4/
fuel8192. The observed count rounds up the longer native-reference count230425
to the32forward completion-observation interval.

**800seconds for this tiny pair is far too slow. Practical latency remains a
blocking delivery gap.** There is no repeated full run scheduled. Current rate
is ~288forwards/s and ~170native forwards per semantic step. At that rate even a
10second decoding budget would allow only~2880forwards; this is a scale estimate,
not an agreed deadline or promised result. Both scheduling overhead and forward
count require substantial further reduction, preserving the entire rules/domain.

[Result](completed-small-stock.json) and [input/code/runtime audit](completed-small-stock-audit.json)
preserve exact outputs, resource details, launch command, dependency versions and
SHA256s of original source/config/log/report. Both inputs are byte-for-byte equal
to the pinned commit. The raw full log remains in scratch. This is bounded current
source STOCK evidence; it is not complete Lean semantics, larger/nested-source
coverage, or a practical generic tool. Existing target.md semantic GAPs remain.

Earlier checkpoints follow.

# Return-address forwarding correction (2026-11-15)

A static timing audit found a real bug in fused call/immediate-return: the first
handler operation could select the previous model return latch while storing its
new return PC. The late-result module test allowed a retry and missed the extra
forward. The current full source attempt was stopped around 70K forwards; its
partial execution is not admission or native-reference correspondence evidence.
The fix forwards the new encoded return PC on that same operation. The stock
module now asserts the PC at each of the first three forwards for both branch
edges and repeated calls; it passes. The prefix diagnostic also has an optional
AFTER-inference native PC boundary comparison, which never supplies inference
inputs/cache/control/answers. The corrected 512-forward check passes: ALL hidden/cache tensors/logits match
eager/replay, and 370 native instruction PC boundaries match per input. The
reference runs after inference and supplies no model data/control. Replay is
288.61forwards/s; setup49.44s on the cached compiled path. The whole dense
shape remains48,290,654parameters/L65/755channels. A same-pair full retry is
now capped at1200s total; no completed source result yet.
Earlier short prefix eager/replay equality remains scheduling evidence only;
complete small-stock source correctness remains pending the corrected full run.
The earlier cold-production hook-installation error was fixed by a restored eager
stock forward before Dynamo tracing; cold production then ran 512 forwards.

Earlier checkpoints follow.

# Full finite control dispatch (2026-11-15 07:14 UTC)

Fixed enum-selection lowering now recognizes unions of equality cases, preserves
first-match priority for overlaps, shares identical alternatives, and evaluates
only the selected source-address mux branch. Smaller case groups and preflight
selection use the existing bounded native page dispatch. Unknown 16-bit values
retain explicit default paths. These are compiler transforms over the fixed
checker; no input declaration/proof/name is inspected.

All 73 rule families / 6,454 effects map to **46,608 immutable records**, including
135 indexed tables / 7,200 entries / 198 alignment records, within the 16-bit PC.
Complete matched source OFFLINE checks are exact at every state, now using
**225,506 / 230,425 native forwards**. The whole emitted/loaded stock model is
**48,290,654 logical dense parameters**, H768/I256/L65, 19 active GDN layers and
46 tiny stock attention layers, 755 allocated channels. Formula:
19*(3HI+644H+1666) + 46*(3HI+12H+4) + 129H. All semantic bounds are unchanged.

The actual 128-forward stock prefix passes exact ALL hidden/cache-tensor/logit
checks against eager: replay 0.443845s, **288.38885 forwards/s**, setup 138.906s.
This sample enables the installed PyTorch immutable-weight freezing option via
TORCHINDUCTOR_FREEZING=1. This is stock framework compilation, not a custom
executor; weights remain immutable. The different preceding model's rate cannot
establish a freezing speedup. The longer current case projects to 799.0s (~13.3min)
of decoding plus setup/build/prefill. One same-pair full-source check is planned
with a 20-minute total cap, not an hours-long retry or broad campaign. No completed
small-stock source result is claimed before that check terminates and is audited.

The dirty-row commit experiment passed module/correspondence checks but saved
only ~1.8% of forwards and is not selected; patch/logs remain in scratch.
Existing semantic GAPs and larger native-domain coverage remain open.

Earlier checkpoints follow.

# Threaded dispatch and trimmed stock layout (2026-11-15 06:50 UTC)

The full fixed program retains 41,472 records, all 73 rule families / 6,454 effects
and the same semantic bounds. After proving handler depth one, the compiler folds
2,106 calls into their first useful operation and 1,661 return edges into the
operation/branch selecting them. Spare record flags capture the return PC in the
model and return on either branch; no host dispatch or dynamic source pruning.
Both complete source cases still match every SPEC state OFFLINE, now using
**250,596 / 255,937 forwards**, down from 286,472 / 291,870.

Four unused budgeted stages are removed, preserving all scheduled operations,
scratch clearing and an inert final layer at the identity-feedback boundary.
The actual emitted/loaded stock model is **46,493,522 logical dense parameters**,
H768 / I256 / L62, 19 active GDN memories and 43 tiny stock attention blocks,
754 allocated channels. Formula: 19*(3HI+644H+1666) + 43*(3HI+12H+4) + 129H.
The actual stock capture/both-return-edges module passes.

The integrated **128-forward** eager/compiled-CUDA-graph prefix passes exact ALL
hidden-state/cache-tensor/logit checks: eager 14.02298s, replay 0.431312s,
**296.7687 forwards/s**, setup 124.7583s. This is a short stock prefix, not full
source termination. The current longer-case projection is 862.41s (~14.4minutes)
plus setup/build/prefill, conditional on the prefix rate. No long full run is
started at this checkpoint. Next is dirty-row commit to reduce repeated queue
and memory work while preserving simultaneous OR updates and atomic publication.
All semantic GAPs and larger native-domain limits remain explicit.

Earlier checkpoints follow.

# Pending urgent latency integration (2026-11-15 06:34 UTC)

The current implementation preserves all 73 rule families / 6,454 effects and
word16 / heap512 / stack32 / context8 / constants4 / fuel8192. Bulk source-row
loads, bulk buffer clears, conservative canonical temporary-width analysis and
five indexed internal-control pages reduce the matched complete-source OFFLINE
native counts to **286,472 / 291,870 forwards**. All 951 registers and all arena
banks match at every 1,316 / 1,355 source step. There are 41,472 immutable records,
including 560 indexed entries and 249 alignment records; all fit the 16-bit PC.
Tables cover fixed checker controls, with explicit defaults for all other words.
They do not specialize source names, declarations or proof shapes.

The complete rule model now uses 19 active stock GDN layers and 47 stock tiny
full-attention layers whose attention outputs are zero. All active memories and
FFN computations remain. This yields **48,889,698 logical dense parameters**,
H768 / I256 / L66. It is a dense architecture count, not CSR storage. The official
StaticCache gives only the zero-output attention blocks a one-token window;
active GDN caches are unchanged. No custom cache/forward or host dispatch is used.
The parameter formula is 19*(3HI+644H+1666) + 47*(3HI+12H+4) + 129H.

A prior integrated 41,076-record variant of this same shape passed a 32-forward
GPU prefix: 278.94 forwards/s, 136.27s capture/setup; hidden state, logits and ALL
stock cache tensors exactly match eager. This does **not** validate whole-source
termination. The new indexed variant has passed a targeted actual stock module
check for 16/256-entry pages, including 0/15/16/255/256/65535 and all RF replicas;
its bounded GPU prefix hit the 240s wall cap in cold stock compilation after
prefill/eager execution (exit124), before replay timing. No indexed GPU speed
claim is made. The exact canonical-width variant before the
indexed pages used 292,064 / 297,686 forwards in the complete offline checks.

Standard torch.compile (eager BF16 precision casts) and CUDA graph capture include
unmodified stock forward/cache plus identity feedback. Warmup restores both native
tensors and stock sliding-cache scalar metadata. Optional fla-core 0.3.2 uses the
stock Transformers provider mechanism; a separate 64-forward all-GDN check matched
every Torch-native cache tensor/logit/hidden value. fla-core 0.6.0 failed import on
installed Triton 3.4 (missing gluon.language.extra); it is not used. Dependencies
are scratch overlays, with no Torch/Transformers replacement.

**No completed small-stock source admission is claimed.** No hours-long run has
been restarted. Short-prefix projections remain conditional; current larger-domain
native coverage and semantic GAPs in target.md are unchanged. The historical
430e26c checkpoint follows below.

# Whole-rule control and stock scheduling checkpoint

This is performance implementation evidence, NOT completed stock source admission.
The parent terminated the unusable83.7M eager source run at68352forwards; its logs
are preserved. No terminal acceptance/rejection was obtained from that run.

The new fixed control keeps all73source families/6454effects, all16bit control
values including invalid paths, and the same word16/heap512/stack32/context8/
constants4/fuel8192 semantics. Global role/owner dispatch avoids scanning all
families; depth-one model handler calls share continuations. Cached validity
results supply the exact complementary rejection guards. Word selections and
membership sets become balanced comparisons. Source addresses remain independent
typed words instead of packed/shifting transport. Original names/schemes/shapes
remain data. No Boolean/RV emulator, semantic host dispatch or proof pruning.

Native reference:41107records,369708/377631forwards, exact ALL951registers/allbanks
on the same1316/1355source transitions. Handler call depth is statically checked
on all reachable callee branches. The return latch is model-owned. Semantic words
remain16bits; finite native outcome/reason latches use3/6bits with the64bit output
interface padded exactly. A targeted stock call/return+GAP publication check passes.

Two separate stock timing samples (same weights within each eager/replay pair):

*128forwards,82,641,304dense/76layers:13.8464s eager vs1.6389s CUDA graph,
  9.244 vs78.101forwards/s. ALL hidden/cache tensors and logits exact.
*32forwards,71,780,484dense/H768/I256/66layers:3.0275s eager vs0.13585s
  standard torch.compile+CUDA graph,235.55forwards/s;80.11s setup. Same exact
  hidden/cache/logit checks. emulate_precision_casts preserves eager BF16 casts.

The second artifact occupies761channels (504features+244scratch+13ballast/tau).
This is a dense stock model, not CSR. CUDA capture includes unchanged stock
forward/cache operations and identity feedback only; warmup restores native
numeric state without semantic processing or cache replacement. Artifacts use
standard PyTorch compilation, not a custom circuit executor.

At the observed short-prefix rate377631forwards would take~1603s (~27minutes),
plus setup. This extrapolation is not a full-source result or an ETA guarantee.
No long rerun is scheduled. Source ports, guard initialization and commit overhead
are still being reduced. Existing kernel semantic GAPs and larger-domain native
coverage remain explicit. Proposed100M size gate passes; practical tool delivery
is still unfinished.

Shared-key memory experiment (2026-11-15): `--grouped-memory` uses four
independent stock GDN value heads per key head. RF/heap pages share their
low-seven-bit keys; frame/declaration/context banks use disjoint key coordinates.
Logical rows, permissions, all rules and source bounds are unchanged. Targeted
STOCK RF page/wrap/borrow and arena/read-only-declaration modules pass. The whole
bundled candidate plans at 59,632,528 dense parameters, H1024/I256/L63, five
active GDN layers, 50,960 immutable records (`grouped-memory-plan.json`).
A short integrated stock prefix is pending; no whole-source or latency result
is claimed for this layout. Default baseline remains the audited 48.29M model.

Optional indexed private-phase dispatch preserves every matched source state
offline but yields 173,182/177,684 forwards versus 175,953/180,686 for bundled
controls, with 60,432 records. This minor reduction is not selected for GPU
validation or practical delivery (`indexed-phase-costs.txt`).

Write-time bounds and ROM layout checkpoint (2026-11-15): the compiler extracts
24 field predicates from the original invalid-syntax expression. Stock weights
check final whole main-row writes, including boot, and retain a sticky invalid
bit in a stock GDN cache. Original preflight stop ordering remains. Shadow,
scratch and arena writes do not affect it; no host computes the bit. An invalid
main boundary cannot be repaired before the original preflight stops. Targeted
STOCK boot/committed-invalid/sticky/ignored-shadow/scratch test passes. Both
matched sources preserve every state offline at 164,109/168,491 forwards.

Input-independent reachability after fusion retains both branches, all table
slots and every handler return continuation; aligned ROM falls from 50,960 to
48,912 records. H960/I512 plans AND actually emits 80,299,412 dense parameters,
47 layers, six active GDN layers, all73 families/6454 effects. The 64-forward
standard `aot_eager` CUDA-graph probe exactly matches ALL eager/captured hidden
states, cache tensors and logits, plus59 native-PC boundaries per item.
126.6011 forwards/s projects1330.9s for the longer case: SLOWER than the validated
baseline, not selected for full execution and not practical delivery.

The grouped H1024/I256 Inductor probe stopped at its300s cap in cold compilation.
Raw CUDA capture of stock sliding cache failed at `cache_utils.py:569`,
`torch.tensor([-1], device=...)`, with `operation not permitted when stream is
capturing`. Standard `aot_eager` resolves capture and gives bounded correctness
evidence, but its4574 kernels/forward are costly. No forward/cache patch or
custom circuit executor was introduced. Full-source and semantic/larger-domain
gaps remain separate from this prefix. No13minute source repeat was launched.

Integrated original source-address operations (2026-11-15): the compiler derives
all addresses from the original `compile_addresses` DAG. Whole bank reads use
the register address directly, with a model-owned modular predecrement flag.
Finite controller choices distribute through nested address arithmetic;15
selector keys plus the complete16bit fallback select11 modular affine schemes.
A shared three-word modulo8 operator computes each scheme in at most2 forwards.
This is source-controller arithmetic, not declaration/name/shape specialization.

Targeted STOCK test covers full16bit sparse keys including500/65535 and unknown
501, high-word operands, negative modular sums, frame0→31 wrap, full row loads,
and untouched RF fields. PASS9.08s. Both original-source cases preserve every
register and bank at every SPEC boundary OFFLINE, at134040/137515 forwards.
The longer source prologue falls45855→14879 forwards. All73families/6454effects
and the semantic domain are retained.

Actual complete model88,821,724DENSE/H1024/I512/L49/48912records/6activeGDN.
The bounded64-forward Inductor+CUDAgraph STOCK prefix passes exactALL hidden/
cacheTENSORS/logits and55nativePC boundaries/item;382.3301FW/s,107.45s capture.
Current longer-case projection359.68s remains minutes; practical seconds-scale
latency NOT delivered. No full-source rerun. Body57414, validation39058 and
commit26163 native forwards now dominate. Semantic/larger-domain gaps remain.

Further fixed-control/layout checkpoint: no-op-first private continuation
dispatch preserves every matched source state OFFLINE at124842/128127 forwards
(48,912ROM records). Both data edges remain. The current stock word/call/return
operations already implement this control; no new interpreter was introduced.

Global continuation sharing reduces the OFFLINE count to109466/112537, but
104,208records exceedPC16. Fixed regional table budgets fit64,272records at
120817/124208 forwards:15K extra records for4K saved forwards versus the simpler
layout. Preserved/unselected, no GPU emission. Profiled frame.phase comparisons
cost17994 LT +6580 bundled forwards in the previous longer case.

Transient feature reuse keeps233 transport/state bits pinned instead of504,
and colors decoded-record/operand slots after their last read. Targeted STOCK
ROM/affine/full-word/row/untouched-field test PASS6.86s. Whole H960/I512 plan
83,271,580DENSE/49layers/904channels, not whole-source STOCK evidence or a speed
result. H896 fails at903channels. Experimental actual-producer birth allocation
only saved2channels and failed a ROM-unit collision test; its code/logs remain
in scratch and it is not selected. No repeated full source run; practical
seconds-scale latency and the existing semantic/larger-domain gaps remain open.
