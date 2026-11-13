"""Typed CORE constructor contracts, never original-source admission evidence."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel import source_transition as original_program
from leanputer.kernel.admission import analyze_core
from leanputer.kernel.arena import LevelTag,KernelError
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.native_cells import CellTag,VectorKind
from leanputer.kernel.recursor import Constructor,Inductive
from tests.test_kernel_source_transition import name,raw
from tests.test_kernel_traversal_machine import CircuitHarness
from tests.test_kernel_native_cells import vector
from types import SimpleNamespace


def core(label,block,dependencies=()):
    return dict(format='leanputer.kernel-core-operation.v1',operation='analyze_core',name=label,block=block,dependencies=list(dependencies))


def functional_block():
    prop=['sort',['zero']];f=['const',name('F'),[]]
    return dict(kind='inductive_block',level_params=[],parameters=0,recursor_claims=[],families=[dict(
        name=name('F'),recursor_name=name('F')+[{'str':'rec'}],type=prop,constructors=[dict(
            name=name('F')+[{'str':'mk'}],type=['pi',0,['pi',0,prop,f],f])])])


def cases():
    block=functional_block();docs=[core('functional-core-block',block)]
    bad=deepcopy(block);family=bad['families'][0];f=['const',name('F'),[]]
    base=name('F')+[{'str':'base'}]
    family['constructors']=[dict(name=base,type=f),dict(name=name('F')+[{'str':'bad'}],type=['const',base,[]])]
    docs.append(core('pending-constructor-is-not-an-assumed-type',bad))
    bad=deepcopy(block);bad['families'][0]['constructors'][0]['type']=['pi',0,['pi',0,f,['sort',['zero']]],f]
    docs.append(core('negative-core-domain',bad))
    assumed=deepcopy(block);assumed['families'][0]['type']=['sort',['succ',['zero']]]
    assumed['families'][0]['constructors'][0]['type']=['pi',0,['const',name('A'),[]],f]
    docs.append(core('previous-checked-environment-visible',assumed,[raw('axiom','A',['sort',['succ',['zero']]])]))
    return docs


def native_cases():
    rows=[json.loads(l) for l in (Path(__file__).parent/'fixtures/kernel-source-smoke.jsonl').read_text().splitlines()[:3]]
    return [core('original-Eq-core-block',rows[2]['declarations'][0]),cases()[0]]


class ConstructorTransitionTest(unittest.TestCase):
    def test_original_source_cannot_supply_core_staging_approval(self):
        cfg=spec.MachineConfig(heap=128,stack=16,context=8,constants=2,fuel=256,word_bits=8)
        circuit=CircuitHarness(cfg)
        # User metadata cannot promote the original-source entry to a core
        # function call or stand in for the missing nested transformation.
        doc=dict(format='leanputer.kernel-source.v1',status='EXPORTED',name='untrusted-core-flags',
            declarations=[functional_block()],target=dict(kind='axiom',name=[],level_params=[],type=['sort',['zero']],value=None),
            core_operation=1,core_index=0,nested_checked=True,admission='ACCEPT')
        state=original_program.prepare(cfg,*original_program.parse_document(doc));machine=spec.SpecMachine(cfg,state)
        for step in range(cfg.fuel+2):
            actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
            if state['regs']['status']:break
        r=state['regs']
        self.assertEqual((r['status'],r['reason']),(spec.Outcome.GAP,spec.Reason.GAP_INDUCTIVE))
        self.assertEqual((r['core_operation'],r['typing_active'],r['decl'],r['env_head']),(0,0,0,0))

    def test_all_schemes_fields_and_pending_metadata_preserve_trust_boundary(self):
        cfg=spec.MachineConfig(heap=512,stack=32,context=16,constants=4,fuel=4096,word_bits=10)
        circuit=CircuitHarness(cfg)
        expected=[('GAP','GAP_RECURSOR_GENERATION',0),('INVALID','UNKNOWN_CONSTANT',0),
                  ('INVALID','NEGATIVE_OCCURRENCE',0),('GAP','GAP_RECURSOR_GENERATION',1)]
        for doc,(outcome,reason,admitted) in zip(cases(),expected):
            source,index,decls=program.parse_document(doc)
            state=program.prepare(cfg,source,index,decls);machine=spec.SpecMachine(cfg,state)
            self.assertEqual((state['regs']['typing_active'],state['regs']['env_head']),(0,0))
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),(doc['name'],step));state=actual
                if state['regs']['status']:break
            r=state['regs']
            self.assertEqual((spec.Outcome(r['status']).name,spec.Reason(r['reason']).name),(outcome,reason),(doc['name'],r))
            self.assertEqual((r['decl'],r['raw_index'],r['typing_active']),(admitted,index,1))
            self.assertEqual(bool(r['env_head']),bool(admitted))
            self.assertNotEqual(r['typing_head'],r['env_head'])
            self.assertFalse(any(row[0]==CellTag.PENDING_CONSTRUCTOR for row in program.prepare(cfg,source,index,decls)['heap']))
            driver=EnvironmentDriver(program.parse_document(doc)[0])
            for dependency in driver.source.declarations[:-1]:driver._ordinary(dependency,True)
            block=driver.source.declarations[-1];a=driver.a
            levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters)
            inds=tuple(Inductive(a.const(f.symbol,levels),f.type,
                tuple(Constructor(c.symbol,c.type) for c in f.constructors),f.recursor_symbol) for f in block.families)
            fresh=len(driver.symbols.names)+1
            if outcome=='INVALID':
                with self.assertRaises(KernelError):analyze_core(driver.services,inds,block.universe_parameters,block.parameters,fresh)
            else:
                analysis=analyze_core(driver.services,inds,block.universe_parameters,block.parameters,fresh)
                expected_fields={c.symbol:c for f in analysis.families for c in f.constructors}
                seen=[];cursor=r['ctor_names'];packed=SimpleNamespace(heap=state['heap'])
                while cursor:
                    tag,entry,cursor,_=state['heap'][cursor];self.assertEqual(tag,CellTag.VECTOR_CELL)
                    tag,symbol,raw_type,meta=state['heap'][entry];self.assertEqual(tag,CellTag.PENDING_CONSTRUCTOR)
                    tag,family,fields,args=state['heap'][meta];self.assertEqual(tag,CellTag.CONSTRUCTOR_ANALYSIS)
                    fields=vector(packed,fields,VectorKind.REFERENCES);want=expected_fields[symbol]
                    self.assertEqual(len(fields),want.fields)
                    recursive=[]
                    for ordinal,field in enumerate(fields):
                        tag,record,descriptor,stored_ordinal=state['heap'][field]
                        self.assertEqual((tag,stored_ordinal),(CellTag.CONSTRUCTOR_FIELD,ordinal))
                        self.assertEqual(state['heap'][record][0],CellTag.LOCAL_DECL)
                        if descriptor:self.assertEqual(state['heap'][descriptor][0],CellTag.RECURSIVE_ARGUMENT);recursive.append(ordinal)
                    self.assertEqual(tuple(recursive),want.recursive_fields);seen.append(symbol)
                self.assertEqual(set(seen),set(expected_fields))
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
