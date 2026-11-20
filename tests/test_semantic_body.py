"""Shared expression walk and checked index add. No torch model."""
import random
import unittest

from leanputer.kernel.arena import Tag
from leanputer.native_vendor.qwenputer.ir import evaluate
from leanputer.kernel.semantic_body import (
    ARGUMENT_WINDOW_TASKS,
    ORIGINAL_DECLARATIONS,
    ORIGINAL_EXPRESSIONS,
    PROLOGUE_FLAG_FIELDS,
    STEP_FRONT_FIELDS,
    _evaluate_samples,
    _features,
    _lower_walk,
    build_checked_index_add,
    build_expression_address,
    build_child_page,
    build_expression_page,
    build_shared_expression_walk,
    build_small_bank,
    build_step_front,
    commit_step_prologue,
    direct_expression_child,
    _expr_value,
    commit_register_word,
    kept_output_dims,
    merge_constant_word,
    source_storage_report,
    step_front_image,
    step_prologue_image,
    unpack_byte,
)
from leanputer.kernel.semantic_step_circuit import PredicateCircuit
from leanputer.native_machine import NativeBuilder
from leanputer.kernel.semantic_step_circuit import build_equality_key_select, partition_equality_keys
from leanputer.kernel.semantic_operators import DENSE_LIMIT
from leanputer.kernel.traversal_machine import Mode, Outcome, Reason, Task


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

    def test_expression_page_reads_the_addressed_row(self):
        def write(ref, tag, a, b, c):
            return dict(
                write_enable=1, write_ref=ref, read_ref=0,
                store_tag=tag, store_a=a, store_b=b, store_c=c,
            )

        def read(ref):
            return dict(
                write_enable=0, write_ref=0, read_ref=ref,
                store_tag=0, store_a=0, store_b=0, store_c=0,
            )

        samples = [
            write(1, int(Tag.APP), 1, 2, 3),
            write(2, int(Tag.LAM), 4, 5, 6),
            write(128, int(Tag.PI), 7, 8, 9),
            write(129, int(Tag.SORT), 10, 11, 12),
            write(512, int(Tag.CONST), 13, 14, 15),
            write(0, int(Tag.APP), 99, 99, 99),
            write(513, int(Tag.APP), 98, 98, 98),
            read(1),
            read(2),
            read(128),
            read(129),
            read(512),
            read(0),
            read(513),
            read(3),
            read(256),
            write(1, int(Tag.LET), 20, 21, 22),
            read(1),
        ]
        report = build_expression_page(512, samples, placement_cap=96)
        self.assertTrue(report['page_read'])
        self.assertTrue(report['expression_page_placed'])
        self.assertFalse(report['small_bank_placed'])
        self.assertFalse(report['memory_placed'])
        self.assertFalse(report['full_checker'])
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertEqual(report['payload_bits'], 52)
        self.assertEqual(report['payload_bytes'], 7)
        self.assertEqual(report['memory_layers_included'], 1)
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)
        self.assertEqual(report['selected_shape']['gdn_layers'], 1)

    def test_child_page_reads_the_walk_child(self):
        def row(child, write_enable, write_ref, tag, a, b, c):
            return dict(
                tag=int(Tag.APP), child_index=0, a=child, b=0, c=0, depth=0,
                require_child=0, service_gap=0, gap_reason=0,
                write_enable=write_enable, write_ref=write_ref,
                store_tag=tag, store_a=a, store_b=b, store_c=c,
            )

        samples = [
            row(0, 1, 1, int(Tag.APP), 1, 2, 3),
            row(1, 0, 0, 0, 0, 0, 0),
            row(0, 1, 129, int(Tag.SORT), 4, 5, 6),
            row(129, 0, 0, 0, 0, 0, 0),
            row(0, 1, 512, int(Tag.CONST), 7, 8, 9),
            row(512, 0, 0, 0, 0, 0, 0),
            row(0, 1, 0, int(Tag.LAM), 9, 9, 9),
            row(0, 1, 513, int(Tag.LAM), 8, 8, 8),
            row(513, 0, 0, 0, 0, 0, 0),
            row(3, 0, 0, 0, 0, 0, 0),
            row(256, 0, 0, 0, 0, 0, 0),
        ]
        report = build_child_page(samples, placement_cap=96)
        self.assertTrue(report['page_read'])
        self.assertTrue(report['expression_page_placed'])
        self.assertFalse(report['small_bank_placed'])
        self.assertFalse(report['full_checker'])
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertEqual(report['memory_layers_included'], 1)
        self.assertEqual(report['payload_bytes'], 7)
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)

    def test_small_bank_reads_stack_context_and_declarations(self):
        def frame(enable, bank, index, words, read_bank, read_index):
            row = dict(
                write_enable=enable, bank=bank, index=index,
                read_bank=read_bank, read_index=read_index,
            )
            for bit, word in enumerate(words):
                row[f'w{bit}'] = word
            return row

        zero = (0, 0, 0, 0, 0, 0)
        samples = [
            frame(1, 0, 0, (1, 2, 3, 4, 5, 6), 0, 0),
            frame(0, 0, 0, zero, 0, 0),
            frame(1, 0, 31, (9, 0, 0, 0, 0, 0), 0, 31),
            frame(0, 0, 0, zero, 0, 0),
            frame(1, 1, 0, (8, 0, 0, 0, 0, 0), 1, 0),
            frame(1, 1, 7, (3, 1, 0, 0, 0, 0), 1, 7),
            frame(1, 2, 0, (4, 0, 0, 0, 0, 0), 2, 0),
            frame(1, 2, 3, (5, 6, 7, 8, 9, 10), 2, 3),
            frame(0, 0, 0, zero, 0, 1),
            frame(1, 0, 32, (99, 0, 0, 0, 0, 0), 0, 32),
            frame(1, 1, 8, (99, 0, 0, 0, 0, 0), 1, 8),
            frame(1, 2, 4, (99, 0, 0, 0, 0, 0), 2, 4),
            frame(1, 3, 0, (99, 0, 0, 0, 0, 0), 3, 0),
            frame(0, 0, 0, zero, 0, 0),
            frame(1, 0, 0, (7, 0, 0, 0, 0, 0), 0, 0),
            frame(0, 0, 0, zero, 0, 31),
            frame(0, 0, 0, zero, 1, 0),
            frame(0, 0, 0, zero, 1, 7),
            frame(0, 0, 0, zero, 2, 0),
            frame(0, 0, 0, zero, 2, 3),
        ]
        report = build_small_bank(32, 8, 4, samples, placement_cap=96)
        self.assertTrue(report['page_read'])
        self.assertTrue(report['small_bank_placed'])
        self.assertFalse(report['expression_page_placed'])
        self.assertFalse(report['memory_placed'])
        self.assertFalse(report['full_checker'])
        self.assertFalse(report['handler_commit_included'])
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertEqual(report['payload_bits'], 96)
        self.assertEqual(report['payload_bytes'], 12)
        self.assertEqual(report['small_bank_keys'], 44)
        self.assertEqual(report['memory_layers_included'], 1)
        self.assertEqual(report['selected_shape']['gdn_layers'], 1)
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)

    def test_small_bank_unaligned_declarations_use_the_adder(self):
        def frame(enable, bank, index, word, read_bank, read_index):
            row = dict(
                write_enable=enable, bank=bank, index=index,
                read_bank=read_bank, read_index=read_index,
            )
            row['w0'] = word
            for bit in range(1, 6):
                row[f'w{bit}'] = 0
            return row

        samples = [
            frame(1, 2, 0, 11, 2, 0),
            frame(1, 2, 4, 12, 2, 4),
            frame(0, 0, 0, 0, 2, 0),
            frame(0, 0, 0, 0, 2, 4),
            frame(1, 2, 5, 13, 2, 5),
            frame(0, 0, 0, 0, 2, 0),
            frame(1, 0, 0, 1, 0, 0),
            frame(1, 1, 7, 2, 1, 7),
            frame(0, 0, 0, 0, 0, 1),
        ]
        report = build_small_bank(32, 8, 5, samples, placement_cap=96)
        self.assertTrue(report['small_bank_placed'])
        self.assertEqual(report['small_bank_keys'], 45)
        self.assertFalse(report['memory_placed'])
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)

    def test_two_writers_or_merge_one_small_bank_row(self):
        def frame(a, b, read_bank, read_index):
            row = dict(read_bank=read_bank, read_index=read_index)
            for prefix, item in (('a_', a), ('b_', b)):
                enable, bank, index, words = item
                row[f'{prefix}guard'] = enable
                row[f'{prefix}bank'] = bank
                row[f'{prefix}index'] = index
                for bit, word in enumerate(words):
                    row[f'{prefix}w{bit}'] = word
            return row

        zero = (0, 0, 0, 0, 0, 0)
        cold = (0, 0, 0, zero)
        samples = [
            frame((1, 0, 1, (1, 0, 0, 0, 0, 0)), (1, 0, 1, (2, 4, 0, 0, 0, 0)), 0, 1),
            frame((1, 0, 1, (0x00ff, 0, 0, 0, 0, 0)), (1, 0, 2, (0xff00, 0, 0, 0, 0, 0)), 0, 3),
            frame(cold, cold, 0, 1),
            frame(cold, cold, 0, 2),
            frame((1, 0, 0, (5, 0, 0, 0, 0, 0)), (0, 0, 7, (0xffff, 1, 1, 1, 1, 1)), 0, 0),
            frame(cold, cold, 0, 7),
            frame((1, 1, 1, (7, 99, 99, 99, 99, 99)), cold, 1, 1),
            frame((1, 1, 2, (1, 2, 0, 0, 0, 0)), (1, 1, 2, (4, 8, 0, 0, 0, 0)), 1, 2),
            frame((1, 0, 4, (1, 2, 3, 4, 5, 6)), cold, 0, 4),
        ]
        report = build_small_bank(
            32, 8, 4, samples, placement_cap=96, writers=2, zero_extend_context=True,
        )
        self.assertTrue(report['guarded_merge_included'])
        self.assertFalse(report['handler_commit_included'])
        self.assertFalse(report['full_checker'])
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)

    def test_two_hot_banks_cannot_share_one_small_token(self):
        zero = (0, 0, 0, 0, 0, 0)
        sample = dict(read_bank=0, read_index=0)
        sample.update(a_guard=1, a_bank=0, a_index=1)
        sample.update(b_guard=1, b_bank=1, b_index=0)
        for bit in range(6):
            sample[f'a_w{bit}'] = 1
            sample[f'b_w{bit}'] = 0
        with self.assertRaises(AssertionError):
            build_small_bank(32, 8, 4, [sample], placement_cap=96, writers=2)

    def test_constant_field_merge_ors_overlapping_hits(self):
        samples = [
            dict(h0=1, h1=0, h2=0),
            dict(h0=0, h1=1, h2=0),
            dict(h0=1, h1=1, h2=0),
            dict(h0=0, h1=0, h2=0),
            dict(h0=1, h1=1, h2=1),
            dict(h0=0, h1=0, h2=1),
        ]
        builder = NativeBuilder(intermediate=256, reset_layers=0, layout_policy='compact')
        words = _features(builder, (('h0', 1), ('h1', 1), ('h2', 1)), 'hit')
        circuit = PredicateCircuit(builder, words, {})
        hit_pairs = [
            (list(zip(circuit.words[name], circuit.bit_ids[name]))[0], value)
            for name, value in (('h0', 0b0001), ('h1', 0b0010), ('h2', 0b0100))
        ]
        merged = merge_constant_word(circuit, hit_pairs, width=4)
        matrix = _evaluate_samples(builder.graph, words, samples)
        expect = (0b0001, 0b0010, 0b0011, 0b0000, 0b0111, 0b0100)
        for index, sample in enumerate(samples):
            got = 0
            for bit, column in enumerate(merged):
                value = _expr_value(column, matrix[index])
                self.assertIn(value, (0, 1))
                got |= value << bit
            self.assertEqual(got, expect[index], sample)

    def test_constant_commit_replaces_the_old_word_or_keeps_it(self):
        # Hot constants replace the word. A hot zero clears it. A cold writer
        # leaves the previous word. Two hot writers OR, including a shared bit.
        samples = [
            dict(h0=1, h1=0, h2=0, old=0b1111),
            dict(h0=0, h1=0, h2=0, old=0b1111),
            dict(h0=0, h1=0, h2=1, old=0b1111),
            dict(h0=1, h1=1, h2=0, old=0b1000),
            dict(h0=0, h1=1, h2=0, old=0b0001),
        ]
        builder = NativeBuilder(intermediate=256, reset_layers=0, layout_policy='compact')
        words = _features(builder, (('h0', 1), ('h1', 1), ('h2', 1), ('old', 4)), 'hit')
        circuit = PredicateCircuit(builder, words, {})
        writers = [
            (list(zip(circuit.words[name], circuit.bit_ids[name]))[0], value)
            for name, value in (('h0', 0b0011), ('h1', 0b0101), ('h2', 0))
        ]
        old = list(zip(circuit.words['old'], circuit.bit_ids['old']))
        merged = commit_register_word(circuit, writers, old, width=4)
        matrix = _evaluate_samples(builder.graph, words, samples)
        expect = (0b0011, 0b1111, 0b0000, 0b0111, 0b0101)
        for index, sample in enumerate(samples):
            got = 0
            for bit, column in enumerate(merged):
                value = _expr_value(column, matrix[index])
                self.assertIn(value, (0, 1))
                got |= value << bit
            self.assertEqual(got, expect[index], sample)
        self.assertEqual(
            commit_register_word(circuit, [], old, width=4),
            old,
        )

    def test_page_byte_unpacks_every_value(self):
        builder = NativeBuilder(intermediate=256, reset_layers=0, layout_policy='compact')
        byte = builder.feature('page/byte')
        bits = unpack_byte(builder, byte, 'page/byte')
        (dim,) = byte.terms
        values = list(range(256))
        builder.graph.token_fns[dim] = lambda token, values=values: values[token]
        matrix = evaluate(builder.graph, values, check=True)
        self.assertEqual(len(bits), 8)
        for index, value in enumerate(values):
            got = 0
            for bit, column in enumerate(bits):
                bit_value = _expr_value(column, matrix[index])
                self.assertIn(bit_value, (0, 1))
                got |= bit_value << bit
            self.assertEqual(got, value)

    def test_small_bank_read_unpacks_to_the_stored_words(self):
        samples = []
        for bank, index, words, read_bank, read_index in (
            (0, 0, (1, 2, 3, 4, 5, 6), 0, 0),
            (0, 31, (255, 0, 0, 0, 0, 0), 0, 31),
            (1, 7, (7, 0, 0, 0, 0, 0), 1, 7),
            (2, 3, (9, 8, 7, 6, 5, 4), 2, 3),
            (0, 1, (0, 0, 0, 0, 0, 0), 0, 1),
        ):
            row = dict(write_enable=1, bank=bank, index=index, read_bank=read_bank, read_index=read_index)
            for bit, word in enumerate(words):
                row[f'w{bit}'] = word
            samples.append(row)
        report = build_small_bank(32, 8, 4, samples, placement_cap=96, unpack=True)
        self.assertTrue(report['page_bytes_unpacked'])
        self.assertTrue(report['page_read'])
        self.assertFalse(report['handler_commit_included'])
        self.assertFalse(report['full_checker'])
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertTrue(report['channel_gate'] and report['dense_gate'])
        self.assertLessEqual(report['selected_shape']['logical_dense_parameters'], DENSE_LIMIT)

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


