# General private inductive-header phase in stock weights

Algorithm/data map: [inductive-native.md](../../docs/kernel/inductive-native.md),
pinned inductive.cpp:check_inductive_types. The source driver now checks family
headers in the PREVIOUS environment, derives shared dependent parameter Locals,
reuses them across families, opens arbitrary bounded indices, compares mutual
result universes and creates output-only family descriptors in a PRIVATE list.
Lookup receives an explicit list head: duplicate checking can search earlier
private headers WITHOUT exposing them to header type inference. Committed Γ,
admitted declaration count and raw input cursor do not advance.

This is a generic phase, NOT inductive admission. The block controller still
returns GAP_INDUCTIVE because constructor/positivity/generation/nested/restoration
and generated recursor/constructor-name checks are unfinished. Raw recursor names
and claims remain untrusted. A valid private header does not become an assumed
public family or a proof acceptance. The full target algorithm is unchanged.

Seven focused all-state IR/reference/source-spec contracts PASS37.075s. Original
exported Prod/Eq headers derive0/1indices; a two-family block reuses A:Sort u/a:A
parameters with one/two-index telescopes. Negative nonuniform-domain,
mutual-result-universe, duplicate-name and private-header type-leak checks reject.
A previous private family cannot type a later header. Every failure leaves the
committed environment empty. Ordinary-source15regression PASS20.255s after
integration (explicit lookup-head-only intermediate check PASS18.233s).

Two targeted stock inputs: original symbolic Eq HEADER and synthetic two-family
dependent/indexed block. Both finish GAP_INDUCTIVE after deriving private headers,
with EXACT all registers and all heap/stack/constants/context cache rows. Eq has
1index; mutual families have1/2. This is not Eq.symm proof checking or a real
mathlib theorem count. The final ordinary target is not reached or assumed.

```bash
.venv/bin/python -m unittest tests.test_kernel_header_transition -v
PYTHONPATH=$PWD /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_header_smoke.py --device cuda \
  --report /mnt/scratch/general-inductive-headers-stock/report.json
```

[Report/inputs](report.json):heap256/stack16/context8/rawbank2/9-bit/f768/FFN512.
795,326,064BF16params/1,590,652,128weight bytes; H4032/L89.
Cold compile18.986000s/GPU forward96.439461s;
119boot/745forwards, native-completion+flush; CUDApeak1,628,407,296bytes.
Stock Qwen3_5ForCausalLM forward/cache and generated standalone weights; no
pretrained weights/custom forward/host checking or reduction. The longest744-step
module contract dictates batch completion, including cost on the shorter input.
No steady/full-source throughput, matched speed/size or broad differential/mathlib
coverage claim. All857source population rows remain the evaluation denominator.
