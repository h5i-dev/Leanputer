# Stock Qwen3.5 native backend

The user requirement is a small existing Transformer with compiler-generated
weights and stock forward, followed by feature expansion on that backend.
The custom sparse circuit/recurrent attention-RAM engine remains a semantic
reference/prototype; arbitrary tensor operations plus attention do not make it
a conventional Transformer. Full pretrained language-model integration is last
and optional. No pretrained model weights have been downloaded.

## Initial bounded STLC slice

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


## Compact layout checkpoint

The default shared-native layout now factors repeated guarded writes, inlines
NOT in projection weights and reserves SwiGLU units for residual slot reuse.
At the identical512-cell Eq+let+True feature boundary, stock native smoke
results/assumptions/semantic steps match while parameters shrink4.021B→668.6M
and GPU allocated peak8.169GB→1.389GB. Compile81.135→11.346s; fixed forward
372.825→315.196s. Stock fallback runtime remains slow. `--layout legacy`
retains the baseline compiler for reproduction. See native-downsizing.md for
exact inputs, dimensions, costs, numerical scope and remaining architectural
debt. No semantic phase or capacity was removed.


## Positive recursor feature work

On the compact compiler, the next fixed slice implements Nonempty, Exists and
Or families/constructors plus their Prop-valued dependent recursors; True,
And and Iff recursors are also added. The semantic IR now has 81 phases.
Ordinary definitions such as recOn/casesOn remain checked dependencies.
Constructor iota dispatch runs inside weights; neutral And/Iff majors stay
neutral, including when a recursor returns data. True's K-like unit rule is
separate. A first prototype wrongly expanded neutral And/Iff proofs; an actual
Lean adversarial check caught it before any feature checkpoint, and the
constructor-only implementation replaces it.

A focused weighted CPU test of six actual closed recursor types, five iota
cases and two required rejections passed. The two negative cases prohibit
large Or elimination and neutral And data reduction. Native GPU bring-up
checks two newly exportable real mathlib proofs and these feature paths, with
explicit assumptions for relative fixtures. Re-exporting only 80 previously
blocked rows produced 37 syntax candidates; this is not 37 accepted proofs or
a new full-population coverage estimate.

Positive recursor stock GPU smoke passed 8 A / 2 R. New actual mathlib
BEx.intro@[1] accepts in 2,769 steps, exists_apply_eq@[1,1] in 1,834, both with
no axiom assumptions. Relative fixtures exercise both Or branches, Nonempty,
Exists and And constructor reduction; neutral And data reduction and large
Or elimination reject. The closed True K fixture accepts. Configuration
heap512/stack32/context16/constants8/fuel3072,61boot records,3074forwards:
318.306s forward,15.113s compile,802,346,762BF16parameters/1,604,693,524bytes,
hidden3072/70layers,peak CUDA1,720,345,088bytes/host1,710,448,640bytes.
This feature-superset development batch differs from the earlier downsizing
comparison and is not a matched speedup claim. Evidence and exact inputs:
benchmarks/native/positive-{smoke.json,input.jsonl,config.json}.


## Quotient primitive slice

The fixed Quot, Quot.mk, Quot.ind and Quot.lift rules reuse the 81-phase native
framework. Lift's carrier/result universe order is checked with actual Lean
aliases at {0,1}/{1,0}. Lift applications check relation respectfulness before
constructor reduction; Ind's motive remains Prop-valued. Neutral quotients
stay neutral. Quot.sound remains a genuine explicit axiom dependency, with its
type checked and its assumption reported. No primitive certificate is supplied
by input preparation.

Targeted weighted/Lean cases agree on constructor reduction and three required
rejections: invalid respectfulness, neutral quotient data reduction, and large
Ind elimination. Five actual closed types plus five relative cases pass the
weighted smoke. New syntax export covers13of23current quotient-first blockers;
the larger funext closures require about41ksemantic transitions and6.5knodes
in planning. Those are not native acceptances. The small native smoke covers
quotient semantics independently of that much larger resource budget; broad
coverage/throughput validation is still deferred.

