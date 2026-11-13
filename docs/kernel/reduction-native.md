# Checked-environment weak-head reduction

Target authority: pinned `type_checker.cpp:whnf_core, is_delta,
unfold_definition_core, unfold_definition, whnf` and
`declaration.h:constant_info::has_value`. This is one general module in the
complete target, not a declaration-shape or selected-name extension.

The existing private argument stack walks application spines. Metadata is
transparent; Let and applied Lam use the shared capture-avoiding instantiation.
For a Const under a checked environment, use the SAME private environment lookup
and universe-arity zip as constant inference. Select its checked body according
to the source kind: definitions AND theorems have values; opaque declarations
and axioms do not unfold. Source `constant_info::has_value()` includes theorems.
For an unfoldable entry, instantiate the original body universe parameters with
the SAME all-Expr source-instantiation walker, restore the caller's context
window, then resume weak-head traversal with the SAME pending application spine.
Repeated aliases/beta/zeta are a data-controlled loop; no supplied reduction
schedule, specialized type or inferred answer enters memory.

An opaque/axiom head returns neutrally; unknown names fail the typed source
checking path. Missing definition bodies cannot be published by the source
driver. Public standalone beta/zeta operations start without a checked
environment and cannot access supplied raw declarations. Fuel/heap/stack/context
exhaustion is RESOURCE. All checked signatures/bodies are immutable and input
cannot encode checked records.

This module does not complete WHNF/conversion. Recursor/K/Quot/projection/literal
reduction and complete typed proof-irrelevance/eta/conversion remain target
modules with explicit GAP callers. Inductive block admission/generation remains
unfinished. Generic header/telescope/positivity/index/recursive-argument callers
reuse this service rather than introduce field-count/name-specific reductions.

Implementation: the SAME constant_machine/constant_rules lookup+zip now dispatch
on the private caller task (inference/type or WHNF/allowed checked body).
[Native4 exact-state/cache evidence](../../benchmarks/kernel-checked-delta-stock/README.md)
covers generic delta, opacity, application spines and symbolic universe zip.
The preceding ordinary-source benchmark is pinned e0db573 with beta/zeta only.

The subsequent generic binder integration must preserve two different source
operations. Opening a telescope creates fresh private Locals and checks its
WHNF before every binder; a bounded prefix returns its tail without opening
extra binders. Consuming a shared parameter telescope reuses the SAME previously
derived Local records: expose Pi, compare its domain against that Local's type,
instantiate the body with the existing Local, advance a data count. Each shared
parameter is checked in order so later domains see the earlier substitutions.
Universe symbol slots and Local slots have explicit context windows. The caller
owns context lifetime; the operation restores windows and never treats symbol
slots/raw types as Local assumptions. Header/constructor callers choose the
source-required normalization policy, not a supported shape class. Missing
conversion propagates GAP. Both loops must call the existing weighted services,
not copy a host telescope or precomputed uniformity result.
