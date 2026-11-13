"""Shared beta/zeta/metadata weak-head subservice, with an explicit spine.

This is one component of WHNF, not a complete reduction or conversion checker.
Delta, recursors, projections, literal/Quot and K/eta are separate kernel rules.
"""
from .arena import Tag
from .operations import instantiate


class BetaZeta:
    def __init__(self, arena, context):
        self.arena, self.context = arena, context

    def __call__(self, root):
        a, arguments = self.arena, []
        while True:
            a.tick(); a.check_stack(arguments)
            row = a.expr(root)
            if row.tag == Tag.MDATA:
                root = row.a
            elif row.tag == Tag.LET:
                root = instantiate(a, row.c, (row.b,))
            elif row.tag == Tag.LOCAL and self.context.lookup(root).value is not None:
                root = self.context.lookup(root).value
            elif row.tag == Tag.APP:
                arguments.append(row.b)
                root = row.a
            elif row.tag == Tag.LAM and arguments:
                root = instantiate(a, row.b, (arguments.pop(),))
            else:
                return a.app(root, reversed(arguments))
