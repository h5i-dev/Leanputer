import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import torch

from leanputer.dependent import Oracle, Rejected
from leanputer.machine_spec import MachineConfig, Outcome, SpecMachine, prepare
from leanputer.references import lean_replay, nanoda_replay
from leanputer.runner import check_batch, parse_document
from leanputer.transition import compile_machine


ROOT = Path(__file__).resolve().parents[1]
NANODA = Path(os.environ.get('LEANPUTER_NANODA_BIN', '/mnt/scratch/leanputer-references/nanoda-target/release/nanoda_bin'))
torch.set_num_threads(1)


@unittest.skipUnless(shutil.which('lean'), 'Lean unavailable')
class ElaboratedLeanInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='leanputer-test-', dir='/mnt/scratch' if Path('/mnt/scratch').is_dir() else None)
        cls.directory = Path(cls.temp.name)
        build = subprocess.run(['lean', '-o', str(cls.directory/'DependentCorpus.olean'), str(ROOT/'examples/DependentCorpus.lean')], capture_output=True, text=True)
        if build.returncode:
            raise RuntimeError(build.stdout+build.stderr)
        targets = [('poly_id', [1]), ('imp_id', []), ('dependent_id', [1, 1]), ('beta_type', []),
                   ('delta_type', []), ('use_library_id', [1]), ('unsupported_nat', [])]
        config, output = cls.directory/'export.json', cls.directory/'corpus.jsonl'
        config.write_text(json.dumps(dict(modules=['DependentCorpus'], targets=[dict(name='LeanputerCorpus.'+name, levels=levels) for name, levels in targets], output=str(output))))
        environment = dict(os.environ, LEAN_PATH=str(cls.directory))
        exported = subprocess.run(['lean', '--run', str(ROOT/'tools/lean/Export.lean'), str(config)], env=environment, capture_output=True, text=True)
        if exported.returncode:
            raise RuntimeError(exported.stdout+exported.stderr)
        cls.documents = [json.loads(line) for line in output.read_text().splitlines()]
        cls.supported = [document for document in cls.documents if 'term' in document]
        cls.invalid = []
        for name, term in [('capture', ['lam', ['sort', 1], ['lam', ['var', 0], ['var', 1]]]),
                           ('free', ['lam', ['sort', 1], ['lam', ['var', 0], ['var', 99]]])]:
            item = copy.deepcopy(cls.supported[0]); item.update(name=name, term=term)
            cls.invalid.append(item)
        wrong_claim = copy.deepcopy(cls.supported[0]); wrong_claim.update(name='wrong_claim', claim=['sort', 0]); cls.invalid.append(wrong_claim)
        bad_environment = copy.deepcopy(cls.supported[-1]); bad_environment['name'] = 'bad_environment'
        bad_environment['environment'][0]['value'] = ['sort', 0]
        cls.invalid.append(bad_environment)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_export_is_real_dependent_syntax_and_complete_dependencies(self):
        self.assertEqual(len(self.supported), 6)
        self.assertEqual(self.documents[-1]['status'], 'UNSUPPORTED')
        self.assertIn('Nat', self.documents[-1]['reason'])
        dependent = self.supported[2]
        self.assertIn('app', str(dependent['claim']))
        self.assertEqual(dependent['provenance']['preparation'], 'syntax-only Expr traversal and universe instantiation')
        self.assertEqual(self.supported[-1]['environment'][0]['name'], 'id@[1]')
        self.assertIsNotNone(self.supported[-1]['environment'][0]['value'])
        # The required beta work remains in the exported type.
        self.assertIn('lam', str(self.supported[3]['claim']))

    def test_model_recursive_operational_and_actual_lean_agree(self):
        documents = self.supported+self.invalid
        cfg = MachineConfig(heap=128, stack=32, context=16, constants=8, fuel=512)
        expected = ['ACCEPT']*len(self.supported)+['REJECT']*len(self.invalid)
        for document, status in zip(documents, expected):
            term, claim, environment = parse_document(document)
            try:
                actual = Oracle(environment).check(term, claim)
            except Rejected:
                actual = False
            self.assertEqual(actual, status == 'ACCEPT', document['name'])
            spec = SpecMachine(cfg, prepare(cfg, term, claim, environment)).run()
            self.assertEqual(Outcome(spec['regs']['status']).name, status, document['name'])
        replay, _ = lean_replay(documents, self.directory/'replay')
        self.assertEqual([r['status'] for r in replay], expected)
        model = compile_machine(cfg)
        report = check_batch(model, documents)
        self.assertEqual([r['status'] for r in report['results']], expected)

    @unittest.skipUnless(NANODA.is_file(), 'nanoda binary unavailable')
    def test_independent_nanoda_replay(self):
        documents = [self.supported[2], self.supported[-1], self.invalid[0], self.invalid[-1]]
        for index, document in enumerate(documents):
            result = nanoda_replay(document, self.directory/f'nanoda-{index}', NANODA)
            self.assertEqual(result['status'], 'REJECT' if document in self.invalid else 'ACCEPT', result)
