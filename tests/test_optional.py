"""Option universe successors, zero/one-field iota and neutral-major boundary."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class OptionalSmoke(unittest.TestCase):
    def test_types_both_branches_and_restrictions(self):
        torch.set_num_threads(1)
        documents = [json.loads(line) for line in
                     (Path(__file__).parent/'fixtures'/'optional.jsonl').read_text().splitlines()]
        model = compile_machine(MachineConfig(heap=256, stack=32, context=16,
                                             constants=8, fuel=1152),
                                memory_update='attention_delta')
        self.assertEqual([r['status'] for r in check_batch(model, documents)['results']],
                         ['ACCEPT']*8+['REJECT']*3)
