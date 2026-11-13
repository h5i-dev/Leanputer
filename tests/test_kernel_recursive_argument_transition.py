"""General recursive-template IR contracts, not new stock/source acceptance.

Unit internal ABI is entered after weighted headers/Locals, never supplied
checked signatures. Descriptor templates are compared against the independent
source algorithm after renaming only the distinct caller Local namespaces.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.arena import LocalContext,LevelTag,Tag
from leanputer.kernel.native_cells import CellTag,VectorKind,pack_source,CellCapacities
from leanputer.kernel.operations import transform,representation_equal
from leanputer.kernel.positivity import BlockTraversal,Family
from leanputer.kernel.services import KernelServices
from leanputer.kernel.telescope import open_telescope,consume_parameters
from tests.test_kernel_header_transition import cases as header_cases
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness
from tests.test_kernel_native_cells import decode_syntax,vector


def probes():
    u=['param',name('u')];sortu=['sort',u];prop=['sort',['zero']];v=lambda i:['var',i]
    def app(s,args):
        root=['const',name(s),[u]]
        for arg in args:root=['app',root,arg]
        return root
    direct=app('F',[v(3),v(2),v(0)])
    once=['pi',1,v(3),app('F',[v(4),v(3),v(0)])]
    twice=['pi',0,v(3),['pi',1,['app',v(2),v(0)],app('G',[v(5),v(4),v(3),v(1)])]]
    no_recursion=['pi',0,v(3),v(4)]
    domains=[v(3),direct,once,twice,no_recursion]
    return [['pi',0,sortu,['pi',0,v(0),['pi',0,['pi',0,v(1),prop],['pi',0,v(2),root]]]] for root in domains]


class RecursiveArgumentTransitionTest(unittest.TestCase):
    def test_general_dependent_functional_prefix_and_index_templates(self):
        cfg=spec.MachineConfig(heap=512,stack=16,context=16,constants=2,fuel=4096,word_bits=10)
        circuit=CircuitHarness(cfg);doc=deepcopy(header_cases()[2]);values=probes()
        aggregate=values[0]
        for value in values[1:]:aggregate=['app',aggregate,value]
        doc['target']['value']=aggregate
        source,args,decls=program.parse_document(doc);a=source.arena
        roots=[];cursor=source.target.value
        for _ in range(len(values)-1):row=a.expr(cursor);roots.append(row.b);cursor=row.a
        roots.append(cursor);roots.reverse()
        packed=pack_source(source,CellCapacities(heap=cfg.heap,constants=cfg.constants,word_bits=cfg.word_bits))
        def run(state,until_parent=False):
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual;r=state['regs']
                if until_parent and r['mode']==spec.Mode.RETURN and r['sp']==1 and state['stack'][0][0]==spec.CALL_SOURCE_BLOCK_HEADERS:return state
                if r['status']:return state
            self.fail('nonterminal recursive module')
        prefix=run(program.prepare(cfg,source,args,decls),True);self.assertFalse(prefix['regs']['status'])
        context=LocalContext(a);services=KernelServices(a,context);block=decls[0]
        params=open_telescope(a,context,block.families[0].type,services.whnf,count=block.parameters).locals
        levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters);families=[]
        for f in block.families:
            tail=consume_parameters(a,context,f.type,params,services.whnf,services.convert)
            with context.scope():indices=open_telescope(a,context,tail,services.whnf)
            families.append(Family(a.const(f.symbol,levels),len(indices.locals)))
        traversal=BlockTraversal(a,context,families,params,services.whnf)
        result_sizes=[]
        for raw in roots:
            state=deepcopy(prefix);r=state['regs']
            r.update(task=int(spec.Task.CONSUME_PARAMETERS),mode=int(spec.Mode.WALK),x=packed.expression_map[raw],
                reuse_base=r['header_parameter_base'],reuse_end=r['header_parameter_end'],reuse_whnf=0)
            state=run(state,True);self.assertFalse(state['regs']['status']);r=state['regs']
            r.update(task=int(spec.Task.OPEN_TELESCOPE),mode=int(spec.Mode.TELESCOPE),x=r['r'],bounded=1,limit=r['ctx']+2,open_tag=int(Tag.PI))
            state=run(state,True);self.assertFalse(state['regs']['status']);r=state['regs']
            live,count,base=r['ctx'],r['count'],r['arg_base'];original_context=deepcopy(state['context'][:live])
            r.update(task=int(spec.Task.RECURSIVE_ARGUMENT),mode=int(spec.Mode.WALK),x=r['r'])
            state=run(state);r=state['regs']
            self.assertEqual((r['status'],r['reason']),(spec.Outcome.GAP,spec.Reason.GAP_INDUCTIVE),r)
            self.assertEqual((r['ctx'],r['count'],r['arg_base'],r['sp'],r['env_head'],r['decl']),(live,count,base,1,0,0))
            self.assertEqual(state['context'][:live],original_context)
            with context.scope():
                tail=consume_parameters(a,context,raw,params,services.whnf,services.convert)
                caller=open_telescope(a,context,tail,services.whnf,count=2)
                expected=traversal.recursive_argument(caller.body)
                if expected is None:
                    self.assertEqual(r['r'],0);result_sizes.append(None);continue
                self.assertNotEqual(r['r'],0)
                tag,family,prefix_vector,index_vector=state['heap'][r['r']]
                self.assertEqual(tag,CellTag.RECURSIVE_ARGUMENT)
                self.assertEqual(state['heap'][family][1],block.families[expected.family].symbol)
                native=SimpleNamespace(heap=state['heap'][:r['free']]);_,decoded=decode_syntax(native,a)
                rename={}
                for i,local in zip(range(r['header_parameter_base'],live),params+caller.locals):
                    record=state['heap'][state['context'][i][0]];uid=state['heap'][record[1]][1];rename[uid]=local
                def normalize(ref):
                    def visit(ref,depth):
                        row=a.expr(ref)
                        return rename.get(row.a) if row.tag==Tag.LOCAL else None
                    return transform(a,decoded[ref],visit)
                binders=vector(native,prefix_vector,VectorKind.REFERENCES)
                indices=vector(native,index_vector,VectorKind.REFERENCES)
                self.assertEqual((len(binders),len(indices)),(len(expected.prefix),len(expected.indices)))
                for binder,want in zip(binders,expected.prefix):
                    tag,domain,binder_info,reserved=state['heap'][binder]
                    self.assertEqual((tag,binder_info,reserved),(CellTag.PREFIX_BINDER,want.binder_info,0))
                    self.assertTrue(representation_equal(a,normalize(domain),want.domain))
                for index,want in zip(indices,expected.indices):self.assertTrue(representation_equal(a,normalize(index),want))
                result_sizes.append((len(binders),len(indices)))
            self.assertEqual(circuit.step(state),state)
        self.assertEqual(result_sizes,[None,(0,1),(1,1),(2,2),None])


if __name__=='__main__':unittest.main()
