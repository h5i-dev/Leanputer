"""Fixed-capacity STLC inference circuit. Compilation takes no proof."""
from dataclasses import dataclass
from .circuit import Circuit
from .terms import parse_type

@dataclass(frozen=True)
class Config:
    nodes: int = 16
    types: tuple = (
        'P', 'Q', 'R', ('P', 'P'), ('P', 'Q'), ('Q', 'R'), ('P', 'R'),
        ('Q', 'Q'), ('R', 'R'), ('Q', 'P'), (('Q', 'R'), ('P', 'R')),
        (('P', 'Q'), (('Q', 'R'), ('P', 'R'))), (('P', 'Q'), ('P', 'Q')),
        ('P', ('Q', 'P')), ('P', ('P', 'P')), ('P', ('Q', 'Q')),
    )

    def __post_init__(self):
        if type(self.nodes) is not int or self.nodes < 1:
            raise ValueError('positive integer node capacity required')
        if not isinstance(self.types, (tuple, list)) or not self.types:
            raise ValueError('nonempty type vocabulary required')
        object.__setattr__(self, 'types', tuple(parse_type(t) for t in self.types))
        if len(set(self.types)) != len(self.types):
            raise ValueError('positive capacity and unique types required')
        for t in self.types:
            if isinstance(t, tuple):
                if len(t) != 2 or any(s not in self.types for s in t):
                    raise ValueError('type vocabulary must be closed under subexpressions')
            elif not isinstance(t, str) or not t:
                raise ValueError('types must be atoms or arrow pairs')


def compile_checker(config=Config()):
    """Build proof-independent fixed weights for closed, bounded STLC terms.

    Output columns: acceptance, conservative type-vocabulary overflow, then
    one inferred-root-type bit per vocabulary entry. Only acceptance includes
    every structural validity condition; root type bits are diagnostic.
    """
    c = Circuit()
    n, types = config.nodes, config.types
    k = len(types)
    tag = [[c.input(f'tag/{i}/{s}') for s in ('pad', 'var', 'lam', 'app')] for i in range(n)]
    a = [[c.input(f'a/{i}/{j}') for j in range(n)] for i in range(n)]
    b = [[c.input(f'b/{i}/{j}') for j in range(n)] for i in range(n)]
    bind = [[c.input(f'bind/{i}/{j}') for j in range(n)] for i in range(n)]
    ann = [[c.input(f'ann/{i}/{t}') for t in range(k)] for i in range(n)]
    claim = [c.input(f'claim/{t}') for t in range(k)]
    def at_most_one(xs):
        return c.NOT(c.OR(*(c.AND(x, y) for i, x in enumerate(xs) for y in xs[i + 1:])))
    def exactly_one(xs):
        return c.AND(c.OR(*xs), at_most_one(xs))
    def iff(x, y):
        return c.OR(c.AND(x, y), c.AND(c.NOT(x), c.NOT(y)))
    valid = [exactly_one(claim)]
    for i in range(n):
        valid.append(exactly_one(tag[i]))
        for row, active in ((a[i], c.OR(tag[i][2], tag[i][3])), (b[i], tag[i][3]),
                            (bind[i], tag[i][1]), (ann[i], tag[i][2])):
            valid.extend((at_most_one(row), iff(c.OR(*row), active)))
        valid.append(c.NOT(c.OR(*(a[i][j] for j in range(i, n)), *(b[i][j] for j in range(i, n)))))
        valid.append(at_most_one([row[i] for row in a + b]))
    edge = [[c.OR(a[j][i], b[j][i]) for j in range(n)] for i in range(n)]
    ancestor = [[None] * n for _ in range(n)]
    for i in reversed(range(n)):
        for j in range(n):
            ancestor[i][j] = c.OR(*(c.AND(edge[i][p], c.AND() if p == j else ancestor[p][j])
                                    for p in range(i + 1, n)))
    # Every active row belongs to the one tree rooted at n-1. In particular,
    # padding cannot be referenced and disconnected active rows are malformed.
    valid.append(c.NOT(tag[-1][0]))
    for i in range(n):
        has_parent = c.OR(*edge[i])
        if i < n - 1:
            valid.append(iff(c.NOT(tag[i][0]), ancestor[i][-1]))
        valid.append(c.NOT(c.AND(tag[i][0], has_parent)))
    inferred, overflow = [], []
    for i in range(n):
        row = []
        fn = [c.OR(*(c.AND(a[i][j], inferred[j][t]) for j in range(i))) for t in range(k)]
        arg = [c.OR(*(c.AND(b[i][j], inferred[j][t]) for j in range(i))) for t in range(k)]
        overflow.append(c.AND(tag[i][2], c.OR(*(
            c.AND(ann[i][d], fn[r]) for d in range(k) for r in range(k)
            if (types[d], types[r]) not in types))))
        for t, ty in enumerate(types):
            var = c.OR(*(c.AND(bind[i][j], tag[j][2], ann[j][t], ancestor[i][j]) for j in range(i + 1, n)))
            lam = c.AND(ann[i][types.index(ty[0])], fn[types.index(ty[1])]) if isinstance(ty, tuple) else c.OR()
            app = c.OR(*(c.AND(fn[u], arg[types.index(arr[0])]) for u, arr in enumerate(types)
                         if isinstance(arr, tuple) and arr[1] == ty))
            row.append(c.OR(c.AND(tag[i][1], var), c.AND(tag[i][2], lam), c.AND(tag[i][3], app)))
        inferred.append(row)
    accept = c.AND(*valid, c.OR(*(c.AND(claim[t], inferred[-1][t]) for t in range(k))))
    model = c.compile([accept, c.AND(*valid, c.OR(*overflow))] + inferred[-1])
    model.config = config
    return model
