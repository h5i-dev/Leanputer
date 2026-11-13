"""Original-scheme syntax boundaries and general source-core integration."""
import json
from pathlib import Path
import unittest
from leanputer.kernel.admission import analyze_core
from leanputer.kernel.arena import KernelError, LevelTag, LocalContext, Tag
from leanputer.kernel.operations import check_scope
from leanputer.kernel.recursor import Constructor, Inductive
from leanputer.kernel.services import KernelServices
from leanputer.kernel.syntax import RawBlock, SourceUnavailable, SyntaxCodec


def name(s):
    return [{'str': s}]


class KernelSyntaxTest(unittest.TestCase):
    def test_general_syntax_and_no_admission_answers(self):
        codec = SyntaxCodec()
        numeric = codec.symbols.intern([{'str': 'a'}, {'num': 1}])
        text = codec.symbols.intern([{'str': 'a'}, {'str': '1'}])
        self.assertNotEqual(numeric, text)
        self.assertNotEqual(codec.symbols.encoded_names[numeric], codec.symbols.encoded_names[text])
        level = ['imax', ['param', name('u')], ['max', ['zero'], ['succ', ['param', name('v')]]]]
        expr = ['pi', 1, ['sort', level], ['let', ['sort', ['zero']],
            ['nat', '1208925819614629174706177'], ['lam', 3, ['sort', ['zero']],
                ['proj', name('R'), 19, ['mdata', ['app', ['const', name('f'), [level]], ['var', 2]]]]]]]
        ref = codec.expression(expr)
        check_scope(codec.arena, ref, universe_parameters=tuple(codec.symbols.intern(name(p)) for p in ('u', 'v')))
        string = codec.expression(['string', 'λ\u0000証'])
        self.assertEqual(codec.arena.vector(codec.arena.expr(string).a), tuple('λ\u0000証'.encode('utf-8')))
        # The parser is not a scope checker: it preserves this invalid closed
        # declaration. The kernel's later scope operation must reject it.
        bad = dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
            target=dict(kind='theorem', name=name('bad'), level_params=[], type=['sort', ['zero']], value=['local', 77]))
        raw = SyntaxCodec().document(bad)
        with self.assertRaises(KernelError):
            check_scope(raw.arena, raw.target.value)
        with self.assertRaises(SourceUnavailable):
            SyntaxCodec().document(dict(format='leanputer.kernel-source.v1', status='UNSUPPORTED',
                reason='body unavailable', declarations=None, target=None))

    def test_original_lean_schemes_and_generated_recursor_claims(self):
        fixture = Path(__file__).parent/'fixtures/kernel-source-smoke.jsonl'
        docs = [json.loads(line) for line in fixture.read_text().splitlines()]
        self.assertEqual([d['status'] for d in docs], ['EXPORTED']*3+['UNSUPPORTED'])
        checked = []
        for doc in docs[:3]:
            codec = SyntaxCodec()
            source = codec.document(doc)
            self.assertTrue(source.target.universe_parameters)
            service = KernelServices(source.arena, LocalContext(source.arena))
            for block in source.declarations:
                if not isinstance(block, RawBlock):
                    continue
                a = source.arena
                us = tuple(a.level(LevelTag.PARAM, p) for p in block.universe_parameters)
                families = tuple(Inductive(a.const(f.symbol, us), f.type,
                    tuple(Constructor(c.symbol, c.type) for c in f.constructors), f.recursor_symbol) for f in block.families)
                # Choose our OWN fresh symbol, never the claimed elimination
                # answer. Scheme comparison alpha-renames universe binders.
                fresh = codec.symbols.intern(name('_checkerElimination'))
                result = analyze_core(service, families, block.universe_parameters,
                    block.parameters, fresh, block.recursor_claims)
                checked.append((doc['name'], result))
                self.assertFalse(service.constants)
        self.assertEqual([n for n, _ in checked], ['Prod.fst', 'Eq.symm'])
        self.assertEqual(checked[0][1].families[0].constructors[0].fields, 2)
        self.assertEqual(checked[1][1].families[0].indices, 1)
        self.assertTrue(checked[1][1].k_eligible)
        # Only block core phases were checked. Full target proof bodies and
        # earlier ordinary declarations are NOT admitted by this test.


if __name__ == '__main__':
    unittest.main()
