"""Membership keeps both carrier universes and the container-first field."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class MembershipSmoke(unittest.TestCase):
    def test_universes_reversed_arguments_eta_and_family_guards(self):
        torch.set_num_threads(1)
        documents=[json.loads(line)for line in
                   (Path(__file__).parent/'fixtures'/'membership.jsonl').read_text().splitlines()]
        model=compile_machine(MachineConfig(heap=512,stack=32,context=16,constants=8,fuel=2432),
                              memory_update='attention_delta')
        self.assertEqual([r['status']for r in check_batch(model,documents)['results']],
                         ['ACCEPT']*3+['REJECT']*3)
