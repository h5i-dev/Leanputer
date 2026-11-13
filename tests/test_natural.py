"""Literal and recursive Nat computations plus explicit numeric resource limits."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class NaturalSmoke(unittest.TestCase):
    def test_recursion_neutral_major_and_numeric_capacity(self):
        torch.set_num_threads(1)
        documents = [json.loads(line) for line in
                     (Path(__file__).parent/'fixtures'/'natural.jsonl').read_text().splitlines()]
        model = compile_machine(MachineConfig(heap=512, stack=32, context=16,
                                             constants=8, fuel=2688),
                                memory_update='attention_delta')
        results = check_batch(model, documents)['results']
        self.assertEqual([r['status'] for r in results],
                         ['ACCEPT']*9+['REJECT']*3+['RESOURCE'])
        self.assertEqual(results[-1]['reason'], 'NATURAL')
