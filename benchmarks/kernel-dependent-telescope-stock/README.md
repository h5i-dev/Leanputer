# Shared dependent telescope parameter reuse in stock weights

Historical checkpoint efcc5af; subsequent shared-service changes have separate evidence.

Authority: pinned inductive.cpp:check_inductive_types/check_constructors and
[general lowering contract](../../docs/kernel/inductive-native.md). Opening now
calls shared weighted WHNF before EVERY binder. A bounded prefix returns its
tail without opening extra binders. Consuming a parameter prefix reuses the SAME
previously derived Local records, checks each dependent domain, substitutes that
Local and advances a data count. Private frames preserve caller loop/binder
state across WHNF/conversion/substitution. No name/field-count paths.

The pure syntax-only operation loader takes two closed telescopes/count/policy;
weights validate symbolic parameters/scopes and derive the Local environment.
It cannot supply Local/type/uniformity answers. Source-required header WHNF and
raw-constructor-prefix policies are data. This is OPERATION evidence, not
inductive or source admission. The source driver still GAPs raw inductive blocks.

Eleven focused IR/reference/independent-operation contracts PASS24.346s:
prefix0/1/2/4, dependent A/x/P:A→Prop/h:P x, metadata WHNF, raw prefix policy,
definite domain mismatch, short telescope, free Local and physical bounds.
Source results are compared after abstracting distinct fresh-Local namespaces.
Inference3caller tests PASS8.641s; telescope physical-bound contract PASS3.159s.

Seven targeted stock cases:4DONE/2INVALID/1RESOURCE, EXACT all registers and all
cache rows. Cases use EMPTY/four-binder prefix, raw vs WHNF policies and negative
scope/domain/resource. DONE returns a term and derived Local context, not a proof
acceptance. Complete conversion gaps still propagate GAP rather than inequality.

```bash
.venv/bin/python -m unittest tests.test_kernel_telescope_reuse -v
PYTHONPATH=$PWD /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_telescope_smoke.py --device cuda \
  --report /mnt/scratch/general-dependent-telescope-stock/report.json
```

[Report/inputs](report.json):heap256/stack16/context8/rawbank2/9-bit/f384/FFN512.
677,468,896BF16params/1,354,937,792weight bytes; hidden3776/layers81.
Cold compilation16.196180s/GPU forward42.687188s;
36boot/353forwards with native completion+flush; CUDApeak1,432,180,736bytes.
Stock Qwen3_5ForCausalLM forward/cache with compiler-generated standalone weights;
no pretrained model/custom forward/host checker. No compression/speed comparison:
program/boot/cases differ from prior source/delta probes. No broad campaign,
mathlib fraction/full-kernel support or formal compiler verification claim.