# Compiler contract checked by transition_contracts. Not a second page size.
_CONTRACT = dict(heap=512, stack=32, context=8)
_SOURCE_FLAGS = (
    'bounded', 'pending_open', 'pending_fold', 'typing_active', 'core_operation',
    'occurrence_internal', 'occurrence_found', 'pending_reuse', 'reuse_whnf',
    'pending_scope', 'env_ready', 'pending_infer', 'vec_changed', 'order_same_base',
)
_SOURCE_ARGUMENT_TASKS = (
    Task.INSTANTIATE, Task.ABSTRACT, Task.OCCURS, Task.HAS_CONSTANTS, Task.FORMAL_LEVELS,
    Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.EXPR_LEVEL_SUBSTITUTE, Task.LEVEL_INSTANTIATE,
    Task.EXPR_LEVEL_INSTANTIATE, Task.EXPR_SCOPE,
)


def _legal_frame(**overrides):
    frame = dict(
        status=int(Outcome.RUNNING), reason=0, fuel=10,
        free=1, sp=0, count=0, ctx=0, mode=0, task=int(Task.LIFT),
        local_base=0, pending_compare=0,
        open_tag=int(Tag.PI), fold_tag=int(Tag.LAM), arg_base=0,
        bounded=0, pending_open=0, pending_fold=0, typing_active=0, core_operation=0,
        occurrence_internal=0, occurrence_found=0, pending_reuse=0, reuse_whnf=0,
        pending_scope=0, env_ready=0, pending_infer=0, vec_changed=0, order_same_base=0,
    )
    frame.update(overrides)
    return frame


