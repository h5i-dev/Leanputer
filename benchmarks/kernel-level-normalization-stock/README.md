# Generic symbolic normalization and equivalence in stock layers

The complete level normalizer traverses all five admitted tags with private
continuations. It merges canonically ordered Max chains, compares structural
bases, retains each base's greatest successor offset, defers the explicit-
universe subsumption decision until all offsets are known, distributes Succ
and normalizes IMax through the SAME smart constructors. Equivalence normalizes
both inputs and calls the SAME structural comparator. Counts/names are data.
See the [source and algorithm map](../../docs/kernel/level-services.md).

Ten focused operation inputs complete DONE: six normalizations and four
true/false equivalences. They exercise nested sorted merging/deduplication,
retained/subsumed explicit universes, successor distribution, symbolic IMax
and commuted Max inputs. Every register and every materialized heap/stack/
context cache row matches the independent development transition reference.
Output syntax/booleans separately match LevelOps; no expected normal forms or
equality answers are loaded. CPU module10tests PASS10.814s retains shared
operations and checks absorbing HEAP/STACK/FUEL exhaustion as RESOURCE.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --group normalization --device cuda \
  --report /mnt/scratch/leanputer-runs/typed-level-normalization-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_level_transition -v
```

[Exact report/inputs](report.json). SAME128heap/16stack/8context/8-bit/f128
capacities; semantic traces25..123steps/free28..63. Stock Qwen3_5ForCausalLM
forward/cache, compiler-generated BF16weights, no pretrained weights/custom
forward. 264,750,828parameters/529,501,656bytes; H2176/L55/FFN512;
compile6.097287s/GPU10.945187s;53boot+130forwards;
CUDApeak599,871,488bytes/hostRSS1,691,234,304bytes.
Timing excludes imports/offline checks; no speed/compression or steady-state/
full-source throughput claim. No weight artifacts or broad campaign.

These operations do not establish proof/declaration acceptance. Conservative
universe geq, typed inference/conversion, generic admission and the whole-source
weighted driver remain unfinished. No new native mathlib coverage or formal
verification is claimed.
