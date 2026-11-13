"""Closed computation rules versus independent source recursor construction.

The typed prefix is derived with development transitions; each new weighted
rule step/bank is compared here. One raw-entry case also compares the whole
controller. This is IR validation, not a seeded production native checker.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.admission import analyze_core
from leanputer.kernel.arena import LevelTag
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.native_cells import CellTag,VectorKind
from leanputer.kernel.operations import representation_equal
from leanputer.kernel.recursor import Inductive,Constructor
from tests.test_kernel_minor_transition import cases as minor_cases
from tests.test_kernel_constructor_transition import native_cases
from tests.test_kernel_native_cells import vector,decode_syntax
from tests.test_kernel_traversal_machine import CircuitHarness


class RecursorRuleTransitionTest(unittest.TestCase):
    def test_all_closed_rhs_order_arity_functional_calls_and_scope(self):
        cfg=spec.MachineConfig(heap=512,stack=16,context=16,constants=2,fuel=4096,word_bits=10)
        circuit=CircuitHarness(cfg);docs=minor_cases();docs.insert(1,native_cases()[1])
        for doc in docs:
            with self.subTest(label=doc['name']):
                source,args,decls=program.parse_document(doc);state=program.prepare(cfg,source,args,decls);machine=spec.SpecMachine(cfg,state);prefix=None
                for step in range(cfg.fuel+2):
                    r=state['regs']
                    if r['task']==spec.Task.BUILD_RECURSOR_RULES and r['mode']==spec.Mode.WALK:prefix=deepcopy(state)
                    if prefix is not None or doc['name']=='functional-core-block':
                        actual=circuit.step(state);self.assertEqual(actual,machine.step(),(doc['name'],step));state=actual
                    else:
                        ref=machine.step();state={'regs':{k:int(v) for k,v in ref['regs'].items()},
                            **{bank:[[int(v) for v in row] for row in ref[bank]] for bank in spec.BANK_FIELDS}}
                    if state['regs']['status']:break
                r=state['regs'];self.assertIsNotNone(prefix)
                self.assertEqual((r['status'],r['reason']),(spec.Outcome.GAP,spec.Reason.GAP_RECURSOR_GENERATION))
                self.assertEqual((r['env_head'],r['decl'],r['raw_index']),(0,0,0))
                self.assertEqual((r['ctx'],r['count'],r['arg_base']),(prefix['regs']['ctx'],prefix['regs']['count'],prefix['regs']['arg_base']))
                self.assertEqual(state['context'][:r['ctx']],prefix['context'][:r['ctx']])
                block=decls[-1];driver=EnvironmentDriver(source);a=driver.a
                levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters)
                inds=tuple(Inductive(a.const(f.symbol,levels),f.type,tuple(Constructor(ct.symbol,ct.type) for ct in f.constructors),f.recursor_symbol) for f in block.families)
                analysis=analyze_core(driver.services,inds,block.universe_parameters,block.parameters,r['elim_fresh'] or len(driver.symbols.names)+1)
                want=[(family.symbol,rule) for family,rec in zip(block.families,analysis.recursors) for rule in rec.rules]
                packed=SimpleNamespace(heap=state['heap'][:r['free']]);_,decoded=decode_syntax(packed,a)
                infos=vector(packed,r['core_rules'],VectorKind.REFERENCES);self.assertEqual(len(infos),len(want))
                for info,(family,want_rule) in zip(infos,want):
                    tag,owner,rule,reserved=state['heap'][info];self.assertEqual((tag,reserved),(CellTag.FAMILY_RULE,0))
                    self.assertEqual(state['heap'][owner][1],family)
                    tag,symbol,nfields,rhs=state['heap'][rule]
                    self.assertEqual((tag,symbol,nfields),(CellTag.CHECKED_RULE,want_rule.constructor,want_rule.fields))
                    self.assertTrue(representation_equal(a,decoded[rhs],want_rule.rhs),(doc['name'],symbol))
                self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
