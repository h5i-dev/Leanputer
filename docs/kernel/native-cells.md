# Typed native input memory

`kernel/native_cells.py` gives the general kernel a physical input representation
usable by the stock compiler's addressed cache. It is syntax transport, not a
checker. `pack_source` imports no inference, reduction or admission service and
emits no admission results. Weighted ordinary source transactions are integrated; general inductive/primitive
source processing remains unfinished.

The heap has four unsigned words per row `(tag,a,b,c)`, with null row0. The raw
declaration bank has six words per row `(kind,symbol,levelParams,type,value,extra)`.
The target scheme/body is a separate six-word record. All entries remain raw
until weighted checking and atomic publication derive checked records.

| Tag space | Data |
|---|---|
| 1..12 | Same Expr tags as the semantic arena, with relocated references |
| 32 | Private derived Local/type/binder-info record; not emitted by input packing |
| 48,49 | Vector header `(length,first,role)` and linked cell `(value,next,0)` |
| 64..68 | Symbolic Zero/Succ/Max/IMax/Param levels; never grounded |
| 80..82 | String/numeral name segments and `(symbolID,nameVector,0)` entries |
| 88 | Raw symbolic-substitution argument `(parameterSymbol,levelPointer,0)` |
| 96..100 | Raw family/constructor/recursor-claim/block records |
| 160..171 | Output-only signature/family/constructor/recursor/rule/scheme/recursive-template records; never input answers |

Vector roles distinguish object references, level references, 16-bit natural
limbs, UTF-8 bytes and symbol IDs. This distinction is necessary: the syntax
arena may intern the SAME integer tuple for a universe argument and a literal.
Relocation follows the owning syntax role; it never guesses that a word which
resembles an address is a pointer. Structured names preserve string/numeric
segments, including arbitrary bounded numeral limbs.

Packing walks only original declaration/claim/target roots. Unreachable artifacts
from any earlier development-spec run cannot enter native input. A focused
contract runs the nested-source spec, confirms it generated new types/rules/
names, then verifies the packed input stays exactly unchanged. Invalid free
locals and unbound universe parameters are transported for checking IN WEIGHTS;
packing does not decide their admissibility.

No derived index/field/positivity/recursion/elimination/K/rule answer is packed.
Raw schemes/constructors are sufficient for the source-defined kernel to derive
them. Actual Quot interfaces remain raw primitive requests whose bindings and
signatures must be validated before use. Ordinary inductives have no catalog.

Capacities are physical. A cell word is 8..21bits; six stack/declaration words
plus two reference columns fit one stock128value head at the upper bound.
The packer reports heap/bank/word exhaustion as RESOURCE. The default transport
capacity4096heap/512raw declarations/16-bit words is not a measured compiled
checker configuration; native operation evidence states its actual smaller
configuration separately.

`kernel/level_transition.py` connects the typed heap to the shared stock
controller: it traverses all five level tags, checks parameter membership and
performs simultaneous raw substitution in weights, and reuses the Pi/Lam
open/fold callers on the same physical ABI. Argument-window offsets preserve
earlier caller-owned context slots; those slots are opaque data, not assumptions.
Standalone operation entry points produce DONE/INVALID, not theorem acceptance.
They do not run full source environment admission. Expression-wide raw universe substitution traverses all twelve Expr tags,
calling the same level operation for Sort and every Const universe argument.
A length-driven vector loop uses private value/return frames; its empty and
unchanged paths retain original syntax. Canonical symbolic normalization/equivalence now reuse those same services.
Conservative universe geq also uses those services. Checked-environment inference/ordinary-source callers now reuse these services;
complete conversion and inductive processing remain unfinished.

Additional raw `level_roots` can be transported as operation operands without
fabricating declaration types or binding answers. The shared consumers now
include structural equality, symbolic nonzero, checked successor separation and
complete smart Max/IMax constructors. These remain operation services; canonical
normalization/equivalence are integrated; typed inference and ordinary source admission use those same services; full
conversion/inductive source processing are unfinished.

The complete [expression scope caller](../../benchmarks/kernel-expression-scope-stock/README.md)
now checks BVar/Local closure and Sort/Const universe membership in one shared
traversal, including empty universe contexts. Raw declaration universe parameters
are scope data, not admitted types. Constant/projection existence, signature
arity and type correctness remain checked-environment/inference work. A scope
DONE must never be reported as proof or declaration acceptance.

The six-word raw declaration bank is now a stock read port, addressed by a
separate `raw_index` register. [Four-bank exact-state evidence](../../benchmarks/kernel-environment-abi-stock/README.md)
includes the raw constants bank. That pinned report covers transport only. Subsequent
[ordinary source evidence](../../benchmarks/kernel-source-transactions-stock/README.md)
covers weighted cursor advancement/checking/publication. Raw type claims become
checked signatures only after all required type/body checks.
The [checked environment integration contract](environment-native.md) reserves
output-only signature/scheme records and separates raw-item/admitted counts.

The new recursive-template IR uses166 `(familySignature,prefixVector,indexVector)`
and167 `(abstractDomain,binderInfo,0)`. Prefix/index vectors and fresh-Local
abstraction are derived by weighted operations. These records may retain
caller constructor Locals until the later generic recursor builder abstracts
the surrounding scope. They are private analysis outputs, not publishable raw
input assumptions. [Composed typed-core stock evidence](../../benchmarks/kernel-typed-core-stock/README.md)
now derives these services from raw syntax. Full original-source admission and
generation remain unfinished.

Private typed-core metadata168/169/170 retain pending constructor names/types,
derived field Local snapshots/recursive descriptors/ordinals and family/field
vectors/result arguments. Pending names support duplicate checks only; the
typing overlay still excludes their types until every constructor passes.
The input packer has no branch emitting any output-only160..171record.

Name-only operations can transport additional raw symbol_roots without any
checked entries. Symbol/path lookup and source recursor-name relation run in
weights. Record171 `(familySignature,verifiedRecursorSymbol,next)` is generated
only after that relation and namespace checks. Raw recursor types remain claims.
This latest name stage has IR evidence; stock typed-core evidence is8161018.
