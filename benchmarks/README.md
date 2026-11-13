# Recorded benchmark evidence

`mathlib-v4.31.0` retains a complete 857-row selected population/outcome manifest
for four fixed owner modules, before expression filtering. These are ground
universe instances, one per source theorem. See `docs/mathlib-evaluation.md` for
scope, pins, trust boundaries, resource limits, timing definitions and commands.
Initial measurements are labeled single-run development observations; repeat
measurements retain raw samples. The entire mathlib library is not enumerated.

Large proof syntax, traces, full evaluation reports and weights remain outside
Git on scratch. Reproduction regenerates them from the pinned source and exact
selection protocol. Compact committed summaries retain corpus/compiler hashes
and experimental provenance, including dirty worktree status where applicable.
A row marked UNSUPPORTED was screened by external syntax preparation and was
never accepted by the weighted checker. Logical rejects, resource failures and
external-reference tool failures must remain distinct from successful proofs.


`native/let-true-{baseline,compact}.json` compare the same six regression rows
under identical capacities/fuel and feature set:3ACCEPT,1REJECT,2UNSUPPORTED.
Only one row is a new real mathlib theorem; this is not a population coverage
estimate. The files retain actual model bytes/parameters, memory and cold
compile/fixed forward costs. Input/config files reproduce the comparison.
See docs/native-downsizing.md for timing boundaries and remaining limitations.
