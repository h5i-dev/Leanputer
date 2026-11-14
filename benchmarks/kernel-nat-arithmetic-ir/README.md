# Nat arithmetic and typed offset source evidence

[Fixed kernel algorithms, scope and remaining gaps](../../docs/kernel/nat-arithmetic-plan.md).
These tests use synthetic original source: general Nat/Eq/Bool blocks, genuine
Quot initialization/claims and ordinary checked function definitions with simple
bodies. Pinned C++ reduce_nat takes precedence on numeric operands; neutral and
capped terms still use ordinary delta. This is not exported Std body admission.
No source annotation supplies an inferred value or acceptance answer.

- source-ir.log: PASS1test200.332s; six source cases,636SELECTED Boolean transitions
  compare ALL registers and banks, including owned returns. Independent SPEC
  accepts with no assumptions; every public signature and recursor RHS matches.
  Source ordinary Nat.add over propositions has no Nat datatype and still checks,
  leaves nat_validated0, DONE695steps/124heap/1published signature. Composed true/
  false predicates with mixed Quot/Nat/Bool-rec operands DONE52210/52209steps,
  heap5259/5257. Multi-limb multiply/divide DONE41386steps/4926heap. Semantic pow
  cap delta fallback DONE36852/3516. Zero/literal conversion DONE36722/3434.
  These last five cases publish29signatures/3original block origins, not29raw rows.
- bounds.log: PASS1test39.619s; invalid universally quantified offset proof returns
  INVALID TYPE_MISMATCH; huge right/zero-left shifts DONE; huge nonzero-left shift
  RESOURCE INDEX. Four selected final transitions compare ALL state. Prefix
  publication remains29signatures.
- regression.log: PASS9tests364.831s; Nat literals/bounds, Quot source/atomicity/
  collision fence, typed conversion, projections, nested source/atomicity.
- quot-collision-gap.log: PASS1test1.981s; actual prior ordinary Quot inductive + Eq
  commits, genuine init collision GAPs without changing environment/origins.
  Pinned add_quot replaces bindings, but whole-prefix invalidation/rechecking is
  unfinished here. The explicit GAP prevents stale original-block provenance.
- cli.log: PASS2tests; reporting and syntax-only inference CLI boundaries.

Raw input.jsonl records the composed source. Independent SPEC and the fixed-rule
transition interpreter are development checks; they supply no native inference
answers. Selected Boolean steps do not establish complete-step Boolean/stock
execution. No Nat arithmetic STOCK or SMALL-model evidence is claimed. Frozen
f5bb04d's10.35B original-source smoke is not a small model. String/bootstrap/
projection/conversion and the explicit metadata/Quot-overwrite gaps remain.
