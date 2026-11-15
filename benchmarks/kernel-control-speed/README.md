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
