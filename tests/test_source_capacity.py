"""Retained-row address map. Transport is not proof checking."""
import json
import unittest
from pathlib import Path

from leanputer.kernel.arena import KernelError
from leanputer.kernel.semantic_body import (
    ORIGINAL_DECLARATIONS,
    ORIGINAL_EXPRESSIONS,
    source_storage_report,
)
from leanputer.kernel.semantic_operators import DENSE_LIMIT
from leanputer.kernel.source_capacity import (
    IN_RANGE,
    INVALID_REFERENCE,
    NULL,
    WORD_OVERFLOW,
    AddressDomain,
    const_references,
    declaration_names,
    measure_transport,
    unplaced_logic_joint,
)


ROOT = Path('benchmarks/mathlib-v4.31.0/fabf563-addressable')
LOGIC = Path('benchmarks/kernel-macro-budget/semantic-body.json')

# Arena sizes from SyntaxCodec transport of the pinned export, word width 16.
# These are retained rows, not a stock admission.
RETAINED = {
    'Nat.succ_injective': dict(
        expression_rows=224, level_rows=8, declared_constants=15,
        const_references=14, records=9, vector_refs=69, vector_cells=258, symbols=20,
    ),
    'And.rotate': dict(
        expression_rows=565, level_rows=6, declared_constants=28,
        const_references=26, records=21, vector_refs=96, vector_cells=371, symbols=31,
    ),
    'em': dict(
        expression_rows=2061, level_rows=11, declared_constants=106,
        const_references=101, records=83, vector_refs=306, vector_cells=1344, symbols=111,
    ),
    'not_iff_not': dict(
        expression_rows=2557, level_rows=12, declared_constants=130,
        const_references=125, records=105, vector_refs=370, vector_cells=1647, symbols=136,
    ),
}


def _sources():
    rows = []
    with (ROOT / 'sources.jsonl').open() as handle:
        for line in handle:
            rows.append(json.loads(line))
    return rows


