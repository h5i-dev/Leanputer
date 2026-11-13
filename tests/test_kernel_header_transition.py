"""General previous-Γ header phase, not inductive admission evidence."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.native_cells import CellTag
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness


def cases():
    original=[json.loads(l) for l in (Path(__file__).parent/'fixtures/kernel-source-smoke.jsonl').read_text().splitlines()[:3]]
    docs=[]
    for i in (1,2):
        d=deepcopy(original[0]);d['declarations']=[original[i]['declarations'][0]]
        d['name']=('original-Prod-header' if i==1 else 'original-Eq-header');docs.append(d)
    u=['param',name('u')]
    prop=['sort',['zero']];sortu=['sort',u]
    def family(s,tail):
        return dict(name=name(s),recursor_name=name(s)+[{'str':'rec'}],constructors=[],type=tail)
    # Same A:Sort u/a:A parameters, arbitrary index telescopes; no count class.
    first=['pi',0,sortu,['pi',0,['var',0],['pi',0,['var',1],prop]]]
    second=['pi',0,sortu,['pi',0,['var',0],['pi',0,['pi',0,['var',1],prop],['pi',0,['var',2],prop]]]]
    block=dict(kind='inductive_block',level_params=[name('u')],parameters=2,
        families=[family('F',first),family('G',second)],recursor_claims=[])
    d=deepcopy(original[0]);d.update(name='mutual-dependent-parameters-indices',declarations=[block]);docs.append(d)
    bad=deepcopy(d);bad['name']='nonuniform-parameter-domain';bad['declarations'][0]['families'][1]['type'][2]=['sort',['succ',u]];docs.append(bad)
    bad=deepcopy(d);bad['name']='different-mutual-result-universe';bad['declarations'][0]['families'][1]['type'][3][3][3][3]=['sort',['succ',['zero']]];docs.append(bad)
    bad=deepcopy(d);bad['name']='duplicate-private-header-name';bad['declarations'][0]['families'][1]['name']=name('F');docs.append(bad)
    isolated=deepcopy(d);isolated['name']='private-header-cannot-type-later-header'
    isolated['declarations'][0].update(parameters=0,families=[family('F',prop),family('G',['const',name('F'),[]])]);docs.append(isolated)
    return docs


class HeaderTransitionTest(unittest.TestCase):
    def test_general_headers_use_previous_environment_and_do_not_publish(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=2048,word_bits=9)
        circuit=CircuitHarness(cfg)
        expected=[('GAP','GAP_INDUCTIVE',[0]),('GAP','GAP_INDUCTIVE',[1]),('GAP','GAP_INDUCTIVE',[2,1]),
            ('INVALID','TYPE_MISMATCH',[1]),('INVALID','UNIVERSE',[1]),
            ('INVALID','DUPLICATE_DECLARATION',[1]),('INVALID','UNKNOWN_CONSTANT',[0])]
        for doc,(outcome,reason,indices) in zip(cases(),expected):
            source,args,decls=program.parse_document(doc)
            state=program.prepare(cfg,source,args,decls);machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state)
                self.assertEqual(actual,machine.step(),(doc['name'],step))
                state=actual
                if state['regs']['status']:break
            r=state['regs']
            self.assertEqual((spec.Outcome(r['status']).name,spec.Reason(r['reason']).name),(outcome,reason),(doc['name'],r))
            self.assertEqual((r['decl'],r['raw_index'],r['env_head']),(0,0,0),doc['name'])
            seen=[];head=r['header_head']
            while head:
                tag,sig,head,_=state['heap'][head];self.assertEqual(tag,CellTag.VECTOR_CELL)
                tag,symbol,type_,scheme=state['heap'][sig];self.assertEqual(tag,CellTag.CHECKED_SIGNATURE)
                tag,params,kind,meta=state['heap'][scheme];self.assertEqual((tag,kind),(CellTag.CHECKED_SCHEME,8))
                tag,count,level,raw=state['heap'][meta];self.assertEqual(tag,CellTag.CHECKED_FAMILY)
                self.assertEqual(state['heap'][raw][0],CellTag.RAW_FAMILY);seen.append(count)
            self.assertEqual(seen,indices,doc['name'])
            # An output-only private list is not a checked public environment.
            independent=EnvironmentDriver(program.parse_document(doc)[0]).check()
            if outcome=='INVALID':self.assertEqual(independent.status,'REJECT',(doc['name'],independent))
            else:self.assertIn(independent.status,('ACCEPT','GAP'))
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
