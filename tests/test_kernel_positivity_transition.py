"""General strict positivity CORE IR; NOT full original-source block checking.

Full-source nested specialization/constructor typing are preceding stages still
unfinished natively. Unit ABI is seeded only after weighted header/Local
creation. These contracts test finite source operations, not supplied answers.
"""
from copy import deepcopy
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.arena import LocalContext,LevelTag,KernelError
from leanputer.kernel.native_cells import pack_source,CellCapacities
from leanputer.kernel.positivity import BlockTraversal,Family
from leanputer.kernel.services import KernelServices
from leanputer.kernel.telescope import open_telescope,consume_parameters
from tests.test_kernel_header_transition import cases as header_cases
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness


def probes():
    u=['param',name('u')];sortu=['sort',u];prop=['sort',['zero']]
    def family(a,p,index):return ['app',['app',['app',['const',name('F'),[u]],a],p],index]
    v=lambda i:['var',i]
    direct=family(v(2),v(1),v(0))
    once=['pi',0,v(2),family(v(3),v(2),v(0))]
    twice=['pi',0,v(2),['pi',0,v(3),family(v(4),v(3),v(0))]]
    negative=['pi',0,direct,family(v(3),v(2),v(1))]
    later=['pi',0,v(2),['pi',0,family(v(3),v(2),v(0)),family(v(4),v(3),v(1))]]
    bad_index=family(v(2),v(1),direct)
    bad_parameter=family(v(2),v(0),v(0))
    metadata=['mdata',['let',prop,direct,v(0)]]
    domains=[['pi',0,v(2),v(3)],direct,once,twice,negative,later,bad_index,bad_parameter,metadata]
    return [(['pi',0,sortu,['pi',0,v(0),['pi',0,v(1),domain]]],i in (4,5,6,7)) for i,domain in enumerate(domains)]


class PositivityTransitionTest(unittest.TestCase):
    def test_empty_formal_universes_and_nullary_application(self):
        cfg=spec.MachineConfig(heap=128,stack=16,context=8,constants=2,fuel=512,word_bits=8)
        circuit=CircuitHarness(cfg);doc=deepcopy(header_cases()[2])
        block=doc['declarations'][0]
        block.update(level_params=[],parameters=0,families=[dict(name=name('Nullary'),
            recursor_name=name('Nullary')+[{'str':'rec'}],constructors=[],type=['sort',['zero']])])
        doc['target']['value']=['const',name('Nullary'),[]]
        source,args,decls=program.parse_document(doc)
        state=program.prepare(cfg,source,args,decls);machine=spec.SpecMachine(cfg,state)
        for step in range(cfg.fuel+2):
            actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual;r=state['regs']
            if r['mode']==spec.Mode.RETURN and r['sp']==1 and state['stack'][0][0]==spec.CALL_SOURCE_BLOCK_HEADERS:break
            self.assertFalse(r['status'])
        self.assertEqual(state['heap'][r['header_levels']][1:],[0,0,2])
        self.assertEqual((r['header_parameter_base'],r['header_parameter_end'],r['ctx']),(0,0,0))
        root=state['constants'][r['target_index']][4]
        r.update(task=int(spec.Task.CHECK_POSITIVITY),mode=int(spec.Mode.WALK),x=root)
        machine=spec.SpecMachine(cfg,state)
        for step in range(cfg.fuel+2):
            actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
            if state['regs']['status']:break
        r=state['regs']
        self.assertEqual((r['status'],r['reason'],r['r']),(spec.Outcome.GAP,spec.Reason.GAP_INDUCTIVE,1))
        self.assertEqual((r['ctx'],r['count'],r['sp'],r['decl'],r['env_head']),(0,0,1,0,0))

    def test_general_core_loop_and_context_restore(self):
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
        def run(state,until_parent=False):
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual;r=state['regs']
                if until_parent and r['mode']==spec.Mode.RETURN and r['sp']==1 and state['stack'][0][0]==spec.CALL_SOURCE_BLOCK_HEADERS:return state
                if r['status']:return state
            self.fail('nonterminal core operation')
        prefix=run(program.prepare(cfg,source,args,decls),True);self.assertFalse(prefix['regs']['status'])
        context=LocalContext(a);services=KernelServices(a,context);block=decls[0]
        params=open_telescope(a,context,block.families[0].type,services.whnf,count=block.parameters).locals
        levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters);families=[]
        for f in block.families:
            tail=consume_parameters(a,context,f.type,params,services.whnf,services.convert)
            with context.scope():indices=open_telescope(a,context,tail,services.whnf)
            families.append(Family(a.const(f.symbol,levels),len(indices.locals)))
        traversal=BlockTraversal(a,context,families,params,services.whnf)
        for i,(raw,(_,invalid)) in enumerate(zip(raw_roots,values)):
            state=deepcopy(prefix);r=state['regs']
            r.update(task=int(spec.Task.CONSUME_PARAMETERS),mode=int(spec.Mode.WALK),x=packed.expression_map[raw],
                reuse_base=r['header_parameter_base'],reuse_end=r['header_parameter_end'],reuse_whnf=0)
            state=run(state,True);self.assertFalse(state['regs']['status']);r=state['regs']
            r.update(task=int(spec.Task.OPEN_TELESCOPE),mode=int(spec.Mode.TELESCOPE),x=r['r'],bounded=1,limit=r['ctx']+1,open_tag=6)
            state=run(state,True);self.assertFalse(state['regs']['status']);r=state['regs']
            live,count,base=r['ctx'],r['count'],r['arg_base'];original_context=deepcopy(state['context'][:live])
            r.update(task=int(spec.Task.CHECK_POSITIVITY),mode=int(spec.Mode.WALK),x=r['r'])
            state=run(state);r=state['regs']
            with context.scope():
                tail=consume_parameters(a,context,raw,params,services.whnf,services.convert)
                root=open_telescope(a,context,tail,services.whnf,count=1).body
                if invalid:
                    with self.assertRaises(KernelError):traversal.check_positivity(root)
                else:traversal.check_positivity(root)
            if invalid:
                expected=spec.Reason.NEGATIVE_OCCURRENCE if i in (4,5) else spec.Reason.INVALID_INDUCTIVE_APPLICATION
                self.assertEqual((r['status'],r['reason']),(spec.Outcome.INVALID,expected),i)
            else:self.assertEqual((r['status'],r['reason'],r['r']),(spec.Outcome.GAP,spec.Reason.GAP_INDUCTIVE,1),i)
            self.assertEqual((r['ctx'],r['count'],r['arg_base'],r['env_head'],r['decl'],r['raw_index']),(live,count,base,0,0,0),i)
            self.assertEqual(state['context'][:live],original_context,i)
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
