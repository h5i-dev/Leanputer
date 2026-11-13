"""Pure iota application ABI over genuinely generated private recursor records.

Arguments here are syntax operands, not claimed typed proofs or normalized-major
certificates. This tests the source RHS segment, not admission or full WHNF.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program, traversal_machine as spec
from leanputer.kernel.arena import Tag
from leanputer.kernel.native_cells import CellTag, VectorKind
from leanputer.kernel.operations import representation_equal, substitute_levels
from tests.test_kernel_minor_transition import cases
from tests.test_kernel_native_cells import vector, decode_syntax
from tests.test_kernel_traversal_machine import CircuitHarness


class RecursorApplyTest(unittest.TestCase):
    def test_generated_rules_specialization_source_slices_and_neutral_failures(self):
        cfg = spec.MachineConfig(heap=1024, stack=16, context=16, constants=2, fuel=8192, word_bits=11)
        circuit = CircuitHarness(cfg)
        def run(state, task, x, **updates):
            state['regs'].update(status=0, reason=0, fuel=cfg.fuel, sp=0, task=int(task), mode=int(spec.Mode.WALK), x=x, **updates)
            before = deepcopy(state); machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state); self.assertEqual(actual, machine.step(), step); state = actual
                if state['regs']['status']: break
            self.assertEqual(state['regs']['status'], spec.Outcome.DONE)
            self.assertEqual(state['context'], before['context'])
            for key in ('ctx', 'count', 'arg_base', 'env_head', 'typing_head', 'decl', 'raw_index'):
                self.assertEqual(state['regs'][key], before['regs'][key], key)
            self.assertEqual(circuit.step(state), state)
            return state
        for doc in cases():
            source, args, decls = program.parse_document(doc)
            machine = spec.SpecMachine(cfg, program.prepare(cfg, source, args, decls))
            for _ in range(cfg.fuel+2):
                state = machine.step(); r = state['regs']
                if r['mode'] == spec.Mode.RETURN and r['sp'] and state['stack'][r['sp']-1][0] == spec.CALL_SOURCE_ASSEMBLY: break
                self.assertFalse(r['status'], doc['name'])
            prefix = {'regs': {k: int(v) for k, v in r.items()}, **{bank: [[int(v) for v in row] for row in state[bank]] for bank in spec.BANK_FIELDS}}
            sigs = vector(SimpleNamespace(heap=prefix['heap']), r['core_rec_signatures'], VectorKind.REFERENCES)
            for sig in sigs:
                _, rec_symbol, _, scheme = prefix['heap'][sig]
                _, params, _, metadata = prefix['heap'][scheme]
                _, _, counts, rules = prefix['heap'][metadata]
                _, nparams, nindices, shared = prefix['heap'][counts]
                _, nmotives, nminors, _ = prefix['heap'][shared]
                major_index = nparams+nmotives+nminors+nindices
                rule_refs = vector(SimpleNamespace(heap=prefix['heap']), rules, VectorKind.REFERENCES)
                for rule in rule_refs or (None,):
                    for variant in ('ordinary', 'different-constructor-parameters', 'missing-major', 'wrong-level-arity', 'no-rule', 'insufficient-fields'):
                        with self.subTest(doc=doc['name'], rule=rule, variant=variant):
                            state = deepcopy(prefix)
                            def cell(tag, a=0, b=0, c=0):
                                ref = state['regs']['free']; self.assertLess(ref, cfg.heap)
                                state['heap'][ref] = list(map(int, (tag, a, b, c))); state['regs']['free'] = ref+1; return ref
                            def vec(values, role):
                                head = 0; values = tuple(values)
                                for value in reversed(values): head = cell(CellTag.VECTOR_CELL, value, head)
                                return cell(CellTag.VECTOR, len(values), head, role)
                            def app(fn, values):
                                for value in values: fn = cell(Tag.APP, fn, value)
                                return fn
                            ctor, fields, rhs = (prefix['heap'][rule][1:] if rule is not None else (97, 0, 0))
                            formal = vector(SimpleNamespace(heap=state['heap']), params, VectorKind.SYMBOLS)
                            zero = cell(CellTag.LEVEL_ZERO); succ = cell(CellTag.LEVEL_SUCC, zero)
                            levels = tuple((zero, succ)[i % 2] for i in range(len(formal)))
                            if variant == 'wrong-level-arity': levels += (zero,)
                            rec_const = cell(Tag.CONST, rec_symbol, vec(levels, VectorKind.LEVELS))
                            major_const = cell(Tag.CONST, 101 if variant == 'no-rule' else ctor, vec((), VectorKind.LEVELS))
                            field_count = fields-1 if variant == 'insufficient-fields' and fields else fields
                            # This deliberately tests the pure segment with a
                            # constructor-prefix count different from recursor
                            # parameters. It does not claim nested admission.
                            constructor_prefix = nparams+2 if variant == 'different-constructor-parameters' else 0
                            if variant == 'insufficient-fields': constructor_prefix = 0
                            major_args = tuple(cell(Tag.BVAR, 100+i) for i in range(constructor_prefix+field_count))
                            major = app(major_const, major_args)
                            rec_args = tuple(cell(Tag.BVAR, 200+i) for i in range(major_index))+(major, cell(Tag.BVAR, 231), cell(Tag.BVAR, 233))
                            if variant == 'missing-major': rec_args = rec_args[:major_index]
                            rec_expr = app(rec_const, rec_args)
                            state = run(state, spec.Task.APPLICATION_SPINE, rec_expr); rec_spine = state['regs']['r']
                            state = run(state, spec.Task.APPLICATION_SPINE, major); major_spine = state['regs']['r']
                            state = run(state, spec.Task.APPLY_RECURSOR_RULE, sig, reduction_rec_spine=rec_spine, reduction_major_spine=major_spine)
                            neutral = rule is None or variant in ('missing-major', 'wrong-level-arity', 'no-rule') or (variant == 'insufficient-fields' and fields > 0)
                            if neutral: self.assertEqual(state['regs']['r'], 0); continue
                            packed = SimpleNamespace(heap=state['heap'][:state['regs']['free']]); decoded_levels, expressions = decode_syntax(packed, source.arena)
                            expected = substitute_levels(source.arena, expressions[rhs], dict(zip(formal, (decoded_levels[v] for v in levels))))
                            selected = rec_args[:nparams+nmotives+nminors]+major_args[len(major_args)-fields:]+rec_args[major_index+1:]
                            expected = source.arena.app(expected, tuple(expressions[v] for v in selected))
                            self.assertTrue(representation_equal(source.arena, expressions[state['regs']['r']], expected))


if __name__ == '__main__': unittest.main()
