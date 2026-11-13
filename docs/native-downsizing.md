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
