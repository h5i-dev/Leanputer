"""Direct strictly-positive recursion derives its own induction hypotheses."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import torch
from leanputer.generic_spec import MachineConfig,SpecMachine,prepare,Outcome,Reason,Op
from leanputer.generic_syntax import parse_document
from leanputer.generic_transition import compile_machine

FIXTURES=Path(__file__).parent/'fixtures'
CFG=MachineConfig(heap=128,stack=16,context=8,constants=8,fuel=1408)
EXPECTED=['ACCEPT']*3+['REJECT','UNSUPPORTED','REJECT','UNSUPPORTED','REJECT','ACCEPT','RESOURCE']


def load(name):return[json.loads(line)for line in(FIXTURES/name).read_text().splitlines()]


class GenericRecursiveSmoke(unittest.TestCase):
    def test_weighted_induction_and_positivity_boundaries(self):
        torch.set_num_threads(1)
        docs=load('generic-recursive.jsonl')
        docs += [load('generic-prop.jsonl')[-1],load('generic-projections.jsonl')[1],
                 load('generic-prop.jsonl')[0],load('generic-source.jsonl')[2]]
        states=[prepare(CFG,*parse_document(d))for d in docs]
        self.assertEqual(states[0],states[1])
        refs=[SpecMachine(CFG,s)for s in states];model=compile_machine(CFG)
        bits=model.initializer(torch.cat([model.layout.encode(s)for s in states]));visited=set()
        with torch.inference_mode():
            for step in range(CFG.fuel+1):
                bits=model(bits)
                for index,(row,ref)in enumerate(zip(bits,refs)):
                    visited.add(ref.state['regs']['mode'])
                    self.assertEqual(model.layout.decode(row.tolist()),ref.step(),(step,index))
        for row,want in zip(bits,EXPECTED+['ACCEPT']*4):
            r=model.layout.decode(row.tolist())['regs']
            actual='UNSUPPORTED'if r['reason']==Reason.UNSUPPORTED_DECLARATION else Outcome(r['status']).name
            self.assertEqual(actual,want)
        self.assertTrue({Op.G_RFIELD,Op.G_IH0,Op.G_RECARG,Op.G_IH_FINISH} <= visited)

    @unittest.skipUnless(shutil.which('lean'),'kernel replay requires Lean')
    def test_independent_recursive_declaration_and_reduction_replay(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory()as tmp:
            out=Path(tmp)/'report.json'
            subprocess.run(['lean','--run',str(root/'tools/lean/ValidateGeneric.lean'),
                            str(FIXTURES/'generic-recursive.jsonl'),str(out)],cwd=root,
                           check=True,capture_output=True,timeout=60)
            for actual,want in zip(json.loads(out.read_text()),EXPECTED):
                if want not in('RESOURCE','UNSUPPORTED'):self.assertEqual(actual['status'],want)
            self.assertEqual(json.loads(out.read_text())[-1]['status'],'ACCEPT')

    def test_actual_nat_and_arbitrary_tally_encode_identically(self):
        tally=load('generic-recursive.jsonl')[0]
        actual_nat=load('generic-native-nat.jsonl')[0]
        self.assertEqual(prepare(CFG,*parse_document(tally)),prepare(CFG,*parse_document(actual_nat)))
        self.assertEqual([r['kind']for r in actual_nat['environment']],
                         ['inductive','constructor','constructor','recursor'])
