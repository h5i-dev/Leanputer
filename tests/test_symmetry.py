"""Sort-level relational records and authenticated bounded atomic reuse."""
import copy
import json
from pathlib import Path
import unittest
import torch
from leanputer.dependent import Tag
from leanputer.machine_spec import MachineConfig, Op, Outcome, Reason, SpecMachine, prepare
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class SymmetrySmoke(unittest.TestCase):
    def test_carriers_direction_recursion_and_atom_pool_boundaries(self):
        torch.set_num_threads(1)
        cfg = MachineConfig(heap=512, stack=32, context=16, constants=8,
                            fuel=2176, atom_pool=True)
        rows = [json.loads(line) for line in
                (Path(__file__).parent/'fixtures'/'symmetry.jsonl').read_text().splitlines()]
        model = compile_machine(cfg, memory_update='attention_delta')
        self.assertEqual([r['status'] for r in check_batch(model, [rows[i] for i in (0,1,2,7)])['results']],
                         ['ACCEPT', 'ACCEPT', 'REJECT', 'REJECT'])
        base = prepare(cfg, ('builtin','True.intro'), ('builtin','True'))
        corrupt = copy.deepcopy(base)
        corrupt['heap'][1][3] = 1
        full = copy.deepcopy(base)
        for i in range(full['regs']['free'], cfg.heap):
            full['heap'][i] = [int(Tag.VAR), 0, 0, 0]
        full['regs'].update(free=cfg.heap, mode=int(Op.INFER), x=cfg.atom_variables+1)
        overflow = copy.deepcopy(full)
        overflow['regs'].update(mode=int(Op.SHIFT), x=cfg.atom_variables, y=0,
                                z=(1<<cfg.word_bits)-(cfg.atom_variables-1))
        states = [corrupt, full, overflow]
        expected = [SpecMachine(cfg, s).step() for s in states]
        with torch.inference_mode():
            actual = model(torch.cat([model.layout.encode(s) for s in states]))
        self.assertEqual([model.layout.decode(bits.tolist()) for bits in actual], expected)
        self.assertEqual((expected[0]['regs']['status'], expected[0]['regs']['reason']),
                         (Outcome.REJECT, Reason.SYNTAX))
        self.assertEqual((expected[1]['regs']['status'], expected[1]['regs']['r'], expected[1]['regs']['free']),
                         (Outcome.RUNNING, cfg.atom_variables+2, cfg.heap))
        self.assertEqual((expected[2]['regs']['status'], expected[2]['regs']['reason']),
                         (Outcome.RESOURCE, Reason.INDEX))
