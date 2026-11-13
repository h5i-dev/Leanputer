"""Structured syntax names: content equality/prefix, not pointer/type answers."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program, traversal_machine as spec
from leanputer.kernel.native_cells import CellTag, VectorKind
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class NamePathTest(unittest.TestCase):
    def test_general_prefix_equality_roles_and_distinct_equal_dags(self):
        paths = [[], [{'str': 'A'}], [{'str': 'A'}, {'num': 7}], [{'str': 'A'}, {'str': '7'}],
            [{'str': 'A'}, {'num': 7}, {'str': 'λ'}], [{'str': ''}, {'num': 0}]]
        roots = [['const', path, []] for path in paths]; body = roots[0]
        for root in roots[1:]: body = ['app', body, root]
        doc = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
            target=dict(kind='definition', name=[{'str': '_syntax_names'}], level_params=[], type=['sort', ['zero']], value=body))
        cfg = spec.MachineConfig(heap=256, stack=8, context=4, constants=2, fuel=256, word_bits=9)
        source, args, decls = program.parse_document(doc); state = program.prepare(cfg, source, args, decls)
        packed = SimpleNamespace(heap=state['heap'])
        table = {state['heap'][entry][1]: state['heap'][entry][2] for entry in vector(packed, state['regs']['symbols_root'], VectorKind.REFERENCES)}
        refs = [table[source.symbols.intern(path)] for path in paths]
        def cell(tag, a=0, b=0, c=0):
            ref = state['regs']['free']; self.assertLess(ref, cfg.heap)
            state['heap'][ref] = list(map(int, (tag, a, b, c))); state['regs']['free'] = ref+1; return ref
        def vec(values, role):
            values = tuple(values); head = 0
            for value in reversed(values): head = cell(CellTag.VECTOR_CELL, value, head)
            return cell(CellTag.VECTOR, len(values), head, role)
        # Generated paths may duplicate canonical syntax content at different
        # addresses. Compare payload content and string-vs-numeral tags.
        parts = []
        for component in vector(packed, refs[4], VectorKind.REFERENCES):
            tag, payload, _, _ = state['heap'][component]
            role = VectorKind.BYTES if tag == CellTag.NAME_STRING else VectorKind.LIMBS
            parts.append(cell(tag, vec(vector(packed, payload, role), role)))
        clone = vec(parts, VectorKind.REFERENCES)
        circuit = CircuitHarness(cfg)
        pairs = [(i, j) for i, j in ((0, 0), (0, 1), (1, 1), (1, 2), (2, 1), (2, 2), (2, 3), (2, 4), (4, 2), (5, 5), (3, 2))]
        trials = [(refs[i], refs[j], prefix, int(paths[i] == paths[j] if not prefix else paths[j][:len(paths[i])] == paths[i]))
            for i, j in pairs for prefix in (0, 1)]
        trials.append((refs[4], clone, 0, 1))
        for left, right, prefix, wanted in trials:
            with self.subTest(left=left, right=right, prefix=prefix):
                trial = deepcopy(state); trial['regs'].update(task=int(spec.Task.COMPARE_NAME_PATH), mode=int(spec.Mode.WALK),
                    x=left, peer=right, path_prefix=prefix)
                before = deepcopy(trial); machine = spec.SpecMachine(cfg, trial)
                for step in range(cfg.fuel+2):
                    actual = circuit.step(trial); self.assertEqual(actual, machine.step(), step); trial = actual
                    if trial['regs']['status']: break
                self.assertEqual((trial['regs']['status'], trial['regs']['r']), (spec.Outcome.DONE, wanted))
                for bank in ('heap', 'context', 'constants'): self.assertEqual(trial[bank], before[bank])
                for key in ('ctx', 'count', 'arg_base', 'env_head', 'symbols_root', 'free'):
                    self.assertEqual(trial['regs'][key], before['regs'][key], key)


if __name__ == '__main__': unittest.main()
