"""Targeted equality typing/K smoke; broad validation remains deferred."""
import json
from pathlib import Path
import unittest

import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class EqualitySmoke(unittest.TestCase):
    def test_universe_order_k_and_invalid_endpoint(self):
        torch.set_num_threads(1)
        # First claim is actual syntax-only Lean export of @Eq.rec.{0,1}.
        # Second forces K reduction under explicit q : a=a, not just refl.
        # Last must reject even though an equality family is well typed.
        path=Path(__file__).parent/'fixtures'/'equality.jsonl'
        documents=[json.loads(line)for line in path.read_text().splitlines()]
        model=compile_machine(MachineConfig(heap=256,stack=32,context=16,constants=8,fuel=1536),
                              memory_update='attention_delta')
        results=check_batch(model,documents)['results']
        self.assertEqual([r['status']for r in results],['ACCEPT','ACCEPT','REJECT'])
        self.assertEqual(results[-1]['reason'],'CONVERSION')
