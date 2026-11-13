# Native layout reduction

The fixed comparison feature set is commit `7e29295`: the ground dependent
fragment, False/Iff/And/projections, Eq/refl/dependent recursor, lets and
True/True.intro. The comparison uses exactly
`benchmarks/native/let-true-input.jsonl` and `let-true-config.json`: heap 512,
stack 32, context 16, constants 8, universe 4, fuel 3072. Four rows enter stock forward;
two unsupported rows remain in the six-row report. No capacity, semantic phase,
proof dependency, primitive schema or numerical dtype is removed.

The legacy layout builds 4.021 billion BF16 parameters. Its persistent input/control and
boot/write fields occupy 396 channels, while 13,245 residual slots are allocated.
The largest cause is repeated masked writes: many semantic rules select the
same data bit (for example the incremented allocation pointer) but materialize
separate guarded copies. Full FFNs also prevent the allocator from clearing
old residual owners and handing their slots to new values. Global homogeneous
hidden width then multiplies this scratch overhead across every stock layer.

The compact compiler makes three changes:

- Factor repeated guarded data by Boolean distributivity:
  `(c₁ ∧ v) ∨ (c₂ ∧ v) = (c₁ ∨ c₂) ∧ v`. This remains true when guards overlap;
  no unchecked mutual-exclusion premise replaces the checker rules. State and
  pending-memory payload selection share a data channel where possible.
- Represent NOT as the affine expression1−x inside subsequent stock projection
  weights. It needs no separately materialized residual channel. SiLU gate
  scaling and the BF16/ballast numerical contract stay unchanged.
- Reserve half the actual 1024 FFN units for residual slot handovers. The logical
  scheduling budget is 512; actual stock FFN width remains 1024. The allocator
  emits exact old-owner subtraction units into the spare SwiGLU rows.

The first change reduces the controller's AND gates 13,268 → 4,424. The selected
plan allocates 2,407 slots and uses hidden 2560 / 70 native layers, rather than
hidden 13312 / 81 layers. All outputs are still snapshotted before register writes;
removing those snapshots would reintroduce the earlier allocation-address alias
bug. A static read/write dependency check protects compilation order. Native
GatedDeltaNet heads, cache methods, recurrent identity feedback, standard
RMSNorm/SwiGLU and final stock model forward remain unchanged.

The pinned Qwenputer compiler's rescheduler explicitly leaves FFN headroom for
allocator handovers. Leanputer uses that design rationale, keeping its own
prefix reset and port ordering. Blind rescheduling would ignore implicit reset
stages. An inspected temporary-delaying variant worsened allocation and is not
selected. No CPU emulator, runtime sparse substitution, layer patch, pretrained
backbone, quantization or host semantic dispatch is involved.

Residual costs remain. The 512-cell heap uses four 128-row banks per heap read
port, plus stack/context/constants ports: 20 active native memory heads in total.
Increasing heap capacity increases bank/selector resources even though values
live in native cache. The homogeneous stock configuration still allocates dense
zero weights in unused sublayers. Snapshot lifetimes and operation scratch are
not overlaid using speculative phase exclusivity. Actual FFN/head width changes
and a larger performance campaign are deferred after this material reduction.

## Reproduction and evidence boundary

```bash
python -m leanputer.native_machine \
  --input benchmarks/native/let-true-input.jsonl \
  --config benchmarks/native/let-true-config.json \
  --layout legacy --device cuda --batch-size 4 --report legacy.json
python -m leanputer.native_machine \
  --input benchmarks/native/let-true-input.jsonl \
  --config benchmarks/native/let-true-config.json \
  --layout compact --device cuda --batch-size 4 --report compact.json
```

Both commands return 1 because the corpus deliberately contains one invalid
judgment. Expected outcomes are 3 ACCEPT, 1 REJECT, 2 UNSUPPORTED; expected semantic
steps are 2685, 117, 141, 45 for the four forwarded rows. Both apply 3074 forwards
plus 80 syntax boot tokens. The main source is real pinned mathlib
`iff_mpr_iff_true_intro@[]`, with no axiom assumptions. It does not establish
new full-population coverage or broad correctness.

