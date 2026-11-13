"""Current/all-queued family occurrence is syntax data, not checked type data."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program, traversal_machine as spec
from leanputer.kernel.arena import Tag
from leanputer.kernel.native_cells import CellCapacities, VectorKind, pack_source
from leanputer.kernel.operations import has_constant
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness


class RawFamilyOccurrenceTest(unittest.TestCase):
    def test_current_family_vector_and_live_scope_are_separate(self):
        name = lambda s: [{'str': s}]; prop = ['sort', ['zero']]
        f, g, other = [['const', name(s), []] for s in ('F', 'G', 'Other')]
        roots = [f, g, other, ['lam', 0, prop, f], ['lam', 0, prop, ['var', 0]],
            ['let', prop, f, other], ['mdata', f], ['lam', 0, g, ['var', 0]]]
        body = roots[0]
        for root in roots[1:]: body = ['app', body, root]
        block = dict(kind='inductive_block', level_params=[], parameters=0, recursor_claims=[],
            families=[dict(name=name(s), recursor_name=name(s)+[{'str': 'rec'}], type=prop, constructors=[]) for s in ('F', 'G')])
        doc = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[block],
            target=dict(kind='definition', name=name('_raw_occurrence'), level_params=[], type=prop, value=body))
        cfg = spec.MachineConfig(heap=128, stack=8, context=4, constants=2, fuel=256, word_bits=8)
        source, args, decls = program.parse_document(doc); a = source.arena
        fs, gs = [source.symbols.intern(name(s)) for s in ('F', 'G')]; fe, ge, oe = [a.const(source.symbols.intern(name(s))) for s in ('F', 'G', 'Other')]
        ty = a.mk(Tag.SORT, a.zero)
        expressions = [fe, ge, oe, a.mk(Tag.LAM, ty, fe), a.mk(Tag.LAM, ty, a.mk(Tag.BVAR, 0)),
            a.mk(Tag.LET, ty, fe, oe), a.mk(Tag.MDATA, fe), a.mk(Tag.LAM, ge, a.mk(Tag.BVAR, 0))]
        packed = pack_source(source, CellCapacities(heap=cfg.heap, constants=cfg.constants, word_bits=cfg.word_bits))
        base = program.prepare(cfg, source, args, decls); block_ref = base['constants'][0][5]; families = base['heap'][block_ref][2]
        first = vector(SimpleNamespace(heap=base['heap']), families, VectorKind.REFERENCES)[0]
        empty = base['heap'][base['heap'][first][3]][1]
        base['regs'].update(ctx=1, count=1); base['context'][0] = [77]
        circuit = CircuitHarness(cfg)
        for family_vector in (families, empty):
            for expression in expressions:
                trial = deepcopy(base); trial['regs'].update(task=int(spec.Task.HAS_RAW_FAMILIES), mode=int(spec.Mode.WALK),
                    x=packed.expression_map[expression], raw_family_vector=family_vector)
                machine = spec.SpecMachine(cfg, trial)
                for step in range(cfg.fuel+2):
                    actual = circuit.step(trial); self.assertEqual(actual, machine.step(), step); trial = actual
                    if trial['regs']['status']: break
                wanted = int(has_constant(a, expression, (fs, gs))) if family_vector == families else 0
                self.assertEqual((trial['regs']['status'], trial['regs']['r']), (spec.Outcome.DONE, wanted))
                self.assertEqual(trial['context'][:1], base['context'][:1])
                self.assertEqual(trial['heap'], base['heap'])
                for key in ('ctx', 'count', 'arg_base', 'env_head', 'typing_head', 'decl', 'raw_index'):
                    self.assertEqual(trial['regs'][key], base['regs'][key], key)


if __name__ == '__main__': unittest.main()
