"""Targeted symbolic-level scope IR/cell integration contracts."""
import unittest
import json
from pathlib import Path
from leanputer.kernel.arena import KernelError
from leanputer.kernel.levels import LevelOps
from leanputer.kernel.operations import check_scope
from leanputer.kernel import level_transition as program
from leanputer.kernel import traversal_machine as spec
from tests.test_kernel_traversal_machine import CircuitHarness
from tests.test_kernel_native_cells import decode_syntax
from leanputer.kernel.operations import substitute_levels, instantiate_levels
from types import SimpleNamespace


def name(s):
    return [{'str': s}]


def cases():
    u, v = ['param', name('u')], ['param', name('v')]
    numeric = [{'str': 'a'}, {'num': 1}]
    string = [{'str': 'a'}, {'str': '1'}]
    probes = [
        ([], ['max', ['zero'], ['succ', ['zero']]]),
        ([name('u'), name('v'), name('unused')], ['imax', ['max', ['succ', u], v], ['succ', u]]),
        ([name('u'), name('v')], ['param', name('missing')]),
        ([], u),
        ([numeric], ['param', string]),
        ([name('別宇宙')], ['succ', ['param', name('別宇宙')]])]
    return [dict(format='leanputer.kernel-level-operation.v1', operation='scope',
                 name=f'level-scope-{i}', parameters=parameters, level=level)
            for i, (parameters, level) in enumerate(probes)]


def telescope_cases():
    u = ['param', name('u')]
    carrier = ['sort', ['succ', u]]
    ty = ['pi', 1, carrier, ['pi', 0, ['var', 0], ['var', 1]]]
    value = ['lam', 1, carrier, ['lam', 0, ['var', 0], ['var', 0]]]
    source = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
        target=dict(kind='definition', name=name('identity'), level_params=[name('u')], type=ty, value=value))
    return [dict(format='leanputer.kernel-data-operation.v1', operation='telescope_roundtrip',
        name='typed-telescope-'+root, source=source, root=root, open_binder=binder)
        for root, binder in (('type', 'pi'), ('value', 'lam'))]


def substitution_cases():
    u, v, w = (['param', name(s)] for s in ('u', 'v', 'w'))
    probes = [
        (['imax', ['succ', u], ['max', v, w]],
            [('u', ['succ', v]), ('v', ['zero'])]),
        (['max', u, ['zero']], []),
        (['succ', w], [('u', ['zero'])]),
        (u, [('u', ['succ', ['zero']]), ('u', ['zero'])])]
    docs = [dict(format='leanputer.kernel-level-operation.v1', operation='substitute_raw',
        name=f'level-substitute-{i}', level=level,
        bindings=[dict(parameter=name(symbol), level=value) for symbol, value in bindings])
        for i, (level, bindings) in enumerate(probes)]
    docs[0]['argument_prefix'] = [77, 79]
    return docs


def expression_cases():
    u, v, w = (['param', name(s)] for s in ('u', 'v', 'w'))
    def source(expr, parameters=()):
        return dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
            target=dict(kind='definition', name=name('t'), level_params=list(parameters), type=expr, value=None))
    # Instantiate the COMPLETE pre-existing expression operation, not a new
    # theorem/datatype class. All12 Expr tags occur, including inert Local and
    # literals: only Sort levels and Const universe arguments should change.
    value = ['app', ['app', ['const', name('f'), [u, v]], ['nat', '1']], ['string', 'ok']]
    body = ['lam', 3, ['sort', u], ['proj', name('R'), 0, ['mdata', ['app', ['var', 0], ['local', 31]]]]]
    root = ['pi', 1, ['sort', v], ['let', ['sort', u], value, body]]
    actual_id = json.loads((Path(__file__).parent/'fixtures/kernel-source-smoke.jsonl').read_text().splitlines()[0])
    specs = [
        (source(root, (name('u'), name('v'))), 'type',
            [dict(parameter=name('u'), level=['succ', w]), dict(parameter=name('v'), level=['zero'])]),
        (source(['const', name('f'), []]), 'type', [dict(parameter=name('u'), level=['zero'])]),
        (actual_id, 'value', [dict(parameter=actual_id['target']['level_params'][0], level=['succ', ['zero']])]),
        (source(['const', name('f'), [u, v]]), 'type', []),
        (source(['const', name('f'), [u, v]]), 'type', [dict(parameter=name('w'), level=['zero'])])]
    docs = [dict(format='leanputer.kernel-data-operation.v1', operation='expr_substitute_raw',
        name=f'expr-level-substitute-{i}', source=s, root=root, bindings=bindings)
        for i, (s, root, bindings) in enumerate(specs)]
    docs[0]['argument_prefix'] = [77]
    return docs


