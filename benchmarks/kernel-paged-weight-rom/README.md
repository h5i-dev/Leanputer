# Paged weight-ROM and shared arena module

This is actual unmodified stock module evidence, not Lean source admission.
The fixed program is independent of the two runtime operand/claim inputs.

The112bit record is encoded as fourteen bytes plus a valid byte per128record
page. One reused128-way low-PC decoder occupies future RF read lanes; fifteen
SwiGLU units per page select bytes from dense weights. Seven shared stages decode
byte bits before RF queries. Payloads stored in GDN caches remain binary.
No sparse parameter storage, host dispatch or per-proof pruning is used.

The current module includes the three coherent RF read copies (nine heads),
seven arena heads for512 heap rows/32 frames/8 context words/4 readonly declaration
rows, model-owned binary write packets, and two-forward arena loads. The same
16bit shared arithmetic and comparisons drive weighted PC updates. Stock forward
and cache are unchanged. Constant position/mask kwargs supply only tensor shapes.

Targeted CPU stock checks: arithmetic wrap/borrow and all RF copies, ROM127/128
boundary, and all arena kinds with nonzero untouched fields; two claim values
produce accept/reject in the fixed module program. See check.log and arena.log.
Current module H768/I256/L38 =41,370,188 logical dense parameters,632 allocated
channels (479 features+140 scratch+13 ballast/tau). L38 includes25 data stages;
30 graph layers are currently occupied including front/ROM/decoder.

shapes.json is separately reproduced with stock meta allocation. At46245 records,
the current partial module shape is64,177,910 parameters/L59. This is CONDITIONAL:
complete native checker actions, encoding, wide words, shadow/dirty queue, commit,
source ports and admission are not connected. It is not a full checker size result.
The prior unphased typed reference uses about1.8M forwards per original source
case; paged ROM changes parameter size, not that unresolved latency cost.
