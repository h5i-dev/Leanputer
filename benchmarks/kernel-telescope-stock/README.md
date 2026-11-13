# Declared telescope stock operation

The shared controller now opens an arbitrary bounded declared Pi telescope or
a requested prefix. The count is input data. Each iteration creates a fresh
Local and private `(Local,type,binderInfo)` record, then calls the SAME
capture-avoiding substitution service to instantiate dependent later domains.
An initial weighted variable-scope walk rejects raw free BVars/Locals. This is
the source's declared-telescope operation, not full typing/universe checking or
normalizing a type hidden behind a definition. All those services remain
separate kernel operations.

The SAME stock model processes16syntax/operand probes:12DONE,3INVALID and
1RESOURCE(INDEX). Missing requested binders yield INVALID/EXPECT_PI; open raw
variables yield INVALID/SCOPE. All registers and every heap/stack/context cache
row, including derived binder records, match the independent transition spec.
DONE means operation completion, **not declaration or proof acceptance**.
The full native source driver remains unfinished.

```
PYTHONPATH=/mnt/scratch/leanputer-runs/kernel-algorithms-tree \
  /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_operation_smoke.py --device cuda \
  --report /mnt/scratch/leanputer-runs/general-telescope-services-stock/report.json
.venv/bin/python -m unittest tests.test_kernel_traversal_machine -v
```

[report.json](report.json) includes exact inputs/configuration. The focused
unit also verifies exact states at context/fuel exhaustion and rejects raw
entry into the internal single-substitution service. No broad campaign.

Stock `Qwen3_5ForCausalLM.forward`/cache, no custom forward or pretrained model.
81,068,240BF16params/162,136,480bytes; H896/L41/FFN512;
64heap/16stack/8context cells,8-bit words/fuel128.
Compile3.487982s, GPU8.279263s including23boot+130forwards;
CUDApeak226,847,232bytes, hostRSS1,682,092,032bytes. Cold run, no steady-state
or complete-checker speed comparison. No weights saved. Python specs/cache
decoding are offline checks and never provide inference-time answers.
