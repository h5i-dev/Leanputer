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
  **Attention sublayers are inactive for this unrolled STLC slice.** The subsequent shared-machine implementation below uses active native
  DeltaNet RAM; these size figures describe only the initial STLC slice.
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

The implemented shared-machine port below preserves the explicit semantic
machine/Boolean IR and lowers its memory to native DeltaNet cache and control
to native SwiGLU. Feature expansion follows measured mathlib blockers. Native
normalization, gating, dtype and cache correspondence remains provisional
until the deferred broad validation phase.

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

A subsequent single-source native smoke accepted real mathlib
`BAll.imp_left@[1]` with heap256/fuel1152:1,060semantic steps,148allocated nodes,
41syntax boot tokens,1,154stock forwards. Banking across native DeltaNet heads
therefore exercised addresses above127. The generated configuration had
642,278,382BF16parameters, hidden3072 and56native layers; the fallback-kernel
forward took92.434s. This is larger and slower than desired, but is a standalone
compiled model, not a downloaded pretrained backbone. It is one actual source
smoke, not a new full-population coverage estimate.

## Proposition-structure checkpoint

The native IR now includes60phases, adding Iff/And fixed positive family and
constructor rules, dependent field-projection typing, unary substitution/shift,
projection iota reduction, neutral projections and conversion. A stock GPU
four-case smoke accepted newly supported mathlib `Imp.swap@[1,1]` (1,232steps),
actual Lean-exported Iff.mp/And.left fixtures, and rejected a wrong-family
projection. No assumptions were introduced. The1538fixed forwards+35syntax
boot records took132.535s. Generated model1,578,440,564BF16parameters
(3,156,881,128weight bytes), hidden7168,59native layers. This large dense-zero
parameter overhead is debt, not a demonstrated minimum architecture size.

Re-exporting only77previously Iff/And-blocked rows yielded12new syntax-export
candidates. This is not12new verified mathlib proofs or a full-population run.
One sparse weighted fixture additionally forced constructor-projection reduction
inside a dependent claim (1,330steps). Broad checks are deliberately deferred
until the planned feature set is implemented. Kernel basis in current native
reports lists the complete fixed intrinsic catalog; initial four-case log's
False-only metadata label was stale and has been corrected in reporting code.

## Equality and compilation memory

The Eq/Eq.refl/dependent Eq.rec slice adds ground universe pairs and six
recursor-control phases (66 total). Partial Eq.rec head/arity is derived by
weighted weak-head normalization; no preprocessing labels recursor applications.
See input-and-trust.md for the typed iota/K reduction premise and remaining
soundness limits. Re-exporting130old Eq-first failures produced38syntax
candidates; this is not38accepted proofs or a complete population update.

To let feature development fit the15GiB host, stock modules are constructed at
the target dtype/device with stock `no_init_weights`, then explicitly zeroed.
The compiler emits/copies one layer's FP32 tensors at a time. This avoids whole
FP32-model and whole-state-dictionary duplicates; it does not shrink parameter
shapes, change native runtime methods, or establish efficient model sizing.

Stock GPU equality smoke passed: actual mathlib Function.const_def@[1,1]
ACCEPT1,213steps with no assumptions; a dependent claim forcing K reduction
ACCEPT1,241steps under explicit A/a/q/P/h assumptions; invalid reflexivity
endpoints REJECT/CONVERSION382steps. These are three development cases, not a
full-population coverage estimate. H256/fuel1536,48boot records and1,538fixed
forwards took143.099s. Model2,934,590,462BF16parameters (5,869,180,924bytes),
hidden12288,64native layers; compile58.088s, peak PyTorch CUDA allocation
5,917,372,416bytes and process RSS1,777,995,776bytes. Layerwise emission bounded
host memory while preserving stock layer shapes. This substantial dense-zero
overhead remains architectural debt. Compact evidence: benchmarks/native/equality-smoke.json.


## Native document CLI and current feature work

`python -m leanputer.native_machine --input corpus.jsonl --config capacities.json
--device cuda --report native-report.json` compiles the shared native machine
and checks JSON/JSONL in batches. The config has the same six MachineConfig
fields as the reference CLI. Input/export failures remain MALFORMED,
UNSUPPORTED or RESOURCE rows. Only syntax-capable rows enter stock forward;
no syntax precheck labels a row ACCEPT. Results report explicit assumptions,
primitive basis, compilation cost and per-batch forward cost, parameter/weight
bytes, CUDA allocation and process RSS. Broad native validation is still pending.

Let support preserves annotation/value/body through export and checks/zeta
inside weights; shift and substitution traverse all three children with the
body binder offset. The IR has74phases. Minimal weighted and Lean cases cover
ordinary/dependent lets, substitution/shift under a let binder, and invalid
unused value rejection. True/True.intro add fixed positive schemas; True.rec
remains unsupported in this slice. Two newly exported real mathlib let closures
exhaust2048heap cells in planning; syntax support is not proof acceptance.

Let/True native baseline passed: real mathlib iff_mpr_iff_true_intro@[]
ACCEPT2,685steps, let substitution117A/shift141A, invalid unused value45R.
Two additional unsupported rows remained explicit (Nonempty, Quot). H512,
stack32/context16/constants8/fuel3072,3,074fixed forwards+80boot records:
compile81.135s,forward372.825s,4,020,610,720BF16parameters/8,041,221,440bytes,
hidden13312/intermediate1024/81native layers,one128-dimensional key/value
head per linear layer. CUDA peak8,168,178,688bytes,host peak1,808,584,704bytes.
These are one cold development run, not repeated throughput. Reproducible
inputs/config/report are under benchmarks/native/let-true-*.

The user has now prioritized compiler/layout downsizing before more features.
This exact Eq+let+True feature set and capacities/documents form the matched
baseline. Further Nonempty/Exists/Or/recursor work is preserved on scratch and
paused. No broad validation campaign, capacity reduction, custom runtime or
host semantic work is part of the downsizing task.
