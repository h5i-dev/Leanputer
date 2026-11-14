# Tail clearing and boot-channel reclamation

Actual STOCK CUDA BF16 passes the same full fixed source checker, unchanged
word16/heap512/stack32/context8/constants4/fuel8192 and source accept/reject pair.
Original E + standalone E.rec claim + identity proof DONE/NONE1316steps; wrong
proof INVALID/TYPE_MISMATCH1355steps. All951registers/all17cache partitions exact
against the SPEC computed after inference. No assumptions; two public signatures.

Boot-only inputs stop occupying persistent channels. Their slots can be used
after the last read. Stock FFNs at the end of each forward clear all temporary
physical slots, including reused boot slots, before identity hidden-state
feedback. Control/pending-write packets stay intact. This removes the reserved
64layer clearing prefix; it does not change kernel rules or data bounds.

| Same whole program |3373602 phase scratch|Tail clearing|
|---|---:|---:|
| Logical parameters |9,066,086,190|8,128,493,942|
| Hidden width / layers |10240/564|9984/518|
| Persistent / allocated slots |1380/10036|1122/9778|
| Nonzero values |1073704|1074141|
| Stored CSR bytes |130917126|118467864|
| Two-case forward seconds |1161.105|1081.347|

The model remains **too large and slow**. Stored bytes are not small logical
architecture evidence. The faster f05dc32 alternative was856.180s at12.010B.
Compile180.853s excludes artifact saving; CUDA peak186781696bytes. These are
development integration timings; CPU-only compiler analysis also ran during
part of validation. No broad campaign or steady-state throughput claim.

The targeted tail-clear test passes3.841s, including FOUR identity-feedback
steps, reclaimed boot input and exact zero in every unprotected physical slot.
This test is separate from the actual full source evidence above.

Artifact: `/mnt/scratch/leanputer-runs/current-full-stock/compiled-source-tail/`.
The normal source CLI loads it without compiler or SPEC processing. A separate
complete load-and-admit run was not repeated. Development reproduction:

```bash
/mnt/scratch/leanputer-native-venv/bin/python -m tools.kernel_stock_delivery \
  --input benchmarks/kernel-full-source-stock/source.jsonl \
  --config benchmarks/kernel-full-source-stock/config.json \
  --bank-control --native-word-ops --phase-scratch --tail-clear --device cuda \
  --report /mnt/scratch/leanputer-runs/current-full-stock/reproduced-tail.json
```

Names/shapes/counts stay input data. No pretrained model, external checker,
host dispatch, CPU emulator, semantic inference preprocessing or custom forward
is used. SMALL/practical delivery, larger/nested native source evidence and the
documented general semantic gaps remain unfinished. The next active layout
groups Boolean contributions by exclusive model owner; its evidence is separate.
