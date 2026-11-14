# General typed conversion lowering

Authority: pinned Lean68218e876d2a38b1985b8590fff244a83c321783,
`type_checker.cpp:is_def_eq_core`1056–1134, `quick_is_def_eq`740,
`is_def_eq_binding`690, `is_def_eq_proof_irrel`836, `is_def_eq_app`815,
`try_eta_expansion_core`778, `try_eta_struct_core`793 and
`is_def_eq_unit_like`1043. `type_checker.h`86–93 tries both eta orientations.

The connected fixed tag/typed algorithm includes:
structural quick equality; dependent binding comparison with scoped fresh locals;
symbolic Sort/literal quick cases; checked WHNF; proof irrelevance by inferred
proposition/type comparison; constant universe equivalence; neutral projection
and application congruence; function eta; checked nonrecursive-structure eta;
and unit-like equality. Every count/name is data. No type or conversion answer
is supplied by the input loader or by an external checker.

The implementation uses eager checked delta/WHNF in place of the pinned lazy
optimization. This can change physical costs, but a resource failure never means
inequality. Subsequent [Nat arithmetic](nat-arithmetic-plan.md),
[Quot](quotient-native.md) and [String](string-native.md) controllers connect the
genuine primitive reductions and typed offset/String extensions. Final
canonical-form negatives no longer blanket GAP on literals or constant-headed
applications after these paths. Missing/incompatible primitive bindings and
unavailable private metadata remain explicit boundaries. The measurements below
are historical pins, not evidence for later primitive controllers.

Conversion contexts and all live data must belong to task-owned frames and
immutable records across recursive inference, conversion and WHNF. A returned
answer restores the entering Local-context mark. Structure eligibility/counts
come from checked family/constructor/recursor records, never a supplied functor
or structure flag. Missing private metadata is explicit GAP, not assumed false.

Current post51e4ce0 implementation connects `conversion_rules.py` and
`structure_info_rules.py` to every source conversion caller. The old
`CONVERT_POSITIVE` task delegates to this general controller. The independent
SPEC implements these rules separately. No converted/inferred value is loaded
from that SPEC into the native runner.

Six original-source cases pass: proof irrelevance, function eta, dependent binder
comparison, structure eta, unit-like equality and two symbolic universe arguments
whose original expressions differ but normalize equivalently.249selected Boolean
transitions match all registers/banks. Combined conversion/projection/nested/
ordinary/CLI regression passes7tests266.436s; the nested fixture now takes188094
reference transitions and retains12signatures/2original origins. All public
schemes, indexed recursor names and RHSs still match independent SPEC.

A malformed recursor claim reaches INVALID TYPE_MISMATCH at adequate physical
bounds:4835transitions,565heap rows including null,51selected Boolean checks,
no public admission. At the historical16-frame configuration it reaches RESOURCE
STACK; that result is not inequality or rejection. Focused claims regression
passes2tests220.719s with both bounds documented. No conversion STOCK run or
full-kernel/primitive support is claimed.

The name audit also removed an earlier unsupported nonempty-name assumption:
pinned `environment.cpp:check_name` checks duplication, not anonymity. Anonymous
paths get ordinary positive symbol IDs; symbol0 stays the physical sentinel.
The recursor-name comparison now handles a zero-length prefix through its normal
counted-loop boundary. Two original-source cases match every Boolean state and
the independent SPEC (1test48.369s). This is name data, not a named primitive rule.
