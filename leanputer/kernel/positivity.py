"""General strict positivity, uniformity and recursive-argument analysis.

Source: pinned Lean inductive.cpp:is_valid_ind_app/check_positivity/
is_rec_argument. Nested specialization is a separate PRECEDING operation, not
an exception granted to arbitrary nested type constructors in this traversal.
"""
from dataclasses import dataclass
from .arena import KernelError, Tag
from .operations import abstract, has_constant, instantiate, spine


@dataclass(frozen=True)
class Family:
    constant: int             # Full Const with the block's symbolic levels.
    index_count: int


@dataclass(frozen=True)
class PrefixBinder:
    domain: int               # Abstracted over preceding functional arguments.
    binder_info: int


@dataclass(frozen=True)
class RecursiveArgument:
    family: int               # Index into the current mutual block, not a name.
    prefix: tuple             # PrefixBinder vector, arbitrary bounded length.
    indices: tuple            # Each abstracted over the entire prefix.


class BlockTraversal:
    """Lives inside a checked shared-parameter context and block overlay."""
    def __init__(self, arena, context, families, parameters, whnf):
        self.arena, self.context = arena, context
        self.families, self.parameters = tuple(families), tuple(parameters)
        self.whnf = whnf
        self.symbols = set()
        for family in self.families:
            row = arena.expr(family.constant)
            if row.tag != Tag.CONST or row.a in self.symbols:
                raise KernelError('invalid/duplicate block family')
            arena.word(family.index_count)
            self.symbols.add(row.a)
        for local in self.parameters:
            context.lookup(local)

    def has_occurrence(self, root):
        return has_constant(self.arena, root, self.symbols)

    def valid_application(self, root):
        a = self.arena
        head, args = spine(a, root)
        row = a.expr(head)
        if row.tag != Tag.CONST:
            return None
        for i, family in enumerate(self.families):
            a.tick()
            expected = a.expr(family.constant)
            if row.a != expected.a:
                continue
            actual_levels, expected_levels = a.vector(row.b), a.vector(expected.b)
            # Pinned is_valid_ind_app compares the entire Const syntax, not
            # definitional level equivalence. Arena level nodes are interned
            # structurally, so tuple identity here is exact syntax equality.
            if actual_levels != expected_levels:
                return None
            n = len(self.parameters)
            if len(args) != n+family.index_count or args[:n] != self.parameters:
                return None
            indices = args[n:]
            if any(self.has_occurrence(index) for index in indices):
                return None
            return i, indices
        return None

    def check_positivity(self, root):
        with self.context.scope():
            while True:
                self.arena.tick()
                root = self.whnf(root)
                if not self.has_occurrence(root):
                    return
                row = self.arena.expr(root)
                if row.tag != Tag.PI:
                    if self.valid_application(root) is None:
                        raise KernelError('invalid inductive occurrence')
                    return
                if self.has_occurrence(row.a):
                    raise KernelError('negative inductive occurrence')
                local = self.context.fresh(row.a, binder_info=row.c)
                root = instantiate(self.arena, row.b, (local,))

    def recursive_argument(self, root):
        """Return closed functional-prefix templates, leaving no temporary Local."""
        a = self.arena
        with self.context.scope():
            locals_, prefix = [], []
            while True:
                a.tick()
                root = self.whnf(root)
                row = a.expr(root)
                if row.tag != Tag.PI:
                    result = self.valid_application(root)
                    if result is None:
                        return None
                    family, indices = result
                    return RecursiveArgument(family, tuple(prefix),
                        tuple(abstract(a, index, locals_) for index in indices))
                prefix.append(PrefixBinder(abstract(a, row.a, locals_), row.c))
                local = self.context.fresh(row.a, binder_info=row.c)
                locals_.append(local)
                root = instantiate(a, row.b, (local,))
