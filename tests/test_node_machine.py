"""WHNF node-transition table: execution, budget, and static rejection."""
import unittest

from leanputer.kernel.node_transition import (
    CAUSE_FUEL, CAUSE_HEAP, CAUSE_STACK, DECL_AXIOM, DECL_DEF, DECL_OPAQUE,
    FRAME_UPD, PC_EVAL, PC_RET, STATUS_DONE, STATUS_INVALID, STATUS_RESOURCE,
    TAG_BVAR, TAG_ENV, TAG_NAPP, Cell, Phase, Port, Row, StaticRejection, Table,
    UnsupportedInput, fixture_cost, load_whnf, readback, run, step, validate_table,
    whnf_table,
)

S0 = ('sort', 0)


def _whnf(term):
    """Call-by-name substitution WHNF. Comparison only; not the machine."""
    def shift(term, delta, cutoff=0):
        tag = term[0]
        if tag == 'var':
            return ('var', term[1] + delta if term[1] >= cutoff else term[1])
        if tag in ('sort', 'const'):
            return term
        if tag == 'let':
            return (tag, shift(term[1], delta, cutoff), shift(term[2], delta, cutoff),
                    shift(term[3], delta, cutoff + 1))
        return (tag, shift(term[1], delta, cutoff), shift(term[2], delta, cutoff + int(tag in ('pi', 'lam'))))

    def subst(term, repl, depth=0):
        tag = term[0]
        if tag == 'var':
            return shift(repl, depth) if term[1] == depth else ('var', term[1] - int(term[1] > depth))
        if tag in ('sort', 'const'):
            return term
        if tag == 'let':
            return (tag, subst(term[1], repl, depth), subst(term[2], repl, depth), subst(term[3], repl, depth + 1))
        return (tag, subst(term[1], repl, depth), subst(term[2], repl, depth + int(tag in ('pi', 'lam'))))

    def go(term, defs):
        if term[0] == 'let':
            return go(subst(term[3], term[2]), defs)
        if term[0] == 'const' and term[1] in defs and defs[term[1]] is not None:
            return go(defs[term[1]], defs)
        if term[0] != 'app':
            return term
        fn = go(term[1], defs)
        if fn[0] == 'lam':
            return go(subst(fn[2], term[2]), defs)
        return ('app', fn, term[2])

    return go(term, {})


def _normalize(term):
    """Full normal form of a ground term, for the memo/sharing difference."""
    head = _whnf(term)
    if head[0] == 'lam':
        return ('lam', _normalize(head[1]), _normalize(head[2]))
    if head[0] == 'pi':
        return ('pi', _normalize(head[1]), _normalize(head[2]))
    if head[0] == 'app':
        return ('app', _normalize(head[1]), _normalize(head[2]))
    if head[0] == 'let':
        return ('let', _normalize(head[1]), _normalize(head[2]), _normalize(head[3]))
    return head


def _run(term, declarations=(), **kwargs):
    machine = load_whnf(term, declarations, **kwargs)
    result = run(machine, whnf_table())
    return machine, result


