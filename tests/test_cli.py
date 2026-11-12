import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import torch

from leanputer import Config, compile_checker, encode, Lam, Var
from leanputer.__main__ import main
from leanputer.artifacts import load_checker, save_checker


class ArtifactAndCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = Config(4, ('P', ('P', 'P')))
        cls.model = compile_checker(cls.config)

    def test_artifact_round_trip_and_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'checker.pt'
            save_checker(self.model, path)
            restored = load_checker(path)
            bits = encode(restored, Lam('p', 'P', Var('p')), ('P', 'P'))
            self.assertEqual(restored(bits).tolist(), self.model(bits).tolist())
            artifact = torch.load(path, weights_only=True)
            artifact['state_dict']['layers.0.bias'][0] += 1
            torch.save(artifact, path)
            with self.assertRaisesRegex(ValueError, 'weight mismatch'):
                load_checker(path)
            artifact['format_version'] = -1
            torch.save(artifact, path)
            with self.assertRaisesRegex(ValueError, 'format'):
                load_checker(path)

    def test_check_statuses_and_loaded_checker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / 'checker.pt'
            save_checker(self.model, artifact)
            cases = [
                (['lam', 'p', 'P', ['var', 'p']], ['P', 'P'], 'ACCEPT', 0),
                (['lam', 'p', 'P', ['var', 'free']], ['P', 'P'], 'REJECT', 1),
                (['lam', 'p', 'P', ['var', 'p']], 'unknown', 'RESOURCE_LIMIT', 2),
                (['lam', 'p', 'P', ['lam', 'q', 'P', ['var', 'q']]], ['P', 'P'], 'RESOURCE_LIMIT', 2),
            ]
            for term, claim, status, code in cases:
                input_path = root / 'input.json'
                input_path.write_text(json.dumps(dict(term=term, claim=claim)))
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    actual = main(['--load', str(artifact), '--check', str(input_path)])
                self.assertEqual(actual, code)
                self.assertEqual(json.loads(out.getvalue())['status'], status)

    def test_malformed_json_and_config_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.json'
            config.write_text(json.dumps(dict(nodes=4, types=['P', ['P', 'P']])))
            input_path = root / 'input.json'
            input_path.write_text(json.dumps(dict(term=['lam', 'x', 'P', ['var', 'x']], claim=['P', 'P'])))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--config', str(config), '--check', str(input_path)]), 0)
            input_path.write_text('{broken')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main(['--config', str(config), '--check', str(input_path)])
            self.assertEqual(raised.exception.code, 2)
            bad_artifact = root / 'broken.pt'
            bad_artifact.write_bytes(b'not a torch artifact')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main(['--load', str(bad_artifact)])
            self.assertEqual(raised.exception.code, 2)
