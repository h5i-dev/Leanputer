"""Nested queue/restoration phase contracts, with checked prior block data."""
import unittest
from leanputer.kernel.admission import analyze_core
from leanputer.kernel.arena import Arena, KernelError, LevelTag, LocalContext, Tag
from leanputer.kernel.nested import NestedRestorer, NestedSpecializer, PriorBlock
from leanputer.kernel.operations import check_scope, has_constant, spine
from leanputer.kernel.recursor import Constructor, Inductive, reduce_constructor_rule
from leanputer.kernel.services import KernelServices, Signature
from leanputer.kernel.syntax import SymbolTable
from leanputer.kernel.syntax import RawBlock, RawConstructor, RawDeclaration, RawInductive, SourceInput
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.telescope import fold_telescope


class NestedAlgorithmTest(unittest.TestCase):
    def setUp(self):
        self.a = Arena()
        self.c = LocalContext(self.a)
        self.s = KernelServices(self.a, self.c)
        self.names = SymbolTable(self.a)
        def sym(*parts):
            return self.names.intern([{'str': p} for p in parts])
        self.sym = sym
        a, c = self.a, self.c
        self.u = sym('v')
        u = a.level(LevelTag.PARAM, self.u)
        self.one = a.level(LevelTag.SUCC, a.zero)
        self.type = a.mk(Tag.SORT, self.one)
        alpha = c.fresh(a.mk(Tag.SORT, u))
        self.fsym, self.gsym = sym('ContainerF'), sym('ContainerG')
        f, g = a.const(self.fsym, (u,)), a.const(self.gsym, (u,))
        family_type = fold_telescope(a, c, (alpha,), a.mk(Tag.SORT, u))
        nil_type = fold_telescope(a, c, (alpha,), a.app(f, (alpha,)))
        head, tail = c.fresh(alpha), c.fresh(a.app(g, (alpha,)))
        cons_type = fold_telescope(a, c, (alpha, head, tail), a.app(f, (alpha,)))
        next_ = c.fresh(a.app(f, (alpha,)))
        pack_type = fold_telescope(a, c, (alpha, next_), a.app(g, (alpha,)))
        self.cons = sym('ContainerF', 'cons')
        self.prior_families = (
            Inductive(f, family_type, (Constructor(sym('ContainerF', 'nil'), nil_type),
                Constructor(self.cons, cons_type)), self.names.recursor_name(self.fsym)),
            Inductive(g, family_type, (Constructor(sym('ContainerG', 'pack'), pack_type),), self.names.recursor_name(self.gsym)))
        # Actually check the prior mutual block. There is no assumed-positive
        # functor flag or dictionary of supplied inferred types.
        analyze_core(self.s, self.prior_families, (self.u,), 1, sym('priorElim'))
        for family in self.prior_families:
            self.s.constants[a.expr(family.constant).a] = Signature((self.u,), family.type)
            for ctor in family.constructors:
                self.s.constants[ctor.symbol] = Signature((self.u,), ctor.type)
        self.prior = PriorBlock((self.u,), 1, self.prior_families)

    def target(self, result_level=None):
        a, c = self.a, self.c
        result_level = self.one if result_level is None else result_level
        carrier = c.fresh(self.type)
        parameter = c.fresh(carrier)
        symbol = self.sym('Target')
        family = a.const(symbol)
        type_ref = fold_telescope(a, c, (carrier, parameter), a.mk(Tag.SORT, result_level))
        occurrence = a.app(family, (carrier, parameter))
        field = c.fresh(a.app(a.const(self.fsym, (result_level,)), (occurrence,)))
        ctor_type = fold_telescope(a, c, (carrier, parameter, field), occurrence)
        ind = Inductive(family, type_ref, (Constructor(self.sym('Target', 'mk'), ctor_type),), self.names.recursor_name(symbol))
        return ind, (carrier, parameter)

    def test_entire_prior_mutual_block_and_restored_rules(self):
        a, c, s = self.a, self.c, self.s
        target, parameters = self.target()
        mark = c.mark()
        nested = NestedSpecializer(a, c, self.names, (self.prior,)).specialize((target,), (), 2)
        self.assertEqual(c.mark(), mark)
        self.assertEqual((len(nested.families), len(nested.templates)), (3, 2))
        # The queue copies BOTH prior families, retains all fields, and reaches
        # a fixed point by rewriting copied constructor references as well.
        core = analyze_core(s, nested.families, (), 2, self.sym('elim'))
        self.assertEqual([[ct.fields for ct in family.constructors] for family in core.families], [[1], [0, 2], [1]])
        self.assertEqual([r.motives for r in core.recursors], [3, 3, 3])
        restorer = NestedRestorer(a, c, self.names, nested)
        records = restorer.recursor_records(core.recursors)
        restored_ctor = restorer.expression(nested.families[0].constructors[0].type, rename_recursors=False)
        self.assertEqual(restored_ctor, target.constructors[0].type)
        auxiliary_symbols = set(t.auxiliary for t in nested.templates)
        auxiliary_symbols.update(aux for t in nested.templates for aux, _ in t.constructors)
        auxiliary_symbols.update(restorer.recursors)
        for rec in records:
            self.assertFalse(has_constant(a, rec.type, auxiliary_symbols))
            check_scope(a, rec.type, universe_parameters=rec.universe_parameters)
            for rule in rec.rules:
                self.assertFalse(has_constant(a, rule.rhs, auxiliary_symbols))
                check_scope(a, rule.rhs, universe_parameters=rec.universe_parameters)
        entries = [(a.expr(target.constant).a, Signature((), target.type)),
                   (target.constructors[0].symbol, Signature((), restored_ctor))]
        entries += [(rec.symbol, Signature(rec.universe_parameters, rec.type)) for rec in records]
        with s.overlay(entries):
            for rec in records:
                s.ensure_type(rec.type)
                for rule in rec.rules:
                    s.infer(rule.rhs)
        # Current block has TWO parameters, original container has ONE. Restored
        # rule reduction must select trailing fields, not subtract two params.
        record = records[1]
        prefix = tuple(a.const(self.sym('arg'+str(i))) for i in range(record.parameters+record.motives+record.minors))
        h, t = a.const(self.sym('h')), a.const(self.sym('tail'))
        major = a.app(a.const(self.cons, (self.one,)), (a.app(target.constant, parameters), h, t))
        reduced = reduce_constructor_rule(a, record, (a.zero,), prefix+(major,), lambda x: x)
        self.assertIsNotNone(reduced)
        _, args = spine(a, s.beta_zeta(reduced))
        self.assertEqual(args[:2], (h, t))

    def test_nested_parameter_closure_and_scope_rollback(self):
        a, c = self.a, self.c
        two = a.level(LevelTag.SUCC, self.one)
        target, parameters = self.target(two)
        carrier = c.fresh(self.type)
        value = c.fresh(carrier)
        occurrence = a.app(target.constant, (carrier, value))
        field = c.fresh(a.app(a.const(self.fsym, (two,)), (occurrence,)))
        result = a.app(target.constant, parameters)
        bad_type = fold_telescope(a, c, parameters+(carrier, value, field), result)
        bad = Inductive(target.constant, target.type, (Constructor(target.constructors[0].symbol, bad_type),), target.recursor_symbol)
        # This is a well-typed signature. It fails the SOURCE nested-parameter
        # closure condition because B,b are fields, not the shared parameters.
        with self.s.overlay([(a.expr(target.constant).a, Signature((), target.type))]):
            self.s.ensure_type(bad_type)
        mark = c.mark()
        with self.assertRaisesRegex(KernelError, 'nested parameters contain loose'):
            NestedSpecializer(a, c, self.names, (self.prior,)).specialize((bad,), (), 2)
        self.assertEqual(c.mark(), mark)

    def test_complete_nested_transaction_driver(self):
        a, c = self.a, self.c
        target, parameters = self.target()
        def raw_block(families, uparams, params):
            return RawBlock(uparams, params, tuple(RawInductive(a.expr(f.constant).a, f.type,
                tuple(RawConstructor(ct.symbol, ct.type) for ct in f.constructors), f.recursor_symbol)
                for f in families), ())
        prior = raw_block(self.prior_families, (self.u,), 1)
        raw_target = raw_block((target,), (), 2)
        value = c.fresh(a.app(target.constant, parameters))
        claim = fold_telescope(a, c, parameters+(value,), c.lookup(value).type)
        body = fold_telescope(a, c, parameters+(value,), value, Tag.LAM)
        goal = RawDeclaration('definition', self.sym('nestedIdentity'), (), claim, body)
        source = SourceInput(a, self.names, (prior, raw_target), goal)
        driver = EnvironmentDriver(source)
        result = driver.check()
        self.assertEqual(result.status, 'ACCEPT', result.reason)
        self.assertEqual(result.checked_input_items, 2)
        # PriorF/G:2families+3ctors+2recs, current:1family+1ctor+3recs.
        self.assertEqual(result.admitted_declarations, 12)
        self.assertFalse(result.assumptions)
        self.assertEqual(driver.c.mark(), 0)
        self.assertEqual(len(driver.services.recursors), 5)


if __name__ == '__main__':
    unittest.main()
