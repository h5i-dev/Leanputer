"""Source K/structure algorithms over generated metadata and checked local types.

Private ABI unit validation, not original-source admission or full recursor WHNF.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program, traversal_machine as spec
from leanputer.kernel.arena import Arena, Tag
from leanputer.kernel.major_rules import Phase
from leanputer.kernel.native_cells import CellTag, VectorKind
from leanputer.kernel.operations import representation_equal
from tests.test_kernel_constructor_transition import native_cases, core
from tests.test_kernel_source_transition import name
from tests.test_kernel_native_cells import vector, decode_syntax
from tests.test_kernel_traversal_machine import CircuitHarness


def structure(label, domains, proposition=False):
    family = ['const', name(label), []]; ctor_type = family
    for domain in reversed(domains): ctor_type = ['pi', 0, domain, ctor_type]
    return core(label, dict(kind='inductive_block', level_params=[], parameters=0, recursor_claims=[], families=[dict(
        name=name(label), recursor_name=name(label)+[{'str': 'rec'}],
        type=['sort', ['zero'] if proposition else ['succ', ['zero']]],
        constructors=[dict(name=name(label)+[{'str': 'mk'}], type=ctor_type)])]))


class MajorTransitionTest(unittest.TestCase):
    def test_eight_bit_task_owned_continuations_do_not_capture_generic_frames(self):
        cfg = spec.MachineConfig(heap=32, stack=4, context=2, constants=2, fuel=32, word_bits=8)
        circuit = CircuitHarness(cfg); a = Arena(); root = a.const(31)
        request, _, _ = spec.parse_document(spec.document(a, root, spec.Task.LIFT))
        for owner in (spec.Task.LIFT, spec.Task.PREPARE_RECURSOR_MAJOR):
            state = spec.prepare(cfg, request)
            state['regs'].update(mode=int(spec.Mode.RETURN), sp=1, r=root)
            state['stack'][0] = list(map(int, (Phase.WHNF, root, root, owner, 0, 0)))
            actual = circuit.step(state); machine = spec.SpecMachine(cfg, state)
            self.assertEqual(actual, machine.step())
            if owner == spec.Task.LIFT: self.assertEqual(actual['regs']['mode'], spec.Mode.RESUME)
            else: self.assertEqual((actual['regs']['mode'], actual['regs']['task']), (spec.Mode.MAJOR_VALUE, owner))

    def test_checked_k_eta_prop_exclusion_recursive_neutral_and_saved_call_state(self):
        cfg = spec.MachineConfig(heap=1024, stack=32, context=16, constants=2, fuel=8192, word_bits=11)
        circuit = CircuitHarness(cfg)
        poison_phases = {Phase.K_INFER, Phase.K_TYPE_WHNF, Phase.K_CANDIDATE_INFER, Phase.K_CONVERT,
            Phase.WHNF, Phase.ETA_INFER, Phase.ETA_TYPE_WHNF, Phase.ETA_SORT_INFER, Phase.ETA_SORT_WHNF}
        def run(state, task, x, poison=False, expected=spec.Outcome.DONE, **updates):
            state = deepcopy(state); state['regs'].update(status=0, reason=0, fuel=cfg.fuel, sp=0,
                task=int(task), mode=int(spec.Mode.WALK), x=x, **updates)
            before = deepcopy(state)
            for step in range(cfg.fuel+2):
                r = state['regs']
                if poison and r['mode'] == spec.Mode.RETURN and r['sp']:
                    frame = state['stack'][r['sp']-1]
                    if frame[3] == spec.Task.PREPARE_RECURSOR_MAJOR and frame[0] in poison_phases:
                        # A recursive child can overwrite every scratch register
                        # of this module. Only continuation fields may survive.
                        for key in spec.REGISTERS:
                            if key.startswith('major_'): r[key] = 0
                machine = spec.SpecMachine(cfg, state)
                actual = circuit.step(state); self.assertEqual(actual, machine.step(), (task, step, r['mode']))
                state = actual
                if state['regs']['status']: break
            self.assertEqual(state['regs']['status'], expected, (task, state['regs']['reason']))
            if task != spec.Task.FRESH_LOCAL: self.assertEqual(state['context'], before['context'])
            for key in ('ctx', 'count', 'arg_base', 'local_base', 'env_head', 'typing_head', 'decl', 'raw_index'):
                if task != spec.Task.FRESH_LOCAL: self.assertEqual(state['regs'][key], before['regs'][key], key)
            return state
        prop = ['sort', ['zero']]
        documents = [native_cases()[0], structure('Data0', []), structure('Data3', [prop, ['var', 0], prop]),
            structure('ProofField', [prop], proposition=True), native_cases()[1]]
        for doc in documents:
            source, args, decls = program.parse_document(doc)
            machine = spec.SpecMachine(cfg, program.prepare(cfg, source, args, decls))
            for _ in range(cfg.fuel+2):
                state = machine.step(); r = state['regs']
                if r['mode'] == spec.Mode.RETURN and r['sp'] and state['stack'][r['sp']-1][0] == spec.CALL_SOURCE_ASSEMBLY: break
                self.assertFalse(r['status'], doc['name'])
            state = {'regs': {key: int(value) for key, value in r.items()},
                **{bank: [[int(value) for value in row] for row in state[bank]] for bank in spec.BANK_FIELDS}}
            def cell(tag, a=0, b=0, c=0):
                ref = state['regs']['free']; self.assertLess(ref, cfg.heap)
                state['heap'][ref] = list(map(int, (tag, a, b, c))); state['regs']['free'] = ref+1; return ref
            sig = vector(SimpleNamespace(heap=state['heap']), r['core_rec_signatures'], VectorKind.REFERENCES)[0]
            scheme = state['heap'][sig][3]; metadata = state['heap'][scheme][3]
            _, owner, counts, rules = state['heap'][metadata]
            rule = vector(SimpleNamespace(heap=state['heap']), rules, VectorKind.REFERENCES)[0]
            _, ctor_symbol, nfields, _ = state['heap'][rule]
            constructor = cell(Tag.CONST, ctor_symbol, r['header_levels'])
            if doc['name'] == 'original-Eq-core-block':
                state = run(state, spec.Task.APPLY_SCOPE, constructor,
                    apply_base=r['header_parameter_base'], apply_end=r['header_parameter_end'])
                constructor = state['regs']['r']
                state = run(state, spec.Task.INFER, constructor); type_ref = state['regs']['r']
            else:
                type_ref = cell(Tag.CONST, state['heap'][owner][1], r['header_levels'])
            # A fresh typed neutral major exercises K or eta; the type comes
            # from checked construction/lookup, not an inferred-answer input.
            state = run(state, spec.Task.FRESH_LOCAL, type_ref, binder_info=0)
            neutral = state['regs']['r']
            for poison in (False, True):
                with self.subTest(doc=doc['name'], poison=poison):
                    actual = run(state, spec.Task.PREPARE_RECURSOR_MAJOR, metadata, major_value=neutral, poison=poison)
                    packed = SimpleNamespace(heap=actual['heap'][:actual['regs']['free']]); _, expressions = decode_syntax(packed, source.arena)
                    if doc['name'] == 'original-Eq-core-block': expected = expressions[constructor]
                    elif doc['name'] in ('Data0', 'Data3'):
                        projections = tuple(source.arena.mk(Tag.PROJ, actual['heap'][owner][1], i, expressions[neutral]) for i in range(nfields))
                        expected = source.arena.app(expressions[constructor], projections)
                    else: expected = expressions[neutral]
                    self.assertTrue(representation_equal(source.arena, expressions[actual['regs']['r']], expected))


if __name__ == '__main__': unittest.main()
