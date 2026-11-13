"""Typed physical input cells for general stock-kernel service integration.

Pure syntax transport: no service/admission/reduction module is imported.
Input records and derived checked records have distinct tags. This packer is
not itself a native checking path; the whole-source weighted driver is pending.
Only reachable ORIGINAL declarations/expressions/names are packed, so running
an offline spec earlier cannot accidentally supply its generated artifacts.
"""
from dataclasses import dataclass
from enum import IntEnum
from .arena import KernelError, LevelTag, ResourceError, Tag, children
from .syntax import RawBlock, RawDeclaration, RawPrimitive, RawRecursorClaim


class CellTag(IntEnum):
    LOCAL_DECL = 32
    VECTOR = 48
    VECTOR_CELL = 49
    LEVEL_ZERO = 64
    LEVEL_SUCC = 65
    LEVEL_MAX = 66
    LEVEL_IMAX = 67
    LEVEL_PARAM = 68
    NAME_STRING = 80
    NAME_NUMERAL = 81
    SYMBOL_ENTRY = 82
    LEVEL_BINDING = 88
    RAW_FAMILY = 96
    RAW_FAMILY_AUX = 97
    RAW_CONSTRUCTOR = 98
    RAW_RECURSOR_CLAIM = 99
    RAW_BLOCK = 100
    # Reserved output-only records. No branch of this syntax packer emits them.
    CHECKED_SIGNATURE = 160
    CHECKED_FAMILY = 161
    CHECKED_CONSTRUCTOR = 162
    CHECKED_RECURSOR = 163
    CHECKED_RULE = 164
    CHECKED_SCHEME = 165          # Output-only (uparams,kind,payload), never packed.
    RECURSIVE_ARGUMENT = 166      # Output-only (familySig,prefixVector,indexVector).
    PREFIX_BINDER = 167           # Output-only (abstractDomain,binderInfo,0).
    PENDING_CONSTRUCTOR = 168     # Private (symbol,rawType,typedFieldMetadata).
    CONSTRUCTOR_FIELD = 169       # Derived (LocalRecord,recursiveDescriptor,ordinal).
    CONSTRUCTOR_ANALYSIS = 170    # Private (familySig,fieldVector,resultArgs).
    VALIDATED_RECURSOR_NAME = 171 # Output-only (familySig,recursorSymbol,next).
    ELIMINATION_INFO = 172       # Derived (elimLevel,recursorUparams,Kflag).
    MOTIVE_INFO = 173            # Derived (familySig,motiveLocalRecord,telescope).
    MOTIVE_TELESCOPE = 174       # Derived (indexLocalVector,majorLocalRecord,recSymbol).
    BLOCK_FLAGS = 175            # Derived raw-domain (recursive,reflexive,0).
    OPENED_RECURSIVE_PREFIX = 176 # Derived (familySig,prefixLocalVector,indexVec).
    MINOR_INFO = 177             # Derived (checkedCtorPending,minorLocalRecord,nfields).
    RECURSOR_TYPE = 178          # Private (familySig,closedGeneratedType,recSymbol).
    FAMILY_RULE = 179            # Private (familySig,generatedRule,0).
    RECURSOR_COUNTS = 180        # Derived (numParams,numIndices,sharedCounts181).
    RECURSOR_SHARED_COUNTS = 181 # Derived (numMotives,numMinors,block182).
    NESTED_APPLICATION = 186    # Derived (priorBlockOrigin,applicationSpine,0), not admission.
    BLOCK_ORIGIN = 185          # Private (originalRawBlock,originalUparams,familySigVector).
    REDUCER_CALL = 184          # Private (originalHead,pendingStackBase,0).
    APPLICATION_SPINE = 183     # Derived (headExpr,argumentVector,0), not a reduction answer.
    RECURSOR_BLOCK = 182         # Derived (Kflag,rawFlags175,allFamilyVector).


class VectorKind(IntEnum):
    REFERENCES = 1
    LEVELS = 2
    LIMBS = 3
    BYTES = 4
    SYMBOLS = 5


class DeclarationKind(IntEnum):
    AXIOM = 1
    DEFINITION = 2
    THEOREM = 3
    OPAQUE = 4
    BLOCK = 5
    RECURSOR_CLAIM = 6
    QUOT_PRIMITIVE = 7


@dataclass(frozen=True)
class CellCapacities:
    heap: int = 4096
    constants: int = 512
    word_bits: int = 16

    def __post_init__(self):
        if not 8 <= self.word_bits <= 21:
            raise ValueError('typed native cells require 8..21-bit words')
        for capacity in (self.heap, self.constants):
            if type(capacity) is not int or capacity < 2 or capacity & (capacity-1):
                raise ValueError('cell capacities must be powers of two >=2')
            if capacity >= 1 << self.word_bits:
                raise ValueError('capacity/sentinel does not fit a word')


