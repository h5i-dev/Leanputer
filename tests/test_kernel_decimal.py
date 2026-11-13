"""Exact bounded decimal formatting at the supported data-word widths."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import traversal_machine as spec
from leanputer.kernel.arena import Arena, Tag
from leanputer.kernel.native_cells import VectorKind
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class DecimalTest(unittest.TestCase):
    def test_zero_carries_full_words_and_physical_exhaustion(self):
        cases = ((8, (0, 1, 9, 10, 99, 100, 255)), (10, (0, 10, 999, 1000, 1023)),
            (21, (0, 999999, 1000000, 2097151)))
        for width, values in cases:
            cfg = spec.MachineConfig(heap=32, stack=2, context=2, constants=2, fuel=32, word_bits=width)
            a = Arena(); root = a.mk(Tag.BVAR, 0)
            request, _, _ = spec.parse_document(spec.document(a, root, spec.Task.LIFT)); base = spec.prepare(cfg, request)
            circuit = CircuitHarness(cfg)
            for number in values:
                with self.subTest(width=width, number=number):
                    state = deepcopy(base); state['regs'].update(task=int(spec.Task.WORD_DECIMAL), decimal_value=number,
                        x=(1 << width)-1)  # A word operation never follows x as a pointer.
                    machine = spec.SpecMachine(cfg, state)
                    for step in range(cfg.fuel+2):
                        actual = circuit.step(state); self.assertEqual(actual, machine.step(), (width, number, step)); state = actual
                        if state['regs']['status']: break
                    self.assertEqual(state['regs']['status'], spec.Outcome.DONE)
                    self.assertEqual(bytes(vector(SimpleNamespace(heap=state['heap']), state['regs']['r'], VectorKind.BYTES)), str(number).encode())
                    self.assertEqual(state['regs']['decimal_number'], 0)
                    for bank in ('stack', 'context', 'constants'): self.assertEqual(state[bank], base[bank])
                    self.assertEqual(state['heap'][:base['regs']['free']], base['heap'][:base['regs']['free']])
                    self.assertEqual(circuit.step(state), state)
            state = deepcopy(base); state['regs'].update(task=int(spec.Task.WORD_DECIMAL), decimal_value=0, free=cfg.heap-1)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state); self.assertEqual(actual, machine.step(), step); state = actual
                if state['regs']['status']: break
            self.assertEqual((state['regs']['status'], state['regs']['reason']), (spec.Outcome.RESOURCE, spec.Reason.HEAP))
            self.assertEqual(circuit.step(state), state)


if __name__ == '__main__': unittest.main()
