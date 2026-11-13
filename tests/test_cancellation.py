"""Cancellation's uniform instance participates in its dependent proof type."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class CancellationSmoke(unittest.TestCase):
    def test_left_right_instances_and_exact_projection_family(self):
        torch.set_num_threads(1)
        rows = [json.loads(line) for line in
                (Path(__file__).parent/'fixtures'/'cancellation.jsonl').read_text().splitlines()]
        rows = [rows[i] for i in (0, 3, 4, 5)]
        model = compile_machine(MachineConfig(heap=512, stack=32, context=16,
                                             constants=8, fuel=1920),
                                memory_update='attention_delta')
        self.assertEqual([r['status'] for r in check_batch(model, rows)['results']],
                         ['ACCEPT', 'ACCEPT', 'REJECT', 'REJECT'])