class AddressMapTest(unittest.TestCase):
    def test_original_pages_and_contract_stay(self):
        original = source_storage_report(ORIGINAL_EXPRESSIONS, ORIGINAL_DECLARATIONS, 32, 8)
        self.assertEqual(original['expression_layers'], 1)
        self.assertEqual(original['small_bank_layers'], 1)
        self.assertEqual(original['declaration_slots'], 4)
        self.assertEqual(original['expression_rows_retained'], 512)
        self.assertEqual(original['spare_expression_rows'], 0)
        self.assertFalse(original['exceeds_original_expression_bound'])
        self.assertFalse(original['exceeds_original_declaration_bound'])
        self.assertFalse(original['placed_graph'])
        self.assertFalse(original['spare_lanes_are_declaration_slots'])
        wider = source_storage_report(513, ORIGINAL_DECLARATIONS, 32, 8)
        self.assertEqual(wider['expression_layers'], 2)
        self.assertTrue(wider['exceeds_original_expression_bound'])
        self.assertEqual(wider['expression_rows_retained'], 513)
        declared = source_storage_report(ORIGINAL_EXPRESSIONS, 5, 32, 8)
        self.assertTrue(declared['exceeds_original_declaration_bound'])
        self.assertEqual(declared['declaration_slots'], 5)
        self.assertGreater(declared['memory_only_logical_dense_parameters'], 0)
        self.assertFalse(source_storage_report(65535, 4, 32, 8)['exceeds_word_reference'])
        self.assertTrue(source_storage_report(65536, 4, 32, 8)['exceeds_word_reference'])
        contract = Path('leanputer/kernel/transition_contracts.py').read_text()
        self.assertIn(
            'MachineConfig(heap=512, stack=32, context=8, constants=4, word_bits=16, fuel=8192)',
            contract,
        )

    def test_padding_is_not_a_live_row(self):
        domain = AddressDomain(224, 15, level_rows=8, vector_refs=69, vector_cells=258)
        self.assertEqual(domain.expression_address(0)['outcome'], NULL)
        self.assertEqual(domain.expression_address(224)['outcome'], IN_RANGE)
        last = domain.expression_address(224)
        self.assertEqual((last['layer'], last['head'], last['row']), (0, 1, 95))
        self.assertEqual(domain.expression_address(225)['outcome'], INVALID_REFERENCE)
        self.assertEqual(domain.expression_address(512)['outcome'], INVALID_REFERENCE)
        self.assertEqual(domain.expression_address(1 << 16)['outcome'], WORD_OVERFLOW)
        layout = domain.layout()
        self.assertEqual(layout['physical_expression_rows'], 512)
        self.assertEqual(layout['spare_expression_rows'], 288)
        self.assertFalse(layout['spare_expression_rows_are_live'])
        self.assertEqual(layout['declaration_slots'], 15)
        self.assertGreater(layout['spare_key_lanes'], 0)
        self.assertFalse(layout['spare_lanes_are_declaration_slots'])
        held = domain.small_address('declaration', 14)
        self.assertEqual(held['outcome'], IN_RANGE)
        self.assertEqual(held['key'], 32 + 8 + 14)
        self.assertEqual(domain.small_address('declaration', 15)['outcome'], INVALID_REFERENCE)
        self.assertEqual(domain.level_address(8)['outcome'], IN_RANGE)
        self.assertEqual(domain.level_address(9)['outcome'], INVALID_REFERENCE)
        self.assertFalse(layout['vector_bank_placed'])
        self.assertFalse(layout['exceeds_original_expression_bound'])
        self.assertTrue(layout['exceeds_original_declaration_bound'])

    def test_open_constant_is_not_dropped(self):
        row = {
            'format': 'leanputer.kernel-source.v1',
            'status': 'EXPORTED',
            'name': 'Demo.missing',
            'target': {
                'kind': 'theorem',
                'name': [{'str': 'Demo'}, {'str': 'missing'}],
                'level_params': [],
                'type': ['const', [{'str': 'Missing'}], []],
                'value': ['sort', ['zero']],
            },
            'declarations': [],
        }
        with self.assertRaises(KernelError):
            measure_transport(row)

    def test_pinned_mathlib_closures_are_retained(self):
        rows = _sources()
        self.assertEqual(
            [row['name'] for row in rows],
            ['Nat.succ_injective', 'not_iff_not', 'And.rotate', 'em'],
        )
        self.assertTrue(all(row['status'] == 'EXPORTED' for row in rows))
        self.assertTrue(all('levels' not in row for row in rows))
        self.assertNotIn('Nat.dvd_sub_self_left', [row['name'] for row in rows])
        union = set()
        for row in rows:
            measured = measure_transport(row)
            expect = RETAINED[row['name']]
            self.assertTrue(measured['transported'])
            self.assertFalse(measured['proof_checked'])
            self.assertIsNone(measured['admission'])
            self.assertFalse(measured['dependencies_dropped'])
            self.assertEqual(measured['missing_const_references'], 0)
            self.assertEqual(measured['expression_rows'], expect['expression_rows'])
            self.assertEqual(measured['level_rows'], expect['level_rows'])
            self.assertEqual(measured['declared_constants'], expect['declared_constants'])
            self.assertEqual(measured['const_references'], expect['const_references'])
            self.assertEqual(measured['declaration_records'], expect['records'])
            self.assertEqual(measured['vector_refs'], expect['vector_refs'])
            self.assertEqual(measured['vector_cells'], expect['vector_cells'])
            self.assertEqual(measured['symbols'], expect['symbols'])
            self.assertTrue(measured['target_has_value'])
            self.assertEqual(const_references(row) - declaration_names(row), set())
            union |= declaration_names(row)
            report = source_storage_report(
                measured['expression_rows'], measured['declared_constants'], 32, 8,
                level_rows=measured['level_rows'], vector_refs=measured['vector_refs'],
                vector_cells=measured['vector_cells'],
            )
            self.assertEqual(report['expression_rows_retained'], measured['expression_rows'])
            self.assertEqual(report['declaration_slots'], measured['declared_constants'])
            self.assertFalse(report['vector_bank_placed'])
            self.assertFalse(report['placed_graph'])
        self.assertEqual(len(union), 147)
        largest = max(RETAINED.values(), key=lambda item: item['expression_rows'])
        bound = source_storage_report(
            largest['expression_rows'], len(union), 32, 8,
            level_rows=max(item['level_rows'] for item in RETAINED.values()),
            vector_refs=max(item['vector_refs'] for item in RETAINED.values()),
            vector_cells=max(item['vector_cells'] for item in RETAINED.values()),
        )
        self.assertEqual(bound['expression_rows_retained'], 2557)
        self.assertEqual(bound['declaration_slots'], 147)
        self.assertEqual(bound['expression_layers'], 5)
        self.assertEqual(bound['level_layers'], 1)
        self.assertEqual(bound['small_bank_layers'], 1)
        self.assertEqual(bound['memory_layers'], 7)
        self.assertTrue(bound['exceeds_original_expression_bound'])
        self.assertTrue(bound['exceeds_original_declaration_bound'])
        self.assertFalse(bound['exceeds_word_reference'])
        logic = json.loads(LOGIC.read_text())['equality_residual_and_walk']['candidate_shapes'][0]
        self.assertEqual(logic['hidden'], 768)
        self.assertEqual(logic['layers'], 79)
        self.assertEqual(logic['logical_dense_parameters'], 47_423_548)
        joint = unplaced_logic_joint(bound, logic['layers'], logic['logical_dense_parameters'])
        self.assertEqual(joint['logical_dense_parameters'], 61_262_324)
        self.assertEqual(joint['over_dense_limit_by'], 61_262_324 - DENSE_LIMIT)
        self.assertEqual(joint['over_dense_limit_by'], 12_971_670)
        self.assertFalse(joint['dense_gate'])
        self.assertFalse(joint['placed_graph'])
        self.assertTrue(joint['vector_cells_unplaced'])
        self.assertEqual(joint['mathlib_theorems_checked'], 0)
        overflow = source_storage_report(184520, 2832, 32, 8, level_rows=63, vector_refs=5997, vector_cells=36081)
        self.assertEqual(overflow['expression_rows_retained'], 184520)
        self.assertEqual(overflow['declaration_slots'], 2832)
        self.assertTrue(overflow['exceeds_word_reference'])
        self.assertEqual(overflow['expression_layers'], 361)
        self.assertNotEqual(overflow['expression_rows_retained'], ORIGINAL_EXPRESSIONS)
        recorded = json.loads((ROOT / 'capacity.json').read_text())
        self.assertEqual(recorded['mathlib_theorems_checked'], 0)
        self.assertFalse(recorded['stock_checked'])
        self.assertFalse(recorded['proof_checking'])
        self.assertEqual(recorded['declaration_union'], 147)
        by_name = {item['name']: item for item in recorded['addressable']}
        self.assertEqual(set(by_name), set(RETAINED))
        for row in rows:
            got = by_name[row['name']]
            fresh = measure_transport(row)
            self.assertEqual(got['expression_rows'], fresh['expression_rows'])
            self.assertEqual(got['declared_constants'], fresh['declared_constants'])
            self.assertEqual(got['level_rows'], fresh['level_rows'])
            self.assertFalse(got['proof_checked'])
        withheld = recorded['word_overflow_source']
        self.assertEqual(withheld['name'], 'Nat.dvd_sub_self_left')
        self.assertFalse(withheld['included_in_sources_jsonl'])
        self.assertFalse(withheld['dependencies_dropped'])
        self.assertEqual(withheld['missing_const_references'], 0)
        self.assertEqual(withheld['declared_constants'], 2832)
        self.assertEqual(withheld['const_references'], 2737)
        self.assertEqual(withheld['transport_word_bits_32']['expression_rows'], 184520)
        self.assertIn('word overflow', withheld['transport_word_bits_16'])
        self.assertEqual(
            recorded['bounding_domain']['unplaced_joint_with_h768_logic']['logical_dense_parameters'],
            61_262_324,
        )


if __name__ == '__main__':
    unittest.main()
