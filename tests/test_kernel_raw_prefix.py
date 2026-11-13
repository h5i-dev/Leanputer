"""Raw prefix syntax operation: dependency, binder info and strict no-WHNF policy."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program, traversal_machine as spec
from leanputer.kernel.arena import Tag
from leanputer.kernel.operations import instantiate, representation_equal
from tests.test_kernel_native_cells import decode_syntax
from tests.test_kernel_traversal_machine import CircuitHarness


class RawPrefixTest(unittest.TestCase):
    def test_exact_dependent_prefixes_preserve_info_and_do_not_normalize(self):
        prop = ['sort', ['zero']]
        pi = ['pi', 1, prop, ['pi', 3, ['var', 0], ['var', 1]]]
        lam = ['lam', 1, prop, ['lam', 3, ['var', 0], ['var', 0]]]
        metadata = ['mdata', pi]
        let = ['let', ['sort', ['succ', ['zero']]], prop, pi]
        cases = [(pi, 0, Tag.PI, spec.Outcome.DONE), (pi, 1, Tag.PI, spec.Outcome.DONE),
            (pi, 2, Tag.PI, spec.Outcome.DONE), (lam, 2, Tag.LAM, spec.Outcome.DONE),
            (pi, 3, Tag.PI, spec.Outcome.INVALID), (metadata, 1, Tag.PI, spec.Outcome.INVALID),
            (let, 1, Tag.PI, spec.Outcome.INVALID), (metadata, 0, Tag.PI, spec.Outcome.DONE),
            (pi, 5, Tag.PI, spec.Outcome.RESOURCE)]
        cfg = spec.MachineConfig(heap=128, stack=8, context=4, constants=2, fuel=256, word_bits=8)
        circuit = CircuitHarness(cfg)
        for root, count, tag, outcome in cases:
            with self.subTest(root=root[0], count=count, binder=tag):
                doc = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
                    target=dict(kind='definition', name=[{'str': '_raw_prefix'}], level_params=[], type=root, value=None))
                source, args, decls = program.parse_document(doc); state = program.prepare(cfg, source, args, decls)
                native_root = state['constants'][0][3]; initial = deepcopy(state)
                state['regs'].update(task=int(spec.Task.OPEN_RAW_PREFIX), x=native_root, raw_prefix_count=count, open_tag=int(tag))
                machine = spec.SpecMachine(cfg, state)
                for step in range(cfg.fuel+2):
                    actual = circuit.step(state); self.assertEqual(actual, machine.step(), step); state = actual
                    if state['regs']['status']: break
                self.assertEqual(state['regs']['status'], outcome)
                for key in ('count', 'arg_base', 'env_head', 'typing_head', 'decl', 'raw_index', 'symbols_root'):
                    self.assertEqual(state['regs'][key], initial['regs'][key], key)
                self.assertEqual(circuit.step(state), state)
                if outcome != spec.Outcome.DONE: continue
                self.assertEqual(state['regs']['ctx'], count)
                _, expressions = decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]), source.arena)
                current = source.target.type; identities = []
                for index in range(count):
                    row = source.arena.expr(current); record = state['context'][index][0]
                    _, local, domain, info = state['heap'][record]
                    self.assertEqual(info, row.c)
                    self.assertTrue(representation_equal(source.arena, expressions[domain], row.a))
                    self.assertEqual(state['heap'][local][1], local)
                    self.assertGreaterEqual(local, initial['regs']['free']); identities.append(local)
                    current = instantiate(source.arena, row.b, (expressions[local],))
                self.assertEqual(len(set(identities)), count)
                self.assertTrue(representation_equal(source.arena, expressions[state['regs']['r']], current))
                if not count: self.assertEqual(state['regs']['r'], native_root)


if __name__ == '__main__': unittest.main()
