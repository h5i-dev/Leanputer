"""Focused fixed-positive primitive/recursor smoke; no broad corpus replay."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class PositivePrimitiveSmoke(unittest.TestCase):
    def test_closed_types_iota_and_restricted_elimination(self):
        torch.set_num_threads(1)
        path=Path(__file__).parent/'fixtures'/'positive.jsonl'
        documents=[json.loads(line)for line in path.read_text().splitlines()]
        model=compile_machine(MachineConfig(heap=256,stack=32,context=16,constants=8,fuel=2048),
                              memory_update='attention_delta')
        results=check_batch(model,documents)['results']
        self.assertEqual([r['status']for r in results],['ACCEPT']*11+['REJECT','REJECT'])
        self.assertEqual([r['reason']for r in results[-2:]],['CONVERSION','CONVERSION'])
