"""Source mk_rec_name relation over raw arbitrary structured names."""
import unittest
from leanputer.kernel import name_transition as program,traversal_machine as spec
from tests.test_kernel_traversal_machine import CircuitHarness


def strings(*parts):return [{'str':part} for part in parts]


class RecursorNameTransitionTest(unittest.TestCase):
    def test_general_paths_use_content_and_preserve_segment_kinds(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=512,word_bits=9)
        circuit=CircuitHarness(cfg);mixed=strings('Namespace')+[{'num':17}]+strings('型')
        pairs=[(strings('F'),strings('F','rec')),(mixed,mixed+strings('rec')),
            (strings('Namespace','17','型'),mixed+strings('rec')),
            (strings('F'),strings('F','recursor')),(strings('F'),strings('F')+[{'num':114}]),
            (strings('Long'),strings('Dong','rec')),(strings('rec'),strings('rec','rec')),
            (strings('F'),strings('F','x','rec')),(strings('F'),strings('F','rеc'))]
        for parent,candidate in pairs:
            doc=dict(format='leanputer.kernel-name-operation.v1',operation='recursor_name',parent=parent,candidate=candidate)
            source,args,decls=program.parse_document(doc);state=program.prepare(cfg,source,args,decls)
            self.assertFalse(any(row[0]>=160 for row in state['heap']))
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),(parent,candidate,step));state=actual
                if state['regs']['status']:break
            r=state['regs'];left,right=(source.symbols.names[i] for i in args)
            self.assertEqual((r['status'],r['reason'],r['r']),(spec.Outcome.DONE,spec.Reason.NONE,int(right==left+(('str','rec'),))))
            self.assertEqual((r['ctx'],r['decl'],r['env_ready'],r['env_head'],r['sp']),(0,0,0,0,0))
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
