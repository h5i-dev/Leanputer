import copy
import json
import tempfile
import unittest
from pathlib import Path

import torch

from leanputer.machine_spec import MachineConfig, prepare
from leanputer.research import main
from leanputer.research_artifacts import load_machine, save_machine
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


torch.set_num_threads(1)
IDENTITY = dict(format='leanputer.dependent.v1', name='identity',
                term=['lam', ['sort', 0], ['var', 0]], claim=['pi', ['sort', 0], ['sort', 0]])


class ResearchRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = MachineConfig(heap=32, stack=8, context=4, constants=2, fuel=64)
        cls.model = compile_machine(cls.config)

    def test_canonical_initialization_ignores_forged_control_and_memory(self):
        original = prepare(self.config, IDENTITY['term'], IDENTITY['claim'])
        forged = copy.deepcopy(original)
        for key in forged['regs']:
            if key not in ('free', 'decl_count', 'term', 'claim'):
                forged['regs'][key] = 3
        forged['stack'] = [[7]*6 for _ in forged['stack']]
        forged['context'] = [[7] for _ in forged['context']]
        actual = self.model.initializer(self.model.layout.encode(forged))
        self.assertTrue(torch.equal(actual, self.model.layout.encode(original)))

    def test_batch_categories(self):
        wrong = copy.deepcopy(IDENTITY); wrong.update(name='unbound', term=['var', 0])
        unsupported = copy.deepcopy(IDENTITY); unsupported['term'] = ['inductive', 'Nat']
        malformed = copy.deepcopy(IDENTITY); malformed['typo'] = True
        resource = copy.deepcopy(IDENTITY); resource['term'] = ['var', 1000]
        result = check_batch(self.model, [IDENTITY, wrong, unsupported, malformed, resource])
        self.assertEqual([r['status'] for r in result['results']], ['ACCEPT', 'REJECT', 'UNSUPPORTED', 'MALFORMED', 'RESOURCE'])
        self.assertEqual(result['runtime']['applied_steps'], 65)
        self.assertEqual(result['results'][0]['semantic_steps'], 52)
        self.assertEqual(result['model']['trainable_parameters'], 0)

    def test_versioned_artifacts_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'machine.pt'
            save_machine(self.model, path)
            restored = load_machine(path)
            self.assertEqual(restored.config, self.config)
            source, output = root/'input.jsonl', root/'report.json'
            source.write_text(json.dumps(IDENTITY)+'\n')
            self.assertEqual(main(['--load', str(path), '--input', str(source), '--report', str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())['results'][0]['status'], 'ACCEPT')
            artifact = torch.load(path, weights_only=True)
            artifact['state_dict']['heap_read.query_weight'][0, 0] += 1
            torch.save(artifact, path)
            with self.assertRaisesRegex(ValueError, 'tensor mismatch'):
                load_machine(path)
            artifact['compiler'] = 'wrong'
            torch.save(artifact, path)
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                load_machine(path)

    def test_attention_write_artifact_preserves_backend(self):
        model = compile_machine(self.config, memory_update='attention_delta')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'attention.pt'
            save_machine(model, path)
            restored = load_machine(path)
            self.assertEqual(restored.memory_update, 'attention_delta')
            self.assertEqual(check_batch(restored, [IDENTITY])['results'],
                             check_batch(self.model, [IDENTITY])['results'])
