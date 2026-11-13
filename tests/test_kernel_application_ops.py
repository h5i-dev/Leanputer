"""General syntax spines/slices needed by iota, K, structure and projection rules."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel.arena import Arena, Tag
from leanputer.kernel import traversal_machine as spec
from leanputer.kernel.native_cells import CellTag, VectorKind
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class ApplicationOpsTest(unittest.TestCase):
    def test_order_arbitrary_lengths_slices_boundaries_and_immutable_scope(self):
        cfg = spec.MachineConfig(heap=128, stack=4, context=4, constants=2, fuel=256, word_bits=8)
        circuit = CircuitHarness(cfg)
        def run(state):
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), step)
                state = actual
                if state['regs']['status']: break
            self.assertEqual(state['context'], [[11], [13], [17], [19]])
            self.assertEqual((state['regs']['ctx'], state['regs']['count']), (4, 4))
            self.assertEqual(circuit.step(state), state)
            return state
        for count in (0, 1, 2, 7):
            a = Arena(); fn = a.const(37)
            arguments = tuple(a.mk(Tag.BVAR, i) for i in range(count))
            expression = a.app(fn, arguments)
            request, _, _ = spec.parse_document(spec.document(a, expression, spec.Task.LIFT))
            state = spec.prepare(cfg, request); state['context'] = [[11], [13], [17], [19]]
            state['regs'].update(ctx=4, count=4, task=int(spec.Task.APPLICATION_SPINE))
            state = run(state); r = state['regs']
            self.assertEqual(r['status'], spec.Outcome.DONE)
            tag, head, argvec, reserved = state['heap'][r['r']]
            self.assertEqual((tag, head, reserved), (CellTag.APPLICATION_SPINE, fn, 0))
            self.assertEqual(vector(SimpleNamespace(heap=state['heap']), argvec, VectorKind.REFERENCES), arguments)
            for index in {0, max(0, count-1), count, 255}:
                selected = deepcopy(state)
                selected['regs'].update(status=0, reason=0, fuel=cfg.fuel, mode=int(spec.Mode.WALK),
                    task=int(spec.Task.VECTOR_REFERENCE), x=argvec, vector_index=index)
                selected = run(selected)
                self.assertEqual(selected['regs']['r'], arguments[index] if index < count else 0)
            slices = {(0, 0), (0, count), (count, 0), (count+1, 0), (0, count+1), (255, 2)}
            if count: slices |= {(count-1, 1), (1, count-1)}
            for start, take in sorted(slices):
                with self.subTest(count=count, start=start, take=take):
                    trial = deepcopy(state)
                    trial['regs'].update(status=0, reason=0, fuel=cfg.fuel, mode=int(spec.Mode.WALK),
                        task=int(spec.Task.APPLY_VECTOR_SLICE), x=argvec, slice_body=fn, slice_start=start, slice_take=take)
                    trial = run(trial); r = trial['regs']
                    if start > count or take > count-start:
                        self.assertEqual((r['status'], r['reason']), (spec.Outcome.INVALID, spec.Reason.SYNTAX)); continue
                    self.assertEqual(r['status'], spec.Outcome.DONE)
                    result, actual = r['r'], []
                    while trial['heap'][result][0] == Tag.APP:
                        _, result, argument, _ = trial['heap'][result]; actual.append(argument)
                    self.assertEqual((result, tuple(reversed(actual))), (fn, arguments[start:start+take]))

    def test_metadata_is_a_head_boundary_and_storage_exhaustion_is_not_reduction(self):
        cfg = spec.MachineConfig(heap=32, stack=2, context=2, constants=2, fuel=64, word_bits=8)
        circuit = CircuitHarness(cfg); a = Arena(); wrapped = a.mk(Tag.MDATA, a.app(a.const(31), (a.mk(Tag.BVAR, 0),)), 17)
        request, _, _ = spec.parse_document(spec.document(a, wrapped, spec.Task.LIFT))
        state = spec.prepare(cfg, request); state['regs'].update(task=int(spec.Task.APPLICATION_SPINE), free=cfg.heap-1)
        machine = spec.SpecMachine(cfg, state)
        for step in range(cfg.fuel+2):
            actual = circuit.step(state); self.assertEqual(actual, machine.step(), step); state = actual
            if state['regs']['status']: break
        self.assertEqual((state['regs']['status'], state['regs']['reason']), (spec.Outcome.RESOURCE, spec.Reason.HEAP))
        self.assertEqual(state['regs']['spine_function'], wrapped)
        self.assertEqual(state['regs']['spine_count'], 0)


if __name__ == '__main__': unittest.main()