@dataclass(frozen=True)
class PackedInput:
    heap: tuple                 # Four-word rows; row0 is the null sentinel.
    constants: tuple            # Six-word raw declaration rows, no admitted flag.
    target: tuple               # Separate six-word target scheme/body.
    symbols: int                # Vector of (symbolID,nameVector) record refs.
    maximum_symbol: int
    expression_map: dict         # Diagnostics/relocation only, not semantic answers.
    level_map: dict
    level_bindings: tuple = ()  # Raw (symbol,level) operation argument records.

    @property
    def initial_free(self):
        return len(self.heap)


class _Cells:
    def __init__(self, capacities):
        self.capacities = capacities
        self.rows = [(0, 0, 0, 0)]
        self.index = {}

    def word(self, value):
        if not isinstance(value, int) or value < 0:
            raise KernelError('invalid unsigned cell word')
        if value >= 1 << self.capacities.word_bits:
            raise ResourceError('typed input word width')
        return int(value)

    def cell(self, tag, a=0, b=0, c=0):
        row = tuple(self.word(v) for v in (tag, a, b, c))
        if row not in self.index:
            if len(self.rows) >= self.capacities.heap:
                raise ResourceError('typed input heap')
            ref = len(self.rows)
            self.rows.append(row); self.index[row] = ref
        return self.index[row]

    def vector(self, values, kind):
        values = tuple(self.word(value) for value in values)
        tail = 0
        for value in reversed(values):
            tail = self.cell(CellTag.VECTOR_CELL, value, tail)
        return self.cell(CellTag.VECTOR, len(values), tail, kind)


def _roots(source):
    expressions, symbols = [], set()
    def scheme(symbol, parameters, type_ref, value=None):
        symbols.add(symbol); symbols.update(parameters)
        expressions.append(type_ref)
        if value is not None:
            expressions.append(value)
    for declaration in source.declarations+(source.target,):
        if isinstance(declaration, RawBlock):
            symbols.update(declaration.universe_parameters)
            for family in declaration.families:
                scheme(family.symbol, (), family.type)
                symbols.add(family.recursor_symbol)
                for ctor in family.constructors:
                    scheme(ctor.symbol, (), ctor.type)
            for claim in declaration.recursor_claims:
                scheme(claim.symbol, claim.universe_parameters, claim.type)
        elif isinstance(declaration, (RawDeclaration, RawPrimitive, RawRecursorClaim)):
            scheme(declaration.symbol, declaration.universe_parameters, declaration.type,
                   declaration.value if isinstance(declaration, RawDeclaration) else None)
        else:
            raise KernelError('unknown raw declaration syntax record')
    return expressions, symbols


