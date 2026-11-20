"""Shared expression walk and checked index add. No torch model."""
import random
import unittest

from leanputer.kernel.arena import Tag
from leanputer.kernel.semantic_body import (
    ORIGINAL_DECLARATIONS,
    ORIGINAL_EXPRESSIONS,
    _lower_walk,
    build_checked_index_add,
    build_expression_address,
    build_shared_expression_walk,
    direct_expression_child,
    kept_output_dims,
    source_storage_report,
)
from leanputer.kernel.semantic_step_circuit import build_equality_key_select, partition_equality_keys
from leanputer.kernel.semantic_operators import DENSE_LIMIT
from leanputer.kernel.traversal_machine import Outcome, Reason


def _walk_samples(width):
    mask = (1 << width) - 1
    rows = (
        (1, 2, 3),
        (0, 0, 0),
        (mask, mask - 1, 1),
    )
    depths = (0, 1, mask - 1, mask)
    samples = []
    tags = [0, 15, *(int(tag) for tag in Tag)]
    for tag in tags:
        for index in range(4):
            for a, b, c in rows:
                for depth in depths:
                    for require in (0, 1):
                        direct = direct_expression_child(tag, index, a, b, c)
                        # Corners cover overflow and the ordinary successor.
                        if depth not in (0, mask) and not (direct['in_range'] and direct['depth_inc']):
                            continue
                        if (a, b, c) != rows[0] and depth not in (0, mask):
                            continue
                        samples.append(dict(
                            tag=tag, child_index=index, a=a, b=b, c=c, depth=depth,
                            require_child=require, service_gap=0, gap_reason=0,
                        ))
    samples.append(dict(
        tag=int(Tag.APP), child_index=0, a=1, b=2, c=3, depth=0,
        require_child=0, service_gap=1, gap_reason=int(Reason.GAP_CONVERSION),
    ))
    samples.append(dict(
        tag=int(Tag.PI), child_index=1, a=1, b=2, c=3, depth=mask,
        require_child=1, service_gap=1, gap_reason=int(Reason.GAP_PROJECTION),
    ))
    return samples