def predicate_cases():
    u, v, w = (['param', name(s)] for s in ('u', 'v', 'w'))
    # Complete source operator cases are defined by tags, not datatype fixtures.
    probes = [
        dict(operation='equal', level=['max', ['succ', u], v], right=['max', ['succ', u], w]),
        dict(operation='equal', level=['succ', u], right=['succ', v]),
        dict(operation='equal', level=['max', u, ['zero']], right=u),
        dict(operation='equal', level=['imax', u, v], right=['imax', u, v]),
        dict(operation='substitute_raw_equal', level=['imax', ['max', u, v], ['succ', u]],
            bindings=[dict(parameter=name('u'), level=w)],
            right=['imax', ['max', w, v], ['succ', w]]),
        dict(operation='not_zero', level=['max', u, v]),
        dict(operation='not_zero', level=['imax', ['succ', u], v]),
        dict(operation='not_zero', level=['max', ['imax', u, v], ['succ', v]]),
        dict(operation='not_zero', level=['max', ['succ', u], v]),
        dict(operation='offset', level=['succ', ['succ', ['imax', u, v]]])]
    return [dict(format='leanputer.kernel-level-operation.v1', name=f'level-predicate-{i}', **probe)
            for i, probe in enumerate(probes)]


def constructor_cases():
    z = ['zero']
    u, v, w = (['param', name(s)] for s in ('u', 'v', 'w'))
    one = ['succ', z]
    probes = [
        ('max', z, u), ('max', u, z), ('max', u, u),
        ('max', u, ['max', v, u]), ('max', ['max', v, u], u),
        ('max', ['max', u, v], u),
        ('max', ['succ', ['succ', u]], ['succ', u]),
        ('max', one, ['succ', one]), ('max', u, v),
        ('max', ['max', u, v], w), ('max', w, ['max', u, v]),
        ('imax', u, ['succ', v]), ('imax', u, z), ('imax', z, u),
        ('imax', one, u), ('imax', ['succ', one], u),
        ('imax', u, u), ('imax', u, v)]
    return [dict(format='leanputer.kernel-level-operation.v1', operation=op,
        name=f'level-constructor-{i}', level=left, right=right)
        for i, (op, left, right) in enumerate(probes)]


def source_instantiation_cases():
    u, v = (['param', name(s)] for s in ('u', 'v'))
    bindings = [dict(parameter=name('u'), level=['zero'])]
    probes = [
        (['max', u, v], bindings), (['imax', v, u], bindings),
        (['imax', v, u], [dict(parameter=name('u'), level=['succ', ['zero']])]),
        (['max', ['zero'], v], []),
        (['max', ['imax', v, u], ['succ', u]], bindings)]
    docs = [dict(format='leanputer.kernel-level-operation.v1', operation='instantiate',
        name=f'level-source-instantiate-{i}', level=level, bindings=pairs)
        for i, (level, pairs) in enumerate(probes)]
    # A generic scheme with multiple Sort/Const sites calls the same source op.
    original = expression_cases()[0]
    from copy import deepcopy
    expr = deepcopy(original)
    expr.update(operation='expr_instantiate', name='expr-source-instantiate')
    expr['source']['target']['type'] = ['pi', 0, ['sort', ['max', u, v]],
        ['app', ['const', name('f'), [['imax', v, u], ['max', u, v]]], ['var', 0]]]
    expr['bindings'] = bindings
    docs.append(expr)
    return docs


