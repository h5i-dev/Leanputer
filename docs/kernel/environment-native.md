# Native checked environment and source transaction integration

Ordinary transactions are implemented; full inductive/primitive integration remains
unfinished. Authority: pinned `src/kernel/environment.cpp`,
`type_checker.cpp:check_declaration, infer_constant` and `inductive.cpp` with the
complete target contract. Input raw declarations and private checked entries
MUST remain distinct. The existing typed core GAP_ENVIRONMENT cannot be closed
by simply reading a supplied raw type as its answer.

Physical ingress uses the six-word read-only raw declaration bank and an input
cursor separate from the admitted-signature counter. A declaration read port
returns raw kind/symbol/parameters/type/value/extra. Data transport does not
establish checking. Each inductive input may generate several checked entries,
so input-item count and admitted-declaration count must never be conflated.

The private environment is an immutable linked list of checked signature refs.
A checked signature160 holds `(symbol,type,schemeMeta)`; output-only metadata165
holds `(universeParameterVector,kind,payload)`. Definition payload is its checked
body; theorem/opaque/axiom kinds have their own source reduction permissions.
Family/constructor/recursor/primitive kinds point to generic derived metadata,
not to host-supplied field/index/recursor answers. Generic list cells carry the
previous environment link. No input packer branch may emit checked records.

The source driver starts with an empty checked environment. For ordinary
axiom/definition/theorem/opaque syntax it checks symbol/profile/name uniqueness,
universe-parameter uniqueness, raw type/body scopes, inferred type Sort and
required value-type conversion BEFORE publication. Non-axiom missing bodies
remain unavailable/GAP; they can never become axioms. Theorem declared types
must be propositions. Explicit axioms are tracked as assumptions only after
their types pass checking. The target scheme/body is checked under the complete
dependency environment, not published as an assumption. Missing callbacks GAP.

Constant lookup traverses only PRIVATE checked signatures, verifies universe
arity/scope and builds simultaneous binding records to call the SAME source
scheme-instantiation service. Delta reduction must use only a checked definition's
allowed payload; its general integration remains the next implementation. No raw type is accepted as an inferred result. Signature-name
and parameter vectors are data; no selected-library-name/field-count paths.

Inductive input goes through the complete header/telescope/positivity/nested/
index/recursive-argument analysis and shared motives/minors/rule generation
contract. Private provisional headers and generated declarations follow source
staging, then restoration/rechecking and atomic publication. All generated
names, elimination permissions, recursive descriptors and rule answers are
derived. Failure/GAP/resource exhaustion cannot publish the pending block.
Genuine kernel primitive/name interfaces alone receive source-justified rules.

Current implementation: `source_machine.py` is the development transition
reference; `source_rules.py` lowers the controller into the SAME stock program.
Private lookup/universe zip and raw parameter/name loops are shared modules.
Ordinary dependencies publish only after weighted checks. The target is checked
under that prefix; duplicate target names and target axioms reject. Missing
non-axiom bodies GAP_UNAVAILABLE_BODY. Genuine pinned native-execution interfaces
`Lean.reduceNat`/`Lean.reduceBool` report UNSUPPORTED_PROFILE; they are not
ordinary library-name special cases. A partially failed transaction does not
publish that declaration. Checked earlier dependencies and their assumptions
remain visible in the report.

[Stock source evidence](../../benchmarks/kernel-source-transactions-stock/README.md)
checks15source transactions including generated environments/constant use, exact
state and all cache banks. `leanputer.kernel_check` is the production syntax-only
loader/stock inference CLI; it invokes no reference checker. Every unavailable,
malformed, packing-resource or native-incomplete row remains in its ledger.
This is not full Lean checking or new native mathlib population coverage.
Inductive blocks/recursor claims/Quot still GAP, as do missing projection/literal
and complete conversion/reduction services. The generic algorithms above remain
the implementation target, not a completed native-support claim.
