"""Generic syntactic has_loose_bvars, including binder domains and opaque Locals."""
from copy import deepcopy
import unittest
from leanputer.kernel import traversal_machine as spec
from leanputer.kernel.arena import Arena, Tag
from leanputer.kernel.operations import has_loose_bvars
from tests.test_kernel_traversal_machine import CircuitHarness


class LooseBVarTest(unittest.TestCase):
    def test_shared_all_expression_walk_and_existing_occurrence_callback(self):
        a = Arena(); ty = a.mk(Tag.SORT, a.zero); b0 = a.mk(Tag.BVAR, 0); b1 = a.mk(Tag.BVAR, 1)
        constant = a.const(73); local = a.mk(Tag.LOCAL, 37)
        roots = [b0, a.mk(Tag.LAM, ty, b0), a.mk(Tag.LAM, ty, b1),
            a.mk(Tag.PI, ty, a.mk(Tag.LAM, b0, b1)), a.mk(Tag.PI, b0, b0),
            a.mk(Tag.LET, ty, constant, b0), a.mk(Tag.LET, ty, b0, b0),
            a.mk(Tag.MDATA, a.mk(Tag.LAM, ty, b0)), a.mk(Tag.PROJ, 11, 0, b0), local,
            a.mk(Tag.MDATA, a.mk(Tag.PROJ, 11, 0, local)), constant,
            a.mk(Tag.NAT, a.vec((17,))), a.mk(Tag.STRING, a.vec((65,)))]
        cfg = spec.MachineConfig(heap=64, stack=8, context=4, constants=2, fuel=128, word_bits=8)
        circuit = CircuitHarness(cfg)
        cases = [(root, spec.Task.HAS_LOOSE_BVARS, (), int(has_loose_bvars(a, root))) for root in roots]
        cases += [(constant, spec.Task.HAS_CONSTANTS, (73,), 1), (constant, spec.Task.HAS_CONSTANTS, (41,), 0)]
        for root, task, symbols, wanted in cases:
            with self.subTest(root=root, task=task, symbols=symbols):
                request, _, _ = spec.parse_document(spec.document(a, root, spec.Task.OCCURS, symbols))
                state = spec.prepare(cfg, request); before = deepcopy(state); state['regs']['task'] = int(task)
                machine = spec.SpecMachine(cfg, state)
                for step in range(cfg.fuel+2):
                    actual = circuit.step(state); self.assertEqual(actual, machine.step(), step); state = actual
                    if state['regs']['status']: break
                self.assertEqual((state['regs']['status'], state['regs']['r']), (spec.Outcome.DONE, wanted))
                for bank in ('heap', 'context', 'constants'): self.assertEqual(state[bank], before[bank])
                self.assertEqual((state['regs']['ctx'], state['regs']['count'], state['regs']['arg_base']),
                    (before['regs']['ctx'], before['regs']['count'], before['regs']['arg_base']))
                self.assertEqual(state['regs']['occurrence_internal'], 0)
                self.assertEqual(circuit.step(state), state)


if __name__ == '__main__': unittest.main()
