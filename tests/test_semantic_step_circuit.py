"""Predicate lowering agrees with the direct control reading. No torch model."""
import unittest

from leanputer.kernel.control_capture import Effect
from leanputer.kernel.semantic_step_circuit import (
    DENSE_LIMIT,
    PredicateCircuit,
    build_continuation_range_select,
    build_continuation_select,
    build_equality_key_select,
    build_predicate_graph,
    build_source_lane,
    continuation_field_map,
    continuation_range_plan,
    equality_pairs,
    holds,
    partition_equality_keys,
    update_descriptor_account,
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

    def test_equality_key_select_follows_exclusive_classes(self):
        names = {1: 'task', 2: 'mode', 3: 'quot_pc'}
        widths = {1: 4, 2: 3, 3: 4}
        predicates = [
            ('and', (('range', 1, 1, 1), ('range', 2, 0, 0))),
            ('and', (('range', 1, 2, 2), ('range', 2, 0, 0))),
            ('and', (('range', 1, 1, 1), ('range', 2, 1, 1), ('range', 3, 4, 4))),
            ('and', (('range', 1, 1, 1), ('range', 2, 1, 1), ('range', 3, 5, 5))),
            ('range', 1, 1, 1),
            ('range', 1, 1, 1),
            ('range', 2, 1, 6),
        ]
        plan = partition_equality_keys(predicates)
        self.assertEqual(plan['field_set_classes'], 3)
        self.assertEqual(plan['collisions'], 1)
        self.assertEqual(plan['equality_handlers'], 6)
        self.assertEqual(plan['residual'], [6])
        samples = []
        for task, mode, quot in (
            (1, 0, 0), (2, 0, 9), (1, 1, 4), (1, 1, 5), (1, 0, 4),
            (0, 0, 0), (7, 7, 7), (1, 2, 0),
        ):
            samples.append({1: task, 2: mode, 3: quot})
        report = build_equality_key_select(names, widths, plan, samples, wave=2, placement_cap=80)
        self.assertEqual(report['exclusive_keys'], 5)
        self.assertEqual(report['collisions'], 1)
        self.assertEqual(report['residual_predicates'], 1)
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)
        self.assertFalse(report['full_checker'])
        self.assertFalse(report['operator_body_included'])
        self.assertEqual(report['residual_lowered'], 0)
        combined = build_equality_key_select(
            names, widths, plan, samples, wave=2, placement_cap=80,
            residual_predicates=[predicates[6]],
        )
        self.assertEqual(combined['residual_lowered'], 1)
        self.assertTrue(combined['channel_gate'] and combined['dense_gate'])
        self.assertFalse(combined['full_checker'])

    def test_continuation_range_keeps_every_handler_and_rejects_holes(self):
        names = {1: 'mode', 2: 'task', 3: 'quot_pc'}
        widths = {1: 4, 2: 4, 3: 4}
        predicates = []
        for pc in range(8):
            predicates.append(('and', (
                ('range', 1, 0, 0), ('range', 2, 5, 5), ('range', 3, pc, pc),
            )))
        # Same key as pc 0, so the class keeps both handler indexes.
        predicates.append(('and', (
            ('range', 1, 0, 0), ('range', 2, 5, 5), ('range', 3, 0, 0),
        )))
        predicates.append(('and', (
            ('range', 1, 1, 1), ('range', 2, 1, 1), ('range', 3, 0, 0),
        )))
        predicates.append(('and', (
            ('range', 1, 1, 1), ('range', 2, 1, 1), ('range', 3, 2, 2),
        )))
        for pc in range(4, 13):
            predicates.append(('and', (
                ('range', 1, 2, 2), ('range', 2, 4, 4), ('range', 3, pc, pc),
            )))
        predicates.append(('range', 3, 0, 3))
        plan = partition_equality_keys(predicates)
        self.assertEqual(plan['field_set_classes'], 1)
        self.assertEqual(plan['equality_handlers'], 20)
        self.assertEqual(plan['collisions'], 1)
        self.assertEqual(plan['residual'], [20])
        ranged = continuation_range_plan(plan['classes'], widths)
        self.assertEqual(ranged['exclusive_keys'], 19)
        item = ranged['classes'][0]
        self.assertEqual(item['axis'], 3)
        self.assertEqual(item['members'], 19)
        self.assertLess(item['predicted_gates'], item['members'])
        spans = {
            group['fixed']: group['spans']
            for group in item['groups'] if group['lowering'] == 'range'
        }
        self.assertEqual(spans[((1, 0), (2, 5))], ((0, 7),))
        self.assertEqual(spans[((1, 2), (2, 4))], ((4, 12),))
        fused = next(group for group in item['groups'] if group['lowering'] == 'fused')
        self.assertEqual(sorted(member['mapping'][3] for member in fused['members']), [0, 2])
        samples = [
            {1: mode, 2: task, 3: pc}
            for mode in range(16)
            for task in range(16)
            for pc in range(16)
        ]
        report = build_continuation_range_select(
            names, widths, plan, samples, wave=3, placement_cap=80,
            residual_predicates=[predicates[20]],
        )
        self.assertEqual(report['index_bits'], 0)
        self.assertEqual(report['handler_identity'], 'live control key')
        self.assertEqual(report['boolean_samples'], len(samples))
        self.assertEqual(report['residual_lowered'], 1)
        self.assertEqual(report['collisions'], 1)
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)
        self.assertFalse(report['full_checker'])
        self.assertFalse(report['operator_body_included'])
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertLess(report['predicted_match_gates'], plan['exclusive_keys'])

    def test_source_lane_follows_the_one_hot(self):
        samples = []
        for chosen in range(3):
            for word in (0, 1, 7, 15):
                words = [word, word ^ 0xA, word ^ 0x5]
                samples.append(dict(select=[1 if index == chosen else 0 for index in range(3)], words=words))
        report = build_source_lane(3, 4, samples, wave=2, placement_cap=80)
        self.assertEqual(report['boolean_samples'], len(samples))
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertTrue(report['one_slot_only'])
        self.assertFalse(report['full_checker'])

    def test_update_descriptor_counts_commit_slots(self):
        class Node:
            def __init__(self, op, data=None, args=()):
                self.op = op
                self.data = data
                self.args = args
                self.width = 16

        nodes = [Node('const', 7), Node('input', 'free'), Node('add', None, (1, 0))]
        effect = Effect(
            'merge_fields', 0, (('dest', 0), ('other', 1), ('sum', 2)),
            'source_rules.py', 1, 'source_rules',
        )
        bank = Effect('write_heap', 0, (1,), 'source_rules.py', 2, 'source_rules', 1)
        account = update_descriptor_account(nodes, [dict(effects=(effect, bank))])
        self.assertEqual(account['kind_counts']['const'], 1)
        self.assertEqual(account['kind_counts']['copy'], 1)
        self.assertEqual(account['kind_counts']['add'], 1)
        self.assertEqual(account['kind_counts']['bank'], 1)
        self.assertEqual(account['write_slots_max'], 4)
        self.assertEqual(account['data_slots_max'], 3)
        self.assertEqual(account['const_slots_max'], 1)
        self.assertEqual(account['distinct_copy_sources'], 1)
        self.assertGreater(account['max_descriptor_bits'], account['bits_per_slot'])
        self.assertFalse(account['placed_graph'])


if __name__ == '__main__':
    unittest.main()
