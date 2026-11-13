# Pinned mathlib coverage protocol and initial results

These are measured results for **four fixed owner modules**, not the whole
mathlib library. The module choice preceded expression inspection:
`Mathlib.Logic.Basic`, `Mathlib.Logic.Function.Basic`,
`Mathlib.Algebra.Group.Defs`, `Mathlib.Data.Nat.Basic`.

Lean 4.31.0 kernel commit: `68218e876d2a38b1985b8590fff244a83c321783`.
Mathlib v4.31.0 commit: `fabf563a7c95a166b8d7b6efca11c8b4dc9d911f`.
The enumerator consults original declaration kinds, including theorem bodies
that Lean's imported environment might otherwise expose as axioms. Private and
internal declarations remain in the population manifest, then the documented
public population excludes them. There were 1,033 original theorem declarations,
857 public declarations, all with available bodies. Public counts by owner:
354 Group.Defs, 245 Function.Basic, 243 Logic.Basic, 15 Nat.Basic.

Selection ranks `SHA256("814732/module/name")` before any body or feature
filtering. The initial discovery sample contained 200 names; the population
experiment selects all 857. Exactly one ground universe instance, setting every
parameter to level 1, is checked for each source theorem. This measures ground
instances, not a theorem valid for every symbolic universe instantiation.
Structured native name parts are preserved to avoid quoted-name aliasing.

The exporter traverses the original term, claim and full reachable supported
environment. It performs no inference, normalization or correctness labeling.
Opaque bodies are required and checked. Genuine axioms are explicit. An absent
non-axiom dependency body is unsupported, never an invented free assumption.
The four exported population judgments have empty dependency environments.
There is no trusted-library mode, verified-dependency cache or environment-cost
amortization in these results.

## Initial coverage and fixed-budget costs

All population rows survive export and batching. The exporter produced 853
`UNSUPPORTED` records and four syntax documents in 3.577 seconds using an
already provisioned Lean/mathlib cache. This excludes checkout/cache download,
which is setup rather than proof-checking work.

| Heap / fuel | ACCEPT | RESOURCE | UNSUPPORTED | Accepted fraction | CUDA fixed-batch forward |
| --- | ---: | ---: | ---: | ---: | ---: |
| 256 / 2,048 | 1 | 3 heap | 853 | 1/857 (0.117%) | 6.266 s |
| 2,048 / 16,384 | 4 | 0 | 853 | 4/857 (0.467%) | 59.161 s |

Both runs use optimized `attention_delta` writes, float32, one packed batch of
four attempted judgments, CUDA graph replay on an NVIDIA A10G, fixed fuel+1
transitions, and absorbing finished states. Context/continuation capacities are
32 at the smaller budget and 64 at the larger; constants=16 and universe=4.
These are initial single-run observations, **not repeat-based latency estimates**.
The smaller budget's accepted throughput is 0.1596 proofs/s; the larger budget's
is 0.0676 proofs/s. Unsupported screening does not count as accepted throughput.

The larger model has 104,463 state bits/item (417,852 float32 bytes), 1,805,104
buffer bytes, 34,272 sparse nonzeros and 43 logical sequential stages/step.
Compilation/device placement took 0.497 s; graph setup 0.320 s; syntax encoding
0.136 s; weighted initialization 0.0109 s. Compile+check elapsed was 60.239 s,
excluding Python process startup, external export and independent references.
Peak PyTorch-allocated device memory was 31,039,488 bytes, which is not total
CUDA driver/process memory. The host has an AMD EPYC 7R32, four visible logical
CPUs; evaluation uses one PyTorch CPU thread.

| Accepted source theorem | Input DAG nodes | Semantic steps | Allocated nodes |
| --- | ---: | ---: | ---: |
| BAll.imp_left | 40 | 1,060 | 148 |
| forall₂_imp | 74 | 4,453 | 599 |
| BAll.imp_right | 48 | 2,037 | 272 |
| forall₃_imp | 136 | 12,332 | 1,620 |

All four agree with the operational specification, independent recursive oracle,
actual Lean kernel replay and nanoda. The final whole-state digest also agrees
with the operational specification. Full per-step traces were checked on the
smaller accepted case; the large population run uses final-state comparisons,
not a claim that every large trace was retained. The 853 unsupported cases do
not receive a weighted proof-checking verdict. Most first-encountered failures
are inductive/structure dependencies (including Decidable, Eq, Exists, Iff,
Mul/Add and Monoid). This is a first-failure histogram, not a complete syntax
feature census. Inductives, eliminators and symbolic universes are the main
coverage gaps. Fresh syntax allocation and a common fixed fuel limit also make
current accepted throughput poor.

A negative development result is preserved: the original wide Boolean-memory
controller took 48.961 s on CUDA graphs versus 16.598 s CPU eager for the same
single exported discovery proof at heap256/fuel2048. Attention writes reduced
that development sample to 6.173 s CUDA / 5.993 s CPU. These samples were not
controlled repeated trials. No GPU speedup is claimed from them.

## Reproduction

Provision the pinned mathlib checkout and its module cache outside this repo.
Then enumerate/export all public declarations and run the complete denominator:

