"""Private generation operations over genuinely derived model metadata."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.native_cells import VectorKind
from tests.test_kernel_native_cells import vector,decode_syntax
from tests.test_kernel_constructor_transition import native_cases,core
from tests.test_kernel_header_transition import cases as header_cases
from tests.test_kernel_traversal_machine import CircuitHarness


class GenerationOpsTest(unittest.TestCase):
    def test_family_lookup_and_argument_list_application(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=2048,word_bits=9)
        circuit=CircuitHarness(cfg)
        def run(state):
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state);self.assertEqual(actual,machine.step(),step);state=actual
                if state['regs']['status']:break
            return state
        for doc in (native_cases()[0],core('mutual-motive-lookup',header_cases()[2]['declarations'][0])):
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
            for _ in range(cfg.fuel+2):
                machine.step()
                if machine.state['regs']['status']:break
            ref=machine.state;prefix={'regs':{k:int(v) for k,v in ref['regs'].items()},
                **{bank:[[int(v) for v in row] for row in ref[bank]] for bank in spec.BANK_FIELDS}}
            self.assertEqual(prefix['regs']['status'],spec.Outcome.GAP)
            packed=SimpleNamespace(heap=prefix['heap'])
            infos=vector(packed,prefix['regs']['core_motives'],VectorKind.REFERENCES)
            for info in infos:
                family,record=prefix['heap'][info][1:3]
                state=deepcopy(prefix);state['regs'].update(status=0,reason=0,fuel=cfg.fuel,sp=0,
                    task=int(spec.Task.FIND_MOTIVE),mode=int(spec.Mode.WALK),x=prefix['regs']['core_motives'],motive_query=family)
                state=run(state)
                self.assertEqual((state['regs']['status'],state['regs']['r'],state['regs']['motive_lookup_info']),
                    (spec.Outcome.DONE,prefix['heap'][record][1],info))
            if doc['name']!='original-Eq-core-block':continue
            r=prefix['regs'];pending=prefix['heap'][r['ctor_names']][1];analysis=prefix['heap'][pending][3]
            head=prefix['heap'][analysis][3];arguments=[];cursor=head
            while cursor:arguments.append(prefix['heap'][cursor][1]);cursor=prefix['heap'][cursor][2]
            fn=prefix['heap'][prefix['heap'][infos[0]][2]][1]
            for skip in range(len(arguments)+2):
                state=deepcopy(prefix);state['regs'].update(status=0,reason=0,fuel=cfg.fuel,sp=0,
                    task=int(spec.Task.APPLY_LIST),mode=int(spec.Mode.WALK),x=fn,list_head=head,list_skip=skip)
                state=run(state)
                if skip>len(arguments):
                    self.assertEqual((state['regs']['status'],state['regs']['reason']),(spec.Outcome.INVALID,spec.Reason.SYNTAX));continue
                self.assertEqual(state['regs']['status'],spec.Outcome.DONE)
                _,decoded=decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]),source.arena)
                self.assertEqual(decoded[state['regs']['r']],source.arena.app(decoded[fn],tuple(decoded[v] for v in arguments[skip:])))
                self.assertEqual((state['regs']['ctx'],state['regs']['count'],state['regs']['env_head']), (r['ctx'],r['count'],0))


if __name__=='__main__':unittest.main()
