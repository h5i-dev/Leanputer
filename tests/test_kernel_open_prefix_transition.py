"""Generic recursive-template reopening, internal ABI and independent oracle.

Development transitions derive all headers/Locals/templates; only the new
subroutine is compared stepwise here. No such seeded state enters production
native inference. Composed stock evidence remains separately pinned.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.arena import LocalContext,LevelTag,Tag
from leanputer.kernel.native_cells import CellTag,VectorKind,pack_source,CellCapacities
from leanputer.kernel.operations import transform,representation_equal
from leanputer.kernel.positivity import BlockTraversal,Family
from leanputer.kernel.recursor import open_recursive_prefix
from leanputer.kernel.services import KernelServices
from leanputer.kernel.telescope import open_telescope,consume_parameters
from tests.test_kernel_header_transition import cases as header_cases
from tests.test_kernel_recursive_argument_transition import probes
from tests.test_kernel_native_cells import decode_syntax,vector
from tests.test_kernel_traversal_machine import CircuitHarness


class OpenPrefixTransitionTest(unittest.TestCase):
    def test_dependent_prefixes_indices_and_empty_vectors_share_loops(self):
        cfg=spec.MachineConfig(heap=512,stack=16,context=16,constants=2,fuel=4096,word_bits=10)
        circuit=CircuitHarness(cfg)
        doc=deepcopy(header_cases()[2]);values=probes()[1:4]
        # A second raw block removes F's index; this tests the same empty-vector
        # paths, not a different descriptor implementation.
        empty_doc=deepcopy(doc);empty_doc['declarations'][0]['families'][0]['type'][3][3]=['sort',['zero']]
        empty_value=deepcopy(values[0]);node=empty_value
        for _ in range(3):node=node[3]
        node[3]=node[3][1]
        groups=[(doc,values),(empty_doc,[empty_value])];sizes=[]
        def run(state,weighted=False):
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                if weighted:
                    actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
                else:
                    ref=machine.step();state={'regs':{k:int(v) for k,v in ref['regs'].items()},
                        **{bank:[[int(v) for v in row] for row in ref[bank]] for bank in spec.BANK_FIELDS}}
                r=state['regs']
                if r['mode']==spec.Mode.RETURN and r['sp']==1 and state['stack'][0][0]==spec.CALL_SOURCE_BLOCK_HEADERS:return state
                self.assertFalse(r['status'],(spec.Outcome(r['status']),spec.Reason(r['reason'])))
            self.fail('operation did not return')
        for doc,values in groups:
            aggregate=values[0]
            for value in values[1:]:aggregate=['app',aggregate,value]
            doc['target']['value']=aggregate
            source,args,decls=program.parse_document(doc);a=source.arena
            roots=[];cursor=source.target.value
            for _ in range(len(values)-1):row=a.expr(cursor);roots.append(row.b);cursor=row.a
            roots.append(cursor);roots.reverse()
            packed=pack_source(source,CellCapacities(heap=cfg.heap,constants=cfg.constants,word_bits=cfg.word_bits))
            prefix=run(program.prepare(cfg,source,args,decls));context=LocalContext(a);services=KernelServices(a,context);block=decls[0]
            params=open_telescope(a,context,block.families[0].type,services.whnf,count=block.parameters).locals
            levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters);families=[]
            for family in block.families:
                tail=consume_parameters(a,context,family.type,params,services.whnf,services.convert)
                with context.scope():opened=open_telescope(a,context,tail,services.whnf)
                families.append(Family(a.const(family.symbol,levels),len(opened.locals)))
            traversal=BlockTraversal(a,context,families,params,services.whnf)
            for raw in roots:
                state=deepcopy(prefix);r=state['regs']
                r.update(task=int(spec.Task.CONSUME_PARAMETERS),mode=int(spec.Mode.WALK),x=packed.expression_map[raw],
                    reuse_base=r['header_parameter_base'],reuse_end=r['header_parameter_end'],reuse_whnf=0)
                state=run(state);r=state['regs']
                r.update(task=int(spec.Task.OPEN_TELESCOPE),mode=int(spec.Mode.TELESCOPE),x=r['r'],bounded=1,limit=r['ctx']+2,open_tag=int(Tag.PI))
                state=run(state);r=state['regs'];r.update(task=int(spec.Task.RECURSIVE_ARGUMENT),mode=int(spec.Mode.WALK),x=r['r'])
                state=run(state);r=state['regs'];self.assertNotEqual(r['r'],0)
                live,count,base=r['ctx'],r['count'],r['arg_base'];before=deepcopy(state['context'][:live])
                r.update(task=int(spec.Task.OPEN_RECURSIVE_PREFIX),mode=int(spec.Mode.WALK),x=r['r'])
                state=run(state,weighted=True);r=state['regs'];tag,family,locals_vec,index_vec=state['heap'][r['r']]
                self.assertEqual(tag,CellTag.OPENED_RECURSIVE_PREFIX)
                native=SimpleNamespace(heap=state['heap'][:r['free']]);native_locals=vector(native,locals_vec,VectorKind.REFERENCES)
                native_indices=vector(native,index_vec,VectorKind.REFERENCES)
                self.assertEqual((r['ctx'],r['count'],r['arg_base']),(live+len(native_locals),count,base))
                self.assertEqual(state['context'][:live],before)
                self.assertEqual(tuple(row[0] for row in state['context'][live:r['ctx']]),native_locals)
                with context.scope():
                    tail=consume_parameters(a,context,raw,params,services.whnf,services.convert)
                    caller=open_telescope(a,context,tail,services.whnf,count=2)
                    descriptor=traversal.recursive_argument(caller.body)
                    xs,indices=open_recursive_prefix(a,context,descriptor)
                    self.assertEqual(state['heap'][family][1],block.families[descriptor.family].symbol)
                    self.assertEqual((len(native_locals),len(native_indices)),(len(xs),len(indices)))
                    _,decoded=decode_syntax(native,a);rename={}
                    records=tuple(row[0] for row in state['context'][r['header_parameter_base']:live])+native_locals
                    for record,local in zip(records,params+caller.locals+xs):
                        rename[state['heap'][state['heap'][record][1]][1]]=local
                    def normalized(ref):
                        return transform(a,decoded[ref],lambda ref,depth:rename.get(a.expr(ref).a) if a.expr(ref).tag==Tag.LOCAL else None)
                    for record,x in zip(native_locals,xs):
                        tag,local,type_ref,info=state['heap'][record];self.assertEqual(tag,CellTag.LOCAL_DECL)
                        self.assertEqual(info,context.lookup(x).binder_info)
                        self.assertTrue(representation_equal(a,normalized(type_ref),context.lookup(x).type))
                    for ref,index in zip(native_indices,indices):self.assertTrue(representation_equal(a,normalized(ref),index))
                    sizes.append((len(xs),len(indices)))
        self.assertEqual(sizes,[(0,1),(1,1),(2,2),(0,0)])


if __name__=='__main__':unittest.main()
