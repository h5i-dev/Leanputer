# Stock Qwen3.5 backend migration

The user requirement is a small existing Transformer with compiler-generated
weights and stock forward, followed by feature expansion on that backend.
The custom sparse circuit/recurrent attention-RAM engine remains a semantic
reference/prototype; arbitrary tensor operations plus attention do not make it
a conventional Transformer. Full pretrained language-model integration is last
and optional. No pretrained model weights have been downloaded.

## Implemented native slice

`python -m leanputer.native` compiles the **complete bounded STLC checker** into
unmodified `transformers.Qwen3_5ForCausalLM`. Syntax/table validity, lexical
scope, inference, claimed-type comparison and vocabulary-overflow flags all run
in generated model weights. The compiler receives capacities/vocabulary only,
never a proof answer. Host code packs untrusted syntax bits into `inputs_embeds`
and reads output flags. No custom model forward, replaced sublayer, monkeypatch,
checker callback, training or general CPU emulator is used.

Minimal smoke configuration:

- Five syntax nodes; types P, P→P, (P→P)→(P→P); 113 input bits.
- Hidden size704, intermediate256, 37 linear-attention/native SwiGLU layers plus
  one inactive full-attention layer; 38,292,874 generated parameters (~153MB fp32).
- Stock RMSNorm, SiLU/SwiGLU, convolution and GatedDeltaNet implementations.
  **Attention sublayers are inactive for this unrolled STLC slice.** Native
  DeltaNet RAM for the shared dependent machine is not yet implemented.
- Stock model can save/reload with `save_pretrained`/`from_pretrained` and
  `trust_remote_code` is unnecessary. Metadata records input packing slots.

Four minimal cases passed on CPU/CUDA: identity and closed application accept;
wrong claim and unbound variable reject. CPU batch forward0.153s and CUDA1.136s
were initial cold development observations, not repeated performance estimates.
The stock implementation warned that optimized causal-convolution and
flash-linear-attention kernels were absent, using its reference PyTorch paths.
No GPU speedup or final differential validation is claimed. Broad tests wait
until the native architecture and intended feature expansion are implemented.

## Numerical compilation and provenance

The adapted compiler follows [Qwenputer's native Qwen3.5
compiler](https://github.com/divagr18/qwenputer/tree/0cab57038a8b218dabe481f994174c3437405e3d/chipformer/q35):
large constant ballast channels make the RMSNorm scale a known power of two on
the bounded numerical domain; projected weights compensate that scale. SiLU
inputs scaled by128 implement ReLU at tested integer gate values because its
positive sigmoid saturates to1 and its negative tail underflows to0. This is a
floating-point domain property requiring final validation, not a real-arithmetic
identity or an assertion that generic RMSNorm/SwiGLU preserves Boolean logic.
Weights include liveness-based residual slot reuse. The final stock norm/head
read only designated output flags. Every parameter, including unused native
sublayers, is overwritten by compiler-generated tensors.

Attributed MIT compiler utilities (Expr, graph/slot allocation and weight
emission) are vendored with license and exact upstream provenance in
`leanputer/native_vendor/qwenputer`. No CHIP-8/RISC-V semantics, firmware or
emulator is used. Leanputer's checker IR supplies the actual computation.

## Reproduction

Use Python3.11+ in a separate environment with the native extra. The tested
scratch environment has Python3.12, torch2.8.0+cu128, transformers5.19.0. The
existing Python3.9 environment remains usable for the reference backend.

```bash
python3.12 -m venv /mnt/scratch/leanputer-native-venv
/mnt/scratch/leanputer-native-venv/bin/python -m pip install -e '.[native]'
/mnt/scratch/leanputer-native-venv/bin/python -m leanputer.native --device cuda \
  --save /mnt/scratch/leanputer-runs/native-stlc-stock
```

Next implementation: preserve the explicit dependent semantic machine/Boolean
IR, compile memory reads/writes to native DeltaNet cache and register-control
rules to native SwiGLU, establish stock-forward recurrence, then add False/Iff/
And/equality support based on the measured mathlib blockers. Native memory state,
normalization, gating, dtype and cache behavior need executable correspondence;
the current custom rank-one RAM update is not evidence of native compatibility.

## Shared dependent native execution (bring-up checkpoint)

The shared dependent port now emits the existing49-phase register-control IR
into native SwiGLU and uses **active stock GatedDeltaNet cache** for heap,
continuations, context and constants. Each read port has a replicated native
memory head; pending writes commit through the native delta recurrence before
the next read. Banks larger than128 rows split across native heads/layers.
There is no host rank-one memory update. Stock layer methods/cache behavior are
unchanged. A two-case CPU/CUDA smoke now accepts the valid identity in52semantic
steps and rejects an unbound variable. Broad correctness validation is pending.

The host loads syntax-only boot records, then applies a fixed fuel+2 stock
forward schedule. Raw pre-final-norm hidden state feeds back by identity through
the public hidden-state output; stock cache carries memory. Compiled prefix
SwiGLUs clear temporary channels, and compiled final stages snapshot outputs
before updating register slots. That snapshot matters: write addresses must
observe old allocation/stack pointers, not their simultaneously incremented
values. The first bring-up failure exposed and corrected this aliasing bug.
No host inference, substitution, conversion, operation dispatch or halting is
performed. Final register flags are decoded after the fixed schedule.

This first recurrent configuration is larger than the unrolled STLC smoke:
roughly260Mgenerated parameters at hidden2048/intermediate1024. BF16 is used for
native memory outputs and saturated gates; no host rounding repairs results.
A10G fallback-kernel smoke took6.740s for two judgments/130forwards, including
five syntax boot tokens. It is a development observation, not a speedup claim.
The CPU test used the earlier full-capacity boot schedule and took42.144s, so
these are not matching timing boundaries. Sparse-reference results and native
results must remain separately labeled until the deferred validation phase.
