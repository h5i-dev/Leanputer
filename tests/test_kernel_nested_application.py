"""Complete nested condition over raw query syntax and derived prior metadata.

The origin list here is a private ABI fixture, NOT a published original-source
block. The real source producer/restoration transaction is tested separately.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program, traversal_machine as spec
from leanputer.kernel.syntax import SyntaxCodec
from leanputer.kernel.native_cells import CellTag, CellCapacities, VectorKind, pack_source
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class NestedApplicationTest(unittest.TestCase):
    def test_complete_parameter_scan_prior_lookup_and_conditional_loose_error(self):
        name = lambda s: [{'str': s}]; type0 = ['sort', ['succ', ['zero']]]; prop = ['sort', ['zero']]
        pair = ['const', name('Pair'), []]; f = ['const', name('F'), []]
        def app(fn, arguments):
            for argument in arguments: fn = ['app', fn, argument]
            return fn
        prior = dict(kind='inductive_block', level_params=[], parameters=2, recursor_claims=[], families=[dict(
            name=name('Pair'), recursor_name=name('Pair')+[{'str': 'rec'}], type=['pi', 0, type0, ['pi', 0, type0, type0]],
            constructors=[dict(name=name('Pair')+[{'str': 'mk'}], type=['pi', 0, type0, ['pi', 0, type0,
                ['pi', 0, ['var', 1], ['pi', 0, ['var', 1], app(pair, (['var', 3], ['var', 2]))]]]])])])
        current = dict(kind='inductive_block', level_params=[], parameters=0, recursor_claims=[], families=[dict(
            name=name('F'), recursor_name=name('F')+[{'str': 'rec'}], type=type0, constructors=[])])
        cases = [(app(pair, (f, prop)), True, False), (app(pair, (prop, f)), True, False),
            (app(pair, (prop, prop)), False, False), (app(pair, (['var', 0], prop)), False, False),
            (app(pair, (f, ['var', 0])), False, True), (app(pair, (['var', 0], f)), False, True),
            (app(pair, (f,)), False, False), (pair, False, False),
            (app(['const', name('Foreign'), []], (f, prop)), False, False),
            (app(pair, (['lam', 0, prop, ['var', 0]], f)), True, False),
            (app(pair, (['lam', 0, prop, ['var', 1]], f)), False, True),
            (app(f, (f, prop)), False, False)]
        body = cases[0][0]
        for expression, _, _ in cases[1:]: body = ['app', body, expression]
        doc = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[prior, current],
            target=dict(kind='definition', name=name('_nested_condition_probe'), level_params=[], type=prop, value=body))
        cfg = spec.MachineConfig(heap=1024, stack=32, context=16, constants=4, fuel=8192, word_bits=11)
        codec = SyntaxCodec(); source = codec.document(doc); args = None; decls = source.declarations
        # The test explicitly selects a kernel CORE operation on the FIRST raw
        # block to derive metadata. Source JSON cannot set this internal flag.
        initial = program.prepare(cfg, source, args, decls); initial['regs'].update(core_operation=1, core_index=0)
        machine = spec.SpecMachine(cfg, initial)
        for _ in range(cfg.fuel+2):
            machine.step()
            if machine.state['regs']['status']: break
        reference = machine.state
        self.assertEqual((reference['regs']['status'], reference['regs']['reason']), (spec.Outcome.GAP, spec.Reason.GAP_RECURSOR_GENERATION))
        self.assertEqual((reference['regs']['env_head'], reference['regs']['decl']), (0, 0))
        base = {'regs': {key: int(value) for key, value in reference['regs'].items()},
            **{bank: [[int(value) for value in row] for row in reference[bank]] for bank in spec.BANK_FIELDS}}
        def cell(tag, a=0, b=0, c=0):
            ref = base['regs']['free']; self.assertLess(ref, cfg.heap)
            base['heap'][ref] = list(map(int, (tag, a, b, c))); base['regs']['free'] = ref+1; return ref
        origin = cell(CellTag.BLOCK_ORIGIN, base['constants'][0][5], base['constants'][0][2], base['regs']['core_family_vector'])
        registry = cell(CellTag.VECTOR_CELL, origin)
        # The condition checks the current checked signature before provenance.
        for signature in vector(SimpleNamespace(heap=base['heap']),base['regs']['core_family_vector'],VectorKind.REFERENCES):
            base['regs']['env_head']=cell(CellTag.VECTOR_CELL,signature,base['regs']['env_head'])
        current_vector = base['heap'][base['constants'][1][5]][2]
        packed = pack_source(source, CellCapacities(heap=cfg.heap, constants=cfg.constants, word_bits=cfg.word_bits))
        # Re-encoding existing syntax keys supplies no checker/reducer result.
        before_rows = len(source.arena.rows)
        roots = [codec.expression(expression) for expression, _, _ in cases]
        self.assertEqual(len(source.arena.rows), before_rows)
        circuit = CircuitHarness(cfg)
        trials = [(registry, ref, nested, invalid) for ref, (_, nested, invalid) in zip(roots, cases)]
        trials.append((0, roots[0], False, False))
        for head, expression, nested, invalid in trials:
            with self.subTest(head=head, expression=expression, nested=nested, invalid=invalid):
                state = deepcopy(base); state['regs'].update(status=0, reason=0, fuel=cfg.fuel, sp=0,
                    task=int(spec.Task.IS_NESTED_APPLICATION), mode=int(spec.Mode.WALK), x=packed.expression_map[expression],
                    nested_registry_head=head, raw_family_vector=current_vector)
                before = deepcopy(state); machine = spec.SpecMachine(cfg, state)
                for step in range(cfg.fuel+2):
                    actual = circuit.step(state); expected = machine.step()
                    if actual != expected:
                        differences = {key: (actual['regs'][key], int(expected['regs'][key])) for key in spec.REGISTERS if actual['regs'][key] != expected['regs'][key]}
                        banks = {bank: [(i, left, right) for i, (left, right) in enumerate(zip(actual[bank], expected[bank])) if left != right][:3] for bank in spec.BANK_FIELDS}
                        self.fail(str((step, state['regs']['task'], state['regs']['mode'], differences, banks)))
                    state = actual
                    if state['regs']['status']: break
                if invalid:
                    self.assertEqual((state['regs']['status'], state['regs']['reason']), (spec.Outcome.INVALID, spec.Reason.INVALID_NESTED_PARAMETERS))
                else:
                    self.assertEqual(state['regs']['status'], spec.Outcome.DONE)
                    if not nested: self.assertEqual(state['regs']['r'], 0)
                    else:
                        tag, got_origin, spine, reserved = state['heap'][state['regs']['r']]
                        self.assertEqual((tag, got_origin, reserved), (CellTag.NESTED_APPLICATION, origin, 0))
                        self.assertEqual(state['heap'][spine][0], CellTag.APPLICATION_SPINE)
                        self.assertEqual(len(vector(SimpleNamespace(heap=state['heap']), state['heap'][spine][2], VectorKind.REFERENCES)), 2)
                self.assertEqual(state['context'][:before['regs']['ctx']], before['context'][:before['regs']['ctx']])
                for key in ('ctx', 'count', 'arg_base', 'env_head', 'typing_head', 'decl', 'raw_index'):
                    self.assertEqual(state['regs'][key], before['regs'][key], key)


if __name__ == '__main__': unittest.main()
