"""General checked-body delta/argument-spine contract from pinned kernel source.

Source syntax only. Every private environment is created by weighted admission;
no pre-admitted signatures or host normalization answers are packed.
"""
from copy import deepcopy
import unittest
from leanputer.kernel import source_transition as program
from leanputer.kernel import traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from tests.test_kernel_source_transition import name, raw, source
from tests.test_kernel_traversal_machine import CircuitHarness


def cases():
    zero=['zero'];one=['succ',zero]
    prop=['sort',zero];type0=['sort',one]
    const=lambda s,us=[]:['const',name(s),us]
    u=name('u');v=name('v')
    a=raw('definition','U',type0,prop)
    p=raw('axiom','p',const('U'))
    hp=raw('axiom','hp',const('p'))
    target=raw('theorem','proof',const('p'),const('hp'))
    docs=[source('delta-alias-type-sort',[a,p,hp],target)]
    opaque=deepcopy(a);opaque['kind']='opaque'
    docs.append(source('opaque-body-not-unfolded',[opaque,p,hp],target))
    # Full application spine survives delta -> beta -> metadata -> zeta.
    identity_type=['pi',0,type0,type0]
    identity=raw('definition','typeId',identity_type,['lam',0,type0,['var',0]])
    alias=raw('definition','U',type0,['app',const('typeId'),prop])
    docs.append(source('delta-application-spine',[identity,alias,p],raw('definition','proof',['pi',0,const('p'),const('p')],['lam',0,const('p'),['var',0]])))
    # Scheme lengths and actual levels are DATA; two parameters use the same zip.
    maximum=['max',['param',u],['param',v]]
    generic=raw('definition','U',['sort',['succ',maximum]],['sort',maximum],[u,v])
    ua=const('U',[zero,one])
    dep=raw('axiom','A',ua)
    value=['lam',0,const('A'),['var',0]]
    ty=['pi',0,const('A'),const('A')]
    docs.append(source('delta-two-universe-parameters',[generic,dep],raw('definition','proof',ty,value)))
    # Multiple arguments in a definition body use the existing one-at-a-time
    # capture-avoiding algorithm, not an arity-specific branch.
    two_type=['pi',0,type0,['pi',0,type0,type0]]
    two=raw('definition','choose',two_type,['lam',0,type0,['lam',0,type0,['var',1]]])
    applied=['app',['app',const('choose'),prop],prop]
    docs.append(source('delta-two-argument-metadata-let',[two,raw('definition','U',type0,
        ['mdata',['let',type0,applied,['var',0]]]),p],raw('definition','proof',['pi',0,const('p'),const('p')],['lam',0,const('p'),['var',0]])))
    return docs


class DeltaTransitionTest(unittest.TestCase):
    def test_checked_bodies_and_symbolic_scheme_zip_share_the_reduction_loop(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=4,fuel=1024,word_bits=9)
        circuit=CircuitHarness(cfg)
        for doc in cases():
            state=program.prepare(cfg,*program.parse_document(doc))
            machine=spec.SpecMachine(cfg,state)
            delta_reads=0
            for step in range(cfg.fuel+2):
                if state['regs']['mode']==spec.Mode.CONST_SCHEME and state['regs']['task']==spec.Task.BETA_ZETA:
                    delta_reads+=1
                actual=circuit.step(state)
                self.assertEqual(actual,machine.step(),(doc['name'],step))
                state=actual
                if state['regs']['status']:break
            r=state['regs']
            self.assertGreater(delta_reads,0,doc['name'])
            want=('GAP','GAP_CONVERSION') if doc['name']=='opaque-body-not-unfolded' else ('DONE','NONE')
            self.assertEqual((spec.Outcome(r['status']).name,spec.Reason(r['reason']).name),want,(doc['name'],r))
            independent=EnvironmentDriver(program.parse_document(doc)[0]).check()
            self.assertEqual(independent.status,'REJECT' if want[0]=='GAP' else 'ACCEPT',(doc['name'],independent))
            if want[0]=='DONE':self.assertEqual(r['raw_index'],r['target_index'])
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
