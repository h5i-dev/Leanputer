# Simultaneous raw symbolic substitution in stock layers

The shared controller maps parameter symbols to level DAG arguments using typed
binding records and a count-driven forward search. Replacements are returned
without rewriting them again: substitution is simultaneous. Missing mappings
leave parameters unchanged; duplicate keys use the first supplied pair, matching
the pinned list-instantiation operation. Declared parameter uniqueness is a
separate admission rule. No name/arity/field-count catalog is involved.

This is RAW syntax substitution over all five level tags. Canonical constructors,
normalization/equality and full typing remain separate unfinished weighted
services. The model does not accept declarations or proofs through this entry.
Binding records are operation arguments, not inferred types/admission answers.

An argument-window offset lets callers preserve earlier context slots. The
same stock model checks12probes:9DONE/3INVALID(UNIVERSE), including retained
symbolic scope/Pi/Lam calls, simultaneous non-rewriting, empty/missing maps,
first-match behavior and a preserved opaque caller prefix. Every register and
every materialized heap/stack/context cache row matches the independent spec.
The prefix is opaque caller data, not an admitted local-context declaration.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --device cuda \
  --report /mnt/scratch/leanputer-runs/typed-level-substitution-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_level_transition -v
```

Exact inputs/config/results: [report.json](report.json).
Same128heap/16stack/8context/8-bit/fuel128 capacities as the earlier typed smoke;
the semantic operation set changes, so no downsizing/speed comparison is claimed.
114,447,832BF16params/228,895,664bytes; H1152/L45/FFN512;
compile3.969430s, GPU9.039274s,64boot+130forwards;
CUDApeak294,769,664bytes, hostRSS1,682,948,096bytes.
Timings cover cold compilation and forward execution, excluding imports/offline
validation, with no steady-state/full-source throughput claim. No weights saved,
no broad campaign, no native full-source/mathlib coverage claim.
