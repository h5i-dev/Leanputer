# Native checked environment and source transaction integration

Work in progress. Authority: pinned `src/kernel/environment.cpp`,
`type_checker.cpp:check_declaration, infer_constant` and `inductive.cpp` with the
complete target contract. Input raw declarations and private checked entries
MUST remain distinct. The existing typed core GAP_ENVIRONMENT cannot be closed
by simply reading a supplied raw type as its answer.

Physical ingress uses the six-word read-only raw declaration bank and an input
cursor separate from the admitted-signature counter. A declaration read port
returns raw kind/symbol/parameters/type/value/extra. Data transport does not
establish checking. Each input may eventually generate several checked entries,
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
scheme-instantiation service. Delta reduction uses only a checked definition's
allowed payload. No raw type is accepted as an inferred result. Signature-name
and parameter vectors are data; no selected-library-name/field-count paths.

Inductive input goes through the complete header/telescope/positivity/nested/
index/recursive-argument analysis and shared motives/minors/rule generation
contract. Private provisional headers and generated declarations follow source
staging, then restoration/rechecking and atomic publication. All generated
names, elimination permissions, recursive descriptors and rule answers are
derived. Failure/GAP/resource exhaustion cannot publish the pending block.
Genuine kernel primitive/name interfaces alone receive source-justified rules.

The current typed controller and raw transport are operation evidence, NOT this
complete declaration transaction. This document specifies the integration being
implemented; it claims no new native source theorem/mathlib coverage.
