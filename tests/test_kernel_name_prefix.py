"""General source Name.replacePrefix, including anonymous and numeral paths."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program, traversal_machine as spec
from leanputer.kernel.native_cells import CellTag, VectorKind
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class NamePrefixTest(unittest.TestCase):
    def test_generic_source_composition_and_new_symbol_visibility(self):
        a = [{'str': 'A'}, {'num': 7}]; original = a+[{'str': 'ctor'}]; new = [{'str': 'B'}]
        cases = [(original, a, new), (original, a, []), (original, [], new), (a, a, new),
            (original, [{'str': 'A'}, {'str': '7'}], new), ([{'str': 'A.7'}, {'str': 'ctor'}], a, new), ([], [], new)]
        parts = [path for triple in cases for path in triple]
        body = ['const', parts[0], []]
        for path in parts[1:]: body = ['app', body, ['const', path, []]]
        doc = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
            target=dict(kind='definition', name=[{'str': '_prefix_probe'}], level_params=[], type=['sort', ['zero']], value=body))
        cfg = spec.MachineConfig(heap=256, stack=8, context=4, constants=2, fuel=1024, word_bits=9)
        source, args, decls = program.parse_document(doc); base = program.prepare(cfg, source, args, decls); circuit = CircuitHarness(cfg)
        def run(initial, task, **updates):
            trial = deepcopy(initial); trial['regs'].update(task=int(task), mode=int(spec.Mode.WALK),
                status=0, reason=0, fuel=cfg.fuel, sp=0, **updates)
            machine = spec.SpecMachine(cfg, trial)
            for step in range(cfg.fuel+2):
                actual = circuit.step(trial); self.assertEqual(actual, machine.step(), (task, step)); trial = actual
                if trial['regs']['status']: break
            self.assertEqual(trial['regs']['status'], spec.Outcome.DONE)
            for bank in ('context', 'constants'): self.assertEqual(trial[bank], initial[bank])
            for key in ('ctx', 'count', 'arg_base', 'env_head', 'typing_head', 'decl', 'raw_index'):
                self.assertEqual(trial['regs'][key], initial['regs'][key], key)
            return trial
        for original, old, new in cases:
            with self.subTest(original=original, old=old, new=new):
                symbol, old_symbol, new_symbol = [source.symbols.intern(path) for path in (original, old, new)]
                state = run(base, spec.Task.REPLACE_NAME_PREFIX, query_symbol=symbol,
                    name_parent_symbol=old_symbol, name_candidate_symbol=new_symbol)
                result = state['regs']['r']; matched = original[:len(old)] == old
                if not matched:
                    self.assertEqual((result, state['regs']['symbols_root'], state['regs']['free']),
                        (symbol, base['regs']['symbols_root'], base['regs']['free']))
                state = run(state, spec.Task.GET_NAME_PATH, x=state['regs']['symbols_root'], query_symbol=result)
                packed = SimpleNamespace(heap=state['heap']); actual = []
                for component in vector(packed, state['regs']['r'], VectorKind.REFERENCES):
                    tag, payload, _, _ = state['heap'][component]
                    if tag == CellTag.NAME_STRING: actual.append({'str': bytes(vector(packed, payload, VectorKind.BYTES)).decode()})
                    else: actual.append({'num': sum(limb << (16*i) for i, limb in enumerate(vector(packed, payload, VectorKind.LIMBS)))})
                self.assertEqual(actual, new+original[len(old):] if matched else original)


if __name__ == '__main__': unittest.main()