Timing is one fresh-process development observation per layout. Compilation
includes layout/weight construction and device setup after CLI imports/input
loading; it is not full process/pipeline cold latency. Forward includes syntax
boot and the fixed recurrent schedule, not external Lean/nanoda replay. CUDA
peaks are PyTorch allocated bytes; host RSS is process-wide, not model-only.
A tiny CPU stock-forward test covers overlapping-guard factoring; three
original Eq cases are checked separately for retention. Large CPU mathlib
latency is not measured in this downsizing phase. Full formal soundness and broad differential native
validation remain outstanding.


## Matched GPU result

| Metric | Legacy | Compact |
| --- | ---: | ---: |
| Generated BF16 parameters | 4,020,610,720 | 668,641,546 |
| Actual weight bytes | 8,041,221,440 | 1,337,283,092 |
| Hidden / FFN width | 13312 / 1024 | 2560 / 1024 |
| Native layers | 81 | 70 |
| Allocated residual slots | 13,245 | 2,407 |
| Persistent channels | 396 | 396 |
| Compile seconds | 81.135 | 11.346 |
| Fixed forward seconds | 372.825 | 315.196 |
| Peak CUDA allocated bytes | 8,168,178,688 | 1,388,660,224 |
| Peak process RSS bytes | 1,808,584,704 | 1,707,610,112 |

Results, assumptions and semantic steps match exactly: 3 A, 1 R, 2 U. Both use one
128-dimensional key/value head per linear layer, 20 active memory heads overall,
80 boot records and 3074 stock forwards. Parameters fall 83.37% (6.013×); forward
latency falls only 15.46% (1.183×). The stock reference GDN/convolution kernels
and Python/module-launch overhead remain substantial. This is a successful
size reduction, not evidence of high proof throughput or broad correctness.
Reports: benchmarks/native/let-true-baseline.json and let-true-compact.json.

The original three Eq cases also pass at heap 256 / fuel 1536, with every final
register equal to the Eq checkpoint `fc65017` baseline: Function.const_def 1,213 A,
relative K 1,241 A, wrong reflexivity endpoint 382 R. The compact model also supports let/True,
so this is capacity-matched feature retention, not the strict same-feature
size comparison above. It uses 464,688,106 parameters / 929,376,212 weight bytes,
hidden 2304 / 54 layers, compile 8.387s, forward 121.772s. All 1538 forwards + 48 boot
records remain. Report: benchmarks/native/equality-compact-retention.json.


## Small CPU/GPU fixture comparison

An auxiliary matched configuration uses heap 32, stack 8, context 4, constants 2,
fuel 64, FFN width 1024 and the identical feature set. Each fresh process checks
the same identity and unbound-variable documents: ACCEPT at 52 semantic steps,
REJECT at 11. Every run includes 5 boot records and 66 stock forwards. These
are small fixtures, not CPU timings for the larger mathlib batch above.

| Device | Layout | Compile seconds | Forward seconds | Parameters |
| --- | --- | ---: | ---: | ---: |
| CPU | Legacy | 35.181 | 76.601 | 1,686,507,104 |
| CPU | Compact | 5.073 | 19.670 | 235,476,048 |
| A10G | Legacy | 32.613 | 5.148 | 1,686,507,104 |
| A10G | Compact | 5.147 | 4.476 | 235,476,048 |

CPU is one thread on AMD EPYC 7R32, with BF16 stock fallback operations; the
GPU uses the same BF16 weights/stock kernels. CPU peak process RSS decreases
4,391,399,424 → 1,209,950,208 bytes. GPU peak PyTorch allocation decreases
3,392,349,184 → 502,330,368 bytes. All outcomes and semantic counts match across
CPU/GPU and layouts. Fresh-process totals, where separately observed by the
harness, include imports/startup: CPU 114.031 → 26.648s, GPU 39.925 → 11.777s.
Per-run JSON reports and exact core-input/core-config files are in benchmarks/native.
These are single observations, with no repeated-latency confidence claim.

## Bank accumulation and finer width selection

A second experiment freezes the complete `6c3563c` feature set: 74 fixed
primitives, 112 operational phases, including Eq, let, all added records,
Nat/OfNat and PUnit. The identical three judgments are the real
Function.const_def@[1,1] source closure, relative Eq K and an unequal-endpoint
reflexivity rejection. Both configurations use heap512, stack32, context16,
constants8, ground universe bound4, fuel1536, BF16 weights and FFN1024.