Quotient stock GPU smoke passed7A3R with exact expected steps:five closed
quotient types, lift/ind constructor iota, three forbidden shortcuts. Model
619,554,538BF16parameters/1,239,109,076weightbytes/H3072/54layers at
heap256/stack32/context16/constants8/fuel1536,40boot+1538forwards127.681s,
compile12.530s,CUDApeak1,317,785,600bytes/host1,705,603,072bytes. This is a
new semantic development batch with a different capacity from the512-cell
positive checkpoint; no matched speedup claim. Evidence under benchmarks/native/
quotient-{smoke.json,input.jsonl,config.json}. No new real-mathlib native
acceptance is claimed for this slice because its dependency closures exceed
current small budgets. The nanoda adapter now explicitly returns UNSUPPORTED
for unimplemented syntax, rather than treating every unknown tag as Pi.


## Decidable checkpoint

Fixed Decidable/isFalse/isTrue/rec uses the same81semantic phases. A small
stock-native four-case smoke accepts true/false data branches and rejects a
neutral branch shortcut and invalid constructor evidence. The256-cell model
still has619,554,538BF16parameters/H3072/54layers;1538forwards take121.700s.

The newly supported actual mathlib Decidable.or_not_of_imp@[] accepts in5,390
semantic steps with four checked dependencies and no axiom assumptions. The
larger matched budget is heap1024/stack32/context16/constants8/fuel5504:
120boot records+5506forwards,798.690s forward,22.109s compile,1,459,725,898BF16
parameters/2,919,451,796weightbytes/H3840/102layers; peak CUDA2,947,642,368bytes,
host1,738,149,888bytes. This is one development observation, not efficient
throughput or a size/speed comparison with a smaller configuration. Only114
fuel steps beyond planned checking work were provisioned. Of133Decidable-first
blockers29now syntax-export; one new source was checked natively. Exact reports,
inputs and configs are under benchmarks/native/decidable-{small,real}*.


## Subtype record checkpoint

The fixed Subtype family/mk/rec plus dependent projections and typed data eta
extend the shared IR to91phases. Actual Lean aliases exercise the universe floor
at carrier0/1 and recursor order{result,carrier}. Eleven targeted native cases
pass9A2R, including dependent property projection, neutral record/recursor eta,
rejection of different vals and wrong projection family. The same cases passed
weighted CPU checking(70.007s); five relative cases agree with Lean(2.167s).

At heap256/stack32/context16/constants8/fuel2304:44boot+2306forwards181.295s,
671,183,338BF16parameters/1,342,366,676weightbytes/H3328/54layers,CUDApeak
1,459,555,328bytes/host1,702,318,080bytes. This is a new feature/case set, not a
matched performance comparison. Elevenof95current subtype-first blockers now
syntax-export. Inspected Classical.some_spec₂ and axiom_of_choice closures
plan at19,696/21,373steps and2,786/3,041nodes, with genuine Classical.choice
assumptions; these are not native verified proofs. Small fixture evidence and
exact configs/inputs are under benchmarks/native/subtype-*.

## Heterogeneous equality checkpoint

HEq/refl/rec adds seven-argument spines and carrier+value K checks to98semantic
phases. Seven native cases pass5A2R, including rejection when either carrier or
value differs. At heap256/stack32/context16/constants8/fuel2304:45boot+2306
forwards182.537s,compile12.355s,722,805,994BF16params/1,445,611,988weightbytes,
H3584/54layers,CUDApeak1,532,254,208bytes/host1,689,567,232bytes. Weighted
unit50.865s and actualLean four relative cases2.096sagree. Actual mathlib cast
closures plan at~8.5ksteps/~1.2knodes, outside this small native smoke; no new
native mathlib acceptance for this slice. Evidence under benchmarks/native/heq-*.

## Bool checkpoint

