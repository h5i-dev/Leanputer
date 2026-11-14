# Original-source literal checkpoint

Compiler-generated stock architecture retained; no host semantic result enters
inference. This directory is semantic/SELECTED Boolean IR evidence, not STOCK.
See docs/kernel/string-native.md for algorithms, authority and remaining limits.

* final-literals.log: final shared literal-type binding + String/Nat literal and
  Nat arithmetic source checks, PASS7tests542.320s. String460+28selected,
  Nat literal241+4terminal, Nat arithmetic636+4terminal; all states compared.
* source.log/source.jsonl: earlier String seven-case pass before type-only
  refinement,434selected, PASS2tests218.351s. Boundary outcomes there are reference
  checks, not additional Boolean comparisons. Raw source fixtures retain original
  declarations and goal data, no admitted metadata.
* cross-source.log: initial String integration, before shared type-only refinement,
  PASS9tests595.544s through arithmetic/Quot/conversion/projection/nested atomicity.
* cli.log: PASS2tests. Lean4.31.0 syntax-only exporter also compiles.
* prelude-helper-spec-*.log: one actual String.ofList closure262dependencies.
  Default fuel exhausts at151; increased fuel instead exhausts the65,536expression
  arena at197/Nat.div_rec_fuel_lemma. Neither is complete Prelude admission or IR.

Independent SPEC comparison is development verification only. Python Unicode,
integer and checker results are never inference inputs. No full Boolean run,
String STOCK, SMALL-model, throughput, corpus or full-kernel coverage claim.
The frozen10.35B historical stock smoke is not the small-model target.
