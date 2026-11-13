"""Four universes, three distinct carriers and the retained natural boundary."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class HeterogeneousSmoke(unittest.TestCase):
    def test_fourth_level_fields_parameters_and_retained_natural_overflow(self):
        torch.set_num_threads(1)
        rows=[json.loads(line)for line in
              (Path(__file__).parent/'fixtures'/'heterogeneous.jsonl').read_text().splitlines()]
        cfg=MachineConfig(heap=512,stack=32,context=16,constants=8,fuel=3392)
        rows[-1]['claim'][2][2][1]=(1<<cfg.word_bits)-1
        model=compile_machine(cfg,
                              memory_update='attention_delta')
        self.assertEqual([r['status']for r in check_batch(model,rows)['results']],
                         ['ACCEPT']*3+['REJECT']*5+['ACCEPT','RESOURCE'])
