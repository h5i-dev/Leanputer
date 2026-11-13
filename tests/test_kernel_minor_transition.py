"""General generated minors versus independent closed recursor telescopes."""
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.admission import analyze_core
from leanputer.kernel.arena import LevelTag,Tag
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.native_cells import CellTag,VectorKind
from leanputer.kernel.operations import transform,representation_equal
from leanputer.kernel.recursor import Constructor,Inductive
from leanputer.kernel.telescope import open_telescope
from tests.test_kernel_constructor_transition import native_cases,core,functional_block
from tests.test_kernel_header_transition import cases as header_cases
from tests.test_kernel_native_cells import decode_syntax,vector
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness


def cases():
    block=functional_block();f=['const',name('F'),[]];prop=['sort',['zero']]
    block['families'][0]['constructors']=[dict(name=name('F')+[{'str':'base'}],type=f),
        dict(name=name('F')+[{'str':'mk'}],type=['pi',0,prop,['pi',0,['pi',0,prop,f],['pi',0,f,f]]])]
    return [native_cases()[0],core('all-minors-mixed-fields',block),
        core('empty-mutual-indexed-minors',header_cases()[2]['declarations'][0])]


class MinorTransitionTest(unittest.TestCase):
    def test_all_minor_types_functional_ihs_source_order_and_scope(self):
        self.check_documents(cases())

    def test_shared_field_restore_in_mixed_minor_scope(self):
        self.check_documents([cases()[1]])

    def check_documents(self,documents):
        cfg=spec.MachineConfig(heap=512,stack=16,context=16,constants=2,fuel=4096,word_bits=10)
        circuit=CircuitHarness(cfg)
        for doc in documents:
            with self.subTest(label=doc['name']):
                source,args,decls=program.parse_document(doc);state=program.prepare(cfg,source,args,decls);machine=spec.SpecMachine(cfg,state)
                for step in range(cfg.fuel+2):
                    actual=circuit.step(state);self.assertEqual(actual,machine.step(),(doc['name'],step));state=actual
                    rr=state['regs']
                    if rr['mode']==spec.Mode.RETURN and rr['sp'] and state['stack'][rr['sp']-1][0]==spec.CALL_SOURCE_MINORS:break
                    if state['regs']['status']:break
                r=state['regs'];self.assertEqual((r['status'],r['mode']),(spec.Outcome.RUNNING,spec.Mode.RETURN))
                self.assertEqual((r['env_head'],r['decl'],r['raw_index']),(0,0,0))
                block=decls[-1];ctors=tuple(ctor for family in block.families for ctor in family.constructors)
                self.assertEqual(r['ctx'],r['header_parameter_end']+len(block.families)+len(ctors))
                packed=SimpleNamespace(heap=state['heap'][:r['free']]);infos=vector(packed,r['core_minors'],VectorKind.REFERENCES)
                self.assertEqual(len(infos),len(ctors))
                driver=EnvironmentDriver(source);a,c,services=driver.a,driver.c,driver.services
                levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters)
                inductives=tuple(Inductive(a.const(f.symbol,levels),f.type,tuple(Constructor(ct.symbol,ct.type) for ct in f.constructors),f.recursor_symbol)
                    for f in block.families)
                analysis=analyze_core(services,inductives,block.universe_parameters,block.parameters,r['elim_fresh'] or len(driver.symbols.names)+1)
                count=block.parameters+len(block.families)+len(ctors)
                expected=open_telescope(a,c,analysis.recursors[0].type,services.whnf,count=count).locals
                records=tuple(row[0] for row in state['context'][r['header_parameter_base']:r['ctx']])
                self.assertEqual(len(records),len(expected));_,decoded=decode_syntax(packed,a)
                rename={state['heap'][state['heap'][record][1]][1]:local for record,local in zip(records,expected)}
                def normalized(ref):
                    return transform(a,decoded[ref],lambda ref,depth:rename.get(a.expr(ref).a) if a.expr(ref).tag==Tag.LOCAL else None)
                expected_fields={ctor.symbol:ctor.fields for family in analysis.families for ctor in family.constructors}
                for i,(info,ctor) in enumerate(zip(infos,ctors)):
                    tag,pending,record,nfields=state['heap'][info];self.assertEqual(tag,CellTag.MINOR_INFO)
                    self.assertEqual(state['heap'][pending][1],ctor.symbol);self.assertEqual(nfields,expected_fields[ctor.symbol])
                    self.assertEqual(record,records[block.parameters+len(block.families)+i])
                    self.assertEqual(state['heap'][record][0],CellTag.LOCAL_DECL)
                    want=c.lookup(expected[block.parameters+len(block.families)+i]).type
                    self.assertTrue(representation_equal(a,normalized(state['heap'][record][2]),want),(doc['name'],i))


if __name__=='__main__':unittest.main()