def pack_source(source, capacities=CellCapacities(), *, level_bindings=(), level_roots=(), symbol_roots=()):
    """Relocate raw schemes into one typed heap plus a raw declaration bank.

    Vector roles are essential: the Arena can intern the SAME integer tuple as
    universe references, Nat limbs or bytes. These must be relocated according
    to their actual syntax role, never by guessing whether a word is a pointer.
    Scope, typing, arity, positivity and claims are all left for the weights.
    """
    a, cells = source.arena, _Cells(capacities)
    if len(source.declarations) > capacities.constants:
        raise ResourceError('raw declaration input bank')
    pending, symbols = _roots(source)
    for symbol in symbol_roots:
        a.word(symbol)
        if symbol >= len(source.symbols.names): raise KernelError('unknown raw symbol root')
        symbols.add(symbol)
    level_bindings = tuple(level_bindings)
    symbols.update(symbol for symbol, _ in level_bindings)
    exprs, levels = set(), set()
    level_pending = list(level_roots)+[ref for _, ref in level_bindings]
    while pending:
        if len(pending) > capacities.heap:
            raise ResourceError('syntax transport work stack')
        ref = pending.pop()
        if ref in exprs:
            continue
        row = a.expr(ref); exprs.add(ref)
        pending.extend(child for child, _ in children(row))
        if row.tag == Tag.SORT:
            level_pending.append(row.a)
        elif row.tag == Tag.CONST:
            symbols.add(row.a); level_pending.extend(a.vector(row.b))
        elif row.tag == Tag.PROJ:
            symbols.add(row.a)
    while level_pending:
        if len(level_pending) > capacities.heap:
            raise ResourceError('level transport work stack')
        ref = level_pending.pop()
        if ref in levels:
            continue
        row = a.level_row(ref); levels.add(ref)
        if row.tag == LevelTag.PARAM:
            symbols.add(row.a)
        elif row.tag == LevelTag.SUCC:
            level_pending.append(row.a)
        elif row.tag in (LevelTag.MAX, LevelTag.IMAX):
            level_pending.extend((row.a, row.b))
    level_map, expression_map = {}, {}
    level_tags = {LevelTag.ZERO: CellTag.LEVEL_ZERO, LevelTag.SUCC: CellTag.LEVEL_SUCC,
                  LevelTag.MAX: CellTag.LEVEL_MAX, LevelTag.IMAX: CellTag.LEVEL_IMAX, LevelTag.PARAM: CellTag.LEVEL_PARAM}
    # Arena DAG children precede parents. These are syntax relabelings only.
    for ref in sorted(levels):
        row = a.level_row(ref)
        left = (row.a if row.tag == LevelTag.PARAM else level_map[row.a] if row.tag != LevelTag.ZERO else 0)
        right = level_map[row.b] if row.tag in (LevelTag.MAX, LevelTag.IMAX) else 0
        level_map[ref] = cells.cell(level_tags[row.tag], left, right)
    for ref in sorted(exprs):
        row = a.expr(ref)
        x, y, z = row.a, row.b, row.c
        if row.tag == Tag.SORT:
            x = level_map[x]
        elif row.tag == Tag.CONST:
            y = cells.vector((level_map[level] for level in a.vector(y)), VectorKind.LEVELS)
        elif row.tag in (Tag.APP, Tag.PI, Tag.LAM):
            x, y = expression_map[x], expression_map[y]
        elif row.tag == Tag.LET:
            x, y, z = expression_map[x], expression_map[y], expression_map[z]
        elif row.tag == Tag.PROJ:
            z = expression_map[z]
        elif row.tag == Tag.MDATA:
            x = expression_map[x]
        elif row.tag in (Tag.NAT, Tag.STRING):
            x = cells.vector(a.vector(x), VectorKind.LIMBS if row.tag == Tag.NAT else VectorKind.BYTES)
        expression_map[ref] = cells.cell(row.tag, x, y, z)

    def parameter_vector(parameters):
        return cells.vector(parameters, VectorKind.SYMBOLS)

    def claim_record(claim):
        return cells.cell(CellTag.RAW_RECURSOR_CLAIM, claim.symbol, expression_map[claim.type],
                          parameter_vector(claim.universe_parameters))

    ordinary_kinds = {'axiom': DeclarationKind.AXIOM, 'definition': DeclarationKind.DEFINITION,
                      'theorem': DeclarationKind.THEOREM, 'opaque': DeclarationKind.OPAQUE}
    def declaration_row(declaration):
        if isinstance(declaration, RawBlock):
            families = []
            for family in declaration.families:
                constructors = cells.vector((cells.cell(CellTag.RAW_CONSTRUCTOR, ctor.symbol,
                    expression_map[ctor.type]) for ctor in family.constructors), VectorKind.REFERENCES)
                extra = cells.cell(CellTag.RAW_FAMILY_AUX, constructors, family.recursor_symbol)
                families.append(cells.cell(CellTag.RAW_FAMILY, family.symbol, expression_map[family.type], extra))
            claims = cells.vector((claim_record(claim) for claim in declaration.recursor_claims), VectorKind.REFERENCES)
            meta = cells.cell(CellTag.RAW_BLOCK, declaration.parameters,
                              cells.vector(families, VectorKind.REFERENCES), claims)
            return (DeclarationKind.BLOCK, 0, parameter_vector(declaration.universe_parameters), 0, 0, meta)
        if isinstance(declaration, RawDeclaration):
            if declaration.kind not in ordinary_kinds:
                raise KernelError('unknown ordinary declaration syntax kind')
            return (ordinary_kinds[declaration.kind], declaration.symbol, parameter_vector(declaration.universe_parameters),
                    expression_map[declaration.type], 0 if declaration.value is None else expression_map[declaration.value], 0)
        if isinstance(declaration, RawRecursorClaim):
            kind, extra = DeclarationKind.RECURSOR_CLAIM, 0
        elif isinstance(declaration, RawPrimitive):
            kind = DeclarationKind.QUOT_PRIMITIVE
            extra = {'type': 1, 'ctor': 2, 'lift': 3, 'ind': 4}[declaration.interface]
        else:
            raise KernelError('unknown declaration syntax kind')
        return (kind, declaration.symbol, parameter_vector(declaration.universe_parameters), expression_map[declaration.type], 0, extra)

    constants = tuple(tuple(cells.word(v) for v in declaration_row(d)) for d in source.declarations)
    target = tuple(cells.word(v) for v in declaration_row(source.target))
    binding_records = tuple(cells.cell(CellTag.LEVEL_BINDING, symbol, level_map[ref]) for symbol, ref in level_bindings)
    symbol_records = []
    for symbol in sorted(symbols):
        if not 0 < symbol < len(source.symbols.names):
            raise KernelError('invalid syntax symbol reference')
        components = []
        for tag, value in source.symbols.names[symbol]:
            if tag == 'str':
                payload = cells.vector(value.encode('utf-8'), VectorKind.BYTES)
                components.append(cells.cell(CellTag.NAME_STRING, payload))
            else:
                limbs = []
                while value:
                    value, limb = divmod(value, 65536); limbs.append(limb)
                payload = cells.vector(limbs, VectorKind.LIMBS)
                components.append(cells.cell(CellTag.NAME_NUMERAL, payload))
        path = cells.vector(components, VectorKind.REFERENCES)
        symbol_records.append(cells.cell(CellTag.SYMBOL_ENTRY, symbol, path))
    symbol_vector = cells.vector(symbol_records, VectorKind.REFERENCES)
    return PackedInput(tuple(cells.rows), constants, target, symbol_vector, max(symbols, default=0),
                       expression_map, level_map, binding_records)
