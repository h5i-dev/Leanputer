# Original-source String literal integration

Authority is Lean4.31.0 commit68218e876d2a38b1985b8590fff244a83c321783:
`Lean/Expr.lean:Literal.type`, `inductive.cpp:1191–1233`, `inductive.h:92–97`,
`type_checker.cpp:try_string_lit_expansion,reduce_proj_core`, and
`runtime/utf8.cpp:utf8_decode`. Hashes are in [sources.json](sources.json).

`string_rules.py` validates the already checked signatures of the finite genuine
expansion helpers String, Char, List, List.nil, List.cons, Char.ofNat and String.ofList.
Literal typing uses the shared literal_type_rules.py signature/Type0 check for
String alone. It does not require Nat or the expansion helpers.
Universe arities and the helpers specialized at zero are checked with general
instantiation/conversion. Nat uses its checked literal interface. There is no
fixed Char/String field layout, constructor spelling or List constructor count.
Ordinary declarations still use the complete general inductive algorithm.

The weighted controller reads the original UTF8 byte vector, decodes scalar
values with strict valid-Unicode bounds, and constructs Nat literals from low
and high16bit limbs. It builds the character list by generic linked-list folds
and returns String.ofList applied to that list. Empty strings, embedded NUL,
multibyte scalars and astral scalars use the same loops. No host decoding or
preconstructed character answer is passed to inference. Source Unicode syntax
rejects lone surrogates; malformed UTF8 is outside that transport domain.
A physical word below16bits gives RESOURCE INDEX rather than truncating scalars.

String literals remain inert under ordinary WHNF. `string_bridge_rules.py`
expands them only for projections, recursor-major preparation and the exact
String.ofList conversion extension. Recursor preparation returns directly after
normalizing the helper image, skipping structure eta on this branch as pinned
inductive.h requires. General structure eta and projections also handle a
transparent ofList whose WHNF is the ordinary String constructor. Owned frames
preserve literal/image/peer and the return branch across recursive services.

`string_reference.py` is an independent development specification. Its Python
Unicode decoding supplies expected results only; the native loader never calls
it. The original-source tests declare general Nat/Eq/List/Char/String blocks and
ordinary checked helper definitions, then require literal inference, projection,
recursor computation and opaque-helper conversion in the target proof. List has
three constructors; Char uses an arbitrary constructor name; String has either
one field or three fields including a dependent proof. All public schemes and
recursor RHS are compared with the independent EnvironmentDriver.

The initial six source cases passed362 SELECTED Boolean transitions comparing
ALL registers and memory banks (144.010s). This is selected IR and semantic
evidence, not full Boolean execution, actual Prelude-body admission or STOCK.
Final targeted run: PASS2tests218.351s, seven positive original-source cases
and434SELECTED all-state Boolean transitions. The extra case spans scalar
boundaries7f/80/7ff/800/d7ff/e000/ffff/10000/10ffff. Missing and mismatched
helpers GAP_PRIMITIVE; unequal λ/Λ literals INVALID TYPE_MISMATCH; a14bit word
RESOURCE INDEX; lone-surrogate source syntax is rejected. These four terminal
boundaries are transition-reference evidence (not separate Boolean comparisons).
The Lean syntax-only exporter compiles. Coupled regression evidence is recorded
in benchmarks/kernel-string-ir after completion.

Expansion helper signatures must already be checkable when expansion is needed;
unavailable/incompatible checked expansion helpers GAP. Literal typing has no
helper-closure bootstrap dependency: original source with String alone and an
ofList definition whose body contains a literal are separate targeted checks.
Actual pinned String.ofList is acyclic and contains no String literal, but its
complete exported dependencies have not been admitted here.
These boundaries remain explicit; no raw helper metadata is trusted.
A syntax-only export of actual String.ofList has262dependency records. A separate
development SPEC diagnostic hits fuel1,000,000 after151records; at10,000,000fuel
it instead exhausts the default65,536-expression arena after197records at
Nat.div_rec_fuel_lemma (1,865,610kernel steps). Neither run admits the complete
Prelude helper closure or supplies inference answers. No bound/profile campaign
was run; exact logs are archived with the String checkpoint.

The standalone compiler-generated stock forward/cache architecture is retained.
There is no String STOCK run or new size/performance claim. The frozen10.35B
original-source stock smoke is not the SMALL-model goal, which remains unmet.

## Final literal-typing checkpoint

The final combined targeted run passes7tests542.320s: String, Nat literals and
Nat arithmetic. String has seven projection/recursor/opaque-extension source
cases with460SELECTED all-state Boolean transitions, plus String-only typing and
literal-bearing helper bootstrap with28SELECTED transitions. Nat literal cases
have241SELECTED transitions and four terminal all-state comparisons; all15Nat
operations and mixed Quot/Bool normalization have636SELECTED transitions plus
four offset/shift boundary comparisons. Public schemes/RHS match independent
SPEC and positive cases have no assumptions. These are development/reference
and selected IR checks only. Logs: benchmarks/kernel-string-ir/final-literals.log.

The initial String integration also passes the coupled9test595.544s regression
through Nat arithmetic, Quot, conversion, projection and nested-source atomicity
(benchmarks/kernel-string-ir/cross-source.log). That run precedes the shared
literal-type-only refinement; its exact scope is separate from the final literal
run above. CLI2tests pass. There is no new STOCK run or small-model evidence.
