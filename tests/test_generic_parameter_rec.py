"""Derive parameterized eliminators and keep their parameter context scoped."""
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

FIXTURE=Path(__file__).parent/'fixtures/generic-parameter-rec.jsonl'
CFG=MachineConfig(heap=256,stack=32,context=16,constants=8,fuel=2816)
EXPECTED=['ACCEPT']*5+['REJECT']*3+['UNSUPPORTED','RESOURCE','ACCEPT']+['ACCEPT']*4


class GenericParameterizedRecursorSmoke(unittest.TestCase):
    def test_weighted_types_reduction_and_scope(self):
        torch.set_num_threads(1)
        docs=[json.loads(line)for line in FIXTURE.read_text().splitlines()]
        self.assertEqual(len(docs),len(EXPECTED))
        states=[prepare(CFG,*parse_document(d))for d in docs]
        self.assertEqual(states[0],states[10])
        refs=[SpecMachine(CFG,s)for s in states];model=compile_machine(CFG)
        bits=model.initializer(torch.cat([model.layout.encode(s)for s in states]));visited=set();halted={}
        with torch.inference_mode():
            for step in range(CFG.fuel+1):
                bits=model(bits)
                for index,(row,ref)in enumerate(zip(bits,refs)):
                    if index in halted:
                        self.assertTrue(torch.equal(row,halted[index]),(step,index,'absorbing state'))
                        continue
                    visited.add(ref.state['regs']['mode'])
                    expected=ref.step()
                    self.assertEqual(model.layout.decode(row.tolist()),expected,(step,index))
                    if expected['regs']['status']:halted[index]=row.clone()
        for row,want,doc in zip(bits,EXPECTED,docs):
            r=model.layout.decode(row.tolist())['regs']
            actual='UNSUPPORTED'if r['reason']==Reason.UNSUPPORTED_DECLARATION else Outcome(r['status']).name
            self.assertEqual(actual,want)
            if actual=='ACCEPT':
                self.assertEqual((r['ctx'],r['permit']),(0,0))
                self.assertEqual(r['decl'],len(doc['environment']))
        self.assertTrue({Op.R_PARAMS,Op.G_RDOM,Op.G_CVAR,Op.G_RTCSTRIP,Op.G_HEADWALK}<=visited)

    @unittest.skipUnless(shutil.which('lean'),'independent replay requires Lean')
    def test_independent_parameterized_kernel_replay(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory()as tmp:
            out=Path(tmp)/'report.json'
            subprocess.run(['lean','--run',str(root/'tools/lean/ValidateGeneric.lean'),str(FIXTURE),str(out)],
                           cwd=root,capture_output=True,check=True,timeout=60)
            replay=json.loads(out.read_text())
            self.assertEqual(replay[8]['status'],'ACCEPT')
            self.assertEqual(replay[9]['status'],'ACCEPT')
            for row,want in zip(replay,EXPECTED):
                if want not in('RESOURCE','UNSUPPORTED'):self.assertEqual(row['status'],want)