Separate bank outputs keep one residual vector per 128-row RAM bank until
summation. The new compiler mode instead emits each bank's output projection
into the same residual dimensions. Exactly one query bank is active; all other
contributions are zero. The existing prefix reset clears these scratch channels
before each transition. This uses upstream Qwenputer's existing `Graph.head`
`into` mechanism and stock residual addition. There is no runtime reduction,
custom layer, cache change, semantic host dispatch or reduced capacity.

Bank accumulation alone changes slots4624→4485 and head-clear operations293→130,
but the original width search still chooses hidden5120. Parameters and peak
CUDA allocation are unchanged. Its single forward observation is161.574s versus
159.093s for separate banks; this ablation gives no measured speed benefit.
Dense size is quantized by the compiler's normalization layout, so fewer live
slots do not guarantee fewer parameters.

The expanded search allows up to64 ballast channels instead of16. Every
candidate still requires hidden divisible by64 and hidden/ballast a power of
four, retaining the upstream power-of-two normalization scale. Ballast magnitude
remains2^40, arithmetic remains BF16 with FP32 reductions, and stock RMSNorm
is unchanged. This is a compiler configuration choice, not quantization.

At heap4096/stack64/context32/constants16, a metadata-only comparison already
reduces the separate16 plan from7713slots/hidden8192/298layers/9,081,335,506params
to5122slots/hidden6144/296layers/6,765,459,918params with accumulation16.
These are unexecuted projected shapes, not proof results, memory peaks or timing.
The larger proof closures remain slow; no full mathlib campaign is part of this
checkpoint. The finite numerical tests do not prove floating-point soundness.

The combined matched A10G result uses18 ballast channels and hidden4608:

| Measurement | Separate / max16 | Accumulate / max64 |
| --- | ---: | ---: |
| Allocated residual slots | 4624 | 4485 |
| Hidden width / native layers | 5120 / 71 | 4608 / 71 |
| BF16 parameters | 1,356,184,972 | 1,220,578,188 |
| Actual weight bytes | 2,712,369,944 | 2,441,156,376 |
| Compile seconds | 26.408 | 25.198 |
| Fixed forward seconds | 159.093 | 158.515 |
| Peak CUDA allocated bytes | 2,748,868,096 | 2,584,449,536 |
| Peak process RSS bytes | 1,727,647,744 | 1,750,122,496 |

Both runs retain20 active RAM heads, one128-dimensional key/value head per
linear layer, final full-attention head256, 48 boot tokens and1538 stock
forwards. Outcomes/reasons/steps/allocated heap/dependencies/assumptions match:
real source1213A/noaxioms, relativeK1241A/fiveexplicitassumptions, unequal
endpoints383R/CONVERSION. Complete final memory/cache correspondence was not
measured. Parameters fall10%; latency differs only0.36%, with single observations
and no established speedup. The metadata-only sizing process overlapped part
of the combined run's cold setup; this is development evidence, not a controlled
latency benchmark. Compile is cold weight generation; forward includes syntax
boot and fixed execution, excluding imports/compilation, and is not a measured
steady-state throughput distribution. CPU proof latency was not rerun for this
second experiment. CPU and GPU pass focused RAM boundary checks, including an
explicitly selected greater-than16-ballast layout, changing query banks and
disabled writes.

Accumulation/max64 is now the shared-native default. Reproduce the prior layout
with `--bank-layout separate --max-ballast 16`; the STLC compiler keeps its
original search default. Exact documents, configuration and all three reports
are `benchmarks/native/banks-*`. Reproduce, using the native Python environment:

```bash
python -m leanputer.native_machine --input benchmarks/native/banks-input.jsonl \
  --config benchmarks/native/banks-config.json --device cuda --batch-size 3 \
  --bank-layout accumulate --max-ballast 64 --report /mnt/scratch/banks.json
python -m unittest discover -s tests -p test_native_banks.py -v
```

The CLI's exit1 is expected because the matched batch includes a rejection.
Features resume after this checkpoint; dispatch overhead, sequential bank
layers and repeated semantic allocation remain open limits. No claim that this
parameter count is necessary or that the larger-source throughput is adequate.

The expanded4096-capacity plan selects21 ballast channels, hidden5376 and
295layers, with5,899,860,044 projected parameters (35.03% below separate16).
This remains metadata only: no GPU weights, execution or theorem acceptances
were generated for that configuration. `banks-expanded-plan.json` retains the
full stock config, capacities and explicit NOT_RUN_PLAN_ONLY label.
