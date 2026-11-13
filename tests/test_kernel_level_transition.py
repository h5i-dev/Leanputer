"""Targeted symbolic-level scope IR/cell integration contracts."""
import unittest
from leanputer.kernel.arena import KernelError
from leanputer.kernel.operations import check_scope
from leanputer.kernel import level_transition as program
from leanputer.kernel import traversal_machine as spec
from tests.test_kernel_traversal_machine import CircuitHarness


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


if __name__ == '__main__':
    unittest.main()
