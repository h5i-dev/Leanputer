"""HEq K requires convertible carriers and endpoint values."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class HeterogeneousEqualitySmoke(unittest.TestCase):
    def test_types_iota_k_and_both_index_checks(self):
        torch.set_num_threads(1)
        documents=[json.loads(line)for line in(Path(__file__).parent/'fixtures'/'heq.jsonl').read_text().splitlines()]
        model=compile_machine(MachineConfig(heap=256,stack=32,context=16,constants=8,fuel=2304),memory_update='attention_delta')
        self.assertEqual([r['status']for r in check_batch(model,documents)['results']],['ACCEPT']*4+['REJECT']*2+['ACCEPT'])
