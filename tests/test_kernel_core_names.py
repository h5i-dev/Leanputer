"""Raw recursor-name claims must be checked before any generation/publication."""
from copy import deepcopy
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.native_cells import CellTag
from tests.test_kernel_constructor_transition import functional_block,core
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness


class CoreNamesTest(unittest.TestCase):
    def test_arbitrary_parent_paths_and_untrusted_recursor_name_claims(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=2048,word_bits=9)
        circuit=CircuitHarness(cfg)
        wrong=functional_block();wrong['families'][0]['recursor_name']=name('F')+[{'str':'recurse'}]
        collision=functional_block();collision['families'][0]['constructors'][0]['name']=name('F')+[{'str':'rec'}]
        mixed=[{'str':'Namespace'},{'num':17}]
        def rename(node):
            if isinstance(node,list):
                if node and all(isinstance(n,dict) and ('str' in n or 'num' in n) for n in node):
                    return mixed+node[1:] if node[:1]==name('F') else node
                return [rename(n) for n in node]
            if isinstance(node,dict):return {k:rename(v) for k,v in node.items()}
            return node
        valid=rename(functional_block())
        for block,want in [(wrong,('INVALID','INVALID_RECURSOR_NAME')),
                           (collision,('INVALID','DUPLICATE_DECLARATION')),
                           (valid,('GAP','GAP_RECURSOR_GENERATION'))]:
            doc=core('core-name-claim',block);source,index,decls=program.parse_document(doc)
            state=program.prepare(cfg,source,index,decls);machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
                if state['regs']['status']:break
            r=state['regs']
            self.assertEqual((spec.Outcome(r['status']).name,spec.Reason(r['reason']).name),want,r)
            self.assertEqual((r['decl'],r['env_head'],r['raw_index']),(0,0,0))
            if want[0]=='GAP':
                tag,family,symbol,tail=state['heap'][r['core_rec_names']]
                self.assertEqual((tag,tail),(CellTag.VALIDATED_RECURSOR_NAME,0))
                self.assertEqual(state['heap'][family][1],decls[0].families[0].symbol)
                self.assertEqual(symbol,decls[0].families[0].recursor_symbol)
            else:self.assertEqual(r['core_rec_names'],0)
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
