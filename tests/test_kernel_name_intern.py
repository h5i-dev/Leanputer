"""Weighted symbol interning is syntax data, never declaration admission."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program, traversal_machine as spec
from leanputer.kernel.native_cells import CellTag, VectorKind
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class NameInternTest(unittest.TestCase):
    def test_content_interning_table_visibility_and_atomic_resource_failures(self):
        old = [{'str': 'root'}, {'num': 7}]
        doc = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
            target=dict(kind='definition', name=[{'str': '_names'}], level_params=[],
                type=['sort', ['zero']], value=['const', old, []]))
        cfg = spec.MachineConfig(heap=256, stack=8, context=4, constants=2, fuel=512, word_bits=9)
        source, args, decls = program.parse_document(doc); state = program.prepare(cfg, source, args, decls)
        def cell(tag, a=0, b=0, c=0):
            ref = state['regs']['free']; self.assertLess(ref, cfg.heap)
            state['heap'][ref] = list(map(int, (tag, a, b, c))); state['regs']['free'] = ref+1; return ref
        def vec(values, role):
            values = tuple(values); head = 0
            for value in reversed(values): head = cell(CellTag.VECTOR_CELL, value, head)
            return cell(CellTag.VECTOR, len(values), head, role)
        def path(parts):
            components = []
            for part in parts:
                if 'str' in part:
                    components.append(cell(CellTag.NAME_STRING, vec(part['str'].encode(), VectorKind.BYTES)))
                else:
                    value = part['num']; limbs = []
                    while value: value, limb = divmod(value, 65536); limbs.append(limb)
                    components.append(cell(CellTag.NAME_NUMERAL, vec(limbs, VectorKind.LIMBS)))
            return vec(components, VectorKind.REFERENCES)
        duplicate_old = path(old)
        new = path([{'str': 'root'}, {'str': '7'}])
        duplicate_new = path([{'str': 'root'}, {'str': '7'}])
        other = path([{'str': 'other'}, {'num': 0}, {'str': 'λ'}])
        circuit = CircuitHarness(cfg)
        def run(initial, task, x, expected=spec.Outcome.DONE, **updates):
            trial = deepcopy(initial); trial['regs'].update(task=int(task), mode=int(spec.Mode.WALK), x=x,
                status=0, reason=0, fuel=cfg.fuel, sp=0, **updates)
            before = deepcopy(trial); machine = spec.SpecMachine(cfg, trial)
            for step in range(cfg.fuel+2):
                actual = circuit.step(trial); self.assertEqual(actual, machine.step(), step); trial = actual
                if trial['regs']['status']: break
            self.assertEqual(trial['regs']['status'], expected)
            self.assertEqual(trial['context'], before['context'])
            for key in ('ctx', 'count', 'arg_base', 'env_head', 'typing_head', 'decl', 'raw_index'):
                self.assertEqual(trial['regs'][key], before['regs'][key], key)
            return trial
        initial = deepcopy(state); initial_root = state['regs']['symbols_root']; initial_free = state['regs']['free']
        existing = run(state, spec.Task.INTERN_NAME_PATH, duplicate_old)
        self.assertEqual((existing['regs']['r'], existing['regs']['symbols_root'], existing['regs']['free']),
            (source.symbols.intern(old), initial_root, initial_free))
        state = run(state, spec.Task.INTERN_NAME_PATH, new); fresh = state['regs']['r']
        self.assertEqual(fresh, len(source.symbols.names))
        self.assertEqual(state['regs']['free'], initial_free+3)
        updated_root, updated_free = state['regs']['symbols_root'], state['regs']['free']
        found = run(state, spec.Task.GET_NAME_PATH, updated_root, query_symbol=fresh)
        self.assertEqual(found['regs']['r'], new)
        repeated = run(state, spec.Task.INTERN_NAME_PATH, duplicate_new)
        self.assertEqual((repeated['regs']['r'], repeated['regs']['symbols_root'], repeated['regs']['free']), (fresh, updated_root, updated_free))
        self.assertEqual(repeated['heap'], state['heap'])
        limited = deepcopy(state); limited['regs']['free'] = cfg.heap-2
        limited = run(limited, spec.Task.INTERN_NAME_PATH, other, spec.Outcome.RESOURCE)
        self.assertEqual((limited['regs']['reason'], limited['regs']['symbols_root'], limited['regs']['free']),
            (spec.Reason.HEAP, updated_root, cfg.heap-2))
        # A sparse maximum input symbol is legal; allocation must not wrap.
        entry = cell(CellTag.SYMBOL_ENTRY, (1 << cfg.word_bits)-1, duplicate_old)
        maximum = vec((entry,), VectorKind.REFERENCES)
        limited = deepcopy(state); limited['regs']['symbols_root'] = maximum
        limited = run(limited, spec.Task.INTERN_NAME_PATH, other, spec.Outcome.RESOURCE)
        self.assertEqual((limited['regs']['reason'], limited['regs']['symbols_root']), (spec.Reason.INDEX, maximum))
        self.assertEqual(limited['heap'], state['heap'])


if __name__ == '__main__': unittest.main()
