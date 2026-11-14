# Current whole-program stock delivery

Latest matched checkpoint: [lossless byte controls](../../benchmarks/kernel-byte-controls-stock/README.md)
passed the same complete source accept/reject and all-register/cache validation.
Logical size is15,799,810,694parameters, hidden17408/layers581, stored219,396,384bytes.
The forward took1197.032s. Bounds/rules/word16 are unchanged; the small/practical
model goal remains unfinished. The detailed21.471B evidence below is the prior
paired-control baseline, preserved for a matched comparison.

The safe kernel program is unchanged from 127751c. The compiler keeps all general
rules: no proof/name/shape pruning, pretrained backbone, CPU emulator, semantic
host inference, or trusted source metadata. The runtime is stock
transformers.Qwen3_5ForCausalLM.forward/cache and identity hidden-state feedback.

## Matched physical domain and actual planning

All rows below use heap512, stack32, context8, four raw declarations, fuel8192,
16bit words, FFN width512. These are whole fixed-program plans, independent of
proof inputs. Original Nat precision remains a vector of16bit limbs bounded by
physical memory. Symbolic universes and all expression tags remain input data.

| Emission | Logical parameters | BF16 dense-equivalent bytes | Status |
|---|---:|---:|---|
| Original full current lowering |67,839,051,050|135,678,102,100|Meta plan only; cannot fit A10G |
| Exact one-unit OR, dependency commits |54,009,533,768|108,019,067,536|Meta plan only |
| Lossless paired control |40,937,709,110|81,875,418,220|Meta plan only |
| Lifetime commits/private digit accumulation |29,972,142,004|59,944,284,008|Emitted and source-validated |
| Stock zero attention in FFN-only layers |21,471,112,926|42,942,225,852|Latest emitted and source-validated |

A further linear Boolean fusion experiment increased peak liveness and planned
size to87,487,739,282parameters; it is disabled and preserved under scratch.
The first three rows are meta tensor shapes only. The last two also have actual
stock source acceptance/rejection evidence. Dense-equivalent bytes are not GPU allocation.
The indexed allocator preserves first-fit policy and reduces planning from427s
to about11s. No corpus, differential, scaling or throughput campaign was run.

## Storage and unmodified stock execution

The current architecture has hidden22528/layers603 and7913persistent channels.
It is **not a small logical Transformer**. The latest model has 21.471B logical
parameters regardless of sparse storage. The small-model target remains unmet.
Only the seven RAM layers require Gated DeltaNet. Other layers use standard
full attention with zero projections and head dimension two; their FFNs still
execute every compiled rule. No stock forward/cache code is changed.

Compiler-generated projections are sparse. Standard PyTorch CSR parameter
tensors let the existing stock nn.Linear forward execute those same matrices;
no module or forward/cache implementation is replaced. Direct sparse emission
avoids ever allocating their dense equivalents. The latest complete fixed model has
288,206,120 stored parameter/index bytes and 1,153,323 nonzero parameter
values. Compilation plus saving the artifact took 142.003s. The two-case
run peaked at 426,602,496 CUDA-allocated bytes. The previous all-linear
profile emitted in 54.103s without saving, so these compile timings differ in scope.
Framework/cache/workspace memory is additional. This removes the allocation
blocker for this storage path, not the small-architecture blocker.

Sparse PyTorch linear operations fail under inference_mode in this environment
with `Cannot set version_counter for inference tensor`. Sparse execution uses
standard no_grad instead. Stock BF16 tests cover overlapping updates,
simultaneous swaps, lossless packing and repeated identity feedback. A reused
aggregate slot clears only on its first scheduled writer.

The logical control words are still16bits. Two Boolean bits share a residual
value0..3; stock FFNs unpack them. Packed keep-old terms avoid retaining every
old bit through the full circuit. Output decoding is serialization only; decoded
values never supply feedback. The model's hidden state is fed back unchanged.

## Runnable artifact and command

The complete current compiled model is at:

    /mnt/scratch/leanputer-runs/current-full-stock/compiled-source-efficient/

