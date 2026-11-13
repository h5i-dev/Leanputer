"""Fixed quotient type/iota tests with three unsafe shortcuts rejected."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class QuotientSmoke(unittest.TestCase):
    def test_types_universe_order_and_required_respect(self):
        torch.set_num_threads(1)
        documents=[json.loads(line)for line in(Path(__file__).parent/'fixtures'/'quotient.jsonl').read_text().splitlines()]
        model=compile_machine(MachineConfig(heap=256,stack=32,context=16,constants=8,fuel=1536),memory_update='attention_delta')
        results=check_batch(model,documents)['results']
        self.assertEqual([r['status']for r in results],['ACCEPT']*6+['REJECT']*3+['ACCEPT'])
        self.assertEqual([r['reason']for r in results[6:9]],['CONVERSION']*3)
