"""Shared derived-Local window operations, internal ABI contracts only."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import traversal_machine as spec
from leanputer.kernel.arena import Arena,LocalContext,Tag
from leanputer.kernel.operations import abstract,instantiate_rev
from leanputer.kernel.telescope import fold_telescope
from leanputer.kernel.native_cells import VectorKind
from tests.test_kernel_native_cells import vector
from tests.test_kernel_traversal_machine import CircuitHarness,canonical_heap


class ScopeWindowsTest(unittest.TestCase):
    def test_order_capture_avoidance_empty_and_nonzero_scope_windows(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=512,word_bits=9)
        circuit=CircuitHarness(cfg);a=Arena();context=LocalContext(a)
        prop=a.mk(Tag.SORT,a.zero);carrier=context.fresh(prop);x=context.fresh(carrier)
        p=context.fresh(a.mk(Tag.PI,carrier,prop))
        body=a.mk(Tag.LAM,carrier,a.app(a.const(37),(x,p,a.mk(Tag.BVAR,0))))
        root=fold_telescope(a,context,(carrier,x,p),body)
        def run(state):
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
                if state['regs']['status']:break
            self.assertEqual((state['regs']['status'],state['regs']['reason']),(spec.Outcome.DONE,spec.Reason.NONE))
            return state
        prefix=run(spec.prepare(cfg,*spec.parse_document(spec.document(a,root,spec.Task.OPEN_TELESCOPE))))
        mapping=canonical_heap(prefix,a);result=prefix['regs']['r'];original=mapping[result]
        locals_=tuple(mapping[prefix['heap'][row[0]][1]] for row in prefix['context'][:3])
        for base,end in ((0,3),(1,3),(2,2)):
            with self.subTest(window=(base,end)):
                state=deepcopy(prefix)
                def operation(task,x):
                    state['regs'].update(status=0,reason=0,fuel=cfg.fuel,task=int(task),mode=int(spec.Mode.WALK),x=x,
                        abstract_base=base,abstract_end=end)
                    return run(state)
                state=operation(spec.Task.ABSTRACT_SCOPE,result)
                expected=abstract(a,original,locals_[base:end])
                self.assertEqual(canonical_heap(state,a)[state['regs']['r']],expected)
                state=operation(spec.Task.INSTANTIATE_SCOPE,state['regs']['r'])
                self.assertEqual(canonical_heap(state,a)[state['regs']['r']],instantiate_rev(a,expected,locals_[base:end]))
                self.assertEqual(canonical_heap(state,a)[state['regs']['r']],original)
                state=operation(spec.Task.SNAPSHOT_SCOPE,0)
                self.assertEqual(vector(SimpleNamespace(heap=state['heap']),state['regs']['r'],VectorKind.REFERENCES),
                    tuple(row[0] for row in prefix['context'][base:end]))
                self.assertEqual((state['regs']['ctx'],state['regs']['count'],state['regs']['arg_base']),(3,0,0))
                self.assertEqual(state['context'][:3],prefix['context'][:3])


if __name__=='__main__':unittest.main()
