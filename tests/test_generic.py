"""Focused declaration-as-data checks; no per-name semantic catalog."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import torch

from leanputer.generic_examples import focused_cases, unary_cases
from leanputer.generic_spec import MachineConfig, Outcome, Reason, SpecMachine, prepare
from leanputer.generic_syntax import parse_document, assumptions
from leanputer.generic_transition import compile_machine

CFG = MachineConfig(heap=128, stack=16, context=8, constants=8, fuel=1056)


def metadata_cases():
    base = focused_cases()[0][0]
    cases = []
    for position, key, value in ((1, 'family', 'false'), (3, 'family', 'false'),
                                 (3, 'level', 0), (0, 'constructors', 127)):
        row = deepcopy(base)
        row['environment'][position][key] = value
        cases.append((row, 'REJECT'))
    recursive = deepcopy(base)
    recursive['environment'][1]['type'] = ['pi', ['const', 'Bool'], ['const', 'Bool']]
    cases.append((recursive, 'UNSUPPORTED'))
    unbounded = deepcopy(base)
    unbounded['environment'][3]['level'] = CFG.universe
    cases.append((unbounded, 'RESOURCE'))
    return cases


class GenericDeclarationSmoke(unittest.TestCase):
    def test_renaming_is_identical_input_state(self):
        first, renamed = [prepare(CFG, *parse_document(row)) for row, _ in focused_cases()[:2]]
        self.assertEqual(first, renamed)
        self.assertEqual(assumptions(parse_document(focused_cases()[0][0])[2]), [])

    def test_focused_weighted_transitions_and_metadata_guards(self):
        torch.set_num_threads(1)
        model = compile_machine(CFG)
        cases = focused_cases() + unary_cases() + metadata_cases()
        states = [prepare(CFG, *parse_document(row)) for row, _ in cases]
        refs = [SpecMachine(CFG, state) for state in states]
        bits = model.initializer(torch.cat([model.layout.encode(s) for s in states]))
        with torch.inference_mode():
            for step in range(CFG.fuel+1):
                bits = model(bits)
                for index, (row, ref) in enumerate(zip(bits, refs)):
                    self.assertEqual(model.layout.decode(row.tolist()), ref.step(), (step, index))
        for (document, expected), row in zip(cases, bits):
            regs = model.layout.decode(row.tolist())['regs']
            status = ('UNSUPPORTED' if regs['reason'] == Reason.UNSUPPORTED_DECLARATION
                      else Outcome(regs['status']).name)
            self.assertEqual(status, expected, document)

    @unittest.skipUnless(shutil.which('lean'), 'Lean kernel replay requires Lean')
    def test_independent_lean_kernel_replay(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/'input.jsonl', Path(tmp)/'output.json'
            cases = focused_cases() + unary_cases()
            source.write_text(''.join(json.dumps(d)+'\n' for d, _ in cases))
            subprocess.run(['lean', '--run', str(root/'tools/lean/ValidateGeneric.lean'),
                            str(source), str(output)], cwd=root, check=True, capture_output=True, timeout=60)
            statuses = [r['status'] for r in json.loads(output.read_text())]
            for actual, (_, expected) in zip(statuses, cases):
                if expected != 'UNSUPPORTED':
                    self.assertEqual(actual, expected)

    @unittest.skipUnless(shutil.which('lean'), 'real source export requires Lean')
    def test_actual_source_export_is_dependency_complete(self):
        from leanputer.preparation import export
        root = Path(__file__).resolve().parents[1]
        expected = [json.loads(s) for s in (root/'tests/fixtures/generic-source.jsonl').read_text().splitlines()][:3]
        targets = json.loads((root/'examples/generic-targets.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'source.jsonl'
            export(root/'examples/GenericInductives.lean', 'GenericInductives', targets,
                   out, tmp, helper='ExportGeneric.lean')
            actual = [json.loads(s) for s in out.read_text().splitlines()]
        self.assertEqual(len(actual), 3)
        for got, want in zip(actual, expected):
            self.assertEqual(got, want)
            self.assertEqual(assumptions(parse_document(got)[2]), [])
        self.assertEqual([len(d['environment']) for d in actual], [4, 5, 7])
        self.assertTrue(all('builtin' not in json.dumps(d) for d in actual))

    def test_cli_preserves_unsupported_preparation_rows(self):
        from leanputer.generic import check_documents
        from types import SimpleNamespace
        source = dict(format='leanputer.generic.v1', name='unsupported-target',
                      status='UNSUPPORTED', reason='unresolved universe', provenance={'source_constant': 'target'})
        report = check_documents(SimpleNamespace(config=CFG), [source], backend='circuit')
        self.assertEqual(report['counts'], {'UNSUPPORTED': 1})
        self.assertIsNone(report['results'][0]['environment_declarations'])
        self.assertIsNone(report['results'][0]['assumptions'])
        self.assertEqual(report['results'][0]['provenance'], source['provenance'])