def _front_cases():
    """Hand-read outcomes. Fuel 10 decrements to 9. The image is not consulted."""
    run, inv, res = int(Outcome.RUNNING), int(Outcome.INVALID), int(Outcome.RESOURCE)
    syntax, fuel, context = int(Reason.SYNTAX), int(Reason.FUEL), int(Reason.CONTEXT)
    stay, bad, window = (run, 0, 9), (inv, syntax, 9), (res, context, 9)
    rows = []

    def add(prologue, front, **overrides):
        rows.append((overrides, prologue, front))

    add(stay, stay)
    add((run, 6, 9), (run, 6, 9), reason=6)
    add((1, 14, 0), (1, 14, 0), status=1, reason=14, fuel=0, free=0, open_tag=0, fold_tag=0)
    add((3, 2, 4), (3, 2, 4), status=3, reason=2, fuel=4, free=0)
    add((2, 1, 0), (2, 1, 0), status=2, reason=1, fuel=0, sp=99)
    add((4, 11, 1), (4, 11, 1), status=4, reason=11, fuel=1, open_tag=0)
    add((5, 0, 8), (5, 0, 8), status=5, fuel=8)
    add((res, fuel, 0), (res, fuel, 0), fuel=0, free=0, open_tag=0, fold_tag=0)
    add((res, fuel, 0), (res, fuel, 0), fuel=0)
    add((res, fuel, 0), (res, fuel, 0), fuel=0, free=513)
    add((run, 0, 0), (run, 0, 0), fuel=1)
    add((run, 14, 0), (run, 14, 0), fuel=1, reason=14)
    add((run, 0, 65534), (run, 0, 65534), fuel=65535)
    add((run, 0, 255), (run, 0, 255), fuel=256)
    add((run, 0, 4), (run, 0, 4), fuel=5, free=512)
    add((inv, syntax, 4), (inv, syntax, 4), fuel=5, free=513)
    add((inv, syntax, 4), (inv, syntax, 4), fuel=5, free=0, reason=7)
    add((run, 0, 4), (run, 0, 4), fuel=5, sp=32)
    add((inv, syntax, 4), (inv, syntax, 4), fuel=5, sp=33)
    add((run, 0, 4), (run, 0, 4), fuel=5, count=8)
    add((inv, syntax, 4), (inv, syntax, 4), fuel=5, count=9, task=int(Task.INSTANTIATE))
    add((run, 0, 4), (run, 0, 4), fuel=5, ctx=8)
    add((inv, syntax, 4), (inv, syntax, 4), fuel=5, ctx=9)
    add((run, 0, 4), (run, 0, 4), fuel=5, mode=int(Mode.MINOR_LINK))
    add((inv, syntax, 4), (inv, syntax, 4), fuel=5, mode=int(Mode.MINOR_LINK) + 1)
    add((run, 0, 5), (run, 0, 5), fuel=6, task=int(Task.CHECK_PUBLISHED_RECURSOR), arg_base=8, count=1)
    add((inv, syntax, 5), (inv, syntax, 5), fuel=6, task=int(Task.CHECK_PUBLISHED_RECURSOR) + 1)
    add(stay, stay, bounded=1)
    add(bad, bad, bounded=2)
    add(stay, stay, pending_compare=2)
    add(bad, bad, pending_compare=3)
    add(stay, stay, local_base=8)
    add(bad, bad, local_base=9)
    add(stay, stay, open_tag=int(Tag.LAM), fold_tag=int(Tag.LAM))
    add(stay, stay, open_tag=int(Tag.PI), fold_tag=int(Tag.PI))
    add((inv, syntax, 2), (inv, syntax, 2), fuel=3, open_tag=0)
    add(bad, bad, fold_tag=0)
    add(bad, bad, open_tag=int(Tag.APP))
    add(bad, bad, open_tag=int(Tag.LET))
    add(bad, bad, fold_tag=int(Tag.APP))
    add((inv, syntax, 2), (inv, syntax, 2), fuel=3, free=0, sp=40)
    add(stay, stay, task=int(Task.INSTANTIATE), arg_base=0, count=8)
    add(stay, window, task=int(Task.INSTANTIATE), arg_base=1, count=8)
    add(stay, stay, task=int(Task.INSTANTIATE), arg_base=7, count=1)
    add(stay, window, task=int(Task.INSTANTIATE), arg_base=7, count=2)
    add(stay, stay, task=int(Task.INSTANTIATE), arg_base=0, count=0)
    add((res, fuel, 0), (res, fuel, 0), task=int(Task.INSTANTIATE), fuel=0, arg_base=10, count=10)
    add((inv, syntax, 3), (inv, syntax, 3), task=int(Task.INSTANTIATE), fuel=4, free=0, arg_base=10, count=10)
    add((1, 0, 5), (1, 0, 5), status=1, task=int(Task.INSTANTIATE), fuel=5, arg_base=10, count=10)
    add(stay, window, task=int(Task.ABSTRACT), arg_base=65535, count=1)
    add(stay, stay, task=int(Task.LIFT), arg_base=65535, count=8)
    add(stay, stay, task=int(Task.ABSTRACT_ONE), arg_base=8, count=1)
    add(stay, stay, task=int(Task.LEVEL_EQUAL), arg_base=8, count=1)
    add(stay, stay, task=int(Task.INFER), arg_base=65535, count=0)
    add(stay, stay, task=int(Task.HAS_FAMILIES), arg_base=8, count=1)
    add(stay, stay, task=int(Task.BETA_ZETA), arg_base=8, count=1)
    add((run, 6, 9), window, task=int(Task.INSTANTIATE), arg_base=8, count=1, reason=6)
    for name in _SOURCE_FLAGS:
        add(bad, bad, **{name: 2})
    for task in _SOURCE_ARGUMENT_TASKS:
        add(stay, window, task=int(task), arg_base=8, count=1)
    return rows


