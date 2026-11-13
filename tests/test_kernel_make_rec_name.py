"""Pinned rec/rec_index construction is independent of the family name shape."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program, traversal_machine as spec
from leanputer.kernel.native_cells import CellTag, VectorKind
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class MakeRecNameTest(unittest.TestCase):
    def test_arbitrary_numeric_macro_scoped_and_anonymous_parents(self):
        parents = [[{'str': 'A'}, {'num': 7}],
            [{'str': 'user'}, {'str': '_@'}, {'str': 'Ctx'}, {'str': '_hyg'}, {'num': 2}], []]
        body = ['const', parents[0], []]
        for path in parents[1:]: body = ['app', body, ['const', path, []]]
        doc = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
            target=dict(kind='definition', name=[{'str': '_rec_name_probe'}], level_params=[], type=['sort', ['zero']], value=body))
        cfg = spec.MachineConfig(heap=256, stack=16, context=4, constants=2, fuel=2048, word_bits=9)
        source, args, decls = program.parse_document(doc); base = program.prepare(cfg, source, args, decls); circuit = CircuitHarness(cfg)
        def run(initial, task, **updates):
            trial = deepcopy(initial); trial['regs'].update(task=int(task), mode=int(spec.Mode.WALK),
                status=0, reason=0, fuel=cfg.fuel, sp=0, **updates)
            machine = spec.SpecMachine(cfg, trial)
            for step in range(cfg.fuel+2):
                actual = circuit.step(trial); self.assertEqual(actual, machine.step(), (task, step)); trial = actual
                if trial['regs']['status']: break
            self.assertEqual(trial['regs']['status'], spec.Outcome.DONE, trial['regs']['reason'])
            for bank in ('context', 'constants'): self.assertEqual(trial[bank], initial[bank])
            for key in ('ctx', 'count', 'arg_base', 'env_head', 'typing_head', 'decl', 'raw_index'):
                self.assertEqual(trial['regs'][key], initial['regs'][key], key)
            return trial
        for parent in parents:
            for indexed, index in ((0, 511), (1, 10)):
                with self.subTest(parent=parent, indexed=indexed, index=index):
                    symbol = source.symbols.intern(parent)
                    state = run(base, spec.Task.MAKE_RECURSOR_NAME, query_symbol=symbol,
                        generated_rec_indexed=indexed, generated_rec_index=index)
                    generated = state['regs']['r']
                    state = run(state, spec.Task.GET_NAME_PATH, x=state['regs']['symbols_root'], query_symbol=generated)
                    packed = SimpleNamespace(heap=state['heap']); actual = []
                    for component in vector(packed, state['regs']['r'], VectorKind.REFERENCES):
                        tag, payload, _, _ = state['heap'][component]
                        if tag == CellTag.NAME_STRING: actual.append({'str': bytes(vector(packed, payload, VectorKind.BYTES)).decode()})
                        else: actual.append({'num': sum(limb << (16*i) for i, limb in enumerate(vector(packed, payload, VectorKind.LIMBS)))})
                    self.assertEqual(actual, parent+[{'str': 'rec_'+str(index) if indexed else 'rec'}])
                    if not indexed and parent:
                        state = run(state, spec.Task.CHECK_RECURSOR_NAME, name_parent_symbol=symbol, name_candidate_symbol=generated)
                        self.assertEqual(state['regs']['r'], 1)


if __name__ == '__main__': unittest.main()
