"""Syntax-only original-scheme input codec for the general kernel target.

No kernel algorithm/service is imported. Names/universes/expressions are
interned injectively; all declarations, bodies and recursor claims remain raw
data. Parsing is neither admission nor scope/type checking. The complete source
format is experimental and not yet accepted by a full native kernel driver.
"""
from dataclasses import dataclass
from typing import Optional
from .arena import Arena, KernelError, LevelTag, Limits, Tag


class SourceUnavailable(Exception):
    """An unexported source row, never a kernel rejection/empty dependency set."""


class SymbolTable:
    def __init__(self, arena):
        self.arena = arena
        self.names = [None]
        self.encoded_names = [0]  # Generic vector references for weighted layout.
        self.index = {}

    def intern(self, parts):
        if not isinstance(parts, list):
            raise KernelError('name must be a structured component array')
        key = []
        for part in parts:
            if not isinstance(part, dict) or len(part) != 1:
                raise KernelError('invalid name component')
            if 'str' in part and isinstance(part['str'], str):
                key.append(('str', part['str']))
            elif 'num' in part and type(part['num']) is int and part['num'] >= 0:
                # Name numerals are syntax integers, not expression words.
                key.append(('num', part['num']))
            else:
                raise KernelError('invalid name component value')
        key = tuple(key)
        if key not in self.index:
            ref = self.arena.word(len(self.names))
            components = []
            for tag, value in key:
                if tag == 'str':
                    payload = self.arena.vec(value.encode('utf-8'))
                else:
                    digits = []
                    while value:
                        value, digit = divmod(value, 65536)
                        digits.append(digit)
                    payload = self.arena.vec(digits)
                components.append(self.arena.vec((int(tag == 'num'), payload)))
            encoded = self.arena.vec(components)
            self.index[key] = ref
            self.names.append(key)
            self.encoded_names.append(encoded)
        return self.index[key]


@dataclass(frozen=True)
class RawDeclaration:
    kind: str
    symbol: int
    universe_parameters: tuple
    type: int
    value: Optional[int]


@dataclass(frozen=True)
class RawConstructor:
    symbol: int
    type: int


@dataclass(frozen=True)
class RawInductive:
    symbol: int
    type: int
    constructors: tuple
    recursor_symbol: int


@dataclass(frozen=True)
class RawRecursorClaim:
    symbol: int
    universe_parameters: tuple
    type: int


@dataclass(frozen=True)
class RawBlock:
    universe_parameters: tuple
    parameters: int
    families: tuple
    recursor_claims: tuple


@dataclass(frozen=True)
class RawPrimitive:
    symbol: int
    universe_parameters: tuple
    type: int
    interface: str


@dataclass(frozen=True)
class SourceInput:
    arena: Arena
    symbols: SymbolTable
    declarations: tuple
    target: RawDeclaration


