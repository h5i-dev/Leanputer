# Native nested-inductive elimination and restoration

Authority: Lean68218e876d2a38b1985b8590fff244a83c321783,
`inductive.cpp:elim_nested_inductive_fn` (roughly875–1093),
`elim_nested_inductive_result::restore_nested`, `mk_aux_rec_name_map`, and
`environment::add_inductive`; executable development operations in `nested.py`
and `environment.py`. These determine the complete algorithm before lowering.
The original-source controller retains its GAP until the whole transaction is
connected. The CORE function API cannot approve an original nested block.

## Data and lifetime

All records below are private heap data produced by fixed weighted operations;
none is emitted by the input syntax packer. Counts/names are data with physical
word/heap/stack/fuel bounds. They never select a supported shape class.

* An original-block origin record holds its original raw block100, original
  universe-symbol vector and an ordered vector of its checked family signatures.
  A linked registry indexes **previous committed original** blocks. Register only
  after full restoration/rechecking/publication; provisional CORE headers cannot
  supply a prior-block admission answer. Retain original schemes, not a previous
  block's expanded auxiliary declaration.
* A work queue holds original and generated raw families with their constructor
  vectors. A persistent front list/back reverse list implements FIFO; reverse
  only when the front empties. A separate persistent all-family list and count
  make newly queued auxiliaries visible to occurrence checking immediately.
  A processed-family list records rewritten constructors in original queue order.
* Specialization entries hold the prior family identity, an Expr structurally
  abstracted over the current block's parameter Locals, an auxiliary symbol, and
  constructor-name mappings. Copy all members of a prior mutual block together;
  each gets its own entry even if a different member triggered the occurrence.
* A declaration transaction retains original raw block/schemes, old public Γ and
  registry heads, original family count, universe scheme, current parameter
  snapshot, growing queue/maps and eventual restored signatures/rules. Pending
  state must not alter public Γ or the committed registry.
* A generated name is a canonical structured name/path, interned into the same
  symbol/path representation used by input names. Freshness searches checked Γ
  and reserved names with a counted counter; constructor prefix replacement and
  indexed auxiliary recursor names are generic structured-name operations.
  Private auxiliary names may be alpha-renamed consistently; restored public
  names follow the pinned `<main>.rec_<index>` convention. No host-generated name
  list, container catalog, functor flag, specialization certificate or type answer
  is accepted at inference.

## Complete queue algorithm

1. Read the original nonempty family vector and declared parameter count. Open
   that exact Pi prefix from the first family with raw syntax operations (no
   WHNF), preserving dependent domains and binder info. Retain a parameter
   snapshot for structural specialization keys. Initialize FIFO/all-family data
   from every original family and reserve every original family/constructor/
   recursor name.
2. Pop a family. For each constructor reopen the declared parameter Pi prefix
   with fresh Locals, preserving its own binder info. Traverse the entire
   remaining Expr with a fixed **preorder replacement callback**. A replacement
   is returned as a whole subtree and is not traversed again, matching source
   `replace`. Domains and bodies use the shared binder-depth traversal.
3. The callback considers an application with Const head belonging to the
   committed prior-block registry. Split its arguments; require at least the
   prior block's declared parameter count. Scan **all** actual parameter Exprs
   for current/all-queued family constants and for loose bound variables. No
   occurrence means no replacement; occurrence plus a loose BVar is invalid.
4. Build the prior-family/actual-parameter application and abstract over this
   constructor's current parameter Locals. Search specialization entries by
   structural Expr equality, not conversion. Existing entry: apply its auxiliary
   at current block universe parameters, current parameter Locals and remaining
   actual indices.
5. New entry: specialize the **whole prior mutual block** at the triggering
   universe arguments and actual parameters. Check universe arity; instantiate
   each original type/constructor universe scheme, strip the exact declared raw
   Pi parameter prefix, bulk instantiate in telescope order, then Pi-fold current
   parameters. Generate fresh auxiliary/prefix-replaced constructor names and
   entries before enqueueing. Publish every auxiliary to the private all-family
   occurrence set immediately. Return the selected auxiliary application. Newly
   copied constructor types are processed by the same FIFO loop, including nested
   occurrences involving newly queued families. Arbitrary bounded mutual/field/
   parameter/index counts use these same loops.
6. Fold each rewritten constructor's current parameter Locals, preserving binder
   info, and store the rewritten family. Continue until the growing FIFO empties.
   Build the expanded block and pass it through the existing complete CORE
   header/constructor/positivity/recursor construction operations. The number of
   auxiliary families is data required by source nested metadata, not an admission
   shortcut or a host-computed approval flag.

## Restoration, validation and publication

Construct auxiliary recursor renamings from all-family order after the original
family count. Reopen the original leading parameter prefix of each generated
scheme/RHS; fixed preorder traversal renames auxiliary recursor Consts, replaces
auxiliary family applications by instantiated original specialization templates,
and replaces auxiliary constructor applications by original constructor heads at
restored universe/parameter arguments plus trailing actual fields. It must not
assume original and expanded parameter counts coincide. Fold the preserved
parameter prefix with its original Pi/Lam tag.

Restore every original family/constructor, every generated recursor type/RHS,
constructor identities in auxiliary recursor rules, original all-family metadata
and public recursor names. Build a private overlay of the restored environment.
Check the original/source-required type compatibility and all required scopes,
restored types/RHS typing and supplied recursor claims under that overlay, using
shared checked inference/conversion/reduction. A missing callback GAPs; resource
exhaustion is not inequality; any failure leaves public Γ/registry unchanged.
Only then atomically replace the public environment head, advance the raw input
cursor and record the original block in the committed prior-block registry.
The executable spec deliberately rechecks generated restored records; this is a
conservative validation step, not a host inference hook in the native loader.

## Lowering interfaces and status

Shared building blocks already implemented in Boolean IR include expression and
level instantiation, scope/occurrence/binder traversal, raw/scoped telescope
opening/folding and snapshots, immutable vector reversal/selection/application,
structural equality, checked environment lookup, name paths/recursor-name checks,
complete CORE generation, untrusted claims, and reentrant runtime iota/K/eta.
Stock evidence is separately pinned; later IR modules are not silently included
in earlier measurements.

Next lower the committed-origin registry lookup, generic structured-name
intern/prefix/counter operations, FIFO state, and fixed nested replacement/
restoration traversals. The callback walkers use distinct owner tasks for
continuations; generic Expr frames and controller-local phase labels must not
alias. The visitor's operation is fixed by the kernel program, never supplied
as a proof micro-op tape. No no-nested/one-field/container-name bypass will be
installed as a completed support milestone. Broad corpus evaluation remains
separate from implementation and targeted operation checks.

The first native data operation, `PRIOR_BLOCK_LOOKUP`, is now implemented in
reference and Boolean IR. It traverses immutable origin185
`(originalRawBlock,originalUniverseParameters,checkedFamilySignatureVector)`
records through generic list cells, using shared signature-vector lookup. Only
family identities match; recursor/constructor/unknown names do not supply
container ownership. It allocates no heap data and changes no scope or Γ.
Focused exact-state lookup/empty/multi-cell/mutual-data tests passed1test6.825s.
Those are private ABI fixtures assembled from model-generated CORE signatures,
**not registered source admissions**. The full source producer/publication path
is still pending; no loader can supply origin185 or enter this internal task.
