"""Whole source rule capture, not native admission or a host checker backend."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest

from leanputer.kernel import source_transition as p,traversal_machine as spec
from leanputer.kernel.control_capture import capture
from leanputer.kernel.control_reference import TypedReference


class TypedCaptureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=p.MachineConfig(heap=512,stack=32,context=8,constants=4,fuel=8192,word_bits=16)
        cls.compiler,cls.addresses=capture(cls.cfg)

    def test_every_source_rule_family_is_captured(self):
        import inspect
        from leanputer.kernel.traversal_transition import RuleCompiler
        tree=ast.parse(inspect.getsource(RuleCompiler))
        expected=[n.args[0].id for n in ast.walk(tree)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='include_rules']
        self.assertEqual(sorted(expected),sorted(row['module']for row in self.compiler.families))
        self.assertEqual(len(expected),73)
        self.assertTrue(all(row['effects'] for row in self.compiler.families))
        self.assertEqual(set(self.compiler.r),set(spec.REGISTERS))
        self.assertEqual({e.kind for e in self.compiler.effects},{'merge_fields','write_heap','write_stack','write_context'})

    def test_same_original_sources_match_all_reference_states(self):
        import json
        docs=[json.loads(line)for line in Path('benchmarks/kernel-full-source-stock/source.jsonl').read_text().splitlines()]
        typed=TypedReference(self.compiler,self.addresses)
        for doc in docs:
            state=p.prepare(self.cfg,*p.parse_document(doc));reference=spec.SpecMachine(self.cfg,state)
            for step in range(self.cfg.fuel+2):
                state=typed.step(state);expected=reference.step()
                self.assertEqual(state,expected,(doc['name'],step+1))
                if state['regs']['status']:break
            self.assertTrue(state['regs']['status'])
