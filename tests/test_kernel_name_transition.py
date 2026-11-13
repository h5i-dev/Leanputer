"""Raw structured-name/profile contract; no checked types/answers as input."""
import unittest
from leanputer.kernel.arena import KernelError
from leanputer.kernel.environment import EnvironmentDriver, UnsupportedProfile
from leanputer.kernel import level_transition as program
from leanputer.kernel import traversal_machine as spec
from tests.test_kernel_traversal_machine import CircuitHarness


class NameTransitionTest(unittest.TestCase):
    def test_generic_name_data_and_only_genuine_native_interfaces(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=128, word_bits=8)
        circuit = CircuitHarness(cfg)
        names = [[{'str':'Main'}], [{'str':'Lean'},{'str':'reduceNat'}],
            [{'str':'Lean'},{'str':'reduceBool'}], [{'str':'Lean'},{'str':'reduceNAt'}],
            [{'str':'Lean.reduceNat'}], [{'str':'Lean'},{'num':2**80+1}],
            [{'str':'Lean'},{'str':'reduceNat'},{'str':'child'}], []]
        for name in names:
            def raw(symbol):
                return dict(kind='axiom', name=[{'str':symbol}], level_params=[], type=['sort',['zero']], value=None)
            document = dict(format='leanputer.kernel-data-operation.v1', operation='infer',
                source=dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[raw('beforeA'),raw('beforeB')],
                    target=dict(kind='definition', name=name, level_params=[], type=['sort',['zero']], value=None)))
            source, args, declarations = program.parse_document(document)
            state = program.prepare(cfg, source, args, declarations)
            # Isolated private-operation contract over RAW name syntax only.
            # No checked entry, inferred type or admission answer is supplied.
            state['regs'].update(task=int(spec.Task.CHECK_NAME), x=state['regs']['symbols_root'],
                query_symbol=source.target.symbol, pending_scope=0, pending_infer=0)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (name,step))
                state = actual
                if state['regs']['status']: break
            driver = EnvironmentDriver(source)
            try: driver._name(source.target.symbol)
            except UnsupportedProfile:
                self.assertEqual((state['regs']['status'],state['regs']['reason']),
                    (spec.Outcome.UNSUPPORTED_PROFILE,spec.Reason.NATIVE_EXECUTION))
            except KernelError:
                self.assertEqual((state['regs']['status'],state['regs']['reason']),
                    (spec.Outcome.INVALID,spec.Reason.INVALID_DECLARATION))
            else:
                self.assertEqual((state['regs']['status'],state['regs']['r']), (spec.Outcome.DONE,1))
            self.assertEqual((state['regs']['decl'],state['regs']['env_ready'],state['regs']['env_head']), (0,0,0))
            self.assertEqual(circuit.step(state),state)


if __name__ == '__main__': unittest.main()
