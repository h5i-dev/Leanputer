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
