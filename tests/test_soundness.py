"""Adversarial tables and differential checks independent of the encoder."""
import itertools
import random
import unittest

import torch

from leanputer import App as A, Config, Lam as L, ResourceLimit, Var as V, compile_checker, encode
from leanputer.circuit import Circuit
from leanputer.examples import demo_config
from leanputer.terms import infer, reference_check


torch.set_num_threads(1)


class CircuitInvariantTests(unittest.TestCase):
    def test_reject_invalid_builders(self):
        c = Circuit()
        x = c.input('x')
        for op, args in [('xor', (x,)), ('not', ()), ('not', (x, x)), ('and', (-1,)), ('or', (10,))]:
            with self.assertRaises(ValueError):
                c.gate(op, *args)
        with self.assertRaises(ValueError):
            c.input('x')
        c.NOT(x)
        with self.assertRaises(ValueError):
            c.input('late')
        with self.assertRaises(ValueError):
            c.compile([-1])
        self.assertEqual(Circuit().compile([])(torch.empty(2, 0)).shape, (2, 0))

    def test_large_fanin_autocast_and_layer_invariants(self):
        # BF16 and TF32 cannot distinguish 4097 from 4096: unprotected OR
        # cancellation can fail. Exercise both sums and scratch reuse.
        c = Circuit()
        count = 4097
        wires = [c.input(str(i)) for i in range(count)]
        disjunction, conjunction = c.OR(*wires), c.AND(*wires)
        outputs = [disjunction, conjunction, c.NOT(disjunction)]
        model = c.compile(outputs)
        bits = torch.tensor([[0.] * count, [1.] * count, [1.] + [0.] * (count - 1)])
        expected = [[0, 0, 1], [1, 1, 0], [1, 0, 0]]
        with torch.autocast('cpu', dtype=torch.bfloat16):
            self.assertEqual(model(bits).tolist(), expected)
        if torch.cuda.is_available():
            gpu = c.compile(outputs).cuda()
            with torch.autocast('cuda', dtype=torch.float16):
                self.assertEqual(gpu(bits.cuda()).cpu().tolist(), expected)
        x = torch.zeros((3, 2 * model.width))
        x[:, :count] = bits
        for layer in model.layers:
            x = layer(x)
            self.assertTrue(torch.all((x == 0) | (x == 1)))
            self.assertTrue(torch.all(x[:, model.width:] == 0))
        with self.assertRaises(ValueError):
            model.half()(bits)

    def test_config_validation(self):
        for nodes, types in [(0, ('P',)), (True, ('P',)), (2.0, ('P',)), (2, ()),
                             (2, ('P', 'P')), (2, ('',)), (2, ('P', ('P', 'Q'))),
                             (2, ('P', ('P',))), (2, ('P', {}))]:
            with self.assertRaises(ValueError):
                Config(nodes, types)
        self.assertEqual(Config(2, ['P', ['P', 'P']]).types, ('P', ('P', 'P')))

    def test_weights_ignore_default_dtype(self):
        previous = torch.get_default_dtype()
        try:
            torch.set_default_dtype(torch.float64)
            c = Circuit()
            x = c.input('x')
            model = c.compile([c.NOT(x)])
            self.assertTrue(all(b.dtype == torch.float32 for b in model.buffers() if b.is_sparse))
            self.assertEqual(model(torch.tensor([[0.], [1.]])).tolist(), [[1], [0]])
            checker = compile_checker(Config(2, ('P', ('P', 'P'))))
            bits = encode(checker, L('p', 'P', V('p')), ('P', 'P'))
            self.assertEqual(bits.dtype, torch.float32)
            self.assertEqual(checker(bits)[0, :2].tolist(), [1, 0])
        finally:
            torch.set_default_dtype(previous)


class TableSoundnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = compile_checker(demo_config())
        cls.index = {name: i for i, name in enumerate(cls.model.input_names)}

    def mutate(self, term, claim, changes):
        bits = encode(self.model, term, claim)
        for name, bit in changes.items():
            bits[0, self.index[name]] = bit
        return bits

    def test_disconnected_rows_and_padding_references(self):
        identity, ty = L('p', 'P', V('p')), ('P', 'P')
        # Add a disconnected variable in the otherwise padded prefix. Before
        # rootedness validation the unchanged root was accepted.
        disconnected = self.mutate(identity, ty, {
            'tag/0/pad': 0, 'tag/0/var': 1, 'bind/0/15': 1,
        })
        # Root refers to padding instead of its real body.
        padding = self.mutate(identity, ty, {'a/15/14': 0, 'a/15/0': 1})
        self.assertEqual(self.model(torch.cat([disconnected, padding]))[:, :2].tolist(), [[0, 0], [0, 0]])

    def test_forged_scope_sharing_cycles_and_metadata(self):
        # Both variables have type P; redirecting one to a sibling lambda must
        # fail on lexical ancestry, rather than accidentally on type mismatch.
        term = L('p', 'P', A(L('q', 'P', V('q')), V('p')))
        ty = ('P', 'P')
        bits = encode(self.model, term, ty)
        self.assertEqual(self.model(bits)[0, :2].tolist(), [1, 0])
        mutations = [
            {'bind/13/15': 0, 'bind/13/12': 1},  # sibling binder
            {'bind/11/12': 0, 'bind/11/14': 1},  # application is not a binder
            {'a/12/11': 0, 'a/12/12': 1},        # self cycle
            {'a/12/11': 0, 'a/12/15': 1},        # forward edge
            {'b/14/13': 0, 'b/14/11': 1},        # shared child, disconnected row
            {'ann/11/0': 1},                     # inactive annotation
            {'claim/3': 0},                      # no claim
        ]
        raw = torch.cat([self.mutate(term, ty, m) for m in mutations])
        self.assertEqual(self.model(raw)[:, :2].tolist(), [[0, 0]] * len(mutations))

    def test_every_single_bit_flip_is_rejected(self):
        model = compile_checker(Config(6, ('P', 'Q', ('P', 'P'), ('Q', 'Q'))))
        bits = encode(model, L('p', 'P', V('p')), ('P', 'P'))
        # Every bit participates in arity, one-hot, tree, binder, or claim
        # validation. This exhausts all single-bit corruptions of a valid table.
        for start in range(0, bits.shape[1], 32):
            ids = torch.arange(start, min(start + 32, bits.shape[1]))
            batch = bits.repeat(len(ids), 1)
            batch[torch.arange(len(ids)), ids] = 1 - batch[torch.arange(len(ids)), ids]
            self.assertTrue(torch.all(model(batch)[:, :2] == 0), ids.tolist())

    def test_malformed_encoder_inputs_and_json_types(self):
        for term in [None, 3, {}, 'var', ['var'], ['var', 1], ['lam', 'p', [], ['var', 'p']],
                     ['app', ['var', 'p']], ['unknown', 'p']]:
            with self.assertRaises(ValueError):
                encode(self.model, term, ('P', 'P'))
        bits = encode(self.model, ['lam', 'p', 'P', ['var', 'p']], ['P', 'P'])
        self.assertEqual(self.model(bits)[0, :2].tolist(), [1, 0])

    def test_exhaustive_raw_binder_assignments(self):
        # Enumerate all 6^2 binder targets on one branching skeleton, including
        # padding, self-links, non-lambdas, and a lambda in a sibling subtree.
        # Unique binder names let the ordinary recursive oracle decide scope
        # without reproducing the circuit's ancestor computation.
        model = compile_checker(Config(6, ('P', ('P', 'P'))))
        names = {name: i for i, name in enumerate(model.input_names)}
        ty = ('P', 'P')
        template = L('node5', 'P', A(L('node2', 'P', V('node2')), V('node5')))
        original = encode(model, template, ty)
        rows, expected = [], []
        for left, right in itertools.product(range(6), repeat=2):
            bits = original.clone()
            bits[0, names['bind/1/2']] = 0
            bits[0, names['bind/3/5']] = 0
            bits[0, names[f'bind/1/{left}']] = 1
            bits[0, names[f'bind/3/{right}']] = 1
            rows.append(bits)
            term = L('node5', 'P', A(L('node2', 'P', V(f'node{left}')), V(f'node{right}')))
            expected.append(reference_check(term, ty))
        result = model(torch.cat(rows))[:, :2].tolist()
        self.assertEqual([bool(row[0]) for row in result], expected)
        self.assertEqual(sum(expected), 2)
        self.assertTrue(all(row[1] == 0 for row in result))

    def test_overflow_inside_beta_redex(self):
        # The final type P -> P is in the vocabulary, but the inner identity on
        # functions needs (P -> P) -> (P -> P), which this vocabulary omits.
        model = compile_checker(Config(7, ('P', ('P', 'P'))))
        term = A(L('f', ('P', 'P'), V('f')), L('p', 'P', V('p')))
        self.assertTrue(reference_check(term, ('P', 'P')))
        self.assertEqual(model(encode(model, term, ('P', 'P')))[0, :2].tolist(), [0, 1])

    def test_generated_successes_and_all_claims(self):
        rng = random.Random(58461)
        # These generated trees have at most five nodes. A second capacity
        # exercises compilation/configuration independence and keeps this
        # exhaustive claim cross-product inexpensive.
        model = compile_checker(demo_config(nodes=6))
        cases = []
        # Generate closed, well-typed terms independently of the circuit, with
        # beta redexes, shadowing, and higher-order lambda annotations. Checking
        # every compiled claim yields many positive and wrong-statement cases.
        for _ in range(36):
            domain = rng.choice(['P', 'Q', ('P', 'Q')])
            name = rng.choice(['x', 'y'])
            body = V(name)
            if rng.random() < .7:
                body = A(L(name, domain, V(name)), body)
            term = L(name, domain, body)
            inferred = infer(term)
            self.assertIn(inferred, model.config.types)
            cases.extend((term, claim) for claim in model.config.types)
        positives = 0
        for start in range(0, len(cases), 32):
            batch = cases[start:start + 32]
            bits = torch.cat([encode(model, term, claim) for term, claim in batch])
            for (term, claim), result in zip(batch, model(bits).tolist()):
                self.assertEqual(result[1], 0, (term, claim, result))
                self.assertEqual(bool(result[0]), reference_check(term, claim), (term, claim, result))
                positives += result[0]
        self.assertEqual(positives, 36)


if __name__ == '__main__':
    unittest.main()
