"""Focused core admission contracts with actual internal inference services.

These exercise a source-defined phase, NOT complete admission/native inference.
No supplied inferred types/admission booleans or external oracle are used.
"""
import unittest
from leanputer.kernel.admission import analyze_core
from leanputer.kernel.arena import Arena, KernelError, LevelTag, LocalContext, Tag
from leanputer.kernel.levels import LevelOps
from leanputer.kernel.recursor import Constructor, Inductive
from leanputer.kernel.services import KernelServices, MissingOperation, Signature
from leanputer.kernel.telescope import fold_telescope


class KernelAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.a = Arena()
        self.c = LocalContext(self.a)
        self.s = KernelServices(self.a, self.c)
        self.type = self.a.mk(Tag.SORT, self.s.levels.succ(self.a.zero))

    def test_dependent_term_parameters_and_all_fields(self):
        a, c = self.a, self.c
        carrier = c.fresh(self.type)
        x = c.fresh(carrier)
        predicate = c.fresh(fold_telescope(a, c, (x,), self.type))
        family = a.const(101)
        family_type = fold_telescope(a, c, (carrier, predicate), self.type)
        # Four dependent fields, including non-Sort parameter B:(A -> Type).
        v = c.fresh(a.app(predicate, (x,)))
        y = c.fresh(carrier)
        w = c.fresh(a.app(predicate, (y,)))
        ctor_type = fold_telescope(a, c, (carrier, predicate, x, v, y, w), a.app(family, (carrier, predicate)))
        ind = Inductive(family, family_type, (Constructor(103, ctor_type),), 107)
        mark = c.mark()
        analysis = analyze_core(self.s, (ind,), (), 2, 71)
        self.assertEqual(c.mark(), mark)
        self.assertEqual(self.s.constants, {})
        self.assertEqual(analysis.families[0].constructors[0].fields, 4)
        self.assertEqual(analysis.recursors[0].parameters, 2)
        self.assertFalse(analysis.k_eligible)

    def test_mutual_indexed_functional_admission_and_rollback(self):
        a, c = self.a, self.c
        carrier = c.fresh(self.type)
        x = c.fresh(carrier)
        f, g = a.const(151), a.const(191)
        family_type = fold_telescope(a, c, (carrier, x), self.type)
        y = c.fresh(carrier)
        child = c.fresh(fold_telescope(a, c, (y,), a.app(g, (carrier, y))))
        step_type = fold_telescope(a, c, (carrier, x, child), a.app(f, (carrier, x)))
        prev = c.fresh(a.app(f, (carrier, x)))
        join_type = fold_telescope(a, c, (carrier, x, prev), a.app(g, (carrier, x)))
        inds = (Inductive(f, family_type, (Constructor(157, step_type),), 163),
                Inductive(g, family_type, (Constructor(193, join_type),), 197))
        before = c.mark()
        analysis = analyze_core(self.s, inds, (), 1, 71)
        self.assertEqual([f.indices for f in analysis.families], [1, 1])
        self.assertEqual([f.constructors[0].recursive_fields for f in analysis.families], [(1,), (1,)])
        self.assertTrue(analysis.families[0].constructors[0].reflexive)
        self.assertFalse(analysis.families[1].constructors[0].reflexive)
        # Negative occurrence is typed by the same general inference module
        # before strict positivity rejects it. No shape whitelist intervenes.
        negative = c.fresh(fold_telescope(a, c, (prev,), carrier))
        bad_type = fold_telescope(a, c, (carrier, x, negative), a.app(f, (carrier, x)))
        bad = (Inductive(f, family_type, (Constructor(157, bad_type),), 163), inds[1])
        current = c.mark()
        with self.assertRaisesRegex(KernelError, 'negative inductive occurrence'):
            analyze_core(self.s, bad, (), 1, 71)
        self.assertEqual(c.mark(), current)
        self.assertEqual(self.s.constants, {})
        self.assertGreaterEqual(current, before)

    def test_symbolic_universe_elimination_and_exact_prop_k(self):
        a = self.a
        u = a.level(LevelTag.PARAM, 17)
        f = a.const(211, (u,))
        ind = Inductive(f, a.mk(Tag.SORT, u), (Constructor(223, f), Constructor(227, f)), 229)
        result = analyze_core(self.s, (ind,), (17,), 0, 71)
        # u may be Prop. Ground-specializing u=1 before admission loses this.
        self.assertEqual(result.elimination_level, a.zero)
        self.assertFalse(result.k_eligible)
        positive = Inductive(f, a.mk(Tag.SORT, self.s.levels.succ(u)), ind.constructors, 229)
        result = analyze_core(self.s, (positive,), (17,), 0, 71)
        self.assertNotEqual(result.elimination_level, a.zero)
        prop = a.const(233)
        result = analyze_core(self.s, (Inductive(prop, a.mk(Tag.SORT, a.zero), (Constructor(239, prop),), 241),), (), 0, 71)
        self.assertTrue(result.k_eligible)

    def test_level_normalization_order_and_gaps_are_explicit(self):
        a, ops = self.a, self.s.levels
        u = a.level(LevelTag.PARAM, 13)
        v = a.level(LevelTag.PARAM, 29)
        maximum = a.level(LevelTag.MAX, u, a.level(LevelTag.MAX, v, ops.succ(u)))
        expected = a.level(LevelTag.MAX, ops.succ(u), v)
        self.assertTrue(ops.equal(maximum, expected))
        self.assertTrue(ops.equal(ops.succ(a.level(LevelTag.MAX, u, v)),
            a.level(LevelTag.MAX, ops.succ(v), ops.succ(u))))
        self.assertTrue(ops.geq(maximum, u))
        self.assertFalse(ops.geq(u, ops.succ(u)))
        self.assertFalse(ops.not_zero(u))
        self.assertTrue(ops.not_zero(ops.succ(u)))
        self.assertTrue(ops.is_zero(a.level(LevelTag.IMAX, u, a.zero)))
        self.assertTrue(ops.equal(ops.imax(ops.succ(a.zero), u), u))
        with self.assertRaises(MissingOperation):
            self.s.convert(a.const(251), a.const(257))
        with self.assertRaises(MissingOperation):
            self.s.infer(a.mk(Tag.PROJ, 151, 4, a.const(157)))


if __name__ == '__main__':
    unittest.main()
