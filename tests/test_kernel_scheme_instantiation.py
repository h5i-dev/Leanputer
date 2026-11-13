"""Shared scheme substitution preserves context and pinned level-object semantics."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.arena import LevelTag,Tag
from leanputer.kernel.native_cells import CellTag,VectorKind
from leanputer.kernel.operations import representation_equal,substitute_levels
from tests.test_kernel_constructor_transition import native_cases,functional_block,core
from tests.test_kernel_source_transition import name
from tests.test_kernel_native_cells import decode_syntax,vector
from tests.test_kernel_traversal_machine import CircuitHarness


def documents():
    block=functional_block();u=['param',name('u')]
    block.update(level_params=[name('u')]);block['families'][0].update(type=['sort',u],constructors=[])
    block['recursor_claims']=[dict(name=name('F')+[{'str':'rec'}],level_params=[name('v'),name('u')],
        type=['sort',['max',u,['zero']]])]
    duplicate=deepcopy(block)
    duplicate['recursor_claims'][0].update(level_params=[name('u'),name('u')],type=['sort',u])
    return [native_cases()[0],core('raw-max-rebuilds-for-distinct-param-object',block),
        core('pure-duplicate-parameters-first-match',duplicate)]


class SchemeInstantiationTest(unittest.TestCase):
    def test_shared_substitution_preserves_context_and_source_object_change(self):
        cfg=spec.MachineConfig(heap=512,stack=16,context=8,constants=2,fuel=4096,word_bits=10)
        circuit=CircuitHarness(cfg)
        def run(state):
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
                if state['regs']['status']:break
            return state
        for doc in documents():
            with self.subTest(label=doc['name']):
                source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
                for _ in range(cfg.fuel+2):
                    machine.step()
                    rr=machine.state['regs']
                    if rr['mode']==spec.Mode.RETURN and rr['sp'] and machine.state['stack'][rr['sp']-1][0]==spec.CALL_SOURCE_ASSEMBLY:break
                    if machine.state['regs']['status']:break
                ref=machine.state;state={'regs':{k:int(v) for k,v in ref['regs'].items()},
                    **{bank:[[int(v) for v in row] for row in ref[bank]] for bank in spec.BANK_FIELDS}}
                self.assertEqual(state['regs']['status'],spec.Outcome.RUNNING)
                sort=next(i for i,(tag,a,b,c) in enumerate(state['heap']) if tag==Tag.SORT and state['heap'][a][0]==CellTag.LEVEL_ZERO)
                # These are genuine weighted FreshLocal calls, not supplied
                # checked locals. The mapping must work with no free ctx slot.
                while state['regs']['ctx']<cfg.context:
                    state['regs'].update(status=0,reason=0,fuel=cfg.fuel,sp=0,task=int(spec.Task.FRESH_LOCAL),mode=int(spec.Mode.WALK),x=sort,binder_info=0)
                    state=run(state);self.assertEqual(state['regs']['status'],spec.Outcome.DONE)
                r=state['regs'];raw_block=state['constants'][args][5]
                claim=vector(SimpleNamespace(heap=state['heap']),state['heap'][raw_block][3],VectorKind.REFERENCES)[0]
                _,symbol,type_ref,params=state['heap'][claim];before=deepcopy(state['context']);count,base,ctx=r['count'],r['arg_base'],r['ctx']
                r.update(status=0,reason=0,fuel=cfg.fuel,sp=0,task=int(spec.Task.INSTANTIATE_SCHEME),mode=int(spec.Mode.WALK),
                    x=type_ref,parameter_vector=params,level_vector=r['core_rec_levels'])
                state=run(state);r=state['regs'];self.assertEqual((r['status'],r['reason']),(spec.Outcome.DONE,spec.Reason.NONE))
                self.assertEqual((r['ctx'],r['count'],r['arg_base'],r['level_map_head']),(ctx,count,base,0))
                self.assertEqual(state['context'],before)
                packed=SimpleNamespace(heap=state['heap'][:r['free']]);_,decoded=decode_syntax(packed,source.arena)
                expected_params=vector(packed,r['core_rec_parameters'],VectorKind.SYMBOLS)
                raw_claim=decls[-1].recursor_claims[0]
                rename={}
                for p,q in zip(raw_claim.universe_parameters,expected_params):
                    rename.setdefault(p,source.arena.level(LevelTag.PARAM,q))
                expected=substitute_levels(source.arena,raw_claim.type,rename)
                if doc['name']=='raw-max-rebuilds-for-distinct-param-object':
                    # Pinned level.cpp:update_max uses is_eqp, not structural ==.
                    # The generated formal Param is a distinct runtime object;
                    # the interning arena oracle cannot represent that sharing.
                    self.assertNotEqual(state['heap'][type_ref][1],state['heap'][r['r']][1])
                    expected=source.arena.mk(Tag.SORT,source.arena.level(LevelTag.PARAM,expected_params[1]))
                self.assertTrue(representation_equal(source.arena,decoded[r['r']],expected),doc['name'])

    def test_checked_polymorphic_constant_inference_and_delta_use_same_map(self):
        from tests.test_kernel_delta_transition import cases as delta_cases
        from leanputer.kernel import source_transition as source_program
        from leanputer.kernel.environment import EnvironmentDriver
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=4,fuel=1024,word_bits=9)
        circuit=CircuitHarness(cfg);doc=delta_cases()[3]
        state=source_program.prepare(cfg,*source_program.parse_document(doc));machine=spec.SpecMachine(cfg,state)
        for step in range(cfg.fuel+2):
            actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
            if state['regs']['status']:break
        self.assertEqual((state['regs']['status'],state['regs']['reason']),(spec.Outcome.DONE,spec.Reason.NONE))
        self.assertEqual(state['regs']['level_map_head'],0)
        self.assertEqual(EnvironmentDriver(source_program.parse_document(doc)[0]).check().status,'ACCEPT')


if __name__=='__main__':unittest.main()
