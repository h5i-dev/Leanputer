"""Predicate lowering agrees with the direct control reading. No torch model."""
import unittest

from leanputer.kernel.semantic_step_circuit import (
    DENSE_LIMIT,
    PredicateCircuit,
    build_continuation_select,
    build_predicate_graph,
    continuation_field_map,
    equality_pairs,
    holds,
)
from leanputer.native_machine import NativeBuilder


def words_and_circuit(widths):
    builder = NativeBuilder(intermediate=256, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = 232
    words = {
        variable: [builder.feature(f'w/{variable}/{bit}') for bit in range(width)]
        for variable, width in widths.items()
    }
    domains = {variable: (0, (1 << width) - 1) for variable, width in widths.items()}
    return builder, PredicateCircuit(builder, words, domains), domains


class PredicateLoweringTest(unittest.TestCase):
    def test_equality_interval_and_or_match_every_assignment(self):
        _, circuit, domains = words_and_circuit({1: 4, 2: 4})
        predicates = [
            ('range', 1, 5, 5),
            ('range', 1, 2, 4),
            ('and', (('range', 1, 1, 6), ('range', 2, 0, 3))),
            ('or', (('range', 1, 0, 1), ('range', 2, 14, 15))),
            ('and', (('or', (('range', 1, 0, 0), ('range', 1, 15, 15))), ('range', 2, 7, 9))),
        ]
        compiled = circuit.compile_all(predicates)
        samples = [
            {1: left, 2: right}
            for left in range(16)
            for right in range(16)
        ]
        circuit.agrees(predicates, compiled, samples)
        for predicate in predicates:
            for values in samples:
                self.assertIn(int(holds(predicate, values)), (0, 1))
        self.assertEqual(domains[1][1], 15)

    def test_less_than_five_uses_two_set_bit_gates(self):
        builder, circuit, _ = words_and_circuit({1: 4})
        circuit.compile(('range', 1, 0, 4))  # x <= 4 iff x < 5
        units = sum(len(node.terms) for node in builder.graph.nodes if node.__class__.__name__ == 'FFN')
        # x < 5 has set bits at 0 and 2. Each case is one AND. The disjunction is a free sum.
        self.assertEqual(units, 2)

    def test_shared_graph_reports_a_dense_shape(self):
        variables = (1, 2)
        domains = {1: (0, 15), 2: (0, 15)}
        widths = {1: 4, 2: 4}
        predicates = [
            ('range', 1, 3, 3),
            ('and', (('range', 1, 0, 7), ('range', 2, 8, 15))),
            ('or', (('range', 1, 1, 1), ('range', 2, 2, 2))),
            ('range', 2, 0, 15),
        ]
        samples = [{1: left, 2: right} for left in range(0, 16, 5) for right in range(0, 16, 5)]
        report = build_predicate_graph(variables, domains, widths, predicates, samples, wave=2)
        self.assertTrue(report['boolean_samples'])
        self.assertGreater(report['ffn_units'], 0)
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)
        self.assertTrue(report['channel_gate'])
        self.assertEqual(report['predicates'], 4)

    def test_equality_pairs_reject_intervals(self):
        self.assertEqual(equality_pairs(('range', 3, 4, 4)), ((3, 4),))
        self.assertIsNone(equality_pairs(('range', 3, 1, 4)))
        self.assertEqual(
            equality_pairs(('and', (('range', 1, 2, 2), ('range', 3, 5, 5)))),
            ((1, 2), (3, 5)),
        )
        self.assertIsNone(equality_pairs(('or', (('range', 1, 0, 0), ('range', 1, 1, 1)))))

    def test_continuation_select_follows_the_task_map(self):
        names = {1: 'task', 2: 'quot_pc', 3: 'convert_pc'}
        widths = {1: 4, 2: 4, 3: 4}
        mapping = {0: 2, 1: 2, 5: 3}
        samples = []
        for task, field in list(mapping.items()) + [(7, None)]:
            samples.append({
                1: task,
                2: (task * 3 + 1) & 15,
                3: (task * 5 + 2) & 15,
            })
        report = build_continuation_select(names, widths, mapping, task_index=1, samples=samples, wave=2)
        self.assertTrue(report['channel_gate'])
        self.assertTrue(report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)
        self.assertEqual(report['tasks'], 3)
        self.assertEqual(report['buses'], 1)
        dual = build_continuation_select(
            names, widths, {0: 2, 4: (3, 2)}, task_index=1,
            samples=[
                {1: 0, 2: 9, 3: 3},
                {1: 4, 2: 1, 3: 14},
                {1: 7, 2: 2, 3: 2},
            ],
            wave=2,
        )
        self.assertEqual(dual['buses'], 2)
        self.assertTrue(dual['channel_gate'] and dual['dense_gate'])
        plan = continuation_field_map([
            ('and', (('range', 1, 0, 0), ('range', 2, 4, 4))),
            ('and', (('range', 1, 5, 5), ('range', 3, 1, 1))),
            ('range', 1, 0, 3),
        ], names)
        self.assertEqual(plan['_mapping'], {0: 2, 5: 3})
        self.assertEqual(plan['conflict_tasks'], 0)
        self.assertEqual(plan['skipped']['not-equality'], 1)
        named = {1: 'task', 2: 'quot_pc', 3: 'convert_pc', 4: 'mode'}
        addressed = continuation_field_map([
            ('and', (('range', 1, 1, 1), ('range', 4, 0, 0), ('range', 2, 3, 3))),
            ('and', (('range', 1, 2, 2), ('range', 2, 0, 0), ('range', 3, 1, 1))),
        ], named)
        self.assertEqual(addressed['_mapping'], {1: 2})
        self.assertEqual(addressed['conflict_tasks'], 1)


if __name__ == '__main__':
    unittest.main()
