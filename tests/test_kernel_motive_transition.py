"""All-family motives versus independent telescope construction, IR contracts."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.arena import LocalContext,LevelTag,Tag
from leanputer.kernel.native_cells import CellTag,VectorKind
from leanputer.kernel.operations import representation_equal,transform
from leanputer.kernel.services import KernelServices
from leanputer.kernel.telescope import consume_parameters,open_telescope,fold_telescope
from tests.test_kernel_constructor_transition import core,native_cases
from tests.test_kernel_header_transition import cases as header_cases
from tests.test_kernel_native_cells import vector,decode_syntax
from tests.test_kernel_traversal_machine import CircuitHarness,cases as traversal_cases


class MotiveTransitionTest(unittest.TestCase):
    def test_all_family_motives_indices_majors_and_outer_scope(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=2048,word_bits=9)
        circuit=CircuitHarness(cfg)
        docs=native_cases()+[core('mutual-dependent-motives',header_cases()[2]['declarations'][0])]
        for doc in docs:
            with self.subTest(label=doc['name']):
                source,index,decls=program.parse_document(doc);state=program.prepare(cfg,source,index,decls)
                machine=spec.SpecMachine(cfg,state);prefix=None
                for step in range(cfg.fuel+2):
                    r=state['regs']
                    if r['task']==spec.Task.BUILD_MOTIVES and r['mode']==spec.Mode.WALK:prefix=deepcopy(state)
                    actual=circuit.step(state);self.assertEqual(actual,machine.step(),(doc['name'],step));state=actual
                    rr=state['regs']
                    if rr['mode']==spec.Mode.RETURN and rr['sp'] and state['stack'][rr['sp']-1][0]==spec.CALL_SOURCE_MOTIVES:break
                    if state['regs']['status']:break
                r=state['regs'];self.assertIsNotNone(prefix)
                self.assertEqual((r['status'],r['mode']),(spec.Outcome.RUNNING,spec.Mode.RETURN))
                self.assertEqual((r['env_head'],r['decl'],r['raw_index']),(0,0,0))
                end=r['header_parameter_end'];self.assertEqual(state['context'][:end],prefix['context'][:end])
                block=decls[-1];self.assertEqual(r['ctx'],end+len(block.families))
                packed=SimpleNamespace(heap=state['heap'][:r['free']]);infos=vector(packed,r['core_motives'],VectorKind.REFERENCES)
                self.assertEqual(len(infos),len(block.families));a=source.arena;c=LocalContext(a);services=KernelServices(a,c)
                params=open_telescope(a,c,block.families[0].type,services.whnf,count=block.parameters).locals
                levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters)
                elimination=a.level(LevelTag.PARAM,r['elim_fresh']) if r['elim_large'] else a.zero
                _,decoded=decode_syntax(packed,a)
                parameter_rename={}
                for i,local in zip(range(r['header_parameter_base'],end),params):
                    rec=state['heap'][state['context'][i][0]]
                    parameter_rename[state['heap'][rec[1]][1]]=local
                def normalized(ref,rename):
                    return transform(a,decoded[ref],lambda ref,depth:
                        rename.get(a.expr(ref).a) if a.expr(ref).tag==Tag.LOCAL else None)
                for position,(info,family) in enumerate(zip(infos,block.families)):
                    tag,signature,motive,telescope=state['heap'][info];self.assertEqual(tag,CellTag.MOTIVE_INFO)
                    self.assertEqual(state['heap'][signature][1],family.symbol)
                    tag,indices,major,rec_symbol=state['heap'][telescope]
                    self.assertEqual((tag,rec_symbol),(CellTag.MOTIVE_TELESCOPE,family.recursor_symbol))
                    self.assertEqual(state['context'][end+position],[motive])
                    self.assertEqual(state['heap'][motive][0],CellTag.LOCAL_DECL)
                    self.assertEqual(state['heap'][major][0],CellTag.LOCAL_DECL)
                    with c.scope():
                        tail=consume_parameters(a,c,family.type,params,services.whnf,services.convert)
                        opened=open_telescope(a,c,tail,services.whnf)
                        major_type=a.app(a.const(family.symbol,levels),params+opened.locals)
                        expected_major=c.fresh(major_type)
                        expected_type=fold_telescope(a,c,opened.locals+(expected_major,),a.mk(Tag.SORT,elimination))
                        native_indices=vector(packed,indices,VectorKind.REFERENCES)
                        self.assertEqual(len(native_indices),len(opened.locals))
                        rename=dict(parameter_rename)
                        for record,expected in zip(native_indices,opened.locals):
                            self.assertEqual(state['heap'][record][0],CellTag.LOCAL_DECL)
                            rename[state['heap'][state['heap'][record][1]][1]]=expected
                        self.assertTrue(representation_equal(a,normalized(state['heap'][major][2],rename),major_type))
                        self.assertTrue(representation_equal(a,normalized(state['heap'][motive][2],parameter_rename),expected_type))

    def test_existing_zero_base_roundtrip_uses_same_fold(self):
        cfg=spec.MachineConfig(heap=128,stack=16,context=8,constants=2,fuel=512,word_bits=8)
        circuit=CircuitHarness(cfg)
        doc=next(d for d in traversal_cases() if d['task']=='ROUNDTRIP_TELESCOPE')
        state=spec.prepare(cfg,*spec.parse_document(doc));machine=spec.SpecMachine(cfg,state)
        for step in range(cfg.fuel+2):
            actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
            if state['regs']['status']:break
        self.assertEqual((state['regs']['status'],state['regs']['ctx']),(spec.Outcome.DONE,0))


if __name__=='__main__':unittest.main()