def _front_samples(cases, limits):
    samples = []
    for overrides, prologue, front in cases:
        sample = _legal_frame(**overrides)
        if step_prologue_image(sample, limits) != prologue or step_front_image(sample, limits) != front:
            raise AssertionError(f'front image disagrees with the hand-read case {overrides}')
        sample['expect_prologue'] = prologue
        sample['expect_front'] = front
        samples.append(sample)
    return samples


class StepFrontTest(unittest.TestCase):
    def test_front_vocabulary_matches_the_source_lists(self):
        self.assertEqual(PROLOGUE_FLAG_FIELDS, _SOURCE_FLAGS)
        self.assertEqual(ARGUMENT_WINDOW_TASKS, tuple(int(task) for task in _SOURCE_ARGUMENT_TASKS))
        self.assertEqual(set(_legal_frame()), set(STEP_FRONT_FIELDS))
        self.assertEqual(len(PROLOGUE_FLAG_FIELDS), 14)
        self.assertEqual(len(ARGUMENT_WINDOW_TASKS), 11)
        self.assertEqual(int(Mode.MINOR_LINK), 254)
        self.assertEqual(int(Task.CHECK_PUBLISHED_RECURSOR), 120)
        self.assertEqual(int(Tag.PI), 6)
        self.assertEqual(int(Tag.LAM), 7)

    def test_front_image_matches_the_hand_read_cases(self):
        cases = _front_cases()
        samples = _front_samples(cases, _CONTRACT)
        self.assertGreaterEqual(len(samples), 60)
        self.assertEqual(step_front_image(samples[0], _CONTRACT), (int(Outcome.RUNNING), 0, 9))

    def test_step_prologue_rejects_a_bad_limit_and_a_missing_word(self):
        builder = NativeBuilder(intermediate=256, reset_layers=0, layout_policy='compact')
        circuit = PredicateCircuit(builder, {}, {})
        with self.assertRaises(ValueError):
            commit_step_prologue(circuit, dict(heap=65536, stack=32, context=8))
        with self.assertRaises(ValueError):
            commit_step_prologue(circuit, dict(heap=True, stack=32, context=8))
        with self.assertRaises(ValueError):
            commit_step_prologue(circuit, dict(heap=512, stack=32, context=8))

    def test_step_front_matches_fuel_syntax_and_argument_window(self):
        samples = _front_samples(_front_cases(), _CONTRACT)
        report = build_step_front(_CONTRACT, samples)
        self.assertTrue(report['step_prologue_included'])
        self.assertTrue(report['argument_window_included'])
        self.assertFalse(report['handler_bodies_included'])
        self.assertFalse(report['handler_commit_included'])
        self.assertFalse(report['continuation_range_attached'])
        self.assertFalse(report['full_checker'])
        self.assertFalse(report['stock_emitted'])
        self.assertFalse(report['joint_delivery_gate'])
        self.assertFalse(report['private_algorithms_placed'])
        self.assertFalse(report['constants_bound_checked'])
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertEqual(report['gdn_layers'], 0)
        self.assertEqual(report['prologue_frame_bytes'], 54)
        self.assertEqual(report['frame_bytes'], 56)
        self.assertEqual(report['limits'], _CONTRACT)
        self.assertEqual(report['boolean_samples'], len(samples))
        dense = report['selected_shape']['logical_dense_parameters']
        self.assertEqual(report['within_working_dense_limit'], dense <= report['working_dense_limit'])
        self.assertEqual(report['within_ideal_dense_limit'], dense <= report['ideal_dense_limit'])
        self.assertEqual(report['within_absolute_dense_limit'], dense < report['absolute_dense_limit'])
        self.assertLessEqual(dense, report['working_dense_limit'])
        self.assertLess(dense, report['absolute_dense_limit'])
        self.assertLessEqual(report['selected_shape']['channels_needed'], report['selected_shape']['hidden'])

    def test_step_front_uses_the_limit_arguments(self):
        limits = dict(heap=9, stack=4, context=5)
        run, inv, res = int(Outcome.RUNNING), int(Outcome.INVALID), int(Outcome.RESOURCE)
        syntax, context = int(Reason.SYNTAX), int(Reason.CONTEXT)
        stay, bad = (run, 0, 9), (inv, syntax, 9)
        cases = []

        def add(prologue, front, **overrides):
            cases.append((overrides, prologue, front))

        add(stay, stay, free=9, sp=4, count=5, ctx=5, local_base=5)
        add(bad, bad, free=10)
        add(bad, bad, sp=5)
        add(bad, bad, count=6)
        add(bad, bad, ctx=6)
        add(bad, bad, local_base=6)
        add(stay, stay, task=int(Task.INSTANTIATE), arg_base=2, count=3)
        add(stay, (res, context, 9), task=int(Task.INSTANTIATE), arg_base=3, count=3)
        add((res, int(Reason.FUEL), 0), (res, int(Reason.FUEL), 0), fuel=0, free=0)
        samples = _front_samples(cases, limits)
        report = build_step_front(limits, samples)
        self.assertEqual(report['limits'], limits)
        self.assertEqual(report['mathlib_theorems_checked'], 0)
        self.assertFalse(report['full_checker'])


if __name__ == '__main__':
    unittest.main()
