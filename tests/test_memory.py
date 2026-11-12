import itertools
import unittest

import torch

from leanputer.bitvec import Builder
from leanputer.memory import AddressedRead


torch.set_num_threads(1)


class SharedSubstrateTests(unittest.TestCase):
    def test_exhaustive_small_bitvectors(self):
        width = 4
        b = Builder([f'{v}/{i}' for v in ('a', 'b') for i in range(width)])
        a, c = tuple(b.inputs[:width]), tuple(b.inputs[width:])
        subtraction, borrow = b.sub(a, c)
        outputs = [b.eq(a, c), b.lt(a, c), borrow] + list(b.add(a, c)) + list(subtraction)
        module = b.compile(outputs)
        values = list(itertools.product(range(16), repeat=2))
        bits = torch.tensor([[float(bool(v & (1 << i))) for v in pair for i in range(width)] for pair in values])
        actual = module(bits).tolist()
        for (a, c), row in zip(values, actual):
            self.assertEqual(row[:3], [int(a == c), int(a < c), int(a < c)])
            self.assertEqual(sum(int(x) << i for i, x in enumerate(row[3:7])), (a+c) % 16)
            self.assertEqual(sum(int(x) << i for i, x in enumerate(row[7:])), (a-c) % 16)

    def test_address_attention_all_positions_and_devices(self):
        generator = torch.Generator().manual_seed(674)
        for cells in [2, 4, 16, 64, 256]:
            read = AddressedRead(cells)
            addresses = torch.tensor([[[float(bool(i & (1 << j))) for j in range(read.bits)] for i in range(cells)]])
            memory = torch.randint(0, 2, (1, cells, 19), generator=generator).float()
            with torch.autocast('cpu', dtype=torch.bfloat16):
                self.assertTrue(torch.equal(read(addresses, memory), memory))
            if torch.cuda.is_available():
                gpu = AddressedRead(cells).cuda()
                with torch.autocast('cuda', dtype=torch.float16):
                    self.assertTrue(torch.equal(gpu(addresses.cuda(), memory.cuda()).cpu(), memory))

    def test_address_domain(self):
        for cells in (0, 1, 3, 31):
            with self.assertRaises(ValueError):
                AddressedRead(cells)

class LoweringEquivalenceTests(unittest.TestCase):
    def test_borrow_and_reference_equivalence_exhaustive(self):
        values = list(itertools.product(range(16), repeat=2))
        bits = torch.tensor([[float(bool(v & (1 << i))) for v in pair for i in range(4)] for pair in values])
        for initial in (False, True):
            results = []
            for optimized in (False, True):
                b = Builder([f'x/{i}' for i in range(8)], optimized=optimized)
                subtraction, borrow = b.sub(tuple(b.inputs[:4]), tuple(b.inputs[4:]), borrow_in=initial)
                results.append(b.compile(list(subtraction)+[borrow])(bits))
            self.assertTrue(torch.equal(*results))
            for (a, c), row in zip(values, results[0].tolist()):
                self.assertEqual(sum(int(v) << i for i, v in enumerate(row[:4])), (a-c-int(initial)) % 16)
                self.assertEqual(row[4], int(a < c+int(initial)))

    def test_seeded_wider_arithmetic_and_liveness(self):
        rng = __import__('random').Random(67419)
        width = 12
        values = [(rng.randrange(1 << width), rng.randrange(1 << width)) for _ in range(256)]
        bits = torch.tensor([[float(bool(v & (1 << i))) for v in pair for i in range(width)] for pair in values])
        outputs = []
        for optimized in (False, True):
            b = Builder([f'x/{i}' for i in range(2*width)], optimized)
            a, c = tuple(b.inputs[:width]), tuple(b.inputs[width:])
            difference, borrow = b.sub(a, c)
            result = list(b.add(a, c))+list(difference)+[borrow, b.lt(a, c), b.eq(a, c)]
            outputs.append(b.compile(result)(bits))
        self.assertTrue(torch.equal(*outputs))
        b = Builder(['x'])
        dead = b.inputs[0]
        for _ in range(50):
            dead = b.c.NOT(dead)
        module = b.compile([b.inputs[0]])
        self.assertEqual(len(module.layers), 0)
        self.assertEqual(module(torch.tensor([[0.], [1.]])).tolist(), [[0.], [1.]])
