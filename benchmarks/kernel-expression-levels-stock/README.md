# Expression-wide raw universe substitution in stock layers

The shared controller traverses all twelve Expr tags and calls the SAME raw
symbolic substitution service for Sort and every Const universe argument.
Const vectors are traversed by their stored length and rebuilt using private
continuation/value frames. Empty mappings, empty vectors and unchanged vectors
preserve original syntax; temporary frames are discarded on the unchanged path.
Names, telescope lengths and universe argument counts are data, not branches.

Seventeen focused operation inputs complete: fourteen DONE and three
INVALID(UNIVERSE), retaining earlier scope/telescope contracts and adding an
all-tag algebraic term, the actual exported original `id` body, empty and
unchanged vectors. Every register and every materialized heap/stack/context
cache row matches the explicit development reference. Separate result checks
compare reconstructed syntax with the independent expression substitution spec.
References are used only after inference; no host semantic answers are packed.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --device cuda \
  --report /mnt/scratch/leanputer-runs/typed-expression-substitution-stock/report17.json
.venv/bin/python -m unittest tests.test_kernel_level_transition -v
```

Exact inputs/config/results: [report.json](report.json).
The stock class is Qwen3_5ForCausalLM, compiler-generated BF16 weights with no
pretrained download or custom forward/cache. Same128heap/16stack/8context/
8-bit/fuel128 capacities as the earlier typed services; the operation set grows,
so no matched performance or compression claim is made.
139,545,372parameters/279,090,744weight bytes; H1344/L47/FFN512;
compile4.381198s, GPU9.413113s,81boot+130forwards;
CUDApeak379,152,384bytes, hostRSS1,687,351,296bytes.
Timing excludes imports/offline validation; no steady-state/full-source speed
claim, saved weight artifacts, or broad evaluation campaign.

This is RAW universe instantiation. It does not implement canonical level
constructors/normalization, full conversion, inference or declaration admission.
DONE is operation completion, not theorem acceptance or mathlib coverage.
The full weighted checking driver remains unfinished.

Evidence is pinned to implementation `dbda05a`; later shared programs include
additional operations and need not have the same size/timing.