def ordering_cases():
    u, v, w = (['param', name(s)] for s in ('u', 'v', 'w'))
    probes = [
        (['succ', ['succ', u]], ['succ', u]),
        (['max', ['succ', u], v], ['max', u, v]),
        (['imax', u, v], ['imax', u, w]),
        (['succ', ['zero']], u), (u, u),
        (['max', u, v], ['imax', u, v])]
    return [dict(format='leanputer.kernel-level-operation.v1', operation='compare',
        name=f'level-order-{i}', level=left, right=right) for i, (left, right) in enumerate(probes)]


def normalization_cases():
    z = ['zero']
    u, v, w = (['param', name(s)] for s in ('u', 'v', 'w'))
    one, two = ['succ', z], ['succ', ['succ', z]]
    levels = [
        ['succ', ['max', v, ['succ', u]]],
        ['max', one, ['max', ['succ', u], u]],
        ['max', two, u],
        ['imax', ['max', v, u], ['succ', w]],
        ['imax', ['max', ['succ', u], u], v],
        ['max', z, z]]
    docs = [dict(format='leanputer.kernel-level-operation.v1', operation='normalize',
        name=f'level-normalize-{i}', level=level) for i, level in enumerate(levels)]
    equations = [
        (['max', u, v], ['max', v, u]),
        (['succ', ['max', u, v]], ['max', ['succ', u], ['succ', v]]),
        (['imax', u, v], ['max', u, v]),
        (['max', two, ['succ', u]], ['succ', u])]
    docs.extend(dict(format='leanputer.kernel-level-operation.v1', operation='equivalent',
        name=f'level-equivalent-{i}', level=left, right=right) for i, (left, right) in enumerate(equations))
    return docs


