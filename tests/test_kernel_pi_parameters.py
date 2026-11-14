"""Raw parameter specialization agrees with independent source-level operations."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program, traversal_machine as spec
from leanputer.kernel.native_cells import CellTag, VectorKind
from leanputer.kernel.nested import instantiate_parameters
from leanputer.kernel.operations import representation_equal
from tests.test_kernel_native_cells import decode_syntax
from tests.test_kernel_traversal_machine import CircuitHarness


class PiParametersTest(unittest.TestCase):
    def test_dependent_bulk_substitution_and_strict_raw_prefix(self):
        prop = ['sort', ['zero']]
        root = ['pi', 1, prop, ['pi', 3, ['var', 0], ['pi', 2, ['var', 1], ['app', ['var', 2], ['var', 1]]]]]
        actuals = [prop, ['var', 0], ['lam', 0, prop, ['var', 1]]]
        cases = [(root, 0, 0, spec.Outcome.DONE), (root, 1, 1, spec.Outcome.DONE),
            (root, 2, 3, spec.Outcome.DONE), (root, 3, 3, spec.Outcome.DONE),
            (['mdata', root], 1, 1, spec.Outcome.INVALID), (root, 4, 3, spec.Outcome.INVALID),
            (root, 3, 3, spec.Outcome.RESOURCE)]
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=512, word_bits=8)
        circuit = CircuitHarness(cfg)
        for i, (expression, count, vector_count, outcome) in enumerate(cases):
            with self.subTest(i=i):
                value = actuals[0]
                for arg in actuals[1:]: value = ['app', value, arg]
                doc = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[], target=dict(
                    kind='definition', name=[{'str': '_pi_params'}], level_params=[], type=expression, value=value))
                from leanputer.kernel.syntax import SyntaxCodec
                codec = SyntaxCodec(); source = codec.document(doc); args, decls = None, source.declarations
                refs = [codec.expression(arg) for arg in actuals]
                from leanputer.kernel.native_cells import pack_source, CellCapacities
                packed = pack_source(source, CellCapacities(heap=cfg.heap, constants=cfg.constants, word_bits=cfg.word_bits))
                state = program.prepare(cfg, source, args, decls)
                def cell(tag, a=0, b=0, c=0):
                    ref = state['regs']['free']; state['heap'][ref] = [int(tag), a, b, int(c)]; state['regs']['free'] += 1; return ref
                head = 0
                for ref in reversed(refs[:vector_count]): head = cell(CellTag.VECTOR_CELL, packed.expression_map[ref], head)
                vec = cell(CellTag.VECTOR, vector_count, head, VectorKind.REFERENCES)
                # Live caller data must survive; the final case exhausts only the scratch window.
                ctx = 6 if i == len(cases)-1 else 1
                state['context'][0] = [73]
                state['regs'].update(task=int(spec.Task.INSTANTIATE_PI_PARAMETERS), x=state['constants'][0][3],
                    pi_parameter_vector=vec, pi_parameter_limit=count, ctx=ctx, count=1, arg_base=0)
                before = deepcopy(state); machine = spec.SpecMachine(cfg, state)
                for step in range(cfg.fuel+2):
                    actual = circuit.step(state); self.assertEqual(actual, machine.step(), step); state = actual
                    if state['regs']['status']: break
                self.assertEqual(state['regs']['status'], outcome)
                if outcome == spec.Outcome.DONE:
                    _, expressions = decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]), source.arena)
                    expected = instantiate_parameters(source.arena, source.target.type, refs[:count])
                    self.assertTrue(representation_equal(source.arena, expressions[state['regs']['r']], expected))
                    for key in ('ctx', 'count', 'arg_base', 'env_head', 'typing_head', 'decl', 'raw_index'):
                        self.assertEqual(state['regs'][key], before['regs'][key], key)
                    self.assertEqual(state['context'][:ctx], before['context'][:ctx])


if __name__ == '__main__': unittest.main()
