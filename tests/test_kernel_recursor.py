"""Minimal general generation/reduction contracts; no full/native checker claim."""
import unittest
from leanputer.kernel.arena import Arena, LevelTag, LocalContext, Tag
from leanputer.kernel.operations import check_scope, spine
from leanputer.kernel.positivity import BlockTraversal, Family
from leanputer.kernel.recursor import Constructor, Inductive, RecursorBuilder, reduce_constructor_rule
from leanputer.kernel.reduction import BetaZeta
from leanputer.kernel.telescope import fold_telescope, open_telescope


class RecursorAlgorithmTest(unittest.TestCase):
    def test_mutual_indexed_functional_rules_and_field_order(self):
        a = Arena()
        c = LocalContext(a)
        whnf = BetaZeta(a, c)
        type0 = a.mk(Tag.SORT, a.level(LevelTag.SUCC, a.zero))
        carrier = c.fresh(type0)
        index = c.fresh(carrier)
        f, g = a.const(107), a.const(293)
        family_type = fold_telescope(a, c, (carrier, index), type0)
        base_type = fold_telescope(a, c, (carrier, index), a.app(f, (carrier, index)))
        y = c.fresh(carrier)
        functional = fold_telescope(a, c, (y,), a.app(g, (carrier, y)))
        next_ = c.fresh(functional)
        step_type = fold_telescope(a, c, (carrier, index, next_), a.app(f, (carrier, index)))
        prev = c.fresh(a.app(f, (carrier, index)))
        join_type = fold_telescope(a, c, (carrier, index, prev), a.app(g, (carrier, index)))
        block = BlockTraversal(a, c, (Family(f, 1), Family(g, 1)), (carrier,), whnf, lambda x, y: x == y)
        inductives = (Inductive(f, family_type, (Constructor(109, base_type), Constructor(113, step_type)), 127),
                      Inductive(g, family_type, (Constructor(307, join_type),), 311))
        mark = c.mark()
        recs = RecursorBuilder(block, inductives, (), a.level(LevelTag.PARAM, 71), lambda x, y: x == y).generate()
        self.assertEqual(c.mark(), mark)
        self.assertEqual([(r.parameters, r.motives, r.minors, r.indices) for r in recs], [(1, 2, 3, 1)]*2)
        self.assertEqual([[rule.fields for rule in r.rules] for r in recs], [[1, 2], [2]])
        for rec in recs:
            check_scope(a, rec.type, universe_parameters=(71,))
            for rule in rec.rules:
                check_scope(a, rule.rhs, universe_parameters=(71,))

        # Inspect the generated step minor: ALL fields (index,next) then IH,
        # whose dependent function argument feeds the other family's motive.
        with c.scope():
            binders = open_telescope(a, c, recs[0].type, whnf, count=6).locals
            p, mf, mg, base, step, join = binders
            step_view = open_telescope(a, c, c.lookup(step).type, whnf)
            self.assertEqual(len(step_view.locals), 3)
            x, child, ih = step_view.locals
            ih_view = open_telescope(a, c, c.lookup(ih).type, whnf)
            self.assertEqual(len(ih_view.locals), 1)
            yy = ih_view.locals[0]
            self.assertEqual(ih_view.body, a.app(mg, (yy, a.app(child, (yy,)))))
            self.assertEqual(step_view.body, a.app(mf, (x, a.app(a.const(113), (p, x, child)))))

        # Same generated rule, actual constructor fields and surplus arguments.
        # No handwritten iota expression/constructor branch is used.
        args = tuple(a.const(symbol) for symbol in (401, 409, 419, 421, 431, 433))
        p, mf, mg, base, step, join = args
        x, child, extra = a.const(439), a.const(443), a.const(449)
        major = a.app(a.const(113), (p, x, child))
        reduced = reduce_constructor_rule(a, recs[0], (a.zero,), args+(x, major, extra), whnf)
        head, actual_args = spine(a, whnf(reduced))
        self.assertEqual(head, step)
        self.assertEqual(actual_args[:2], (x, child))
        self.assertEqual(actual_args[-1], extra)
        yy = a.const(457)
        ih_applied = whnf(a.app(actual_args[2], (yy,)))
        self.assertEqual(ih_applied, a.app(a.const(311, (a.zero,)), args+(yy, a.app(child, (yy,)))))
        # Nested restoration may alter constructor parameter count. Rule fields
        # remain trailing, independent of the recursor's parameter count.
        nested_major = a.app(a.const(113), (a.const(461), p, x, child))
        nested = reduce_constructor_rule(a, recs[0], (a.zero,), args+(x, nested_major), whnf)
        self.assertEqual(spine(a, whnf(nested))[1][:2], (x, child))


if __name__ == '__main__':
    unittest.main()
