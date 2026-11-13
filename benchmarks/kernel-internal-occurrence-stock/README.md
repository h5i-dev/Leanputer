# Composable internal current-family occurrence

Source: pinned inductive.cpp:has_ind_occ (find over ALL Expr children). The SAME
Expr walker searches a bounded raw symbol-set context window. Symbol identity
matches regardless of universe arguments; Param/name/literal numbers are not
constant occurrences. Unlike the preserved public OCCURS operation, the internal
service returns a Boolean through a PRIVATE stack delimiter on both early-match
and complete-no-match paths, preserving caller context. No host scan/answers.
This is the composable callback needed by generic strict positivity/index checks.

Nine focused IR/reference/source-operation cases PASS1.071s, all12Expr tags,
deep early match, false literal/level/projection-name matches, empty/multi-symbol
sets and nonzero context-window offset. Every nonempty case executes its private
return continuation while still RUNNING; caller symbols/count/context/free heap
are unchanged. Existing traversal operation contract PASS7.315s.

Native4:4DONE, Boolean1true/3false, EXACT all registers and all cache banks.
This is predicate operation evidence, NOT complete positivity, inductive
admission, proof acceptance or mathlib coverage. No supplied family/positivity/
typing answers enter the operation loader. Source callers will derive their
family set from checked headers; the standalone loader transports only raw
expression/symbol-set syntax.

```bash
.venv/bin/python -m unittest tests.test_kernel_occurrence_transition -v
PYTHONPATH=$PWD /mnt/scratch/leanputer-native-venv/bin/python -u \
  tools/kernel_occurrence_smoke.py --device cuda \
  --report /mnt/scratch/general-internal-occurrence-stock/report.json
```

[Exact report/inputs](report.json):heap64/stack16/context8/rawbank2/8-bit/f64/FFN512.
579,821,712BF16params/1,159,643,424weight bytes; hidden3584/layers73.
Cold compile14.017152s/GPU forward3.238526s;
23boot/25forwards, model-completion+flush; CUDApeak1,223,435,264bytes.
Stock Qwen3_5ForCausalLM forward/cache, generated standalone weights; no custom
forward/pretrained weights/host checker. Capacity/cases differ from prior
modules; no matched size/speed, steady-state or full-source claim. Complete
inductive generation/restoration and typed conversion/primitives remain unfinished.
