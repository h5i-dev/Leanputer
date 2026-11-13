"""Generic family predicate IR contracts, derived private ABI only.

Internal calls are unit-seeded AFTER authentic weighted header/Local generation;
this is not production proof inference and claims no new stock/source acceptance.
Actual positivity/constructor callers will supply this ABI in weights.
"""
from copy import deepcopy
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.arena import LocalContext,LevelTag
from leanputer.kernel.native_cells import pack_source,CellCapacities
from leanputer.kernel.positivity import BlockTraversal,Family
from leanputer.kernel.services import KernelServices
from leanputer.kernel.telescope import open_telescope,consume_parameters
from tests.test_kernel_header_transition import cases as header_cases
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness


def probes():
    u=['param',name('u')];sortu=['sort',u];prop=['sort',['zero']]
    def app(symbol,levels,args):
        value=['const',name(symbol),levels]
        for arg in args:value=['app',value,arg]
        return value
    a,x,p=['var',2],['var',0],['var',1]
    f=lambda args,levels=[u],symbol='F':app(symbol,levels,args)
    g_inside=app('G',[u],[a,p,x,x])
    bodies=[f([a,p,x]),f([a,x,x]),f([a,p]),f([a,p,x],[['zero']]),
            f([a,p,x],symbol='foreign'),f([a,p,g_inside]),f([a,p,x],[['max',u,['zero']]])]
    docs=[(['pi',0,sortu,['pi',0,['var',0],['pi',0,['var',1],body]]],1) for body in bodies]
    g=app('G',[u],[['var',3],['var',2],['var',1],['var',0]])
    docs.append((['pi',0,sortu,['pi',0,['var',0],['pi',0,['pi',0,['var',1],prop],['pi',0,['var',2],g]]]],2))
    return docs


class FamilyApplicationTest(unittest.TestCase):
    def test_complete_family_levels_uniform_parameters_and_occurrence_free_indices(self):
        cfg=spec.MachineConfig(heap=512,stack=16,context=8,constants=2,fuel=4096,word_bits=10)
        circuit=CircuitHarness(cfg);doc=deepcopy(header_cases()[2]);values=probes()
        aggregate=values[0][0]
        for value,_ in values[1:]:aggregate=['app',aggregate,value]
        doc['target']['value']=aggregate
        source,args,decls=program.parse_document(doc);a=source.arena
        raw_roots=[];cursor=source.target.value
        for _ in range(len(values)-1):row=a.expr(cursor);raw_roots.append(row.b);cursor=row.a
        raw_roots.append(cursor);raw_roots.reverse()
        packed=pack_source(source,CellCapacities(heap=cfg.heap,constants=cfg.constants,word_bits=cfg.word_bits))
        state=program.prepare(cfg,source,args,decls)
        def run(state,until_parent=False):
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual;r=state['regs']
                if until_parent and r['mode']==spec.Mode.RETURN and r['sp']==1 and state['stack'][0][0]==spec.CALL_SOURCE_BLOCK_HEADERS:return state
                if r['status']:return state
            self.fail('nonterminal module')
        prefix=run(state,True);self.assertFalse(prefix['regs']['status'])
        # Independent source operations derive their own Local/family metadata.
        context=LocalContext(a);services=KernelServices(a,context);block=decls[0]
        params=open_telescope(a,context,block.families[0].type,services.whnf,count=block.parameters).locals
        families=[];levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters)
        for family in block.families:
            tail=consume_parameters(a,context,family.type,params,services.whnf,services.convert)
            with context.scope():indices=open_telescope(a,context,tail,services.whnf)
            families.append(Family(a.const(family.symbol,levels),len(indices.locals)))
        traversal=BlockTraversal(a,context,families,params,services.whnf)
        outcomes=[]
        for raw,(_,fields) in zip(raw_roots,values):
            state=deepcopy(prefix);r=state['regs']
            r.update(task=int(spec.Task.CONSUME_PARAMETERS),mode=int(spec.Mode.WALK),x=packed.expression_map[raw],
                reuse_base=r['header_parameter_base'],reuse_end=r['header_parameter_end'],reuse_whnf=0)
            state=run(state,True);self.assertFalse(state['regs']['status'])
            r=state['regs'];r.update(task=int(spec.Task.OPEN_TELESCOPE),mode=int(spec.Mode.TELESCOPE),x=r['r'],
                bounded=1,limit=r['ctx']+fields,open_tag=6)
            state=run(state,True);self.assertFalse(state['regs']['status'])
            r=state['regs'];live,count,base=r['ctx'],r['count'],r['arg_base']
            r.update(task=int(spec.Task.FAMILY_APPLICATION),mode=int(spec.Mode.WALK),x=r['r'])
            state=run(state);r=state['regs']
            with context.scope():
                tail=consume_parameters(a,context,raw,params,services.whnf,services.convert)
                result=open_telescope(a,context,tail,services.whnf,count=fields).body
                expected=traversal.valid_application(result)
            self.assertEqual((r['status'],r['reason']),(spec.Outcome.GAP,spec.Reason.GAP_INDUCTIVE))
            self.assertEqual(bool(r['r']),expected is not None,(raw,r));outcomes.append(bool(r['r']))
            if expected is not None:self.assertEqual(state['heap'][r['r']][1],block.families[expected[0]].symbol)
            self.assertEqual((r['ctx'],r['count'],r['arg_base'],r['sp'],r['env_head'],r['decl']),(live,count,base,1,0,0))
        self.assertEqual(outcomes,[True,False,False,False,False,False,False,True])


if __name__=='__main__':unittest.main()
