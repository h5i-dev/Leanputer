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
