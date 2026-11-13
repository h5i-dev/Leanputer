# General inductive lowering and shared loops

Complete target/data contract: target.md and pinned `inductive.cpp`, with
original raw cells96..100 in native-cells.md. No library names, constructor
field-count classes or host-derived positivity/index/recursor answers define
this implementation. Count branches are only source semantics (including Prop
elimination/K rules) or physical bounds. This document records the module
integration order, not a claim that an incomplete module admits a block.

1. Validate the raw block/universe/name vectors. Check every header as a closed
   type in the previous checked environment, BEFORE the temporary family overlay.
   Open shared parameters from the first header. For every other header reuse
   the SAME Local records, checking dependent domains in order; open all remaining
   indices with the same telescope/WHNF loop, ensure terminal Sort, and compare
   mutual result levels. Derive family descriptors with counts/templates.
2. Use a private provisional overlay, never publish raw headers as ordinary
   admitted dependencies. Check every constructor type. Consume the common
   parameters under the source-required policy, then traverse arbitrary remaining
   fields. Infer each domain universe, check its permitted result-level bound,
   check strict positivity and derive recursive descriptors before opening the
   field. Check the final owning family application, uniform parameters,
   universe levels and occurrence-free indices.
3. Strict positivity normalizes, calls a shared internal all-Expr current-family
   occurrence operation, rejects occurrences in Pi domains, opens its codomain
   with a fresh private Local, and loops. The terminal application validator
   walks the generic expression spine, matches a current family/level vector,
   exact shared parameter prefix, declared index count and occurrence-free index
   terms. Functional recursive arguments reuse the same telescope/spine loops;
   retain their prefix domains and abstract result indices. None of these results
   is an input bit or a host-produced answer.
4. Derive elimination/K permissions from the source rule; generate motives,
   minors, recursor types and reduction rules using shared context/open/fold/
   abstract/instantiate services. Rule argument positions/counts are derived
   data. Compare raw recursor claims with generated schemes rather than assume
   them. The full algorithm includes nested specialization's growing queue,
   copies of prior complete mutual blocks, restoration and rechecking. Publication
   is atomic only after the complete block and claims pass.
5. Generic iota/K/projection services consume checked derived descriptors and
   actual expression spines, using shared substitution and WHNF. Missing
   conversion/primitive services propagate GAP and cannot supply guessed answers.

Development spec already implements these block modules, including mutual/
indexed/functional recursion and nested restoration. It remains OFFLINE and
cannot supply native input answers. The weighted source driver currently GAPs
at a raw inductive block; no header-only analysis may turn that into ACCEPT.

Current weighted prerequisites: complete symbolic levels, all-Expr traversal/
substitution/scope/comparison, private checked environment, ordinary type/body
checking and general delta. [Shared telescope WHNF/dependent parameter reuse](../../benchmarks/kernel-dependent-telescope-stock/README.md)
is now lowered with exact stock operation evidence. The [current-family occurrence callback](../../benchmarks/kernel-internal-occurrence-stock/README.md)
is now composable and stock-validated: the earlier public OCCURS operation halts its whole top-level run on a
match and is therefore unsuitable as a positivity callback. The internal call
delimits its own private stack, returns a Boolean to its caller and retains
caller context windows on both early-match and full-traversal exits. Then lower
the family-application/positivity/recursive-descriptor callers above. This does
not change the complete block algorithm or select an easiest semantic class.

The next header-stage ABI uses output-only family161 `(indexCount,resultLevel,
rawFamilyRef)`, wrapped by scheme165 `(universeParams,INDUCTIVE_KIND,payload)`
and signature160 `(symbol,checkedHeaderType,scheme)`. These records are generated
ONLY after checking a header in the previous environment. A private linked list
collects them for duplicate checking and the subsequent provisional overlay.
Opening creates the shared parameter Locals; consuming reuses them for each
remaining family; opening indices derives counts, and context rolls back to the
shared parameter end after each family. The header list is separate from the
COMMITTED environment head and admitted-declaration count. Completing headers
must return to the block controller; until constructor/positivity/generation/
restoration checks are integrated that controller still reports GAP_INDUCTIVE.
A partial header list is never proof acceptance or an assumed public family.

Environment lookup will take an explicit private list head. Ordinary inference
passes the committed head; provisional constructor checking later passes the
source-staged overlay; header duplicate checks can search previous private
headers WITHOUT exposing them to header type inference. This removes accidental
ambient-environment mutation and preserves the source staging requirement.
