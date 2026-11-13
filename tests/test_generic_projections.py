"""Generic projection typing, reduction and binding, including neutral negatives."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest
import torch
from leanputer.generic_spec import MachineConfig, SpecMachine, prepare, Outcome, Reason, Op
from leanputer.generic_syntax import parse_document
from leanputer.generic_transition import compile_machine

CFG = MachineConfig(heap=128,stack=16,context=8,constants=8,fuel=1056)
FIXTURES = Path(__file__).parent/'fixtures'
EXPECTED = ['ACCEPT','ACCEPT','REJECT','REJECT','UNSUPPORTED','REJECT','REJECT','ACCEPT','ACCEPT']


def documents():
    return [json.loads(line) for line in (FIXTURES/'generic-projections.jsonl').read_text().splitlines()]


class GenericProjectionSmoke(unittest.TestCase):
    def test_focused_weighted_binding_and_projection_guards(self):
        torch.set_num_threads(1)
        docs = documents()
        # Retain actual Prop K, full mathlib mt closure, and mixed-field recursor.
        prop = [json.loads(line) for line in (FIXTURES/'generic-prop.jsonl').read_text().splitlines()]
        source = [json.loads(line) for line in (FIXTURES/'generic-source.jsonl').read_text().splitlines()]
        docs += [prop[0],prop[-1],source[2]]
        states = [prepare(CFG,*parse_document(d)) for d in docs]
        self.assertEqual(states[0],states[8])
        refs = [SpecMachine(CFG,s) for s in states]
        model = compile_machine(CFG)
        bits = model.initializer(torch.cat([model.layout.encode(s) for s in states]))
        visited = set()
        with torch.inference_mode():
            for step in range(CFG.fuel+1):
                bits = model(bits)
                for index,(row,ref) in enumerate(zip(bits,refs)):
                    visited.add(ref.state['regs']['mode'])
                    self.assertEqual(model.layout.decode(row.tolist()),ref.step(),(step,index))
        for expected,row in zip(EXPECTED+['ACCEPT']*3,bits):
            r = model.layout.decode(row.tolist())['regs']
            status = 'UNSUPPORTED' if r['reason']==Reason.UNSUPPORTED_DECLARATION else Outcome(r['status']).name
            self.assertEqual(status,expected)
        self.assertTrue({Op.P_FAMILY,Op.P_VALUE,Op.P_REBUILD,Op.P_CONV_DONE} <= visited)

    @unittest.skipUnless(shutil.which('lean'),'independent kernel replay requires Lean')
    def test_actual_lean_projection_replay(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'report.json'
            subprocess.run(['lean','--run',str(root/'tools/lean/ValidateGeneric.lean'),
                            str(FIXTURES/'generic-projections.jsonl'),str(out)],
                           cwd=root,check=True,capture_output=True,timeout=60)
            for actual,expected in zip(json.loads(out.read_text()),EXPECTED):
                if expected != 'UNSUPPORTED':
                    self.assertEqual(actual['status'],expected)