class SyntaxCodec:
    def __init__(self, limits=Limits()):
        self.arena = Arena(limits)
        self.symbols = SymbolTable(self.arena)

    @staticmethod
    def _node(node):
        if not isinstance(node, list) or not node or not isinstance(node[0], str):
            raise KernelError('expected tagged syntax array')
        return node[0]

    def level(self, root):
        a, result, pending = self.arena, {}, [(root, False)]
        arity = {'zero': 1, 'param': 2, 'succ': 2, 'max': 3, 'imax': 3}
        tags = {'zero': LevelTag.ZERO, 'param': LevelTag.PARAM, 'succ': LevelTag.SUCC,
                'max': LevelTag.MAX, 'imax': LevelTag.IMAX}
        while pending:
            a.check_stack(pending); a.tick()
            node, returning = pending.pop()
            tag = self._node(node)
            if tag not in arity or len(node) != arity[tag]:
                raise KernelError('invalid universe syntax')
            key = id(node)
            if key in result:
                continue
            if tag == 'zero':
                result[key] = a.zero
            elif tag == 'param':
                result[key] = a.level(LevelTag.PARAM, self.symbols.intern(node[1]))
            elif not returning:
                pending.append((node, True))
                pending.extend((child, False) for child in reversed(node[1:]))
            else:
                result[key] = a.level(tags[tag], *(result[id(child)] for child in node[1:]))
        return result[id(root)]

    def expression(self, root):
        a, result, pending = self.arena, {}, [(root, False)]
        arity = {'var': 2, 'local': 2, 'sort': 2, 'const': 3, 'app': 3, 'pi': 4,
                 'lam': 4, 'let': 4, 'proj': 4, 'nat': 2, 'string': 2, 'mdata': 2}
        while pending:
            a.check_stack(pending); a.tick()
            node, returning = pending.pop()
            tag = self._node(node)
            if tag not in arity or len(node) != arity[tag]:
                raise KernelError('invalid expression syntax')
            key = id(node)
            if key in result:
                continue
            refs = (node[1:] if tag in ('app', 'let') else node[2:] if tag in ('pi', 'lam') else
                    node[3:] if tag == 'proj' else node[1:] if tag == 'mdata' else ())
            if refs and not returning:
                pending.append((node, True))
                pending.extend((child, False) for child in reversed(refs))
                continue
            if tag in ('var', 'local'):
                ref = a.mk(Tag.BVAR if tag == 'var' else Tag.LOCAL, a.word(node[1]))
            elif tag == 'sort':
                ref = a.mk(Tag.SORT, self.level(node[1]))
            elif tag == 'const':
                if not isinstance(node[2], list):
                    raise KernelError('constant universes must be an array')
                ref = a.const(self.symbols.intern(node[1]), [self.level(u) for u in node[2]])
            elif tag in ('app', 'pi', 'lam', 'let'):
                values = [result[id(child)] for child in refs]
                if tag in ('pi', 'lam'):
                    values.append(a.word(node[1]))
                ref = a.mk({'app': Tag.APP, 'pi': Tag.PI, 'lam': Tag.LAM, 'let': Tag.LET}[tag], *values)
            elif tag == 'proj':
                ref = a.mk(Tag.PROJ, self.symbols.intern(node[1]), a.word(node[2]), result[id(node[3])])
            elif tag == 'mdata':
                ref = a.mk(Tag.MDATA, result[id(node[1])])
            elif tag == 'string':
                if not isinstance(node[1], str):
                    raise KernelError('expected string literal')
                ref = a.mk(Tag.STRING, a.vec(node[1].encode('utf-8')))
            else:
                text = node[1]
                if not isinstance(text, str) or not text or any(c not in '0123456789' for c in text):
                    raise KernelError('expected decimal natural literal')
                # Decimal conversion is literal encoding, not arithmetic/checking
                # on Lean terms. No fixed host int string-digit limit applies.
                digits = []
                for char in text:
                    a.tick()
                    carry = ord(char)-48
                    for i, limb in enumerate(digits):
                        carry, digits[i] = divmod(limb*10+carry, 65536)
                    if carry:
                        digits.append(carry)
                    if len(digits)+1 > a.limits.vector_cells:
                        from .arena import ResourceError
                        raise ResourceError('literal vector')
                ref = a.mk(Tag.NAT, a.vec(digits))
            result[key] = ref
        return result[id(root)]

    def _uparams(self, data):
        if not isinstance(data, list):
            raise KernelError('universe parameters must be an array')
        return tuple(self.symbols.intern(name) for name in data)

    def declaration(self, data):
        kind = data['kind']
        if kind not in ('axiom', 'definition', 'theorem', 'opaque'):
            raise KernelError('invalid ordinary declaration kind')
        return RawDeclaration(kind, self.symbols.intern(data['name']), self._uparams(data['level_params']),
            self.expression(data['type']), None if data['value'] is None else self.expression(data['value']))

    def block(self, data):
        families = []
        for family in data['families']:
            constructors = tuple(RawConstructor(self.symbols.intern(ctor['name']), self.expression(ctor['type']))
                for ctor in family['constructors'])
            families.append(RawInductive(self.symbols.intern(family['name']), self.expression(family['type']),
                constructors, self.symbols.intern(family['recursor_name'])))
        claims = tuple(RawRecursorClaim(self.symbols.intern(claim['name']), self._uparams(claim['level_params']),
            self.expression(claim['type'])) for claim in data['recursor_claims'])
        return RawBlock(self._uparams(data['level_params']), self.arena.word(data['parameters']), tuple(families), claims)

    def document(self, data):
        if data['format'] != 'leanputer.kernel-source.v1':
            raise KernelError('expected kernel-source format')
        if data.get('status') != 'EXPORTED':
            raise SourceUnavailable(data.get('reason', 'source was not exported'))
        declarations = []
        for d in data['declarations']:
            if d['kind'] == 'inductive_block':
                declarations.append(self.block(d))
            elif d['kind'] == 'recursor_claim':
                declarations.append(RawRecursorClaim(self.symbols.intern(d['name']), self._uparams(d['level_params']),
                    self.expression(d['type'])))
            elif d['kind'] == 'quot_primitive':
                if d['interface'] not in ('type', 'ctor', 'lift', 'ind'):
                    raise KernelError('invalid Quot interface syntax')
                declarations.append(RawPrimitive(self.symbols.intern(d['name']), self._uparams(d['level_params']),
                    self.expression(d['type']), d['interface']))
            else:
                declarations.append(self.declaration(d))
        return SourceInput(self.arena, self.symbols, tuple(declarations), self.declaration(data['target']))
