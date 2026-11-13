"""Elimination/K algorithm contracts; no original-source admission claim.

Internal ABI tests derive the prefix with development transitions, then compare
every IR step/bank of the new operation. Two composed raw-entry cases also
compare the entire controller; native evidence is separately recorded.
"""
from copy import deepcopy
import unittest
from types import SimpleNamespace
from leanputer.kernel import core_transition as program, traversal_machine as spec
from leanputer.kernel.native_cells import CellTag, VectorKind
from tests.test_kernel_constructor_transition import core, functional_block, native_cases
from tests.test_kernel_native_cells import vector
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness


def decision_cases():
    prop=['sort',['zero']];f=['const',name('F'),[]]
    base=functional_block();base['families'][0]['constructors']=[]
    empty=deepcopy(base)
    singleton=deepcopy(base);singleton['families'][0]['constructors']=[dict(name=name('F')+[{'str':'intro'}],type=f)]
    multiple=deepcopy(singleton);multiple['families'][0]['constructors'].append(dict(name=name('F')+[{'str':'other'}],type=f))
    mutual=deepcopy(base);g=deepcopy(base['families'][0]);g.update(name=name('G'),recursor_name=name('G')+[{'str':'rec'}]);mutual['families'].append(g)
    hidden=deepcopy(singleton);hidden['families'][0]['constructors'][0]['type']=['pi',0,prop,f]
    exposed=deepcopy(hidden);exposed['families'][0]['type']=['pi',0,prop,prop]
    exposed['families'][0]['constructors'][0]['type']=['pi',0,prop,['app',f,['var',0]]]
    nested=deepcopy(hidden);nested['families'][0]['type']=['pi',0,['pi',0,prop,prop],prop]
    nested['families'][0]['constructors'][0]['type']=['pi',0,prop,['app',f,['lam',0,prop,['var',1]]]]
    data=deepcopy(hidden);data['families'][0]['type']=['sort',['succ',['zero']]]
    zero_alias=deepcopy(singleton);zero_alias['families'][0]['type']=['sort',['max',['zero'],['zero']]]
    many=deepcopy(singleton);many['families'][0]['constructors'][0]['type']=['pi',0,f,['pi',0,['pi',0,prop,f],['pi',0,f,f]]]
    return [(label,core(label,block),large,k) for label,block,large,k in (
        ('empty-predicate',empty,True,False),('singleton-nullary-predicate',singleton,True,True),
        ('multiple-predicate',multiple,False,False),('mutual-predicate',mutual,False,False),
        ('hidden-data',hidden,False,False),('direct-result-index',exposed,True,False),
        ('nested-occurrence-is-not-direct-argument',nested,False,False),('data-universe',data,True,False),
        ('raw-max-zero-is-not-source-is-zero',zero_alias,True,False),('three-generic-fields',many,True,False))]


class EliminationTransitionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=2048,word_bits=9)
        cls.circuit=CircuitHarness(cls.cfg)

    def run_operation(self,doc,whole=False):
        source,index,decls=program.parse_document(doc)
        state=program.prepare(self.cfg,source,index,decls);machine=spec.SpecMachine(self.cfg,state)
        prefix=None
        for step in range(self.cfg.fuel+2):
            r=state['regs']
            entering=r['task']==spec.Task.INIT_ELIMINATION and r['mode']==spec.Mode.WALK
            if entering:prefix=deepcopy(state)
            if whole or prefix is not None:
                actual=self.circuit.step(state);self.assertEqual(actual,machine.step(),(doc['name'],step));state=actual
            else:
                reference=machine.step()
                # The strict bit serializer requires plain ints. Development
                # references intentionally use IntEnum constants internally.
                state={'regs':{key:int(value) for key,value in reference['regs'].items()},
                    **{bank:[[int(value) for value in row] for row in reference[bank]]
                        for bank in spec.BANK_FIELDS}}
            if state['regs']['status']:break
        return state,prefix,decls

    def assert_metadata(self,state,prefix,decls,large,k):
        self.assertIsNotNone(prefix)
        r,p=state['regs'],prefix['regs'];block=decls[-1]
        self.assertEqual((r['status'],r['reason']),(spec.Outcome.GAP,spec.Reason.GAP_RECURSOR_GENERATION))
        self.assertEqual(state['heap'][r['core_elim_info']],
            [CellTag.ELIMINATION_INFO,r['core_elim_level'],r['core_rec_parameters'],int(k)])
        self.assertEqual((r['env_head'],r['decl'],r['raw_index'],r['typing_head']),
            (p['env_head'],p['decl'],p['raw_index'],p['typing_head']))
        params=vector(SimpleNamespace(heap=state['heap']),r['core_rec_parameters'],VectorKind.SYMBOLS)
        if large:
            self.assertEqual(state['heap'][r['core_elim_level']],[CellTag.LEVEL_PARAM,r['elim_fresh'],0,0])
            self.assertEqual(params,(r['elim_fresh'],)+block.universe_parameters)
            self.assertNotIn(r['elim_fresh'],block.universe_parameters)
            self.assertEqual(state['context'][1:p['ctx']+1],prefix['context'][:p['ctx']])
            self.assertEqual((r['count'],r['ctx'],r['header_parameter_base'],r['header_parameter_end']),
                (p['header_parameter_base']+1,p['header_parameter_end']+1,p['header_parameter_base']+1,p['header_parameter_end']+1))
        else:
            self.assertEqual(r['core_elim_level'],r['kernel_zero'])
            self.assertEqual(params,block.universe_parameters)
            self.assertEqual((r['ctx'],r['header_parameter_base']), (p['header_parameter_end'],p['header_parameter_base']))
        self.assertEqual(self.circuit.step(state),state)

    def test_source_decisions_share_the_same_general_field_loop(self):
        for label,doc,large,k in decision_cases():
            with self.subTest(label=label):
                state,prefix,decls=self.run_operation(doc)
                self.assert_metadata(state,prefix,decls,large,k)

    def test_raw_entry_fresh_universe_and_derived_local_scope_shift(self):
        for doc,k in zip(native_cases(),(True,False)):
            with self.subTest(label=doc['name']):
                state,prefix,decls=self.run_operation(doc,whole=True)
                self.assert_metadata(state,prefix,decls,True,k)

    def test_raw_zero_equivalence_cannot_bypass_field_universe_guard(self):
        block=functional_block();block['families'][0]['type']=['sort',['max',['zero'],['zero']]]
        block['families'][0]['constructors'][0]['type']=['pi',0,['sort',['zero']],['const',name('F'),[]]]
        state,prefix,_=self.run_operation(core('raw-zero-field-universe',block),whole=True)
        self.assertIsNone(prefix)
        self.assertEqual((state['regs']['status'],state['regs']['reason']), (spec.Outcome.INVALID,spec.Reason.UNIVERSE))
        self.assertEqual((state['regs']['env_head'],state['regs']['core_elim_info']), (0,0))


if __name__=='__main__':unittest.main()
