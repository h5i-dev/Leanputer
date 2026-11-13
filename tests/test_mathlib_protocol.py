import unittest
import json
from pathlib import Path
import tempfile

from leanputer.mathlib_benchmark import select_population, write_syntax_report


class MathlibSelectionTests(unittest.TestCase):
    def test_selection_retains_unavailable_or_unsupported_cases(self):
        declarations = [dict(name=f'theorem_{i}', module='Chosen.Module', internal=False, private=False,
                             body_available=bool(i % 2), unsupported=bool(i % 3)) for i in range(30)]
        declarations += [dict(name='private', module='Chosen.Module', internal=False, private=True, body_available=True),
                         dict(name='internal', module='Chosen.Module', internal=True, private=False, body_available=True)]
        population = dict(declarations=declarations)
        chosen = select_population(population, 12, 814732)
        self.assertEqual(chosen, select_population(population, 12, 814732))
        self.assertEqual(len(chosen), 12)
        self.assertTrue(any(not row['body_available'] for row in chosen))
        self.assertTrue(any(row['unsupported'] for row in chosen))
        self.assertTrue(all(not row['private'] and not row['internal'] for row in chosen))
        all_public = select_population(population, 100, 814732)
        self.assertEqual(len(all_public), 30)

    def test_syntax_report_retains_unknown_dependencies_without_checking(self):
        declarations = [dict(name=n, module='Chosen.Module') for n in ('ok', 'blocked')]
        preparation = dict(selection=dict(declarations=declarations, selected=2,
            mathlib_commit='pinned', lean_toolchain='pinned', modules=['Chosen.Module'],
            original_theorem_declarations=2, public_theorem_population=2,
            protocol='test selection', enumeration_seconds=0.),
            export_seconds=0., unsupported_reasons={'unsupported constructor': 1})
        documents = [dict(provenance=dict(source_constant='ok', ground_levels=[]),
                         term=['builtin', 'Bool.false'], claim=['builtin', 'Bool'],
                         environment=[dict(name='assumption', type=['sort', 0], value=None)]),
                     dict(provenance=dict(source_constant='blocked', ground_levels=[]),
                          status='UNSUPPORTED', reason='unsupported constructor')]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path/'corpus.jsonl').write_text(''.join(json.dumps(d)+'\n' for d in documents))
            summary = write_syntax_report(preparation, path, 'Bool')
            rows = [json.loads(line) for line in (path/'syntax-outcomes.jsonl').read_text().splitlines()]
        self.assertEqual(summary['counts'], {'EXPORTED': 1, 'UNSUPPORTED': 1})
        self.assertEqual([r['checking_status'] for r in rows], ['NOT_RUN_IN_THIS_REFRESH']*2)
        self.assertEqual(rows[0]['assumptions'], ['assumption'])
        self.assertEqual(rows[0]['input_dag_nodes'], 3)
        self.assertIsNone(rows[1]['environment_declarations'])
        self.assertIsNone(rows[1]['assumptions'])
