"""Two fields, three recursor universes and typed eta retain their distinctions."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class PairSmoke(unittest.TestCase):
    def test_universes_eta_both_fields_and_projection_family(self):
        torch.set_num_threads(1)
        documents=[json.loads(line) for line in
                   (Path(__file__).parent/'fixtures'/'pairs.jsonl').read_text().splitlines()]
        model=compile_machine(MachineConfig(heap=512,stack=32,context=16,
                                          constants=8,fuel=3648),
                              memory_update='attention_delta')
        self.assertEqual([r['status']for r in check_batch(model,documents)['results']],
                         ['ACCEPT']*3+['REJECT']*4+['ACCEPT']*2)
