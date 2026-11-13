import unittest

from leanputer.mathlib_benchmark import select_population


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