```bash
python -m leanputer.mathlib_benchmark --mathlib /mnt/scratch/leanputer-mathlib \
  --count 1000000 --output /mnt/scratch/leanputer-runs/mathlib-population
cat > /mnt/scratch/leanputer-runs/mathlib-config.json <<'JSON'
{"heap":2048,"stack":64,"context":64,"constants":16,"universe":4,"fuel":16384}
JSON
python -m leanputer.evaluation \
  --input /mnt/scratch/leanputer-runs/mathlib-population/corpus.jsonl \
  --config /mnt/scratch/leanputer-runs/mathlib-config.json \
  --output /mnt/scratch/leanputer-runs/mathlib-evaluation \
  --device cuda --execution cuda_graph --memory-update attention_delta \
  --batch-size 16 --lean --repeats 3
```

Add `--nanoda /path/to/nanoda_bin` for independent Rust replay. Tested nanoda_lib
v0.4.32 revision: `0da9f98feadd3a0a2ef4b3dbcf52a298a6fef929`.
Reports retain all rows, corpus hashes, source constants, selected input positions,
resource reasons, actual/strict steps, configuration, fixed buffers, numerical
settings, cold compile/check costs and raw reused-weight repeat timings with
median/nearest-rank p95. Export manifests retain enumeration/export costs and
unsupported reasons. A subprocess startup measurement must be added separately
when reporting a full cold pipeline; adding these internal timings alone omits
Python/PyTorch startup. Repeats reuse weights/graphs, not proof answers.

For the explicit fresh-process boundary, use the harness below. It preserves
raw per-trial timings and the complete population/preparation/evaluation files:

```bash
python -m leanputer.pipeline --mathlib /mnt/scratch/leanputer-mathlib \
  --config /mnt/scratch/leanputer-runs/mathlib-config.json \
  --output /mnt/scratch/leanputer-runs/mathlib-pipeline \
  --device cuda --cold-repeats 1 --steady-repeats 3
```

The cold timer starts before enumeration and stops on the child's
`checking_complete` event, before repeat timing and reference validation. The
cache is provisioned and file-system pages may already be warm; this measures
fresh checker processes, not a rebooted machine or first-ever dependency setup.
The parent harness's own Python startup is explicitly outside that timer.

## Fresh-process repeated measurement

A completed CUDA pipeline trial reran all 857 exports, with the same 4 ACCEPT /
853 UNSUPPORTED and zero model/reference/final-state mismatches. Cold time was
69.624 s: preparation 7.922 s (enumeration 4.175 s, export 3.665 s and manifest
overhead), plus fresh checker process 61.702 s. That includes 1.321 s of child
startup/input overhead beyond its internal compile/check timer. Provisioned
checkout/cache and parent harness startup remain outside the boundary.

Three reused-weight/graph forward samples were 59.153644, 59.153518 and
59.153688 s. Median 59.153644 s; nearest-rank p95 59.153688 s (the maximum of
only three samples, not a statistical tail estimate). Median accepted throughput
is 0.06762 proofs/s for four proofs, including the fixed fuel overhead. No
additional graph capture was required. Complete raw compact records are in
`benchmarks/mathlib-v4.31.0/cuda-pipeline.json` and
`cuda-repeated-evaluation.json`; all selected outcomes remain in
`population-outcomes.jsonl`. No other GPU workload ran concurrently.

A minimal cache-provisioning command (run in the pinned checkout) is:

```bash
MATHLIB_CACHE_DIR=/mnt/scratch/leanputer-mathlib-cache lake exe cache get \
  Mathlib/Logic/Basic.lean Mathlib/Logic/Function/Basic.lean \
  Mathlib/Algebra/Group/Defs.lean Mathlib/Data/Nat/Basic.lean
```

The recorded setup fetched 128 reachable module artifacts. The benchmark does
not require downloading the complete mathlib cache or any language-model
weights. Pin the checkout before provisioning, and retain the generated
`lake-manifest.json` hash in the selection manifest.

## Current syntax boundary

The Bool99-phase exporter refresh produces362EXPORTED/495UNSUPPORTED, retaining
all857selected ground instances and their names. Export took8.877814s on the
provisioned cache. This is syntax coverage, not native proof acceptance; native
checking_status is NOT_RUN_IN_THIS_REFRESH for every row. Unknown unsupported
dependency closures have null assumption and size metadata. Complete compact
records are in benchmarks/mathlib-v4.31.0/current-fragment. Reproduce this
syntax-only report with:

```bash
python -m leanputer.mathlib_benchmark --mathlib /mnt/scratch/leanputer-mathlib \
  --count 857 --output /mnt/scratch/leanputer-runs/mathlib-bool-fragment \
  --syntax-report Bool99phasefixedfragment
```

The earlier whole-population4/857 proof result above belongs to the old custom
reference backend. Current native feature checkpoints validate selected sources
and small relative fixtures with different budgets; they do not constitute a
new matched full-population result. Broad native replay remains deferred.

The subsequent Option100-phase syntax refresh retains the same857names:
366EXPORTED/491UNSUPPORTED, export7.871665s. It supersedes the Bool snapshot in
the current-fragment files; historical hashes/outcomes remain in Git history.
Use --syntax-report Option100phasefixedfragment for that feature boundary.
This is still a syntax-only update with every checking_status NOT_RUN, not a
new native proof-coverage fraction.
