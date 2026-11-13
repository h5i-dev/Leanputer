"""Composed iota/K/eta/WHNF tests with generated metadata, not source admission."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program, traversal_machine as spec
from leanputer.kernel.arena import Tag
from leanputer.kernel.native_cells import CellTag, VectorKind
from leanputer.kernel.operations import representation_equal
from tests.test_kernel_major_transition import structure
from tests.test_kernel_native_cells import vector, decode_syntax
from tests.test_kernel_traversal_machine import CircuitHarness


class RecursorReduceTest(unittest.TestCase):
    def test_reentrant_major_reduction_neutral_partial_and_surplus_beta(self):
        cfg = spec.MachineConfig(heap=1024, stack=32, context=16, constants=2, fuel=8192, word_bits=11)
        circuit = CircuitHarness(cfg); doc = structure('Data0', [])
        source, args, decls = program.parse_document(doc)
        machine = spec.SpecMachine(cfg, program.prepare(cfg, source, args, decls))
        for _ in range(cfg.fuel+2):
            state = machine.step(); r = state['regs']
            if r['mode'] == spec.Mode.RETURN and r['sp'] and state['stack'][r['sp']-1][0] == spec.CALL_SOURCE_ASSEMBLY: break
            self.assertFalse(r['status'])
        state = {'regs': {key: int(value) for key, value in r.items()},
            **{bank: [[int(value) for value in row] for row in state[bank]] for bank in spec.BANK_FIELDS}}
        def cell(tag, a=0, b=0, c=0):
            ref = state['regs']['free']; self.assertLess(ref, cfg.heap)
            state['heap'][ref] = list(map(int, (tag, a, b, c))); state['regs']['free'] = ref+1; return ref
        def vec(values, role):
            values = tuple(values); head = 0
            for value in reversed(values): head = cell(CellTag.VECTOR_CELL, value, head)
            return cell(CellTag.VECTOR, len(values), head, role)
        def app(fn, values):
            for value in values: fn = cell(Tag.APP, fn, value)
            return fn
        def run(initial, task, x, **updates):
            initial = deepcopy(initial); before = deepcopy(initial)
            initial['regs'].update(status=0, reason=0, fuel=cfg.fuel, sp=0, task=int(task),
                mode=int(spec.Mode.BETA_ZETA if task == spec.Task.BETA_ZETA else spec.Mode.WALK), x=x, **updates)
            machine = spec.SpecMachine(cfg, initial)
            for step in range(cfg.fuel+2):
                actual = circuit.step(initial); expected = machine.step()
                if actual != expected:
                    diff = {key: (actual['regs'][key], int(expected['regs'][key])) for key in spec.REGISTERS if actual['regs'][key] != expected['regs'][key]}
                    self.fail(str((task, step, initial['regs']['task'], initial['regs']['mode'], diff)))
                initial = actual
                if initial['regs']['status']: break
            self.assertEqual((initial['regs']['status'], initial['regs']['reason']), (spec.Outcome.DONE, spec.Reason.NONE))
            if task != spec.Task.FRESH_LOCAL:
                for key in ('ctx', 'count', 'arg_base', 'local_base', 'env_head', 'typing_head', 'decl', 'raw_index'):
                    self.assertEqual(initial['regs'][key], before['regs'][key], key)
                self.assertEqual(initial['context'][:before['regs']['ctx']], before['context'][:before['regs']['ctx']])
            return initial
        packed = SimpleNamespace(heap=state['heap'])
        sig = vector(packed, r['core_rec_signatures'], VectorKind.REFERENCES)[0]
        rec_symbol, _, scheme = state['heap'][sig][1:]
        _, _, _, metadata = state['heap'][scheme]; _, owner, _, rules = state['heap'][metadata]
        rule = vector(packed, rules, VectorKind.REFERENCES)[0]
        ctor = cell(Tag.CONST, state['heap'][rule][1], r['header_levels'])
        family = cell(Tag.CONST, state['heap'][owner][1], r['header_levels'])
        zero = cell(CellTag.LEVEL_ZERO); prop = cell(Tag.SORT, zero)
        rec = cell(Tag.CONST, rec_symbol, vec((zero,), VectorKind.LEVELS))
        state = run(state, spec.Task.FRESH_LOCAL, prop, binder_info=0); p = state['regs']['r']
        state = run(state, spec.Task.FRESH_LOCAL, p, binder_info=0); proof = state['regs']['r']
        state = run(state, spec.Task.FRESH_LOCAL, family, binder_info=0); marker = state['regs']['r']
        # Genuine function-valued motive gives a well-typed surplus application.
        identity = cell(Tag.LAM, p, cell(Tag.BVAR, 0), 0)
        motive = cell(Tag.LAM, family, cell(Tag.PI, p, p), 0)
        body = app(rec, (motive, identity, ctor, proof))
        partial = app(rec, (motive, identity))
        data_motive = cell(Tag.LAM, family, family)
        data_rec = cell(Tag.CONST, rec_symbol, vec((cell(CellTag.LEVEL_SUCC, zero),), VectorKind.LEVELS))
        inner = app(data_rec, (data_motive, ctor, ctor))
        nested = app(data_rec, (data_motive, marker, inner))
        for label, expression, wanted in (('surplus-beta', body, proof), ('partial-neutral', partial, partial), ('recursive-major-call', nested, marker)):
            with self.subTest(label=label):
                actual = run(state, spec.Task.BETA_ZETA, expression)
                _, decoded = decode_syntax(SimpleNamespace(heap=actual['heap'][:actual['regs']['free']]), source.arena)
                self.assertTrue(representation_equal(source.arena, decoded[actual['regs']['r']], decoded[wanted]), label)
                self.assertEqual(actual['regs']['sp'], 0)


if __name__ == '__main__': unittest.main()
