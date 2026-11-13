"""Closed generated types versus independent source algorithm, focused IR."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.admission import analyze_core
from leanputer.kernel.arena import LevelTag
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.native_cells import CellTag,VectorKind
from leanputer.kernel.operations import representation_equal
from leanputer.kernel.recursor import Inductive,Constructor
from tests.test_kernel_constructor_transition import functional_block,core
from tests.test_kernel_minor_transition import cases
from tests.test_kernel_native_cells import vector,decode_syntax
from tests.test_kernel_traversal_machine import CircuitHarness


class RecursorTypeTransitionTest(unittest.TestCase):
    def check_documents(self,cfg,docs,whole=False):
        circuit=CircuitHarness(cfg)
        for doc in docs:
            with self.subTest(label=doc['name']):
                source,args,decls=program.parse_document(doc);state=program.prepare(cfg,source,args,decls);machine=spec.SpecMachine(cfg,state);prefix=None
                for step in range(cfg.fuel+2):
                    r=state['regs']
                    if r['task']==spec.Task.BUILD_RECURSOR_TYPES and r['mode']==spec.Mode.WALK:prefix=deepcopy(state)
                    if whole or prefix is not None:
                        actual=circuit.step(state);self.assertEqual(actual,machine.step(),(doc['name'],step));state=actual
                    else:
                        ref=machine.step();state={'regs':{k:int(v) for k,v in ref['regs'].items()},
                            **{bank:[[int(v) for v in row] for row in ref[bank]] for bank in spec.BANK_FIELDS}}
                    if state['regs']['status']:break
                r=state['regs'];self.assertIsNotNone(prefix)
                self.assertEqual((r['status'],r['reason']),(spec.Outcome.GAP,spec.Reason.GAP_RECURSOR_GENERATION))
                self.assertEqual((r['env_head'],r['decl'],r['raw_index']),(0,0,0))
                self.assertEqual((r['ctx'],r['count'],r['arg_base']),(prefix['regs']['ctx'],prefix['regs']['count'],prefix['regs']['arg_base']))
                self.assertEqual(state['context'][:r['ctx']],prefix['context'][:r['ctx']])
                block=decls[-1];driver=EnvironmentDriver(source);a=driver.a
                levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters)
                inductives=tuple(Inductive(a.const(f.symbol,levels),f.type,tuple(Constructor(ct.symbol,ct.type) for ct in f.constructors),f.recursor_symbol) for f in block.families)
                analysis=analyze_core(driver.services,inductives,block.universe_parameters,block.parameters,r['elim_fresh'] or len(driver.symbols.names)+1)
                packed=SimpleNamespace(heap=state['heap'][:r['free']]);_,decoded=decode_syntax(packed,a)
                infos=vector(packed,r['core_rec_types'],VectorKind.REFERENCES)
                self.assertEqual(len(infos),len(block.families))
                for info,family,recursor in zip(infos,block.families,analysis.recursors):
                    tag,signature,type_ref,symbol=state['heap'][info]
                    self.assertEqual((tag,symbol),(CellTag.RECURSOR_TYPE,recursor.symbol))
                    self.assertEqual(state['heap'][signature][1],family.symbol)
                    self.assertTrue(representation_equal(a,decoded[type_ref],recursor.type),doc['name'])
                self.assertEqual(circuit.step(state),state)

    def test_generic_closed_types_preserve_persistent_scope(self):
        cfg=spec.MachineConfig(heap=512,stack=16,context=16,constants=2,fuel=4096,word_bits=10)
        self.check_documents(cfg,cases())

    def test_task_scoped_control_stays_valid_at_eight_bit_minimum(self):
        block=functional_block();block['families'][0]['constructors']=[]
        cfg=spec.MachineConfig(heap=128,stack=16,context=8,constants=2,fuel=512,word_bits=8)
        self.check_documents(cfg,[core('word8-empty-predicate-closed-type',block)],whole=True)


if __name__=='__main__':unittest.main()
