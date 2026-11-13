"""Raw kernel recursion flags must survive normalization-erased occurrences."""
from copy import deepcopy
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.native_cells import CellTag
from tests.test_kernel_constructor_transition import core,functional_block
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness


def cases():
    prop=['sort',['zero']];sort1=['sort',['succ',['zero']]];f=['const',name('F'),[]]
    # F occurs in a dead Let value. Positivity/recursive-argument analysis
    # normalizes that Let; source is_rec/is_reflexive deliberately do not.
    erased=['let',sort1,f,prop]
    domains=[prop,erased,['pi',0,prop,erased]]
    docs=[]
    for label,domain in zip(('nonrecursive','erased-direct','erased-functional'),domains):
        block=functional_block();block['families'][0]['type']=sort1
        block['families'][0]['constructors'][0]['type']=['pi',0,domain,f]
        docs.append(core(label,block))
    docs.append(core('genuine-functional',functional_block()))
    return docs


class BlockFlagsTransitionTest(unittest.TestCase):
    def test_generic_raw_field_scan_is_distinct_from_normalized_descriptors(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=2048,word_bits=9)
        circuit=CircuitHarness(cfg)
        for doc,(recursive,reflexive) in zip(cases(),((0,0),(1,0),(1,1),(1,1))):
            with self.subTest(label=doc['name']):
                state=program.prepare(cfg,*program.parse_document(doc));machine=spec.SpecMachine(cfg,state);prefix=None
                for step in range(cfg.fuel+2):
                    r=state['regs']
                    if r['task']==spec.Task.BLOCK_FLAGS and r['mode']==spec.Mode.WALK:prefix=deepcopy(state)
                    if prefix is not None or doc['name']=='erased-functional':
                        actual=circuit.step(state);self.assertEqual(actual,machine.step(),(doc['name'],step));state=actual
                    else:
                        ref=machine.step();state={'regs':{k:int(v) for k,v in ref['regs'].items()},
                            **{bank:[[int(v) for v in row] for row in ref[bank]] for bank in spec.BANK_FIELDS}}
                    r=state['regs']
                    if r['mode']==spec.Mode.RETURN and r['sp'] and state['stack'][r['sp']-1][0]==spec.CALL_SOURCE_FLAGS:break
                    if r['status']:break
                self.assertIsNotNone(prefix)
                r,p=state['regs'],prefix['regs'];self.assertEqual((r['status'],r['mode']),(spec.Outcome.RUNNING,spec.Mode.RETURN))
                self.assertEqual(state['heap'][r['core_flags']],[CellTag.BLOCK_FLAGS,recursive,reflexive,0])
                self.assertEqual((r['ctx'],r['count'],r['arg_base'],r['env_head'],r['decl'],r['typing_head']),
                    (p['ctx'],p['count'],p['arg_base'],0,0,p['typing_head']))
                self.assertEqual(state['context'][:p['ctx']],prefix['context'][:p['ctx']])
                descriptors=[row[2] for row in state['heap'][:r['free']] if row[0]==CellTag.CONSTRUCTOR_FIELD]
                self.assertEqual(len(descriptors),1)
                self.assertEqual(bool(descriptors[0]),doc['name']=='genuine-functional')


if __name__=='__main__':unittest.main()
