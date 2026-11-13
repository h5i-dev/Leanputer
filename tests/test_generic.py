"""Focused declaration-as-data checks; no per-name semantic catalog."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import torch

from leanputer.generic_examples import focused_cases
from leanputer.generic_spec import MachineConfig, Outcome, Reason, SpecMachine, prepare
from leanputer.generic_syntax import parse_document, assumptions
from leanputer.generic_transition import compile_machine

CFG = MachineConfig(heap=128, stack=16, context=8, constants=8, fuel=1056)


def metadata_cases():
    base = focused_cases()[0][0]
    cases = []
    for position, key, value in ((1, 'family', 'false'), (3, 'family', 'false'),
                                 (3, 'level', 0), (0, 'constructors', 127)):
        row = deepcopy(base)
        row['environment'][position][key] = value
        cases.append((row, 'REJECT'))
    recursive = deepcopy(base)
    recursive['environment'][1]['type'] = ['pi', ['const', 'Bool'], ['const', 'Bool']]
    cases.append((recursive, 'UNSUPPORTED'))
    unbounded = deepcopy(base)
    unbounded['environment'][3]['level'] = CFG.universe
    cases.append((unbounded, 'RESOURCE'))
    return cases


class GenericDeclarationSmoke(unittest.TestCase):
    def test_renaming_is_identical_input_state(self):
        first, renamed = [prepare(CFG, *parse_document(row)) for row, _ in focused_cases()[:2]]
        self.assertEqual(first, renamed)
        self.assertEqual(assumptions(parse_document(focused_cases()[0][0])[2]), [])

    def test_focused_weighted_transitions_and_metadata_guards(self):
        torch.set_num_threads(1)
        model = compile_machine(CFG)
        cases = focused_cases() + metadata_cases()
        states = [prepare(CFG, *parse_document(row)) for row, _ in cases]
        refs = [SpecMachine(CFG, state) for state in states]
        bits = model.initializer(torch.cat([model.layout.encode(s) for s in states]))
        with torch.inference_mode():
            for step in range(CFG.fuel+1):
                bits = model(bits)
                for index, (row, ref) in enumerate(zip(bits, refs)):
                    self.assertEqual(model.layout.decode(row.tolist()), ref.step(), (step, index))
        for (document, expected), row in zip(cases, bits):
            regs = model.layout.decode(row.tolist())['regs']
            status = ('UNSUPPORTED' if regs['reason'] == Reason.UNSUPPORTED_DECLARATION
                      else Outcome(regs['status']).name)
            self.assertEqual(status, expected, document)

    @unittest.skipUnless(shutil.which('lean'), 'Lean kernel replay requires Lean')
    def test_independent_lean_kernel_replay(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/'input.jsonl', Path(tmp)/'output.json'
            source.write_text(''.join(json.dumps(d)+'\n' for d, _ in focused_cases()))
            subprocess.run(['lean', '--run', str(root/'tools/lean/ValidateGeneric.lean'),
                            str(source), str(output)], cwd=root, check=True, capture_output=True, timeout=60)
            statuses = [r['status'] for r in json.loads(output.read_text())]
            self.assertEqual(statuses[:7], [s for _, s in focused_cases()[:7]])
