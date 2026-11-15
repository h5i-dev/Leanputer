"""Complete encoding correspondence is offline, not native source evidence."""
import importlib.util,json,sys,unittest
from pathlib import Path


@unittest.skipUnless(sys.version_info>=(3,11)and importlib.util.find_spec('transformers'),'native stock environment')
class NativeControlTest(unittest.TestCase):
    def test_full_input_independent_encoding_matches_all_original_source_states(self):
        from leanputer.kernel.control_capture import capture
        from leanputer.kernel.control_store import ControlStore
        from leanputer.kernel.stock_control import NativeControl
        from leanputer.kernel.stock_control_reference import NativeControlReference
        from leanputer.kernel import source_transition as source,traversal_machine as spec
        cfg=spec.MachineConfig(**json.loads(Path('benchmarks/kernel-full-source-stock/config.json').read_text()))
        compiler,addresses=capture(cfg);store=ControlStore(compiler,contract_dispatch=True);program=NativeControl(store,addresses)
        self.assertEqual(program.report['rule_families'],73)
        self.assertEqual(program.report['source_effects'],program.report['source_effects_mapped'])
        self.assertTrue(program.report['pc16_encoding_met'])
        self.assertTrue(all(len(record.bits())==112 for record in program.records))
        for line in Path('benchmarks/kernel-full-source-stock/source.jsonl').read_text().splitlines():
            doc=json.loads(line);state=source.prepare(cfg,*source.parse_document(doc));expected=spec.SpecMachine(cfg,state);actual=NativeControlReference(program,state)
            for _ in range(2000000):
                if actual.step():self.assertEqual(actual.state(),expected.step(),(doc.get('name'),actual.semantic_steps))
                if actual.status:break
            else:self.fail('native encoding exceeded targeted source record bound')
            self.assertEqual(actual.status,expected.state['regs']['status'])
            self.assertEqual(actual.reason,expected.state['regs']['reason'])
            self.assertEqual(actual.result,expected.state['regs']['r'])
