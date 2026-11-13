"""Pure immutable container operation shared by name/queue reconstruction."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel.arena import Arena, Tag
from leanputer.kernel import traversal_machine as spec
from leanputer.kernel.native_cells import CellTag, VectorKind
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class VectorSpliceTest(unittest.TestCase):
    def test_roles_all_slices_empty_prefix_bounds_and_suffix_sharing(self):
        cfg = spec.MachineConfig(heap=128, stack=4, context=2, constants=2, fuel=256, word_bits=8)
        a = Arena(); root = a.mk(Tag.BVAR, 0)
        request, _, _ = spec.parse_document(spec.document(a, root, spec.Task.LIFT))
        state = spec.prepare(cfg, request)
        def cell(tag, x=0, y=0, z=0):
            ref = state['regs']['free']; state['heap'][ref] = list(map(int, (tag, x, y, z))); state['regs']['free'] = ref+1; return ref
        def vec(values, role):
            head = 0
            for value in reversed(values): head = cell(CellTag.VECTOR_CELL, value, head)
            return cell(CellTag.VECTOR, len(values), head, role)
        data = []
        for role in VectorKind:
            left_values, right_values = (3, 5, 7), (11, 13, 17, 19)
            data.append((role, vec(left_values, role), vec((), role), vec(right_values, role), left_values, right_values))
        circuit = CircuitHarness(cfg)
        for role, left, empty, right, values, suffix in data:
            for prefix, prefix_values in ((left, values), (empty, ())):
                for skip in (0, 2, 4, 5):
                    with self.subTest(role=role, prefix=prefix_values, skip=skip):
                        trial = deepcopy(state); trial['regs'].update(task=int(spec.Task.VECTOR_SPLICE), mode=int(spec.Mode.WALK),
                            x=prefix, peer=right, splice_role=int(role), splice_skip=skip)
                        before = deepcopy(trial); machine = spec.SpecMachine(cfg, trial)
                        for step in range(cfg.fuel+2):
                            actual = circuit.step(trial); self.assertEqual(actual, machine.step(), step); trial = actual
                            if trial['regs']['status']: break
                        if skip > len(suffix):
                            self.assertEqual((trial['regs']['status'], trial['regs']['reason']), (spec.Outcome.INVALID, spec.Reason.SYNTAX)); continue
                        self.assertEqual(trial['regs']['status'], spec.Outcome.DONE)
                        self.assertEqual(vector(SimpleNamespace(heap=trial['heap']), trial['regs']['r'], role), prefix_values+suffix[skip:])
                        self.assertEqual(trial['heap'][:before['regs']['free']], before['heap'][:before['regs']['free']])
                        self.assertEqual(trial['context'], before['context'])
                        for key in ('ctx', 'count', 'arg_base', 'env_head', 'symbols_root'):
                            self.assertEqual(trial['regs'][key], before['regs'][key], key)


if __name__ == '__main__': unittest.main()
