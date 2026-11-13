"""OfNat keeps the label in its type and extracts the independently stored field."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class OfNatSmoke(unittest.TestCase):
    def test_uniform_parameters_fields_eta_and_ordinary_numerals(self):
        torch.set_num_threads(1)
        documents = [json.loads(line) for line in
                     (Path(__file__).parent/'fixtures'/'ofnat.jsonl').read_text().splitlines()]
        model = compile_machine(MachineConfig(heap=512, stack=32, context=16,
                                             constants=8, fuel=2048),
                                memory_update='attention_delta')
        self.assertEqual([r['status'] for r in check_batch(model, documents)['results']],
                         ['ACCEPT']*6+['REJECT']*3+['ACCEPT']*3)
