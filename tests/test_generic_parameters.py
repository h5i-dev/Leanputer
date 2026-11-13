"""Uniform type-parameter admission validates supplied telescopes and results."""
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
CFG=MachineConfig(heap=128,stack=16,context=8,constants=8,fuel=1536)
EXPECTED=['ACCEPT','ACCEPT','RESOURCE','REJECT','REJECT','UNSUPPORTED','REJECT','REJECT','UNSUPPORTED','ACCEPT','RESOURCE']


def load(name):return[json.loads(line)for line in(FIXTURES/name).read_text().splitlines()]


class GenericParameterSmoke(unittest.TestCase):
    def test_weighted_uniformity_binders_and_phase_scope(self):
        torch.set_num_threads(1)
        docs=load('generic-parameters.jsonl')
        docs += [load('generic-recursive.jsonl')[2],load('generic-projections.jsonl')[1],
                 load('generic-prop.jsonl')[0],load('generic-prop.jsonl')[-1]]
        states=[prepare(CFG,*parse_document(d))for d in docs]
        self.assertEqual(states[0],states[9])
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
        self.assertTrue({Op.G_PARAM_DOMAIN,Op.G_CTOR_SORT,Op.G_U_ARG,Op.G_CTOR_ADMIT}<=visited)
        self.assertTrue(all(not m.state['regs']['permit']for m in refs if m.state['regs']['status']==Outcome.ACCEPT))

    @unittest.skipUnless(shutil.which('lean'),'independent replay requires Lean')
    def test_parameter_declarations_replay_in_actual_kernel(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory()as tmp:
            out=Path(tmp)/'report.json'
            subprocess.run(['lean','--run',str(root/'tools/lean/ValidateGeneric.lean'),
                            str(FIXTURES/'generic-parameters.jsonl'),str(out)],cwd=root,
                           capture_output=True,check=True,timeout=60)
            rows=json.loads(out.read_text())
            for row,want in zip(rows,EXPECTED):
                if want not in('RESOURCE','UNSUPPORTED'):self.assertEqual(row['status'],want)
            self.assertEqual(rows[-1]['status'],'ACCEPT')