class SymbolicLevelTransitionTest(unittest.TestCase):
    def test_same_controller_typed_cells_and_scope_membership(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=128, word_bits=8)
        circuit = CircuitHarness(cfg)
        expected = ['DONE', 'DONE', 'INVALID', 'INVALID', 'INVALID', 'DONE']
        for doc, want in zip(cases(), expected):
            source, level, declarations = program.parse_document(doc)
            state = program.prepare(cfg, source, level, declarations)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']:
                    break
            self.assertEqual(spec.Outcome(state['regs']['status']).name, want)
            if want == 'DONE':
                check_scope(source.arena, source.target.type, universe_parameters=source.target.universe_parameters)
                self.assertEqual(state['regs']['r'], state['regs']['root'])
                self.assertEqual(state['regs']['sp'], 0)
            else:
                self.assertEqual(state['regs']['reason'], spec.Reason.UNIVERSE)
                with self.assertRaises(KernelError):
                    check_scope(source.arena, source.target.type, universe_parameters=source.target.universe_parameters)
            self.assertEqual(circuit.step(state), state)

    def test_telescope_callers_use_the_same_typed_memory_abi(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=128, word_bits=8)
        circuit = CircuitHarness(cfg)
        for doc in telescope_cases():
            state = program.prepare(cfg, *program.parse_document(doc))
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']:
                    break
            self.assertEqual(spec.Outcome(state['regs']['status']), spec.Outcome.DONE)
            self.assertEqual((state['regs']['ctx'], state['regs']['sp']), (0, 0))

    def test_simultaneous_symbolic_substitution_and_argument_window(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=128, word_bits=8)
        circuit = CircuitHarness(cfg)
        for i, doc in enumerate(substitution_cases()):
            source, arguments, declarations = program.parse_document(doc)
            state = program.prepare(cfg, source, arguments, declarations)
            # An opaque caller-owned prefix is outside the argument window;
            # its values are data, never admitted local-context declarations.
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']:
                    break
            self.assertEqual(spec.Outcome(state['regs']['status']), spec.Outcome.DONE)
            first_bindings = {}
            for symbol, level in arguments['bindings']:
                first_bindings.setdefault(symbol, level)
            expected_expr = substitute_levels(source.arena, source.target.type, first_bindings)
            expected = source.arena.expr(expected_expr).a
            decoded, _ = decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]), source.arena)
            self.assertEqual(decoded[state['regs']['r']], expected)
            self.assertEqual(state['regs']['sp'], 0)
            if i == 0:
                self.assertEqual(state['context'][:2], [[77], [79]])

    def test_normalizer_physical_exhaustion_is_not_a_semantic_answer(self):
        probes = [(normalization_cases()[0], dict(heap=128, stack=16, fuel=128), 'heap'),
                  (normalization_cases()[6], dict(heap=128, stack=2, fuel=128), 'stack'),
                  (normalization_cases()[0], dict(heap=128, stack=16, fuel=3), 'fuel')]
        for doc, capacities, resource in probes:
            cfg = spec.MachineConfig(context=8, constants=2, word_bits=8, **capacities)
            state = program.prepare(cfg, *program.parse_document(doc))
            if resource == 'heap': state['regs']['free'] = cfg.heap
            circuit = CircuitHarness(cfg)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (resource, step))
                state = actual
                if state['regs']['status']: break
            self.assertEqual(state['regs']['status'], spec.Outcome.RESOURCE)
            self.assertEqual(state['regs']['reason'], getattr(spec.Reason, resource.upper()))
            self.assertEqual(circuit.step(state), state)

    def test_complete_canonical_normalization_and_equivalence(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=1024, word_bits=8)
        circuit = CircuitHarness(cfg)
        for doc in normalization_cases():
            source, arguments, declarations = program.parse_document(doc)
            state = program.prepare(cfg, source, arguments, declarations)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']: break
            self.assertEqual(spec.Outcome(state['regs']['status']), spec.Outcome.DONE, (doc['name'], state['regs']))
            levels = LevelOps(source.arena)
            if arguments['operation'] == 'normalize':
                expected = levels.normalize(arguments['root_level'])
                decoded, _ = decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]), source.arena)
                self.assertEqual(decoded[state['regs']['r']], expected, doc['name'])
            else:
                expected = int(levels.equal(arguments['root_level'], arguments['peer']))
                self.assertEqual(state['regs']['r'], expected, doc['name'])
            self.assertEqual(state['regs']['sp'], 0)

    def test_total_structural_base_order_and_offsets(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=128, word_bits=8)
        circuit = CircuitHarness(cfg)
        for doc in ordering_cases():
            source, arguments, declarations = program.parse_document(doc)
            state = program.prepare(cfg, source, arguments, declarations)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']: break
            self.assertEqual(spec.Outcome(state['regs']['status']), spec.Outcome.DONE, (doc['name'], state['regs']))
            levels = LevelOps(source.arena)
            left, right = arguments['root_level'], arguments['peer']
            order = levels._compare(left, right)
            self.assertEqual(state['regs']['r'], 0 if order == 0 else 1 if order < 0 else 2)
            self.assertEqual(state['regs']['order_same_base'], int(levels.offset(left)[0] == levels.offset(right)[0]))
            self.assertEqual(state['regs']['sp'], 0)

    def test_source_level_and_expression_instantiation_reuse_constructors(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=128, word_bits=8)
        circuit = CircuitHarness(cfg)
        for doc in source_instantiation_cases():
            source, arguments, declarations = program.parse_document(doc)
            state = program.prepare(cfg, source, arguments, declarations)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']: break
            self.assertEqual(spec.Outcome(state['regs']['status']), spec.Outcome.DONE, (doc['name'], state['regs']))
            expected = instantiate_levels(source.arena, source.target.type, dict(arguments['bindings']))
            levels, expressions = decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]), source.arena)
            if arguments['operation'] == 'instantiate':
                self.assertEqual(levels[state['regs']['r']], source.arena.expr(expected).a, doc['name'])
            else:
                self.assertEqual(expressions[state['regs']['r']], expected, doc['name'])
            self.assertEqual(state['regs']['sp'], 0)

    def test_complete_pinned_smart_level_constructors(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=128, word_bits=8)
        circuit = CircuitHarness(cfg)
        for doc in constructor_cases():
            source, arguments, declarations = program.parse_document(doc)
            state = program.prepare(cfg, source, arguments, declarations)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']: break
            self.assertEqual(spec.Outcome(state['regs']['status']), spec.Outcome.DONE, (doc['name'], state['regs']))
            operation = getattr(LevelOps(source.arena), arguments['operation'])
            expected = operation(arguments['root_level'], arguments['peer'])
            levels, _ = decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]), source.arena)
            self.assertEqual(levels[state['regs']['r']], expected, doc['name'])
            self.assertEqual(state['regs']['sp'], 0)
            self.assertEqual(circuit.step(state), state)

    def test_structural_comparison_nonzero_and_offset_services(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=128, word_bits=8)
        circuit = CircuitHarness(cfg)
        for doc in predicate_cases():
            source, arguments, declarations = program.parse_document(doc)
            state = program.prepare(cfg, source, arguments, declarations)
            machine = spec.SpecMachine(cfg, state)
            duplicate_compared = False
            for step in range(cfg.fuel+2):
                r = state['regs']
                if r['pending_compare'] and r['mode'] == spec.Mode.RETURN and r['sp'] == 0:
                    duplicate_compared = r['r'] != r['peer']
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']: break
            self.assertEqual(spec.Outcome(state['regs']['status']), spec.Outcome.DONE, (doc['name'], state['regs']))
            self.assertEqual(state['regs']['sp'], 0)
            arena, operation, root = source.arena, arguments['operation'], arguments['root_level']
            if operation in ('equal', 'substitute_raw_equal'):
                if operation == 'substitute_raw_equal':
                    bindings = dict(arguments['bindings'])
                    root = source.arena.expr(substitute_levels(arena, source.target.type, bindings)).a
                    self.assertTrue(duplicate_compared, 'runtime allocation must exercise structural equality without pointer identity')
                # The reference Arena interns syntax; this comparison is only
                # post-inference validation, never a packed equality answer.
                expected = int(root == arguments['peer'])
                self.assertEqual(state['regs']['r'], expected)
            elif operation == 'not_zero':
                self.assertEqual(state['regs']['r'], int(LevelOps(arena).not_zero(root)))
            else:
                base, offset = LevelOps(arena).offset(root)
                levels, _ = decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]), arena)
                self.assertEqual((levels[state['regs']['r']], state['regs']['level_offset']), (base, offset))
            self.assertEqual(circuit.step(state), state)
        # Physical offset overflow is detected rather than wrapping.
        doc = dict(format='leanputer.kernel-level-operation.v1', operation='offset', level=['succ', ['zero']])
        state = program.prepare(cfg, *program.parse_document(doc))
        state['regs']['level_offset'] = 255
        machine = spec.SpecMachine(cfg, state)
        actual = circuit.step(state)
        self.assertEqual(actual, machine.step())
        self.assertEqual((actual['regs']['status'], actual['regs']['reason']), (spec.Outcome.RESOURCE, spec.Reason.INDEX))

    def test_expression_schemes_call_the_same_level_subroutine(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=256, word_bits=8)
        circuit = CircuitHarness(cfg)
        for doc in expression_cases():
            source, arguments, declarations = program.parse_document(doc)
            state = program.prepare(cfg, source, arguments, declarations)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']:
                    break
            self.assertEqual(spec.Outcome(state['regs']['status']), spec.Outcome.DONE, (doc['name'], state['regs']))
            bindings = {}
            for symbol, level in arguments['bindings']:
                bindings.setdefault(symbol, level)
            root = source.target.type if arguments['root'] == 'type' else source.target.value
            expected = substitute_levels(source.arena, root, bindings)
            _, decoded = decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]), source.arena)
            self.assertEqual(decoded[state['regs']['r']], expected)
            self.assertEqual(state['regs']['sp'], 0)
            if doc.get('argument_prefix'):
                self.assertEqual(state['context'][0], [77])


if __name__ == '__main__':
    unittest.main()