class SharedExpressionWalkTest(unittest.TestCase):
    def test_walk_matches_arena_children_and_publishes_gap(self):
        samples = _walk_samples(4)
        report = build_shared_expression_walk(4, samples)
        self.assertGreater(report['boolean_samples'], 0)
        self.assertTrue(report['expression_walk_included'])
        self.assertTrue(report['gap_outcome_included'])
        self.assertTrue(report['resource_outcome_included'])
        self.assertFalse(report['heap_gather_included'])
        self.assertFalse(report['handler_commit_included'])
        self.assertFalse(report['full_checker'])
        self.assertFalse(report['joint_delivery_gate'])
        self.assertFalse(report['stock_emitted'])
        self.assertTrue(report['channel_gate'])
        self.assertTrue(report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)
        self.assertEqual(int(Outcome.GAP), 4)
        self.assertEqual(int(Reason.INDEX), 4)

    def test_checked_add_matches_every_four_bit_pair(self):
        samples = [{'x': left, 'y': right} for left in range(16) for right in range(16)]
        report = build_checked_index_add(4, samples)
        self.assertEqual(report['boolean_samples'], 256)
        self.assertFalse(report['full_checker'])
        self.assertFalse(report['expression_walk_included'])
        self.assertTrue(report['dense_gate'])
        self.assertTrue(report['channel_gate'])

    def test_sixteen_bit_add_corners(self):
        mask = (1 << 16) - 1
        corners = [0, 1, 2, 255, 256, 65534, 65535]
        samples = [{'x': left, 'y': right} for left in corners for right in corners]
        rng = random.Random(11)
        for _ in range(32):
            samples.append({'x': rng.randrange(65536), 'y': rng.randrange(65536)})
        report = build_checked_index_add(16, samples)
        self.assertEqual(report['width'], 16)
        self.assertFalse(report['joint_delivery_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)

    def test_walk_and_selector_allocate_once(self):
        predicates = [
            ('and', (('range', 1, 3, 3), ('range', 2, 1, 1))),
            ('and', (('range', 1, 4, 4), ('range', 2, 1, 1))),
            ('and', (('range', 1, 5, 5), ('range', 2, 1, 1))),
        ]
        plan = partition_equality_keys(predicates)
        names = {1: 'mode', 2: 'task'}
        widths = {1: 4, 2: 4}
        samples = [{1: 0, 2: 0}, {1: 3, 2: 1}, {1: 4, 2: 1}, {1: 9, 2: 1}]
        walk_samples = _walk_samples(4)[:8]

        def tail(builder):
            return kept_output_dims(_lower_walk(
                builder, 4, walk_samples, 'walk', input_level=builder.barrier,
            ))

        alone = build_equality_key_select(names, widths, plan, samples, wave=2, placement_cap=96)
        joint = build_equality_key_select(
            names, widths, plan, samples, wave=2, placement_cap=96, tail=tail,
        )
        self.assertFalse(alone['tail_attached'])
        self.assertTrue(joint['tail_attached'])
        self.assertGreater(joint['ffn_units'], alone['ffn_units'])
        self.assertGreaterEqual(joint['graph_layers'], alone['graph_layers'])
        self.assertFalse(joint['full_checker'])
        self.assertFalse(joint['operator_body_included'])
        self.assertEqual(joint['memory_layers_included'], 0)
        self.assertTrue(joint['channel_gate'])
        self.assertTrue(joint['dense_gate'])

    def test_expression_address_matches_the_page_split(self):
        samples = [{'ref': ref} for ref in list(range(0, 600)) + [2048, 2557, 2558, 4096, 65535]]
        report = build_expression_address(2557, samples, placement_cap=96)
        self.assertGreater(len(samples), 600)
        self.assertFalse(report['page_read'])
        self.assertFalse(report['memory_placed'])
        self.assertFalse(report['full_checker'])
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)
        self.assertLessEqual(report['graph_layers'], 12)
        original = build_expression_address(512, [{'ref': ref} for ref in range(0, 520)], placement_cap=96)
        self.assertTrue(original['channel_gate'] and original['dense_gate'])
        self.assertFalse(original['memory_placed'])
        # Wide prefix ANDs are one layer deep. The binary ladder was 6 layers and 106 units.
        self.assertEqual(report['graph_layers'], 3)
        self.assertEqual(report['ffn_units'], 72)
        attached = build_shared_expression_walk(
            16,
            [
                dict(tag=int(Tag.APP), child_index=0, a=1, b=2, c=3, depth=0,
                     require_child=1, service_gap=0, gap_reason=0),
                dict(tag=int(Tag.APP), child_index=0, a=0, b=2, c=3, depth=0,
                     require_child=1, service_gap=0, gap_reason=0),
                dict(tag=int(Tag.APP), child_index=0, a=512, b=0, c=0, depth=1,
                     require_child=0, service_gap=0, gap_reason=0),
                dict(tag=int(Tag.APP), child_index=0, a=513, b=0, c=0, depth=1,
                     require_child=1, service_gap=0, gap_reason=0),
                dict(tag=int(Tag.PROJ), child_index=0, a=9, b=8, c=4, depth=0,
                     require_child=0, service_gap=0, gap_reason=0),
                dict(tag=0, child_index=0, a=1, b=1, c=1, depth=0,
                     require_child=1, service_gap=0, gap_reason=0),
            ],
            placement_cap=96,
            address_retained=512,
        )
        self.assertFalse(attached['page_read'])
        self.assertFalse(attached['memory_placed'])
        self.assertFalse(attached['heap_gather_included'])
        self.assertEqual(attached['address_retained'], 512)
        self.assertTrue(attached['channel_gate'] and attached['dense_gate'])
        self.assertLessEqual(attached['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)
        self.assertEqual(attached['graph_layers'], 9)
        self.assertEqual(attached['ffn_units'], 230)

    def test_storage_pages_keep_every_row(self):
        original = source_storage_report(
            ORIGINAL_EXPRESSIONS, ORIGINAL_DECLARATIONS, 32, 8,
        )
        self.assertEqual(original['expression_layers'], 1)
        self.assertEqual(original['small_bank_layers'], 1)
        self.assertFalse(original['exceeds_original_expression_bound'])
        self.assertFalse(original['exceeds_original_declaration_bound'])
        self.assertFalse(original['placed_graph'])
        wider = source_storage_report(513, ORIGINAL_DECLARATIONS, 32, 8)
        self.assertEqual(wider['expression_layers'], 2)
        self.assertTrue(wider['exceeds_original_expression_bound'])
        declared = source_storage_report(ORIGINAL_EXPRESSIONS, 5, 32, 8)
        self.assertTrue(declared['exceeds_original_declaration_bound'])
        self.assertGreater(declared['memory_only_logical_dense_parameters'], 0)
        self.assertFalse(source_storage_report(65535, 4, 32, 8)['exceeds_word_reference'])
        self.assertTrue(source_storage_report(65536, 4, 32, 8)['exceeds_word_reference'])


if __name__ == '__main__':
    unittest.main()