Bool/false/true/rec adds nullary data-constructor selection in99semantic phases.
Both branches are exercised with distinct data and dependent claims; a neutral
major stays neutral even when both minors are identical. Eight native cases
pass6A2R, agreeing with weighted CPU checking(20.254s) and actual Lean(2.153s).
At heap128/stack32/context16/constants8/fuel768:34boot+770stock forwards49.043s,
compile10.521s,482,431,186BF16parameters/964,862,372weightbytes/H3072/42layers,
CUDApeak1,012,212,224bytes/host1,691,262,976bytes. CPU validation overlapped
initial GPU development bringup; these are development observations, not a
controlled performance comparison. Evidence under benchmarks/native/boolean-*.

The full pinned syntax refresh now exports362of857 and retains495unsupported
rows, export8.878s. Removing Bool unlocks126of142previous first blockers, but
these are not native proof acceptances. The smallest newly exported inspected
classical closure has72dependencies, exceeding the small eight-constant smoke
budget. No new real-mathlib native acceptance is claimed for this slice.

## Option checkpoint

Option/none/some/rec extends the IR to100phases. Its Type-u carrier uses numeric
successor universes inside schema construction; recursor universes are ordered
{result,carrier}. Closed aliases at{0,1}/{1,0}, distinct data branches and three
negative restrictions pass the11case native smoke8A3R, agreeing with weighted
CPU(50.934s) and actualLean(2.175s). A neutral major cannot select either minor;
a wrong some-field or Prop carrier rejects.

At heap256/stack32/context16/constants8/fuel1152:40boot+1154stockforwards97.654s,
compile12.692s,722,798,826BF16parameters/1,445,597,652weightbytes/H3584/54layers,
CUDApeak1,545,679,872bytes/host1,702,318,080bytes. Development timing includes
concurrent initial CPU validation and is not a repeated latency measurement.
Evidence is under benchmarks/native/option-{smoke,input,config}*.
Four of12currentOption-first blockers now syntax-export; newly inspected
Function.IsPartialInv.eq plans at4930transitions/700nodes with three checked
dependencies and noaxioms. Its native check is separate from this small smoke.

The actual mathlib Option judgment Function.IsPartialInv.eq@[1,1] now passes
native checking:4930semantic transitions, three checked dependencies, noaxioms.
At heap1024/stack32/context16/constants8/fuel4992:98boot+4994stockforwards,
740.529s forward,33.727s compile,1,965,272,524BF16parameters/3,930,545,048
weightbytes/H5120/103layers/inter1024; peakCUDA3,957,142,016bytes and
host1,759,862,784bytes. Only62fuelsteps exceeded the planned semantic work.
This12.3minute development run is poor performance, not a throughput claim;
focused CPU record validation overlapped part of it. It is one new verified
source ground instance, not4proved from the syntax subset or a full-population
coverage update. Exact frozen Option checkpoint inputs/config/report are under
benchmarks/native/option-real-*; weighted semantics match commit271263d.

## Fixed one-field records

Inhabited/Mul/Add/Subsingleton share a fixed record path in103semantic phases
and58intrinsics. Projection inference instantiates the actual fixed constructor
schema by weighted substitution, then extracts its field binder domain. This
handles field binding without host inference or input certificates. Inhabited
uses Sort(max1u); Mul/Add use Type-u carriers; Subsingleton is Prop with a proof
of forall a b, Eq a b. Data records use typed eta and neutral recursor expansion.
A neutral Subsingleton cannot compute data through its recursor, matching Lean.

Twenty weighted cases pass16A4R(264.089s), including actual closed aliases,
field typing under binders, constructor/neutral boundaries and two retained
Subtype checks. Nine relative feature cases agree with actualLean(2.415s).
This focused reference validation overlapped part of the preceding Option GPU
run, so it is not a controlled CPU/GPU performance comparison. Native source
and fixture evidence is recorded separately below after checking.

The native12case batch passes9A3R, with every semantic-step count matching the
spec plan. Actual mathlib Function.injective_of_subsingleton@[1,1] accepts in
2643transitions with three checked dependencies and noaxioms; Lean accepts the
same exported judgment(2.603s). The other cases cover the Inhabited universe
floor, Mul recursor type, data eta for all three data records, neutral Inhabited
recursion, constructor Subsingleton iota, three required rejections and retained
Subtype eta.

