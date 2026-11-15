# Typed kernel control store and shared stock checker

Current implementation now maps the complete current general source controller
into64192 fixed112bit native records, all73 source families/6454 grouped effects.
Control generation happens before source input is read. Names, expression tags,
schemes, declaration shapes/counts and literal contents remain runtime data.
`stock_control.py` lowers17/18bit operations through bounded two-limb word
algorithms, bitfield extraction, shared shifts, source address programs, arena
OR-shadow buffers, model-owned field queue/commit and final outcome publication.
`stock_checker.py` transports raw syntax and repeats unmodified stock forward/cache
with identity feedback. No evaluator, host opcode dispatch or semantic cache setup
is used. The compiler retains all explicit semantic GAP/RESOURCE/profile outcomes.

The checked-preflight/control-first mapping is in `control_store.py` and
`control_phases.py`. Global preflight remains checked. Only inside its true branch
is its proven dominating predicate removed from body guards.32 shared guards are
cached. Exact duplicate updates/continuations share records without inspecting
input proofs. Exhaustive Cartesian phase partition exceeded200000compiler blocks;
it is retained as an unsuccessful experiment, not the selected implementation.

Both complete original-source cases match every register and bank in the OFFLINE
native encoding reference at all1316/1355 transitions. Native counts are1,185,877
and1,218,203 model forwards (including row/shift/commit microsteps). This validates
lowering, NOT stock admission. Software references never supply inference data.

The FULL fixed stock model actually emitted and loaded on A10G is83,727,386
**dense logical parameters**, H768/I256/L77,30 paged-ROM layers,7 byte decoder
layers and35 allocated data stages plus front/clear/output. Allocation occupies
ALL768channels:511features+244operator scratch+13ballast/tau.512 RF rows/read copy,
12RF heads and7arena heads implement the existing word16/heap512/stack32/context8/
constants4/fuel8192 integration domain. The larger nested-source domain is not
validated at these bounds. The control store includes all current general rules;
this does not close semantic GAPs recorded in target.md.

Actual standalone stock module checks cover arithmetic wrap/borrow, word bitwise
and bounded shifts, ROM page boundary, binary arena reads/writes with untouched
fields, OR merges, unique dirty queue crossing row boundaries, repeated commit,
and publication preserving GAP/reason/result. The current matched full-source
stock run is in progress; sampled model PCs match the independent offline native
encoding at exact record boundaries through the observed prefix. No full-source
compact stock acceptance/rejection result is claimed yet.

**Latency fails practical delivery.** First512forwards took55.6seconds (~9.2/s)
under installed stock fallbacks. At that observed rate the longer reference count
would take about37hours; this is a conditional extrapolation, not a completion
promise.83.7M meets the proposed100M dense SIZE gate for the current bounded fixed
program, not the desired10–50M range or the practical complete-tool goal.

Run the same original source cases with:

```bash
PYTHONPATH=. /mnt/scratch/leanputer-native-venv/bin/python -m tools.kernel_compact_stock \
  --config benchmarks/kernel-full-source-stock/config.json \
  --source benchmarks/kernel-full-source-stock/source.jsonl \
  --report /mnt/scratch/compact-stock.json --offline-check
```

The source/controller correspondence test is `tests.test_kernel_stock_control`;
`tests.test_kernel_stock_datapath` checks the actual stock modules. The command
reports incomplete max-forward runs without an admission claim. Existing earlier
benchmark shapes/logs are historical checkpoints, not current full-tool evidence.

The original budget table's listed data rows summed to562, not662. The model
must count the separate136-channel pending packet and queue/control latches
explicitly; H768 remains a constraint to prove, not a width to increase silently.
All FFN intermediate sums as well as residual values need exactness bounds;
arbitrary-byte GDN state and unsafe signed same-MLP handovers remain excluded.

Evidence: [full typed program](../../benchmarks/kernel-typed-control-store/README.md)
and [actual stock module](../../benchmarks/kernel-shared-datapath/README.md).
These are coherent integration checkpoints, not task completion. Next is compact
phase dispatch, complete native action/encoding coverage, then the SAME original
source accept/reject through the small fixed stock model with full state checks.
