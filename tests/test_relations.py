"""Relation-valued records keep data eta and distinguish fields and families."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class RelationSmoke(unittest.TestCase):
    def test_universes_neutral_rec_and_relation_field_guards(self):
        torch.set_num_threads(1)
        documents = [json.loads(line) for line in
                     (Path(__file__).parent/'fixtures'/'relations.jsonl').read_text().splitlines()]
        model = compile_machine(MachineConfig(heap=256, stack=32, context=16,
                                             constants=8, fuel=1600),
                                memory_update='attention_delta')
        self.assertEqual([r['status'] for r in check_batch(model, documents)['results']],
                         ['ACCEPT']*5+['REJECT']*3)
