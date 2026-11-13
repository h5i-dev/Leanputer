"""PUnit's Prop/data distinction guards empty-record eta and data recursion."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class UnitSmoke(unittest.TestCase):
    def test_sorts_eta_recursion_and_prop_neutral_restriction(self):
        torch.set_num_threads(1)
        documents = [json.loads(line) for line in
                     (Path(__file__).parent/'fixtures'/'unit.jsonl').read_text().splitlines()]
        model = compile_machine(MachineConfig(heap=128, stack=32, context=16,
                                             constants=8, fuel=1152),
                                memory_update='attention_delta')
        self.assertEqual([r['status'] for r in check_batch(model, documents)['results']],
                         ['ACCEPT']*10+['REJECT']*2+['ACCEPT'])