At heap512/stack32/context16/constants8/fuel2688:75boot+2690stockforwards,
279.794s forward,24.276s compile,1,356,195,212BF16parameters/2,712,390,424
weightbytes/H5120/71layers/inter1024; CUDApeak2,848,267,776bytes and
host1,775,697,920bytes. This is a new feature batch, not a matched speedup
comparison with an earlier smaller model. Actual source work leaves45fuelsteps
padding. Exact input/config/report are in benchmarks/native/one-field-*.
The smaller256cell774.4Mparameter shape is a compiler plan only, not this
measured native batch. Of96prior one-field-first blockers38now syntax-export;
this checkpoint adds one real native mathlib acceptance, not38proved.

## Bounded natural literals and recursion

Nat/zero/succ/rec and Zero/One add109semantic phases/68intrinsics. Nat literals
are atomic syntax with an explicit scalar-word bound. Zero/successor reduction
and recursive step construction happen inside weights. Both literal recursion
and Nat.succ n with a neutral predecessor reduce; a neutral major stays neutral.
Forced successor overflow is RESOURCE/NATURAL, never wrapped arithmetic. Ordinary
numerals still expose their unimplemented OfNat dependency in this checkpoint.

The13case native smoke passes9A3R1RESOURCE, with matched spec steps, including
recursive computation1688, successor-of-neutral590, wrong recursive result2619R,
and numeric overflow136RESOURCE. The weighted focused unit passes341.930s.
ActualLean agrees on the three negative judgments and constructor-neutral
positive(2.422s/2.379s). The resource case remains indeterminate in weights;
Lean rejects that false claim, and no false wrapped acceptance occurs.

At heap512/stack32/context16/constants8/fuel2688:38boot+2690stockforwards,
302.581s forward,26.753s compile,1,356,195,212BF16parameters/2,712,390,424
weightbytes/H5120/71layers/inter1024; CUDApeak2,858,612,224bytes and
host1,771,450,368bytes. This development run overlapped focused CPU validation;
it is not a controlled device/speed comparison. Evidence:benchmarks/native/natural-*.
A missing neutral-constructor reduction and a stale literal conversion guard
were caught in uncommitted prototypes and corrected before this checkpoint.

Only one of44currentNat/Zero/One-first blockers newly syntax-exports:
Nat.succ_injective. Its independent spec plan accepts25397steps/free2845 with
eight checked dependencies at heap8192/stack128/context64/fuel131072. It is NOT
native checked. No expensive large native proof run or new mathlib native
acceptance is claimed for this slice. Nat.add/mul's actual brecOn dependency
closures require further constructs; no arithmetic shortcut replaces them.

## OfNat checkpoint

The fixed OfNat family/mk/rec expands the catalog to71intrinsics/110phases.
A general weighted parameter-spine scan instantiates constructor types using
stacked substitution; the Nat label remains part of the record type. The field
value is independent:the label3/value5 source instance returns5, and the false
claim that it returns3 rejects. Ordinary numerals preserve both checked instance
definitions, without exporter normalization or an unchecked library shortcut.

Native12cases pass9A3R with exact planned steps:five actual Lean source judgments,
neutral recursor, three required rejections and retained Mul/Subtype/Nat cases.
The focused weighted unit passes260.707s; four relative cases agree with
Lean(2.659s). At heap512/stack32/context16/constants8/fuel2048:48boot+2050stock
forwards233.296s,compile27.403s,1,356,195,212BF16parameters/2,712,390,424weightbytes,
H5120/71layers/inter1024; CUDApeak2,835,833,344bytes,host1,773,715,456bytes.
Development validation overlapped CPU/GPU work; this is not a speed comparison
with the higher-fuel Nat batch. Evidence under benchmarks/native/ofnat-*.

All12priorOfNat-first mathlib rows remain explicit unsupported records, now
blocked by PUnit6/HAdd3/HPow2/LT1. No new mathlib acceptance or syntax-coverage
increase is claimed. Ordinary numeral support is a prerequisite for those
closures, not proof that they are already checked. General multi-universe and
inductive/indexed declaration support remain separate work.

