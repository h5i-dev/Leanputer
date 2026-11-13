"""Dependent law constructors use the stored operation and exact family."""
import json
from pathlib import Path
import unittest
import torch
from leanputer.machine_spec import MachineConfig, Outcome, SpecMachine, prepare
from leanputer.runner import check_batch, parse_document
from leanputer.transition import compile_machine


class LawRecordSmoke(unittest.TestCase):
    def test_distinct_neutral_data_never_accepts(self):
        rows = [json.loads(line) for line in
                (Path(__file__).parent/'fixtures'/'law-records.jsonl').read_text().splitlines()]
        cfg = MachineConfig(heap=512, stack=32, context=16, constants=8, fuel=3008)
        state = SpecMachine(cfg, prepare(cfg, *parse_document(rows[3]))).run()
        # The present congruence/eta cycle exhausts stack. A future terminating
        # conversion may reject instead; neither result asserts the false equality.
        self.assertIn(Outcome(state['regs']['status']), (Outcome.REJECT, Outcome.RESOURCE))

    def test_constructor_dependent_proof_and_family(self):
        torch.set_num_threads(1)
        rows = [json.loads(line) for line in
                (Path(__file__).parent/'fixtures'/'law-records.jsonl').read_text().splitlines()]
        rows = [rows[i] for i in (0, 1, 2, 5)]
        model = compile_machine(MachineConfig(heap=512, stack=32, context=16,
                                             constants=8, fuel=2368),
                                memory_update='attention_delta')
        self.assertEqual([r['status'] for r in check_batch(model, rows)['results']],
                         ['ACCEPT', 'ACCEPT', 'REJECT', 'REJECT'])
