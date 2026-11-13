"""Internal family-occurrence ABI contracts; no NEW stock evidence claimed here.

Private headers are first derived by the weighted source prefix. Unit setup then
invokes the internal callback with raw syntax pointers, preserving its already
weighted caller continuation. This is posthoc IR module testing, NOT production
proof inference or trusted supplied admission answers. Stock integration waits
for positivity/constructor callers; no separate GPU campaign for this helper.
"""
from copy import deepcopy
import unittest
from leanputer.kernel import source_transition as source_program,traversal_machine as spec
from leanputer.kernel.native_cells import pack_source,CellCapacities
from leanputer.kernel.operations import has_constant
from tests.test_kernel_header_transition import cases
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness


class FamilyOccurrenceTest(unittest.TestCase):
    def test_borrowed_window_restores_real_weighted_caller_and_local_scope(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=2048,word_bits=9)
        circuit=CircuitHarness(cfg)
        doc=deepcopy(cases()[2]);u=['param',name('u')]
        probes=[['const',name('F'),[u]],['proj',name('G'),0,['var',0]],
                ['sort',u],['let',['sort',['zero']],['const',name('G'),[]],['var',0]]]
        doc['target']['value']=['app',['app',probes[0],probes[1]],['app',probes[2],probes[3]]]
        source,args,decls=source_program.parse_document(doc)
        state=source_program.prepare(cfg,source,args,decls)
        machine=spec.SpecMachine(cfg,state)
        for step in range(cfg.fuel+2):
            actual=circuit.step(state);self.assertEqual(actual,machine.step(),('header-prefix',step));state=actual
            r=state['regs']
            if r['mode']==spec.Mode.RETURN and r['sp'] and state['stack'][r['sp']-1][0]==spec.CALL_SOURCE_BLOCK_HEADERS:break
            self.assertFalse(r['status'])
        prefix=deepcopy(state);self.assertEqual(prefix['regs']['header_seen'],2)
        a=source.arena;root=a.expr(source.target.value)
        left,right=a.expr(root.a),a.expr(root.b);raw_probes=(left.a,left.b,right.a,right.b)
        packed=pack_source(source,CellCapacities(heap=cfg.heap,constants=cfg.constants,word_bits=cfg.word_bits))
        symbols=tuple(f.symbol for f in decls[0].families)
        for raw in raw_probes:
            state=deepcopy(prefix);r=state['regs']
            r.update(task=int(spec.Task.HAS_FAMILIES),mode=int(spec.Mode.WALK),x=packed.expression_map[raw])
            live,count,base,sp,free=r['ctx'],r['count'],r['arg_base'],r['sp'],r['free']
            caller=deepcopy(state['stack'][:sp]);context=deepcopy(state['context'][:live])
            machine=spec.SpecMachine(cfg,state)
            for step in range(128):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),('family-call',raw,step));state=actual
                if state['regs']['status']:break
            r=state['regs'];want=has_constant(a,raw,symbols)
            # The source caller resumes and GAPs its unfinished block stages;
            # this helper must not halt/accept the checker on a match.
            self.assertEqual((r['status'],r['reason'],r['r']),(spec.Outcome.GAP,spec.Reason.GAP_INDUCTIVE,int(want)))
            self.assertEqual((r['ctx'],r['count'],r['arg_base'],r['sp'],r['free']),(live,count,base,sp,free))
            self.assertEqual((r['env_head'],r['decl'],r['raw_index']),(0,0,0))
            self.assertEqual(state['stack'][:sp],caller)
            self.assertEqual(state['context'][:live],context)
            self.assertEqual(r['occurrence_mark'],sp+1)
            self.assertEqual(r['occurrence_internal'],0)
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