## PUnit checkpoint

PUnit/unit/rec extends the catalog to74intrinsics/112phases. The weighted
recursor-root scan checks its carrier universe:Prop0 keeps constructor-only
data iota, while positive-universe empty records permit data eta and neutral
recursion. Typed empty-data equality first verifies the exact type. Actual
Lean tests distinguish proof eta from data-recursion behavior at carrier0/1.

Native13cases pass11A2R with matched steps, including recursor universe aliases,
both eta paths, data recursion, constructor Prop iota, two required rejections
and retained Subtype eta. Focused weighted unit152.988s; actualLean negatives
2.781s agree. At heap128/stack32/context16/constants8/fuel1152:27boot+1154stock
forwards83.816s,compile12.677s,603,029,458BF16parameters/1,206,058,916weightbytes,
H3840/42layers/inter1024; CUDApeak1,284,547,072bytes,host1,733,197,824bytes.
Development CPU validation overlapped; no controlled speed/size comparison with
the larger512-cell checkpoints. Evidence under benchmarks/native/unit-*.

Threeof28PUnit-first rows newly syntax-export:Bool.involutive_not(Gamma11),
Function.IsPartialInv.surjective_getD(Gamma21),Option.rec_update(Gamma183).
Bool.involutive_not plans at43989transitions/3407nodes in the independent spec,
not native verification. No new native mathlib acceptance is claimed here.
Remaining first blockers are PProd19/HAdd6. The full syntax snapshot is408of857
exported, not408proved; large declaration closures remain a concrete limitation.

The later bank-layout checkpoint freezes all74 fixed primitives and112 phases.
Shared bank outputs use stock residual projections, and the width search now
allows64 ballast channels while retaining the required power-of-four ratio.
At identical heap512/fuel1536 the same real Eq source/K/negative cases retain
all reported results, reducing hidden5120→4608 and parameters1.356B→1.221B.
Forward159.093→158.515s is effectively unchanged, not an established speedup.
`--bank-layout separate --max-ballast 16` reproduces the previous layout;
accumulate/64 is now default. No precision, semantic, stock-forward or cache
change. See [matched evidence](native-downsizing.md) for setup, memory peaks,
negative ablation and separate unexecuted large-capacity plans.

## Fixed LT and LE relation records

The catalog now includes LT/LE, their constructors, recursors and projections
(80 fixed primitives,112 phases). The fixed field is `α → α → Prop`, with α in
Type-u. These are data records: typed eta and neutral data recursion apply,
but arbitrary relation values are not definitionally proof-irrelevant. The
compiler instantiates constructor type schemas inside weights to type fields.
A different family or a non-relation field rejects. Source export is syntax
only, and ordinary projection definitions remain checked dependencies.

Focused weighted8cases pass5A3R in70.771s. Actual Lean source compilation and
relative1A3R agree. Native20cases pass12A4R4RESOURCE, matching all planned
outcomes, reasons, semantic steps and allocated heap counts. The batch contains
seven source schema/field/eta/iota fixtures, four relative positive/negative
checks, three previous Eq cases, two PUnit eta cases, and four newly exportable
real mathlib sources retained as RESOURCE/FUEL at the smaller checking budget.
Heap512/stack32/context16/constants8/fuel2624, BF16, defaultaccumulate/max64:
1,288,391,308parameters/2,576,782,616weightbytes, hidden4864/71layers/FFN1024;
compile28.582s,93boot+2626stockforwards273.017s, peakCUDA2,955,234,816bytes,
hostRSS1,769,213,952bytes. CPU validation overlapped this development run;
these are not controlled latency comparisons. Exact evidence: relations-*.

The complete syntax-only857-source refresh is412EXPORTED445UNSUPPORTED in
9.479s. The four new candidates are Function.swap_lt/gt/le/ge@[1], each with
four dependencies and no axioms. They pass the independent spec and actual
Lean replay; larger-budget native checking remains pending at this checkpoint.
This is not412verified proofs or an updated native population fraction.
