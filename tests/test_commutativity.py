"""Operation-class witnesses remain distinct from their equality proof fields."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class CommutativitySmoke(unittest.TestCase):
    def test_prop_carrier_high_code_instance_and_class_field_boundary(self):
        torch.set_num_threads(1)
        rows = [json.loads(line) for line in
                (Path(__file__).parent/'fixtures'/'commutativity.jsonl').read_text().splitlines()]
        cfg = MachineConfig(heap=512, stack=32, context=16, constants=8,
                            fuel=1728, atom_pool=True)
        model = compile_machine(cfg, memory_update='attention_delta')
        self.assertEqual([r['status'] for r in check_batch(model, [rows[i] for i in (0,3,4,5)])['results']],
                         ['ACCEPT', 'ACCEPT', 'REJECT', 'REJECT'])
