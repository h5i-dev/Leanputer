"""Source transactions: only WEIGHTED checks may create private signatures.

Inputs contain raw syntax/claims, never supplied admission or inference answers.
This does not certify missing inductive/primitive/full-conversion callbacks.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from leanputer.kernel import source_transition as program
from leanputer.kernel import traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from tests.test_kernel_traversal_machine import CircuitHarness


def name(s): return [{'str':s}]


def raw(kind, symbol, ty, value=None, parameters=()):
    return dict(kind=kind, name=name(symbol), level_params=list(parameters), type=ty, value=value)


def source(label, declarations, target):
    return dict(format='leanputer.kernel-source.v1',status='EXPORTED',name=label,
                declarations=declarations,target=target)


def cases():
    original=json.loads((Path(__file__).parent/'fixtures/kernel-source-smoke.jsonl').read_text().splitlines()[0])
    dep=deepcopy(original['target'])
    u=dep['level_params'][0]
    v=name('v')
    def rename(node):
        if node == ['param',u]: return ['param',v]
        return [rename(child) for child in node] if isinstance(node,list) else node
    alias=deepcopy(dep);alias.update(name=name('alias'),level_params=[v],type=rename(dep['type']),value=['const',dep['name'],[['param',v]]])
    p=['const',name('p'),[]]
    prop=['sort',['zero']]
    type0=['sort',['succ',['zero']]]
    ty=['pi',0,prop,['pi',0,['var',0],['var',1]]]
    value=['lam',0,prop,['lam',0,['var',0],['var',0]]]
    ax=raw('axiom','p',prop)
    docs=[original, source('checked-polymorphic-dependency',[dep],alias),
        source('pure-theorem',[],raw('theorem','pure',ty,value)),
        source('explicit-axiom-context',[ax,raw('axiom','hp',p)],raw('theorem','proof',p,['const',name('hp'),[]])),
        source('unavailable-nonaxiom',[raw('definition','f',prop)],raw('definition','target',prop,['const',name('f'),[]])),
        source('bad-definition-body',[raw('definition','f',type0,type0)],raw('definition','target',type0,prop)),
        source('universe-arity',[ax],raw('definition','target',prop,['const',name('p'),[['zero']]])),
        source('duplicate-name',[ax,deepcopy(ax)],raw('definition','target',type0,prop)),
        source('forward-dependency',[raw('axiom','first',['const',name('later'),[]]),raw('axiom','later',type0)],raw('definition','target',type0,prop)),
        source('self-reference',[],dict(dep,value=['const',dep['name'],[['param',u]]])),
        source('target-name-collision',[dep],deepcopy(dep)),
        source('theorem-not-prop',[],raw('theorem','bad',type0,prop)),
        source('duplicate-universe',[],dict(dep,level_params=[u,u])),
        source('native-execution-interface',[],dict(dep,name=[{'str':'Lean'},{'str':'reduceNat'}])),
        source('axiom-is-not-a-target-proof',[],raw('axiom','target',prop))]
    docs[0]=deepcopy(docs[0]);docs[0]['name']='original-exported-id'
    return docs


class SourceTransitionTest(unittest.TestCase):
    def test_declarations_check_bodies_before_private_publication(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=4,fuel=1024,word_bits=9)
        circuit=CircuitHarness(cfg)
        expected=[('DONE','NONE',0),('DONE','NONE',1),('DONE','NONE',0),('DONE','NONE',2),
            ('GAP','UNAVAILABLE_BODY',0),('INVALID','TYPE_MISMATCH',0),('INVALID','UNIVERSE_ARITY',1),
            ('INVALID','DUPLICATE_DECLARATION',1),('INVALID','UNKNOWN_CONSTANT',0),('INVALID','UNKNOWN_CONSTANT',0),
            ('INVALID','DUPLICATE_DECLARATION',1),('INVALID','INVALID_DECLARATION',0),
            ('INVALID','DUPLICATE_PARAMETER',0),('UNSUPPORTED_PROFILE','NATIVE_EXECUTION',0),('INVALID','INVALID_DECLARATION',0)]
        self.assertEqual(len(cases()),len(expected))
        for doc,want in zip(cases(),expected):
            source,args,decls=program.parse_document(doc)
            state=program.prepare(cfg,source,args,decls)
            self.assertEqual((state['regs']['env_ready'],state['regs']['env_head'],state['regs']['decl']),(0,0,0))
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state)
                self.assertEqual(actual,machine.step(),(doc['name'],step))
                state=actual
                if state['regs']['status']:break
            r=state['regs']
            got=(spec.Outcome(r['status']).name,spec.Reason(r['reason']).name,r['decl'])
            self.assertEqual(got,want,(doc['name'],r))
            # Every published entry was generated after type/body checks. The
            # input packer cannot emit either checked tag160 or scheme165.
            published=[];cursor=r['env_head']
            while cursor:
                tag,entry,cursor,_=state['heap'][cursor]
                self.assertEqual(tag,49)
                tag,symbol,type_ref,meta=state['heap'][entry]
                self.assertEqual(tag,160);self.assertEqual(state['heap'][meta][0],165)
                published.append(symbol)
            self.assertEqual(len(published),r['decl'])
            assumed=program.assumptions_from_state(decls,r)
            self.assertTrue(all(symbol in published for symbol in assumed))
            independent=EnvironmentDriver(source).check()
            if want[0]=='DONE':
                self.assertEqual(independent.status,'ACCEPT',(doc['name'],independent))
                self.assertEqual(tuple(assumed),independent.assumptions)
                self.assertEqual((r['raw_index'],r['target_index'],r['sp']),(len(decls),len(decls),0))
            elif want[0]=='INVALID':self.assertEqual(independent.status,'REJECT',(doc['name'],independent))
            elif want[0]=='UNSUPPORTED_PROFILE':self.assertEqual(independent.status,'UNSUPPORTED_PROFILE')
            else:self.assertEqual(independent.status,'GAP')
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