It contains model.json and weights.pt (~279MiB). The previous all-linear
artifact round-tripped every stock parameter and source ABI exactly; the latest
artifact was saved before the complete current source run. Artifact hashes
are recorded with the evidence. Loading uses the stock model constructor,
assigns stored tensors and initializes stock RoPE buffers; it does not compile,
check or normalize a source declaration. The loader uses weights_only=True.

From the repository with the native environment:

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m leanputer.kernel_check \
  --load-model /mnt/scratch/leanputer-runs/current-full-stock/compiled-source-efficient \
  --input /mnt/scratch/leanputer-runs/current-full-stock/source.jsonl \
  --device cuda --report /mnt/scratch/leanputer-runs/current-full-stock/cli-report.json
```

For another physical configuration, --config and --save-model compile once;
--load-model reuses the resulting fixed program for new input declarations at
those bounds. Defaults use sparse CSR storage and paired control. Dense storage
and the historical unpacked layout remain explicit options. The logical model
size and physical stored bytes must always be reported separately.

## Evidence boundary

The original source witness declares an empty Prop E, supplies a standalone
E.rec universe claim, then proves forall x:E,E by identity. Transition reference:
DONE1316steps/224heap/2public signatures. A wrong target body is the rejection
case. This is one integration witness, not coverage of all Lean declarations.

The FULL current fixed program passed both source cases on stock CUDA BF16:
DONE at 1,316 semantic steps for the original block/claim/proof, and INVALID
TYPE_MISMATCH at 1,355 for the wrong proof. Both preserve two admitted environment
signatures and use no assumptions. All 951 semantic registers and all rows in
four heap partitions, stack, context and constants match the transition SPEC.
The reference was constructed only after model inference returned. The complete
two-case run took 1,221.760s forward, including syntax boot and native halt flush.
This is slow integration evidence, not a throughput claim. It does not establish
nested admission or all Lean coverage. Earlier Nat/String/Quot/claim results
remain SPEC/selected Boolean IR; the historical f5bb04d 10.35B smoke predates them.

The exact report, input documents, configuration and layout plans are in
[benchmarks/kernel-full-source-stock](../../benchmarks/kernel-full-source-stock/README.md).
The production CLI above runs the same NativeMachine.check path as this admission
validation. A fresh load of the latest artifact matched every register for its first two
source transitions in 10.460s including loading/boot. This is load-path evidence,
not a second admission run. A full CLI load-and-admit run has not been repeated.

## Reproducing the whole-program accounting

This computes the FULL fixed source program, then creates meta stock parameters;
it allocates no GPU weights and reads no proof input:

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m tools.kernel_stock_delivery \
  --plan --config benchmarks/kernel-full-source-stock/config.json \
  --report /mnt/scratch/leanputer-runs/current-full-stock/replanned.json
```

The latest measured plan takes 10.648s and reports 7,913 persistent channels,
21,864 allocated slots, 14,593 scratch reset channels, 137,494 logic FFN units,
602 graph layers and 603 stock layers. Logical parameter ownership is:

| Component | Parameters |
|---|---:|
| MLP matrices |20,865,613,824|
| Embeddings and output head |342,786,048|
| Full attention |134,269,264|
| Gated DeltaNet |101,252,494|
| Norms |27,191,296|

MLP matrices dominate. Removing no-op Gated DeltaNet layers improved the model
size but cannot by itself make this architecture small. A genuinely smaller
layout needs fewer simultaneously materialized control and temporary channels,
or reuse of kernel-specific circuit phases. Static module-access analysis finds
725 private-register candidates and 218 shared registers; this is candidate
analysis, **not** a proven live-range allocation or implemented register bank.
Any such lowering must preserve caller state, all numeric words, generic kernel
rules and identity feedback. It cannot dispatch circuits or supply answers on
the host. This remains a substantive architecture blocker.

Remaining blockers: genuinely small logical architecture and practical runtime;
larger/nested-source stock capacity and integrated evidence; partially replaced
mutual families; unavailable/incompatible primitive bindings/private metadata;
conservative failure classifications. Sparse storage alone does not close these gaps.
