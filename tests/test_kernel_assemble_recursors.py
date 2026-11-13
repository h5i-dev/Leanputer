"""Private recursor metadata/grouping versus the pinned source algorithm."""
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
from tests.test_kernel_minor_transition import cases
from tests.test_kernel_native_cells import vector,decode_syntax
from tests.test_kernel_traversal_machine import CircuitHarness


class AssembleRecursorsTest(unittest.TestCase):
    def test_generic_grouped_counts_rules_schemes_and_private_visibility(self):
        cfg=spec.MachineConfig(heap=512,stack=16,context=16,constants=2,fuel=8192,word_bits=10)
        circuit=CircuitHarness(cfg)
        for doc in cases():
            with self.subTest(label=doc['name']):
                source,args,decls=program.parse_document(doc);state=program.prepare(cfg,source,args,decls);machine=spec.SpecMachine(cfg,state);prefix=None
                for step in range(cfg.fuel+2):
                    r=state['regs']
                    if r['task']==spec.Task.ASSEMBLE_RECURSORS and r['mode']==spec.Mode.WALK:prefix=deepcopy(state)
                    if prefix is not None:
                        actual=circuit.step(state);self.assertEqual(actual,machine.step(),(doc['name'],step));state=actual
                    else:
                        ref=machine.step();state={'regs':{k:int(v) for k,v in ref['regs'].items()},
                            **{bank:[[int(v) for v in row] for row in ref[bank]] for bank in spec.BANK_FIELDS}}
                    rr=state['regs']
                    if rr['mode']==spec.Mode.RETURN and rr['sp'] and state['stack'][rr['sp']-1][0]==spec.CALL_SOURCE_ASSEMBLY:break
                    if state['regs']['status']:break
                r=state['regs'];self.assertIsNotNone(prefix)
                self.assertEqual((r['status'],r['mode']),(spec.Outcome.RUNNING,spec.Mode.RETURN))
                self.assertEqual((r['env_head'],r['decl'],r['raw_index']),(0,0,0))
                self.assertEqual((r['ctx'],r['count'],r['arg_base']),(prefix['regs']['ctx'],prefix['regs']['count'],prefix['regs']['arg_base']))
                self.assertEqual(state['context'],prefix['context'])
                block=decls[-1];driver=EnvironmentDriver(source);a=driver.a
                levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters)
                inds=tuple(Inductive(a.const(f.symbol,levels),f.type,tuple(Constructor(ct.symbol,ct.type) for ct in f.constructors),f.recursor_symbol) for f in block.families)
                analysis=analyze_core(driver.services,inds,block.universe_parameters,block.parameters,r['elim_fresh'] or len(driver.symbols.names)+1)
                packed=SimpleNamespace(heap=state['heap'][:r['free']]);_,decoded=decode_syntax(packed,a)
                sigs=vector(packed,r['core_rec_signatures'],VectorKind.REFERENCES)
                self.assertEqual(len(sigs),len(block.families));total=sum(len(f.constructors) for f in block.families)
                for sig,family,rec in zip(sigs,block.families,analysis.recursors):
                    tag,symbol,type_ref,scheme=state['heap'][sig];self.assertEqual((tag,symbol),(CellTag.CHECKED_SIGNATURE,rec.symbol))
                    self.assertTrue(representation_equal(a,decoded[type_ref],rec.type))
                    tag,params,kind,payload=state['heap'][scheme];self.assertEqual((tag,kind),(CellTag.CHECKED_SCHEME,10))
                    self.assertEqual(vector(packed,params,VectorKind.SYMBOLS),rec.universe_parameters)
                    tag,owner,counts,rules=state['heap'][payload];self.assertEqual(tag,CellTag.CHECKED_RECURSOR)
                    self.assertEqual(state['heap'][owner][1],family.symbol)
                    tag,nparams,nindices,shared=state['heap'][counts];self.assertEqual((tag,nparams,nindices),(CellTag.RECURSOR_COUNTS,rec.parameters,rec.indices))
                    tag,nmotives,nminors,block_info=state['heap'][shared]
                    self.assertEqual((tag,nmotives,nminors),(CellTag.RECURSOR_SHARED_COUNTS,len(block.families),total))
                    self.assertEqual(nparams+nindices+nmotives+nminors,rec.major_position)
                    tag,k,flags,families=state['heap'][block_info];self.assertEqual((tag,k),(CellTag.RECURSOR_BLOCK,int(analysis.k_eligible)))
                    self.assertEqual(state['heap'][flags],[CellTag.BLOCK_FLAGS,int(analysis.is_recursive),int(analysis.is_reflexive),0])
                    self.assertEqual([state['heap'][p][1] for p in vector(packed,families,VectorKind.REFERENCES)],[f.symbol for f in block.families])
                    grouped=vector(packed,rules,VectorKind.REFERENCES);self.assertEqual(len(grouped),len(rec.rules))
                    for rule,want in zip(grouped,rec.rules):
                        tag,ctor,nfields,rhs=state['heap'][rule]
                        self.assertEqual((tag,ctor,nfields),(CellTag.CHECKED_RULE,want.constructor,want.fields))
                        self.assertTrue(representation_equal(a,decoded[rhs],want.rhs))
                seen=[];head=r['typing_head']
                while head!=prefix['regs']['typing_head']:
                    tag,sig,head,_=state['heap'][head];self.assertEqual(tag,CellTag.VECTOR_CELL);seen.append(sig)
                self.assertEqual(seen,list(reversed(sigs)))


if __name__=='__main__':unittest.main()
