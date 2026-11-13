"""Typed relocation, role-alias safety and original-input isolation contracts."""
import json
from pathlib import Path
import unittest
from leanputer.kernel.arena import LevelTag, ResourceError, Tag
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.native_cells import CellCapacities, CellTag, VectorKind, pack_source
from leanputer.kernel.syntax import SyntaxCodec


def vector(packed, ref, kind):
    tag, length, cell, role = packed.heap[ref]
    assert tag == CellTag.VECTOR and role == kind
    values = []
    for _ in range(length):
        tag, value, cell, reserved = packed.heap[cell]
        assert tag == CellTag.VECTOR_CELL and reserved == 0
        values.append(value)
    assert cell == 0
    return tuple(values)


def decode_syntax(packed, arena):
    """Independent reverse codec; no checking/reduction or inferred answers."""
    levels, expressions = {}, {}
    level_tags = {CellTag.LEVEL_ZERO: LevelTag.ZERO, CellTag.LEVEL_SUCC: LevelTag.SUCC,
        CellTag.LEVEL_MAX: LevelTag.MAX, CellTag.LEVEL_IMAX: LevelTag.IMAX, CellTag.LEVEL_PARAM: LevelTag.PARAM}
    for ref, (tag, a, b, c) in enumerate(packed.heap):
        if tag in level_tags:
            left = a if tag == CellTag.LEVEL_PARAM else 0 if tag == CellTag.LEVEL_ZERO else levels[a]
            right = levels[b] if tag in (CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX) else 0
            levels[ref] = arena.level(level_tags[tag], left, right)
        elif Tag.BVAR <= tag <= Tag.MDATA:
            if tag == Tag.SORT:
                a = levels[a]
            elif tag == Tag.CONST:
                b = arena.vec(levels[p] for p in vector(packed, b, VectorKind.LEVELS))
            elif tag in (Tag.APP, Tag.PI, Tag.LAM):
                a, b = expressions[a], expressions[b]
            elif tag == Tag.LET:
                a, b, c = expressions[a], expressions[b], expressions[c]
            elif tag == Tag.PROJ:
                c = expressions[c]
            elif tag == Tag.MDATA:
                a = expressions[a]
            elif tag in (Tag.NAT, Tag.STRING):
                a = arena.vec(vector(packed, a, VectorKind.LIMBS if tag == Tag.NAT else VectorKind.BYTES))
            expressions[ref] = arena.mk(tag, a, b, c)
    return levels, expressions


class NativeCellsTest(unittest.TestCase):
    def test_complete_source_graph_roundtrip_and_no_checked_input_tags(self):
        fixture = Path(__file__).parent/'fixtures/kernel-nested-source.jsonl'
        source = SyntaxCodec().document(json.loads(fixture.read_text()))
        packed = pack_source(source)
        self.assertEqual(len(packed.constants), 2)
        self.assertLess(packed.initial_free, 4096)
        self.assertTrue(all(row[0] < CellTag.CHECKED_SIGNATURE for row in packed.heap))
        levels, expressions = decode_syntax(packed, source.arena)
        self.assertEqual({old: levels[new] for old, new in packed.level_map.items()}, {old: old for old in packed.level_map})
        self.assertEqual({old: expressions[new] for old, new in packed.expression_map.items()}, {old: old for old in packed.expression_map})
        # Injective structured-name transport, including role-tagged payloads.
        for ref in vector(packed, packed.symbols, VectorKind.REFERENCES):
            tag, symbol, path, reserved = packed.heap[ref]
            self.assertEqual((tag, reserved), (CellTag.SYMBOL_ENTRY, 0))
            parts = []
            for segment in vector(packed, path, VectorKind.REFERENCES):
                tag, payload, _, _ = packed.heap[segment]
                if tag == CellTag.NAME_STRING:
                    parts.append(('str', bytes(vector(packed, payload, VectorKind.BYTES)).decode('utf-8')))
                else:
                    self.assertEqual(tag, CellTag.NAME_NUMERAL)
                    digits = vector(packed, payload, VectorKind.LIMBS)
                    parts.append(('num', sum(d << (16*i) for i, d in enumerate(digits))))
            self.assertEqual(tuple(parts), source.symbols.names[symbol])
        before_rows = len(source.arena.rows)
        result = EnvironmentDriver(source).check()
        self.assertEqual(result.status, 'ACCEPT', result.reason)
        self.assertGreater(len(source.arena.rows), before_rows)
        # Generated rule/type/level/name artifacts MUST NOT enter a subsequent
        # native input pack. Only the original reachable syntax is transported.
        self.assertEqual(pack_source(source), packed)

    def test_vector_alias_roles_scope_data_and_physical_bounds(self):
        n = lambda s: [{'str': s}]
        doc = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
            target=dict(kind='definition', name=n('target'), level_params=[], type=['sort', ['zero']],
                value=['app', ['const', n('f'), [['zero']]], ['nat', '1']]))
        codec = SyntaxCodec()
        number = (1 << 80)+1
        doc['target']['name'] = [{'str': 'a'}, {'num': number}]
        doc['target']['value'][1][1] = [{'str': 'a'}, {'str': str(number)}]
        source = codec.document(doc)
        arena = source.arena
        app = arena.expr(source.target.value)
        constant, literal = arena.expr(app.a), arena.expr(app.b)
        # The SOURCE vectors really alias. Their interpretations do not.
        self.assertEqual(constant.b, literal.a)
        packed = pack_source(source)
        const_vector = packed.heap[packed.expression_map[app.a]][2]
        literal_vector = packed.heap[packed.expression_map[app.b]][1]
        self.assertNotEqual(const_vector, literal_vector)
        self.assertEqual(vector(packed, const_vector, VectorKind.LEVELS), (packed.level_map[arena.zero],))
        self.assertEqual(vector(packed, literal_vector, VectorKind.LIMBS), (1,))
        numeral_payloads = [row[1] for row in packed.heap if row[0] == CellTag.NAME_NUMERAL]
        self.assertEqual(len(numeral_payloads), 1)
        self.assertEqual(vector(packed, numeral_payloads[0], VectorKind.LIMBS), (1, 0, 0, 0, 0, 1))
        # This codec preserves invalid semantic input for checking IN WEIGHTS.
        doc['target']['type'] = ['sort', ['param', n('unboundUniverse')]]
        doc['target']['value'] = ['local', 77]
        source = SyntaxCodec().document(doc)
        packed = pack_source(source)
        self.assertEqual(packed.heap[packed.target[4]][:2], (Tag.LOCAL, 77))
        self.assertIn(CellTag.LEVEL_PARAM, [row[0] for row in packed.heap])
        fixture = Path(__file__).parent/'fixtures/kernel-nested-source.jsonl'
        source = SyntaxCodec().document(json.loads(fixture.read_text()))
        with self.assertRaises(ResourceError):
            pack_source(source, CellCapacities(heap=32, constants=8, word_bits=8))


if __name__ == '__main__':
    unittest.main()
