# Read-only raw declaration port in the stock kernel ABI

Historical checkpoint0e968c7. Subsequent source transactions are documented
[here](../kernel-source-transactions-stock/README.md).

The six-word raw declaration bank is now materialized/read through a STOCK cache
head, addressed by raw_index separately from the admitted-signature counter.
The generic circuit harness follows the declared port layout rather than
assuming only heap/stack first reads. Checked-scheme tag165 is reserved OUTPUT
only; no syntax packer emits checked entries. The full checked-environment and
publication algorithm is specified [here](../../docs/kernel/environment-native.md).
Cursor advancement/checking/publication is still subsequent implementation.

Two focused inputs retain positive typed inference and GAP for a supplied RAW
axiom signature. All registers and ALL FOUR materialized cache banks, including
nonzero raw declaration data, exactly match reference state. Admitted count is0:
the raw signature is NOT an inferred/admission answer. The report's assumptions
metadata lists declared raw axiom candidates; this operation uses no admitted
axiom environment. Typed-core controller2tests PASS5.651s after ABI integration.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_level_smoke.py --group environment-abi --device cuda \
  --report /mnt/scratch/leanputer-runs/general-raw-environment-abi-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_inference_transition -v
```

[Exact report/inputs](report.json). Heap128/stack16/context8/raw-bank2/8-bit/f128.
Stock Qwen3_5ForCausalLM forward/cache, generated BF16weights, no pretrained
model/custom forward. 365,385,526parameters/730,771,052weight bytes; H2752/L60/
FFN512; compile7.527337s/GPU11.999520s;40boot+130forwards;
CUDApeak759,309,824bytes/hostRSS1,689,899,008bytes.
Different batch/fuel from the inference17 report; no matched-speed/compression
claim. Imports/offline checks excluded, no steady/full-source throughput claim,
saved weights or broad campaign.

This is raw memory transport evidence, NOT declaration admission/theorem/mathlib
coverage. The typed controller still GAPs checked-environment/projection/literal/
full-conversion callbacks; source checking and publication remain unfinished.