class NodeTransitionTests(unittest.TestCase):
    def test_formula_fixtures_and_measured_whnf_budget(self):
        self.assertEqual(fixture_cost(24, 600, 512, 1024), (16, 30_464_580))
        self.assertEqual(fixture_cost(24, 600, 512, 768), (16, 22_850_884))
        self.assertEqual(fixture_cost(3000, 2500, 512, 1024), (26, 46_316_140))
        self.assertEqual(fixture_cost(3000, 2500, 512, 768), (26, 34_739_564))
        self.assertEqual(fixture_cost(3000, 2500, 4096, 1024), (40, 94_214_620))
        self.assertEqual(fixture_cost(3000, 2500, 4096, 768), (40, 70_674_652))
        report = validate_table(whnf_table())
        self.assertEqual(report['n_rows'], 24)
        self.assertEqual(report['u_mux'], 932)
        self.assertEqual(report['layers'], 16)
        self.assertEqual(report['control_width'], 38)
        self.assertEqual(report['residual_bits']['total'], 769)
        self.assertFalse(report['residual_bits']['stock_placement'])
        self.assertEqual(report['residual_bits']['estimate'], 'conservative_static')
        self.assertGreater(report['residual_bits']['addresses'], 0)
        self.assertGreater(report['residual_bits']['pending_write'], 0)
        self.assertGreater(report['residual_bits']['control'], 0)
        book = report['structural_bookkeeping']
        self.assertEqual(book['programmable_alu_lanes'], 2)
        self.assertFalse(book['counted_in_programmable_alu'])
        self.assertFalse(book['counted_in_u_mux'])
        self.assertEqual(book['bits'], 48)
        by_hidden = {shape['hidden']: shape for shape in report['shapes']}
        self.assertFalse(by_hidden[768]['channel_gate'])
        self.assertTrue(by_hidden[768]['dense_gate'])
        self.assertEqual(by_hidden[768]['logical_dense_parameters'], 22_850_884)
        self.assertTrue(by_hidden[896]['channel_gate'])
        self.assertEqual(by_hidden[896]['logical_dense_parameters'], 26_657_732)
        self.assertEqual(by_hidden[1024]['logical_dense_parameters'], 30_464_580)
        self.assertTrue(report['within_40_layers'])
        self.assertTrue(report['within_working_dense'])
        self.assertFalse(report['stock_forward_equivalence'])
        self.assertFalse(report['weights_emitted'])
        self.assertTrue(report['original_source_requires_inductive'])
        self.assertEqual(report['intermediate_256'][1]['layers'], 19)
        with self.assertRaises(StaticRejection) as caught:
            validate_table(whnf_table(), hidden_candidates=(32,))
        self.assertEqual(caught.exception.check, 'budget')

    def test_reduction_matches_substitution_whnf(self):
        identity = ('lam', S0, ('var', 0))
        machine, result = _run(('app', identity, S0))
        self.assertEqual(machine.regs.status, STATUS_DONE)
        self.assertEqual(readback(machine), _whnf(('app', identity, S0)))
        self.assertEqual((result['steps'], result['allocs'], result['peak_depth']), (6, 2, 1))
        self.assertEqual(result['fueled_rows'], 6)
        self.assertEqual(result['fuel_detections'], 0)
        self.assertLessEqual(result['max_predicates'], 3)
        self.assertLessEqual(result['max_alus'], 2)
        self.assertLessEqual(result['max_heap_ports'], 2)
        self.assertLessEqual(result['max_rounds'], 2)

        machine, result = _run(('const', 'T'), [('T', DECL_DEF, S0, S0)])
        self.assertEqual(readback(machine), ('sort', 0))
        self.assertEqual((result['steps'], result['allocs']), (3, 1))

        machine, _ = _run(('const', 'A'), [('A', DECL_AXIOM, S0, None)])
        self.assertEqual(readback(machine), ('const', 'A'))

        machine, result = _run(('let', S0, S0, ('var', 0)))
        self.assertEqual(readback(machine), _whnf(('let', S0, S0, ('var', 0))))
        self.assertEqual(result['steps'], 5)

        body = ('var', 6)
        for _ in range(7):
            body = ('lam', S0, body)
        term = body
        declarations = []
        for index in range(7):
            name = f'a{index}'
            declarations.append((name, DECL_AXIOM, S0, None))
            term = ('app', term, ('const', name))
        machine, result = _run(term, declarations)
        self.assertEqual(readback(machine), ('const', 'a0'))
        self.assertEqual(_whnf(term), ('const', 'a0'))
        self.assertEqual((result['steps'], result['allocs'], result['peak_depth']), (21, 8, 7))

        two = ('lam', S0, ('lam', S0, ('app', ('var', 1), ('app', ('var', 1), ('var', 0)))))
        plus = ('lam', S0, ('lam', S0, ('lam', S0, ('lam', S0, (
            'app', ('app', ('var', 3), ('var', 1)),
            ('app', ('app', ('var', 2), ('var', 1)), ('var', 0)))))))
        decls = [('s', DECL_AXIOM, S0, None), ('z', DECL_AXIOM, S0, None)]
        applied = ('app', ('app', two, ('const', 's')), ('const', 'z'))
        machine, result = _run(applied, decls)
        self.assertEqual(readback(machine), _whnf(applied))
        summed = ('app', ('app', ('app', ('app', plus, two), two), ('const', 's')), ('const', 'z'))
        machine, result = _run(summed, decls)
        self.assertEqual(readback(machine), _whnf(summed))
        # Proposal table said 28/9/4. This encoding measures 27/9/4.
        self.assertEqual((result['steps'], result['allocs'], result['peak_depth']), (27, 9, 4))

        def church(count):
            body = ('var', 0)
            for _ in range(count):
                body = ('app', ('var', 1), body)
            return ('lam', S0, ('lam', S0, body))

        mul = ('lam', S0, ('lam', S0, ('lam', S0, ('lam', S0, (
            'app', ('app', ('var', 3), ('app', ('var', 2), ('var', 1))), ('var', 0))))))
        product = ('app', ('app', ('app', ('app', mul, church(3)), church(4)), ('const', 's')), ('const', 'z'))
        machine, result = _run(product, decls)
        # Memo forces the shared (4 s) binding, so the WHNF term is not the
        # substitution term. Both full normal forms are twelve applications.
        self.assertEqual(_normalize(readback(machine)), _normalize(_whnf(product)))
        self.assertEqual((result['steps'], result['allocs'], result['peak_depth']), (39, 13, 4))

    def test_invalid_inputs_are_machine_outcomes(self):
        for term in (('var', 0), ('app', S0, S0), ('app', ('pi', S0, S0), S0), ('const', 'missing')):
            machine, result = _run(term)
            self.assertEqual(machine.regs.status, STATUS_INVALID, term)
            self.assertEqual(result['trace'][-1]['row'].endswith('else'), True, result['trace'][-1]['row'])
            self.assertEqual(result['fuel_detections'], 0)

    def test_resources_and_fuel_detection(self):
        machine = load_whnf(S0, fuel=0)
        event = step(machine, whnf_table())
        self.assertEqual(event['row'], 'resource-fuel')
        self.assertEqual(event['cause'], CAUSE_FUEL)
        self.assertEqual(event['fuel_delta'], 0)
        self.assertEqual(machine.regs.fuel, 0)
        self.assertEqual(machine.regs.status, STATUS_RESOURCE)
        self.assertEqual(machine.regs.hp, 2)

        machine, result = _run(S0, heap_cap=1, fuel=10)
        self.assertEqual(result['trace'][-1]['cause'], CAUSE_HEAP)
        self.assertEqual(result['trace'][-1]['fuel_delta'], -1)
        self.assertEqual(machine.regs.fuel, 9)
        self.assertEqual(machine.regs.hp, 2)

        machine, result = _run(('app', S0, S0), stack_cap=1, fuel=10)
        self.assertEqual(result['trace'][-1]['cause'], CAUSE_STACK)
        self.assertEqual(machine.regs.K, 1)

        machine = load_whnf(S0, fuel=0, heap_cap=1)
        event = step(machine, whnf_table())
        self.assertEqual(event['cause'], CAUSE_FUEL)
        self.assertEqual(machine.regs.hp, 2)

    def test_load_limits_and_opaque_scope(self):
        with self.assertRaises(UnsupportedInput):
            load_whnf(('sort', 65536))
        with self.assertRaises(UnsupportedInput):
            load_whnf(S0, fuel=65536)
        with self.assertRaises(UnsupportedInput):
            load_whnf(S0, stack_cap=0)
        with self.assertRaises(UnsupportedInput):
            load_whnf(('const', 'o'), [('o', DECL_OPAQUE, S0, S0)])

    def test_napp_does_not_read_a_lambda_through_the_value(self):
        machine = load_whnf(S0, fuel=20)
        address = machine.regs.hp
        machine.heap[address] = Cell(tag=TAG_NAPP, a=1, b=1, c=0)
        machine.regs.hp = address + 1
        machine.regs.V = address
        machine.regs.pc = PC_RET
        machine.stk[1] = Cell(kind=2, a=1, b=0)  # F_APP
        event = step(machine, whnf_table())
        self.assertEqual(event['row'], 'R-napp-napp')
        self.assertEqual(event['reads']['b'], 0)

    def test_memo_hits_and_double_write(self):
        identity = ('lam', S0, ('var', 0))
        expensive = identity
        for _ in range(3):
            expensive = ('app', expensive, identity)
        body = S0
        for _ in range(4):
            body = ('app', ('var', 0), body)
        machine, shared = _run(('app', ('lam', S0, body), expensive))
        self.assertEqual(readback(machine), S0)
        hits = sum(1 for event in shared['trace'] if 'memo' in event['row'])
        self.assertGreaterEqual(hits, 3)
        duplicated = S0
        for _ in range(4):
            duplicated = ('app', expensive, duplicated)
        machine_dup, repeated = _run(duplicated)
        self.assertEqual(readback(machine_dup), S0)
        self.assertLess(shared['steps'], repeated['steps'])
        self.assertEqual((shared['steps'], repeated['steps']), (40, 78))

        guard = (('kind', 'k', FRAME_UPD),)
        phase = Phase('RET', PC_RET, (
            Port('k', 'stk', 1, ('reg', 'K')),
            Port('v', 'heap_a', 1, ('reg', 'V')),
            Port('b', 'heap_b', 2, ('null',), choices=((guard, ('field', 'k', 'a')),)),
        ), (), (
            Row('RET', 'write', (('kind', 'k', FRAME_UPD), ('tag', 'b', TAG_ENV)),
                heap=('memo', 'b', ('reg', 'V')), stk=('pop',)),
            Row('RET', 'else', (), (('status', ('imm', STATUS_INVALID)),), fallback=True),
        ))
        machine = load_whnf(S0, fuel=5)
        address = machine.regs.hp
        machine.heap[address] = Cell(tag=TAG_ENV, a=1, b=0, c=0, m=1, memo=True)
        machine.regs.hp = address + 1
        machine.regs.pc = PC_RET
        machine.regs.V = 1
        machine.stk[1] = Cell(kind=FRAME_UPD, a=address)
        event = step(machine, Table((phase,)))
        self.assertEqual(event['cause'], 'MEMO_TWICE')
        self.assertEqual(event['fuel_delta'], -1)
        self.assertTrue(machine.heap[address].memo)
        self.assertEqual(machine.heap[address].m, 1)

    def test_static_rejection_of_malformed_tables(self):
        def check(rows, reads=(), alus=()):
            fallback = Row('EVAL', 'else', (), (('status', ('imm', STATUS_INVALID)),), fallback=True)
            phase = Phase('EVAL', PC_EVAL, tuple(reads), tuple(alus), tuple(rows) + (fallback,))
            validate_table(Table((phase,)))

        with self.assertRaises(StaticRejection) as caught:
            check([
                Row('EVAL', 'C0', (('eq', ('reg', 'C'), 0),)),
                Row('EVAL', 'E1', (('eq', ('reg', 'E'), 1),)),
            ])
        self.assertEqual(caught.exception.check, 'exclusive')
        check([
            Row('EVAL', 'A0', (('eq', ('reg', 'A0'), 0),)),
            Row('EVAL', 'A1', (('eq', ('reg', 'A0'), 1),)),
        ])
        with self.assertRaises(StaticRejection) as caught:
            check([Row('EVAL', 'bogus', (), (('C', ('bogus',)),))])
        self.assertEqual(caught.exception.check, 'menu')
        with self.assertRaises(StaticRejection) as caught:
            check([Row('EVAL', 'wide', (), (('A0', ('imm', 65536)),))])
        self.assertEqual(caught.exception.check, 'width')
        with self.assertRaises(StaticRejection) as caught:
            check([
                Row('EVAL', 'nat', (('tag', 'n', TAG_BVAR),), (('C', ('field', 'n', 'a')),)),
            ], reads=(Port('n', 'heap_a', 1, ('reg', 'C')),))
        self.assertEqual(caught.exception.check, 'sort')
        with self.assertRaises(StaticRejection) as caught:
            check([Row('EVAL', 'structural', (), (('hp', ('imm', 1)),))])
        self.assertEqual(caught.exception.check, 'bounds')
        with self.assertRaises(StaticRejection) as caught:
            check([Row('EVAL', 'halt', (), (('status', ('imm', STATUS_DONE)),))])
        self.assertEqual(caught.exception.check, 'stop')
        with self.assertRaises(StaticRejection) as caught:
            check([Row('EVAL', 'only', ())], reads=(
                Port('n', 'heap_a', 1, ('reg', 'C')),
                Port('m', 'heap_a', 1, ('reg', 'E')),
            ))
        self.assertEqual(caught.exception.check, 'bounds')
        with self.assertRaises(StaticRejection) as caught:
            check([Row('EVAL', 'only', ())], reads=(
                Port('n', 'heap_a', 1, ('reg', 'C')),
                Port('q', 'heap_b', 1, ('field', 'n', 'a')),
            ))
        self.assertEqual(caught.exception.check, 'bounds')
        with self.assertRaises(StaticRejection) as caught:
            check([Row('EVAL', 'only', ())], reads=(
                Port('p', 'heap_a', 1, ('reg', 'A1')),
                Port('q', 'heap_b', 2, ('field', 'p', 'c')),
            ))
        self.assertEqual(caught.exception.check, 'sort')
        with self.assertRaises(StaticRejection) as caught:
            check([
                Row('EVAL', 'memo', (('kind', 'k', FRAME_UPD),), heap=('memo', 'k', ('reg', 'V'))),
            ], reads=(Port('k', 'stk', 1, ('reg', 'K')),))
        self.assertEqual(caught.exception.check, 'write')
        check([
            Row('EVAL', 'memo', (('tag', 'n', TAG_ENV), ('not_memo', 'n')),
                heap=('memo', 'n', ('reg', 'V'))),
        ], reads=(Port('n', 'heap_a', 1, ('reg', 'C')),))


if __name__ == '__main__':
    unittest.main()
