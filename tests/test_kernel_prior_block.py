"""Original-block data lookup ABI; this fixture is NOT a committed-source block."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program, traversal_machine as spec
from leanputer.kernel.arena import Arena, KernelError
from leanputer.kernel.native_cells import CellTag, VectorKind
from tests.test_kernel_constructor_transition import native_cases
from tests.test_kernel_header_transition import cases as header_cases
from tests.test_kernel_constructor_transition import core
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class PriorBlockLookupTest(unittest.TestCase):
    def test_generic_family_ownership_only_and_no_raw_admission_entry(self):
        cfg = spec.MachineConfig(heap=512, stack=16, context=8, constants=2, fuel=4096, word_bits=10)
        circuit = CircuitHarness(cfg)
        for doc in (native_cases()[0], core('mutual-registry-abi', header_cases()[2]['declarations'][0])):
            source, index, decls = program.parse_document(doc)
            machine = spec.SpecMachine(cfg, program.prepare(cfg, source, index, decls))
            for _ in range(cfg.fuel+2):
                state = machine.step(); r = state['regs']
                if r['mode'] == spec.Mode.RETURN and r['sp'] and state['stack'][r['sp']-1][0] == spec.CALL_SOURCE_ASSEMBLY: break
                self.assertFalse(r['status'])
            state = {'regs': {key: int(value) for key, value in r.items()},
                **{bank: [[int(value) for value in row] for row in state[bank]] for bank in spec.BANK_FIELDS}}
            def cell(tag, a=0, b=0, c=0):
                ref = state['regs']['free']; self.assertLess(ref, cfg.heap)
                state['heap'][ref] = list(map(int, (tag, a, b, c))); state['regs']['free'] = ref+1; return ref
            # Data-lookup fixture from model-generated family signatures. CORE
            # has NOT admitted an original block, so this is never published in
            # Γ/a registry and cannot stand in for the missing source transaction.
            origin = cell(CellTag.BLOCK_ORIGIN, r['header_block'], state['constants'][index][2], r['core_family_vector'])
            one = cell(CellTag.VECTOR_CELL, origin)
            repeated = cell(CellTag.VECTOR_CELL, origin, one)  # pure traversal stress, not duplicate admission
            sigs = vector(SimpleNamespace(heap=state['heap']), r['core_family_vector'], VectorKind.REFERENCES)
            queries = [(state['heap'][sig][1], origin) for sig in sigs]
            queries += [(decls[-1].families[0].recursor_symbol, 0), ((1 << cfg.word_bits)-1, 0)]
            for head in (0, one, repeated):
                for query, wanted in queries:
                    trial = deepcopy(state); trial['regs'].update(status=0, reason=0, fuel=cfg.fuel, sp=0,
                        mode=int(spec.Mode.WALK), task=int(spec.Task.PRIOR_BLOCK_LOOKUP), x=head, query_symbol=query)
                    before = deepcopy(trial); machine = spec.SpecMachine(cfg, trial)
                    for step in range(cfg.fuel+2):
                        actual = circuit.step(trial); self.assertEqual(actual, machine.step(), (doc['name'], head, query, step)); trial = actual
                        if trial['regs']['status']: break
                    self.assertEqual((trial['regs']['status'], trial['regs']['r']), (spec.Outcome.DONE, wanted if head else 0))
                    self.assertEqual(trial['context'], before['context'])
                    self.assertEqual(trial['heap'], before['heap'])
                    for key in ('ctx', 'count', 'arg_base', 'env_head', 'typing_head', 'decl', 'raw_index', 'free'):
                        self.assertEqual(trial['regs'][key], before['regs'][key], key)
        a = Arena(); root = a.const(31)
        with self.assertRaises(KernelError):
            spec.parse_document(spec.document(a, root, spec.Task.PRIOR_BLOCK_LOOKUP))


if __name__ == '__main__': unittest.main()
