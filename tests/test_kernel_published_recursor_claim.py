"""Standalone claims through the original-source driver and current Γ."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from tests.test_kernel_source_nested_transaction import canonical,assert_public_matches_independent
from tests.test_kernel_traversal_machine import CircuitHarness


def claim_row(claim):
    claim=deepcopy(claim);old=claim['level_params'];new=[[{'str':'renamedClaimUniverse'},{'num':i}]for i in range(len(old))]
    def rename(node):
        if isinstance(node,list)and len(node)==2 and node[0]=='param':
            for p,q in zip(old,new):
                if node[1]==p:return ['param',q]
        return [rename(v)for v in node]if isinstance(node,list)else node
    return dict(kind='recursor_claim',name=claim['name'],level_params=new,type=['mdata',rename(claim['type'])])


class PublishedRecursorClaimTest(unittest.TestCase):
    def test_original_source_claims_current_lookup_scope_and_atomic_failures(self):
        base=json.loads(Path('tests/fixtures/kernel-nested-source.jsonl').read_text())
        cfg=spec.MachineConfig(heap=32768,stack=128,context=128,constants=16,fuel=600000,word_bits=16)
        circuit=CircuitHarness(cfg);seen=set();checks=0
        for kind in ('accepted','unknown','not-recursor','type','arity','duplicate','scope','heap'):
            doc=deepcopy(base)
            if kind=='accepted':
                claims=[claim_row(c)for block in base['declarations']for c in block['recursor_claims']]
                doc['declarations']+=claims+[deepcopy(claims[0])]
            else:
                doc['declarations']=doc['declarations'][:1];claim=claim_row(base['declarations'][0]['recursor_claims'][0]);doc['declarations'].append(claim)
                if kind=='unknown':claim['name']=[{'str':'unregisteredGeneratedClaim'}]
                elif kind=='not-recursor':claim['name']=doc['declarations'][0]['families'][0]['name']
                elif kind=='type':claim['type']=['sort',['zero']]
                elif kind=='arity':claim['level_params']=claim['level_params'][:1]
                elif kind=='duplicate':claim['level_params'][1]=claim['level_params'][0]
                elif kind=='scope':claim['type']=['var',0]
            source,args,decls=program.parse_document(doc);driver=EnvironmentDriver(source)
            if kind!='heap':
                oracle=driver.check();self.assertEqual(oracle.status,'ACCEPT'if kind=='accepted'else'REJECT',(kind,oracle))
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls));prefix=None;injected=False
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1]if r['sp']else[0]*6;key=None
                if kind!='accepted'and r['raw_index']==1 and prefix is None:prefix=tuple(r[k]for k in('env_head','nested_registry_head','published_declarations','raw_index','decl'))
                if kind=='heap'and r['task']==spec.Task.CHECK_PUBLISHED_RECURSOR and r['published_claim_pc']==4 and r['mode']==spec.Mode.WALK and not injected:r['free']=cfg.heap-1;injected=True
                if r['task']==spec.Task.CHECK_PUBLISHED_RECURSOR:key=('claim',int(r['mode']),r['published_claim_pc'],bool(r['r']))
                elif r['mode']==spec.Mode.RETURN and frame[3]==spec.Task.CHECK_PUBLISHED_RECURSOR:key=('return',frame[0],frame[1],bool(r['r']))
                elif r['mode']==spec.Mode.RETURN and frame[3]==spec.Task.CHECK_SOURCE and frame[0]==13:key=('source-return',)
                before=canonical(state)if key is not None and key not in seen else None
                state=machine.step();r=state['regs']
                if before is not None:self.assertEqual(circuit.step(before),state,(kind,step,key));seen.add(key);checks+=1
                if r['status']:break
            self.assertEqual(r['status'],spec.Outcome.DONE if kind=='accepted'else spec.Outcome.RESOURCE if kind=='heap'else spec.Outcome.INVALID,(kind,r['reason'],r['task'],r['mode'],r['published_claim_pc']))
            if kind=='accepted':
                self.assertEqual((r['published_declarations'],r['raw_index'],r['sp'],r['ctx']),(12,6,0,0));assert_public_matches_independent(self,state,driver);self.assertEqual(oracle.assumptions,())
            else:self.assertEqual(tuple(r[k]for k in('env_head','nested_registry_head','published_declarations','raw_index','decl')),prefix)
            print('standalone source recursor claim',kind,spec.Outcome(r['status']).name,spec.Reason(r['reason']).name,step+1,'steps',flush=True)
        print('standalone claim selected Boolean ALL-state transitions',checks,flush=True)


if __name__=='__main__':unittest.main()
