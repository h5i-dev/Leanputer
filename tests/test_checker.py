import itertools
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import torch
from leanputer import Config, compile_checker, App as A, Lam as L, Var as V, encode, ResourceLimit
from leanputer.circuit import Circuit
from leanputer.examples import CASES, demo_config
from leanputer.terms import reference_check


torch.set_num_threads(1)

class CircuitTests(unittest.TestCase):
    def test_boolean_gates_and_scratch_cleanup(self):
        c = Circuit()
        a, b = c.input('a'), c.input('b')
        outputs = [c.AND(a, b), c.OR(a, b), c.NOT(a), c.AND(), c.OR()]
        # Fan-out and multiple circuit depths exercise scratch reuse.
        outputs.append(c.NOT(c.OR(c.AND(a, b), c.NOT(a))))
        model = c.compile(outputs)
        bits = torch.tensor(list(itertools.product([0., 1.], repeat=2)))
        expected = [[a*b, max(a,b), 1-a, 1, 0, 1-max(a*b,1-a)] for a,b in bits.tolist()]
        self.assertEqual(model(bits).tolist(), expected)
        for bad in (float('nan'), float('inf'), .5):
            with self.assertRaises(ValueError):
                model(torch.tensor([[bad, 0.]]))

class CheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = compile_checker(demo_config()).eval()

    def run_cases(self, cases, model=None):
        model = model or self.model
        bits = torch.cat([encode(model, term, ty) for term, ty in cases])
        with torch.inference_mode():
            return model(bits.to(next(model.buffers()).device)).cpu().tolist()

    def test_ten_examples_and_wrong_claims(self):
        good = [(t, ty) for _, t, ty in CASES]
        wrong = [(t, 'P') for _, t, _ in CASES]
        self.assertEqual([r[0] for r in self.run_cases(good)], [1]*10)
        self.assertEqual([r[:2] for r in self.run_cases(wrong)], [[0, 0]]*10)

    def test_shadowing_scope_and_bad_application(self):
        cases = [(L('x', 'P', L('x', 'Q', V('x'))), ('P', ('Q', 'Q'))),
                 (L('x', 'P', V('free')), ('P', 'P')),
                 (L('x', 'P', A(V('x'), V('x'))), ('P', 'P')),
                 (A(L('x', 'P', V('x')), V('x')), 'P')]
        self.assertEqual([r[:2] for r in self.run_cases(cases)], [[1,0], [0,0], [0,0], [0,0]])

    def test_malformed_raw_tables(self):
        original = encode(self.model, CASES[0][1], CASES[0][2])
        names = self.model.input_names
        mutations = []
        for name in ['tag/15/var', 'a/15/15', 'bind/14/14', 'claim/0', 'ann/15/1']:
            bits = original.clone()
            bits[0, names.index(name)] = 1
            mutations.append(bits)
        # Erase the root tag.
        bits = original.clone(); bits[0, names.index('tag/15/lam')] = 0
        mutations.append(bits)
        self.assertTrue(torch.all(self.model(torch.cat(mutations))[:,0] == 0))

    def test_resource_limits(self):
        with self.assertRaises(ResourceLimit):
            encode(self.model, V('x'), 'unknown')
        with self.assertRaises(ResourceLimit):
            encode(compile_checker(Config(1)), CASES[0][1], CASES[0][2])
        model = compile_checker(Config(6, ('P', ('P', 'P'))))
        # Inner identity is representable; its enclosing arrow is not.
        result = self.run_cases([(L('p', 'P', L('q', 'P', V('q'))), ('P', 'P'))], model)[0]
        self.assertEqual(result[:2], [0, 1])

    def test_random_differential(self):
        rng = random.Random(9721)
        domains = ['P', 'Q', ('P','Q'), ('Q','R')]
        def term(depth, scope):
            if depth == 0 or rng.random() < .25:
                return V(rng.choice(scope + ['free']))
            if rng.random() < .55:
                name = f'x{depth}'
                return L(name, rng.choice(domains), term(depth-1, scope+[name]))
            return A(term(depth-1, scope), term(depth-1, scope))
        cases = [(term(3, []), rng.choice(self.model.config.types)) for _ in range(400)]
        cases += [(t, ty) for _, t, ty in CASES] * 4
        checked = 0
        for start in range(0, len(cases), 32):
            batch = cases[start:start+32]
            for (t, ty), result in zip(batch, self.run_cases(batch)):
                if result[1] and not result[0]:
                    continue
                self.assertEqual(bool(result[0]), reference_check(t, ty), (t, ty, result))
                checked += 1
        self.assertGreater(checked, 300)

    @unittest.skipUnless(torch.cuda.is_available(), 'CUDA unavailable')
    def test_cuda_matches_cpu(self):
        model = compile_checker(demo_config()).cuda()
        cases = [(t, ty) for _, t, ty in CASES] + [(V('free'), 'P')]
        self.assertEqual(self.run_cases(cases), self.run_cases(cases, model))

    def test_weights_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'weights.pt'
            torch.save(self.model.state_dict(), path)
            restored = compile_checker(demo_config())
            restored.load_state_dict(torch.load(path, weights_only=True))
            cases = [(t, ty) for _, t, ty in CASES]
            self.assertEqual(self.run_cases(cases), self.run_cases(cases, restored))

    @unittest.skipUnless(shutil.which('lean'), 'Lean unavailable')
    def test_lean_kernel_examples_and_negative(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['lean', str(root/'examples/Proofs.lean')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'Invalid.lean'
            path.write_text('example (P Q : Prop) : P → Q := fun p => p\n')
            result = subprocess.run(['lean', str(path)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

if __name__ == '__main__':
    unittest.main()
