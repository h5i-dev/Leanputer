"""Pinned environment::check_name permits a fresh anonymous name.

Symbol zero remains the physical sentinel. The anonymous structured path is an
ordinary interned positive symbol ID, so no kernel/data interface is special.
"""
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from tests.test_kernel_traversal_machine import CircuitHarness


class AnonymousSourceTest(unittest.TestCase):
    def test_empty_name_path_is_data_in_ordinary_and_inductive_transactions(self):
        prop=['sort',['zero']];truth=['pi',0,prop,['pi',0,['var',0],['var',1]]]
        proof=['lam',0,prop,['lam',0,['var',0],['var',0]]]
        ordinary=dict(format='leanputer.kernel-source.v1',status='EXPORTED',declarations=[],target=dict(
            kind='theorem',name=[],level_params=[],type=truth,value=proof))
        empty=['const',[],[]]
        inductive=dict(format='leanputer.kernel-source.v1',status='EXPORTED',declarations=[dict(
            kind='inductive_block',level_params=[],parameters=0,recursor_claims=[],families=[dict(
                name=[],recursor_name=[{'str':'rec'}],type=prop,constructors=[])])],target=dict(
                    kind='theorem',name=[{'str':'identity'}],level_params=[],type=['pi',0,empty,empty],value=['lam',0,empty,['var',0]]))
        cfg=spec.MachineConfig(heap=512,stack=32,context=8,constants=2,word_bits=10,fuel=8192)
        circuit=CircuitHarness(cfg)
        for doc in (ordinary,inductive):
            source,args,decls=program.parse_document(doc);self.assertEqual(EnvironmentDriver(source).check().status,'ACCEPT')
            source,args,decls=program.parse_document(doc);state=program.prepare(cfg,source,args,decls);machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
                if state['regs']['status']:break
            self.assertEqual((state['regs']['status'],state['regs']['reason']),(spec.Outcome.DONE,0))
            self.assertEqual(state['regs']['published_declarations'],2 if doc['declarations'] else 0)
            self.assertEqual(state['regs']['ctx'],0)


if __name__=='__main__':unittest.main()
