"""Subtype universe floor, dependent projection, data eta and required rejects."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class SubtypeSmoke(unittest.TestCase):
    def test_types_projections_eta_and_distinct_values(self):
        torch.set_num_threads(1)
        documents=[json.loads(line)for line in(Path(__file__).parent/'fixtures'/'subtype.jsonl').read_text().splitlines()]
        model=compile_machine(MachineConfig(heap=256,stack=32,context=16,constants=8,fuel=2304),memory_update='attention_delta')
        self.assertEqual([r['status']for r in check_batch(model,documents)['results']],['ACCEPT']*9+['REJECT']*2)
