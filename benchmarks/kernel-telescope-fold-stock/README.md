# Generic telescope open/fold stock call chain

The finite controller compiles both directions of telescope traversal:
open Pi or Lam binders into fresh Local/type/info records; then fold those
records in reverse using the SAME all-tag abstraction walker. Prefix length,
opening kind and rebuilding kind are data. Pi-to-Lam reconstruction uses the
same compiled model, as do dependent types and preserved binder annotations.
No separate path is installed for any field/parameter count or declaration name.
Private substitution/abstraction/fold entries and continuations are inaccessible
to raw input. A public round-trip wrapper is only an operation test harness.

One stock `Qwen3_5ForCausalLM.forward`/cache model processes20probes:
16DONE/3INVALID/1RESOURCE(INDEX). Every register and every heap/stack/context
cache row matches the independent small-step spec exactly. The unit separately
compares reconstructed ASTs to the independent general open/fold operations,
checks scope restoration, context/fuel bounds and private-entry rejection.
DONE is operation completion, **not proof/declaration acceptance**. The full
native source driver, symbolic-level checking and conversion remain unfinished.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_operation_smoke.py --device cuda \
  --report /mnt/scratch/leanputer-runs/general-telescope-fold-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_traversal_machine -v
```

[report.json](report.json) includes exact raw inputs/configuration. Matching
capacities to the previous operation controller:64heap/16stack/8context,
8-bit words/fuel128. The semantic operation set is extended; this is not a
downsizing/performance comparison or a broad differential campaign.

94,988,498BF16params/189,976,996bytes; H1024/L42/FFN512;
compile3.696549s, GPU8.482352s,23boot+130forwards;
CUDApeak271,050,240bytes, hostRSS1,679,024,128bytes. Cold run, no steady-state
throughput claim, no weights saved. Runtime uses stock forward/cache and identity
feedback, without custom forward, pretrained models or host kernel operations.
Reference runs and cache/AST decoding are offline evidence only.
