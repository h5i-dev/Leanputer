"""Bounded immutable syntax arenas and scoped kernel-local identities.

References are one-based; zero is never an expression/level reference. Creation
checks child references, so syntax is a DAG independently of a later checker.
No constructor checks a type, reduces a term, or admits a declaration.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class ResourceError(Exception):
    """A physical bound was exhausted; this is not kernel rejection."""


class KernelError(Exception):
    """An invalid syntax/scope/semantic condition in the executable spec."""


class Tag(IntEnum):
    BVAR = 1
    LOCAL = 2
    SORT = 3
    CONST = 4
    APP = 5
    PI = 6
    LAM = 7
    LET = 8
    PROJ = 9
    NAT = 10
    STRING = 11
    MDATA = 12


class LevelTag(IntEnum):
    ZERO = 1
    SUCC = 2
    MAX = 3
    IMAX = 4
    PARAM = 5


@dataclass(frozen=True)
class Row:
    tag: Tag
    a: int = 0
    b: int = 0
    c: int = 0


@dataclass(frozen=True)
class LevelRow:
    tag: LevelTag
    a: int = 0
    b: int = 0


@dataclass(frozen=True)
class Limits:
    expressions: int = 65536
    levels: int = 4096
    vector_cells: int = 65536
    locals: int = 4096
    stack: int = 8192
    fuel: int = 1000000
    word_bits: int = 32

    def __post_init__(self):
        if any(v <= 0 for v in self.__dict__.values()):
            raise ValueError('physical limits must be positive')


class Arena:
    def __init__(self, limits=Limits()):
        self.limits = limits
        self.rows = [None]
        self.levels = [None]
        self.vectors = [None]
        self._rows = {}
        self._levels = {}
        self._vectors = {}
        self._cells = 0
        self.steps = 0
        self.zero = self.level(LevelTag.ZERO)

    def tick(self, work=1):
        self.steps += work
        if self.steps > self.limits.fuel:
            raise ResourceError('fuel')

    def check_stack(self, stack):
        if len(stack) > self.limits.stack:
            raise ResourceError('work stack')

    def word(self, value):
        if type(value) is not int or value < 0:
            raise KernelError('expected unsigned integer')
        if value >= 1 << self.limits.word_bits:
            raise ResourceError('word overflow')
        return value

    def expr(self, ref):
        if type(ref) is not int or not 0 < ref < len(self.rows):
            raise KernelError('invalid expression reference')
        return self.rows[ref]

    def level_row(self, ref):
        if type(ref) is not int or not 0 < ref < len(self.levels):
            raise KernelError('invalid level reference')
        return self.levels[ref]

    def vector(self, ref):
        if type(ref) is not int or not 0 < ref < len(self.vectors):
            raise KernelError('invalid vector reference')
        return self.vectors[ref]

    def vec(self, items=()):
        items = tuple(self.word(v) for v in items)
        if items in self._vectors:
            return self._vectors[items]
        if self._cells + 1 + len(items) > self.limits.vector_cells:
            raise ResourceError('vector cells')
        ref = len(self.vectors)
        self.word(ref)
        self.vectors.append(items)
        self._vectors[items] = ref
        self._cells += 1 + len(items)
        return ref

    def level(self, tag, a=0, b=0):
        tag = LevelTag(tag)
        self.word(a); self.word(b)
        if tag == LevelTag.SUCC:
            self.level_row(a)
        elif tag in (LevelTag.MAX, LevelTag.IMAX):
            self.level_row(a); self.level_row(b)
        elif tag == LevelTag.PARAM:
            if not a:
                raise KernelError('zero universe symbol')
        if (tag in (LevelTag.ZERO, LevelTag.PARAM, LevelTag.SUCC) and b
                or tag == LevelTag.ZERO and a):
            raise KernelError('unused level field')
        row = LevelRow(tag, a, b)
        if row in self._levels:
            return self._levels[row]
        if len(self.levels)-1 >= self.limits.levels:
            raise ResourceError('level arena')
        ref = self.word(len(self.levels))
        self.levels.append(row); self._levels[row] = ref
        return ref

    def mk(self, tag, a=0, b=0, c=0):
        tag = Tag(tag)
        self.word(a); self.word(b); self.word(c)
        row = Row(tag, a, b, c)
        for child, _ in children(row):
            self.expr(child)
        if tag == Tag.SORT:
            self.level_row(a)
        elif tag == Tag.CONST:
            if not a:
                raise KernelError('zero constant symbol')
            for level in self.vector(b):
                self.level_row(level)
        elif tag in (Tag.NAT, Tag.STRING):
            for value in self.vector(a):
                if value >= (256 if tag == Tag.STRING else 65536):
                    raise KernelError('literal digit out of range')
            if tag == Tag.NAT and self.vector(a) and self.vector(a)[-1] == 0:
                raise KernelError('noncanonical natural literal')
        elif tag == Tag.LOCAL and not a:
            raise KernelError('zero local identity')
        elif tag == Tag.PROJ and not a:
            raise KernelError('zero projection symbol')
        # Binder info/metadata are raw nonsemantic words. All other unused fields
        # are required zero, preventing alternate encodings of a syntax row.
        if (tag in (Tag.BVAR, Tag.LOCAL, Tag.SORT, Tag.NAT, Tag.STRING) and (b or c)
                or tag in (Tag.CONST, Tag.APP, Tag.MDATA) and c):
            raise KernelError('unused expression field')
        if row in self._rows:
            return self._rows[row]
        if len(self.rows)-1 >= self.limits.expressions:
            raise ResourceError('expression arena')
        ref = self.word(len(self.rows))
        self.rows.append(row); self._rows[row] = ref
        return ref

    def const(self, symbol, levels=()):
        return self.mk(Tag.CONST, symbol, self.vec(levels))

    def app(self, head, args):
        for arg in args:
            self.tick()
            head = self.mk(Tag.APP, head, arg)
        return head


def children(row):
    """Expression children with their binder-depth increments."""
    if row.tag == Tag.APP:
        return ((row.a, 0), (row.b, 0))
    if row.tag in (Tag.PI, Tag.LAM):
        return ((row.a, 0), (row.b, 1))
    if row.tag == Tag.LET:
        return ((row.a, 0), (row.b, 0), (row.c, 1))
    if row.tag == Tag.PROJ:
        return ((row.c, 0),)
    if row.tag == Tag.MDATA:
        return ((row.a, 0),)
    return ()


def rebuild(arena, row, refs):
    if row.tag in (Tag.APP, Tag.PI, Tag.LAM):
        return arena.mk(row.tag, *refs, row.c)
    if row.tag == Tag.LET:
        return arena.mk(row.tag, *refs)
    if row.tag == Tag.PROJ:
        return arena.mk(row.tag, row.a, row.b, refs[0])
    if row.tag == Tag.MDATA:
        return arena.mk(row.tag, refs[0], row.b)
    return arena.mk(row.tag, row.a, row.b, row.c)


@dataclass(frozen=True)
class LocalDecl:
    identity: int
    type: int
    value: Optional[int] = None
    binder_info: int = 0


class LocalContext:
    def __init__(self, arena):
        self.arena = arena
        self.active = {}
        self.order = []
        self._next = 1

    def mark(self):
        return len(self.order)

    def restore(self, mark):
        if type(mark) is not int or not 0 <= mark <= len(self.order):
            raise KernelError('invalid local scope mark')
        while len(self.order) > mark:
            del self.active[self.order.pop()]

    @contextmanager
    def scope(self):
        mark = self.mark()
        try:
            yield self
        finally:
            self.restore(mark)

    def fresh(self, type_ref, value=None, binder_info=0):
        self.arena.expr(type_ref)
        if value is not None:
            self.arena.expr(value)
        if len(self.order) >= self.arena.limits.locals:
            raise ResourceError('local context')
        identity = self.arena.word(self._next)
        self._next += 1  # Never reuse an identity after scope restoration.
        ref = self.arena.mk(Tag.LOCAL, identity)
        self.active[identity] = LocalDecl(identity, type_ref, value, binder_info)
        self.order.append(identity)
        return ref

    def lookup(self, local):
        row = self.arena.expr(local)
        if row.tag != Tag.LOCAL or row.a not in self.active:
            raise KernelError('escaped or invalid local')
        return self.active[row.a]
