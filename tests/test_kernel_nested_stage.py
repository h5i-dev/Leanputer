"""Growing whole-mutual staging from original syntax; no source publication claim.

Prior metadata here is derived by CORE, then put into an explicit private ABI
fixture. Original-source registration/restoration/publication remain required.
Independent nested.py supplies semantic expectations; the native loader never
calls it. Selected Boolean checks belong to the original-source integration test.
"""
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import json
import unittest
from leanputer.kernel import source_transition as program, traversal_machine as spec
from leanputer.kernel.arena import Tag
from leanputer.kernel.native_cells import CellTag, VectorKind
from leanputer.kernel.nested import NestedSpecializer, PriorBlock
from leanputer.kernel.recursor import Inductive, Constructor
from leanputer.kernel.operations import representation_equal, transform
from tests.test_kernel_native_cells import vector, decode_syntax


def run(cfg,state):
    machine=spec.SpecMachine(cfg,state)
    for step in range(cfg.fuel+2):
        machine.step()
        if machine.state['regs']['status']:return machine.state,step+1
    raise AssertionError('no halt')


class NestedStageTest(unittest.TestCase):
    def test_growing_mutual_queue_matches_independent_specializer(self):
        doc=json.loads(Path('tests/fixtures/kernel-nested-source.jsonl').read_text())
        source,args,decls=program.parse_document(doc)
        cfg=spec.MachineConfig(heap=8192,stack=64,context=64,constants=4,fuel=100000,word_bits=14)
        initial=program.prepare(cfg,source,args,decls)
        initial['regs'].update(core_operation=1,core_index=0)
        base,_=run(cfg,initial)
        self.assertEqual((base['regs']['status'],base['regs']['reason']),(spec.Outcome.GAP,spec.Reason.GAP_RECURSOR_GENERATION))
        def cell(tag,a=0,b=0,c=0):
            ref=base['regs']['free'];base['heap'][ref]=list(map(int,(tag,a,b,c)));base['regs']['free']+=1;return ref
        origin=cell(CellTag.BLOCK_ORIGIN,base['constants'][0][5],base['constants'][0][2],base['regs']['core_family_vector'])
        registry=cell(CellTag.VECTOR_CELL,origin)
        base['regs'].update(status=0,reason=0,fuel=cfg.fuel,sp=0,task=int(spec.Task.NESTED_STAGE),mode=int(spec.Mode.WALK),stage_pc=0,
            x=base['constants'][1][5],stage_uparams=base['constants'][1][2],nested_registry_head=registry,
            ctx=0,count=0,arg_base=0,local_base=0,typing_active=0,typing_head=0,env_head=0)
        base={'regs':{k:int(v) for k,v in base['regs'].items()},**{bank:[[int(v) for v in row] for row in base[bank]] for bank in spec.BANK_FIELDS}}
        before=deepcopy(base);state,steps=run(cfg,base)
        self.assertEqual((state['regs']['status'],state['regs']['reason']),(spec.Outcome.DONE,0),
            (steps,{k:state['regs'][k] for k in ('task','mode','stage_pc','copy_pc','free','x')}))
        for key in ('env_head','typing_head','decl','raw_index','nested_registry_head','ctx','count','arg_base'):
            self.assertEqual(state['regs'][key],before['regs'][key],key)
        self.assertEqual(state['heap'][:before['regs']['free']],before['heap'][:before['regs']['free']])
        heap=SimpleNamespace(heap=state['heap'][:state['regs']['free']])
        _,expressions=decode_syntax(heap,source.arena)
        block=heap.heap[state['regs']['r']]
        self.assertEqual((block[0],block[1]),(CellTag.RAW_BLOCK,2))
        refs=vector(heap,block[2],VectorKind.REFERENCES)
        self.assertEqual(len(refs),3) # Data expectation from this fixture, no compiled branch.
        # Arena LevelTag.PARAM is imported explicitly to avoid relying on its encoding.
        from leanputer.kernel.arena import LevelTag,LocalContext
        def raw_inductives(raw):
            levels=tuple(source.arena.level(LevelTag.PARAM,p) for p in raw.universe_parameters)
            return tuple(Inductive(source.arena.const(f.symbol,levels),f.type,tuple(Constructor(c.symbol,c.type) for c in f.constructors),f.recursor_symbol) for f in raw.families)
        prior=decls[0];current=decls[1]
        expected=NestedSpecializer(source.arena,LocalContext(source.arena),source.symbols,
            [PriorBlock(prior.universe_parameters,prior.parameters,raw_inductives(prior))]).specialize(
                raw_inductives(current),current.universe_parameters,current.parameters)
        renaming={}
        for ref,family in zip(refs,expected.families):
            _,symbol,_,aux=heap.heap[ref];renaming[symbol]=source.arena.expr(family.constant).a
            ctor_refs=vector(heap,heap.heap[aux][1],VectorKind.REFERENCES)
            self.assertEqual(len(ctor_refs),len(family.constructors))
            renaming[heap.heap[aux][2]]=family.recursor_symbol
            for ctor_ref,ctor in zip(ctor_refs,family.constructors):renaming[heap.heap[ctor_ref][1]]=ctor.symbol
        def renamed(root):
            def visit(ref,depth):
                row=source.arena.expr(ref)
                if row.tag==Tag.CONST and row.a in renaming:return source.arena.const(renaming[row.a],source.arena.vector(row.b))
                return None
            return transform(source.arena,root,visit)
        for ref,family in zip(refs,expected.families):
            _,symbol,type_ref,aux=heap.heap[ref]
            self.assertTrue(representation_equal(source.arena,renamed(expressions[type_ref]),family.type))
            for ctor_ref,ctor in zip(vector(heap,heap.heap[aux][1],VectorKind.REFERENCES),family.constructors):
                self.assertTrue(representation_equal(source.arena,renamed(expressions[heap.heap[ctor_ref][2]]),ctor.type))
        self._restored_original_constructor(cfg,state,source,current,refs,heap,expressions)
        print('nested-stage independent SPEC steps',steps,'heap',state['regs']['free'],flush=True)
    def _restored_original_constructor(self,cfg,state,source,current,refs,heap,expressions):
        native_ctor=vector(heap,heap.heap[heap.heap[refs[0]][3]][1],VectorKind.REFERENCES)[0]
        restore=deepcopy(state)
        restore['regs'].update(status=0,reason=0,fuel=cfg.fuel,sp=0,task=int(spec.Task.RESTORE_NESTED_EXPR),mode=int(spec.Mode.WALK),
            restore_expr_pc=0,restore_rec_map=0,x=heap.heap[native_ctor][2],ctx=0,count=0,arg_base=0,local_base=0)
        restored,steps=run(cfg,restore)
        self.assertEqual((restored['regs']['status'],restored['regs']['reason']),(spec.Outcome.DONE,0),
            (steps,{k:restored['regs'][k] for k in ('task','restore_expr_pc','restore_cb_pc','rewrite_pc','x')}))
        _,decoded=decode_syntax(SimpleNamespace(heap=restored['heap'][:restored['regs']['free']]),source.arena)
        self.assertTrue(representation_equal(source.arena,decoded[restored['regs']['r']],current.families[0].constructors[0].type))
        self.assertEqual((restored['regs']['ctx'],restored['regs']['rewrite_restoring']),(0,0))
        print('nested original constructor restoration independent SPEC steps',steps,flush=True)


if __name__=='__main__':unittest.main()
