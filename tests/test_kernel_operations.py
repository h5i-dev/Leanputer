"""Targeted contracts for source-defined general operations, not native claims."""
import unittest
from dataclasses import replace

from leanputer.kernel.arena import Arena, KernelError, LevelTag, Limits, LocalContext, ResourceError, Tag
from leanputer.kernel.operations import (abstract, check_scope, has_constant,
    instantiate, instantiate_rev, lift, spine, substitute_levels)
from leanputer.kernel.positivity import BlockTraversal, Family
from leanputer.kernel.telescope import consume_parameters, fold_telescope, open_telescope


class GeneralOperationsTest(unittest.TestCase):
    def setUp(self):
        self.a = Arena()
        self.c = LocalContext(self.a)
        self.sort = self.a.mk(Tag.SORT, self.a.zero)

    def test_all_tag_capture_avoiding_substitution(self):
        a = self.a
        x, y = a.mk(Tag.BVAR, 0), a.mk(Tag.BVAR, 1)
        # Under a Let and lambda, original free #0 must become #2. Metadata and
        # projection are traversed while their non-expression words stay intact.
        lam = a.mk(Tag.LAM, self.sort, a.mk(Tag.PROJ, 127, 19,
            a.mk(Tag.MDATA, a.mk(Tag.BVAR, 2), 57)), 3)
        root = a.mk(Tag.LET, self.sort, x, lam)
        actual = instantiate(a, root, (y,))
        expected = a.mk(Tag.LET, self.sort, y, a.mk(Tag.LAM, self.sort,
            a.mk(Tag.PROJ, 127, 19, a.mk(Tag.MDATA, a.mk(Tag.BVAR, 3), 57)), 3))
        self.assertEqual(actual, expected)
        self.assertEqual(instantiate(a, a.mk(Tag.BVAR, 6), (x, y), start=2), a.mk(Tag.BVAR, 4))
        literal = a.mk(Tag.NAT, a.vec((1, 5)))
        string = a.mk(Tag.STRING, a.vec((0, 255, 67)))
        self.assertEqual(lift(a, a.app(literal, (string,)), 2), a.app(literal, (string,)))

    def test_dependent_telescope_lengths_and_scope(self):
        a, c = self.a, self.c
        # One algorithm for arbitrary lengths; later domains depend on the
        # preceding binder. The source expression has no externally free Local.
        for length in (0, 2, 9):
            with c.scope():
                locals_ = []
                for i in range(length):
                    domain = self.sort if not i else a.app(a.const(71), (locals_[-1],))
                    locals_.append(c.fresh(domain, binder_info=i % 4))
                result = a.app(a.const(83), locals_)
                root = fold_telescope(a, c, locals_, result)
                check_scope(a, root)
            with c.scope():
                opened = open_telescope(a, c, root, lambda x: x)
                self.assertEqual(len(opened.locals), length)
                self.assertEqual(fold_telescope(a, c, opened.locals, opened.body), root)
                for i, local in enumerate(opened.locals[1:], 1):
                    self.assertEqual(spine(a, c.lookup(local).type)[1], (opened.locals[i-1],))
                saved = opened.locals[-1] if length else None
            if saved:
                with self.assertRaises(KernelError):
                    check_scope(a, saved, c)
        self.assertEqual(c.mark(), 0)

    def test_abstract_rev_and_local_occurrence_opacity(self):
        a, c = self.a, self.c
        u = c.fresh(a.const(199))
        v = c.fresh(self.sort)
        body = a.app(a.const(29), (u, v))
        closed = abstract(a, body, (u, v))
        self.assertEqual(instantiate_rev(a, closed, (u, v)), body)
        self.assertFalse(has_constant(a, u, {199}))
        # Existing BVars are not shifted during Local abstraction (Lean source).
        self.assertEqual(abstract(a, a.mk(Tag.BVAR, 3), (u,)), a.mk(Tag.BVAR, 3))

    def test_symbolic_levels_and_closed_scope(self):
        a = self.a
        u = a.level(LevelTag.PARAM, 11)
        v = a.level(LevelTag.PARAM, 37)
        level = a.level(LevelTag.IMAX, a.level(LevelTag.SUCC, u), a.level(LevelTag.MAX, u, v))
        root = a.mk(Tag.PI, a.mk(Tag.SORT, level), a.const(73, (level, v)))
        check_scope(a, root, universe_parameters=(11, 37))
        with self.assertRaises(KernelError):
            check_scope(a, root, universe_parameters=(11,))
        actual = substitute_levels(a, root, {11: a.zero})
        expected_level = a.level(LevelTag.IMAX, a.level(LevelTag.SUCC, a.zero),
            a.level(LevelTag.MAX, a.zero, v))
        self.assertEqual(actual, a.mk(Tag.PI, a.mk(Tag.SORT, expected_level), a.const(73, (expected_level, v))))

    def test_uniform_parameters_indices_and_functional_recursion(self):
        a, c = self.a, self.c
        p = c.fresh(self.sort)
        f, g = a.const(91), a.const(212)
        block = BlockTraversal(a, c, (Family(f, 1), Family(g, 2)), (p,), lambda x: x)
        # A functional recursive field into the OTHER family with dependent
        # index expressions, not a direct self-reference special case.
        x = c.fresh(self.sort)
        y = c.fresh(a.app(a.const(62), (x,)))
        field = fold_telescope(a, c, (x, y), a.app(g, (p, x, y)))
        mark = c.mark()
        block.check_positivity(field)
        desc = block.recursive_argument(field)
        self.assertEqual(c.mark(), mark)
        self.assertEqual(desc.family, 1)
        self.assertEqual(len(desc.prefix), 2)
        self.assertEqual(desc.indices, (a.mk(Tag.BVAR, 1), a.mk(Tag.BVAR, 0)))
        self.assertEqual(desc.prefix[1].domain, a.app(a.const(62), (a.mk(Tag.BVAR, 0),)))
        check_scope(a, fold_telescope(a, c, (p,), field))
        bad_parameter = a.app(f, (self.sort, self.sort))
        bad_index = a.app(f, (p, a.app(g, (p, self.sort, self.sort))))
        negative = a.mk(Tag.PI, a.app(f, (p, self.sort)), self.sort)
        for bad in (bad_parameter, bad_index, negative):
            with self.assertRaises(KernelError):
                block.check_positivity(bad)
            self.assertEqual(c.mark(), mark)

    def test_parameter_domains_are_checked_dependently(self):
        a, c = self.a, self.c
        p = c.fresh(self.sort)
        q = c.fresh(a.app(a.const(52), (p,)))
        root = fold_telescope(a, c, (p, q), a.app(a.const(81), (p, q)))
        actual = consume_parameters(a, c, root, (p, q), lambda x: x, lambda x, y: x == y)
        self.assertEqual(actual, a.app(a.const(81), (p, q)))
        with self.assertRaises(KernelError):
            consume_parameters(a, c, root, (q, p), lambda x: x, lambda x, y: x == y)

    def test_dag_bounds_not_python_recursion_bounds(self):
        a = self.a
        root = a.mk(Tag.BVAR, 0)
        for _ in range(1100):
            root = a.mk(Tag.MDATA, root, 2)
        expected = a.mk(Tag.BVAR, 3)
        for _ in range(1100):
            expected = a.mk(Tag.MDATA, expected, 2)
        self.assertEqual(lift(a, root, 3), expected)
        limited = Arena(replace(Limits(), stack=2))
        root = limited.mk(Tag.BVAR, 0)
        for _ in range(4):
            root = limited.mk(Tag.MDATA, root, 2)
        with self.assertRaises(ResourceError):
            lift(limited, root, 1)
        with self.assertRaises(KernelError):
            a.mk(Tag.APP, 0, self.sort)


if __name__ == '__main__':
    unittest.main()
