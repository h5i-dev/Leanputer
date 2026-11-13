"""Source-order ctor ordinals and private declaration boundary, generic data."""
from copy import deepcopy
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.native_cells import CellTag,VectorKind
from tests.test_kernel_constructor_transition import functional_block,core
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness
from tests.test_kernel_native_cells import vector
from types import SimpleNamespace


class DeclareConstructorsTest(unittest.TestCase):
    def test_all_checked_constructors_declared_in_source_vector_order(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=2048,word_bits=9)
        circuit=CircuitHarness(cfg);block=functional_block();f=['const',name('F'),[]]
        block['families'][0]['constructors'].insert(0,dict(name=name('F')+[{'str':'base'}],type=f))
        source,index,decls=program.parse_document(core('source-ctor-ordinal',block))
        state=program.prepare(cfg,source,index,decls);machine=spec.SpecMachine(cfg,state)
        entered=False
        for step in range(cfg.fuel+2):
            r=state['regs']
            if r['task']==spec.Task.DECLARE_CONSTRUCTORS and r['mode']==spec.Mode.WALK:
                entered=True
                self.assertEqual((r['core_ctor_declared'],r['typing_head']),(0,r['header_head']))
            actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
            if state['regs']['status']:break
        r=state['regs']
        self.assertTrue(entered)
        self.assertEqual((r['status'],r['reason']),(spec.Outcome.GAP,spec.Reason.GAP_RECURSOR_GENERATION))
        self.assertEqual((r['decl'],r['raw_index'],r['env_head'],r['core_ctor_declared']),(0,0,0,2))
        packed=SimpleNamespace(heap=state['heap']);cursor=r['typing_head'];seen={}
        while cursor!=r['header_head']:
            tag,sig,cursor,_=state['heap'][cursor];self.assertEqual(tag,CellTag.VECTOR_CELL)
            tag,symbol,type_ref,scheme=state['heap'][sig];self.assertEqual(tag,CellTag.CHECKED_SIGNATURE)
            tag,params,kind,info=state['heap'][scheme];self.assertEqual((tag,kind),(CellTag.CHECKED_SCHEME,9))
            tag,family,fields,ordinal=state['heap'][info];self.assertEqual(tag,CellTag.CHECKED_CONSTRUCTOR)
            self.assertEqual(state['heap'][family][1],decls[0].families[0].symbol)
            fields=vector(packed,fields,VectorKind.REFERENCES)
            seen[symbol]=(ordinal,len(fields),type_ref)
        self.assertEqual({symbol:(ordinal,fields) for symbol,(ordinal,fields,type_ref) in seen.items()},
            {ctor.symbol:(i,i) for i,ctor in enumerate(decls[0].families[0].constructors)})
        self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
