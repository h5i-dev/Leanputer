import dataclasses
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import torch

from leanputer.dependent import Oracle, Rejected
from leanputer.dependent_examples import conversion_cases
from leanputer.machine_spec import MachineConfig, Outcome, SpecMachine, prepare
from leanputer.references import lean_replay, nanoda_replay
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


NANODA = Path(os.environ.get('LEANPUTER_NANODA_BIN', '/mnt/scratch/leanputer-references/nanoda-target/release/nanoda_bin'))
torch.set_num_threads(1)


def documents():
    return [dict(format='leanputer.dependent.v1', name=name, term=term, claim=claim,
                 environment=[dataclasses.asdict(d) for d in env])
            for name, term, claim, env, _ in conversion_cases()]


class ExtendedConversionTests(unittest.TestCase):
    def test_recursive_operational_and_weighted_conversion(self):
        cfg = MachineConfig(heap=64, stack=16, context=8, constants=8, fuel=512)
        cases = conversion_cases()
        for name, term, claim, env, expected in cases:
            try:
                actual = Oracle(env).check(term, claim)
            except Rejected:
                actual = False
            self.assertEqual(actual, expected, name)
            spec = SpecMachine(cfg, prepare(cfg, term, claim, env)).run()
            self.assertEqual(spec['regs']['status'], Outcome.ACCEPT if expected else Outcome.REJECT, (name, spec['regs']))
        report = check_batch(compile_machine(cfg), documents())
        self.assertEqual([r['status'] for r in report['results']], ['ACCEPT', 'ACCEPT', 'REJECT', 'REJECT', 'REJECT'])

    @unittest.skipUnless(shutil.which('lean'), 'Lean unavailable')
    def test_actual_lean_conversion_rules(self):
        with tempfile.TemporaryDirectory(dir='/mnt/scratch' if Path('/mnt/scratch').is_dir() else None) as directory:
            replay, _ = lean_replay(documents(), directory)
            self.assertEqual([r['status'] for r in replay], ['ACCEPT', 'ACCEPT', 'REJECT', 'REJECT', 'REJECT'])

    @unittest.skipUnless(NANODA.is_file(), 'nanoda binary unavailable')
    def test_nanoda_conversion_and_opacity(self):
        with tempfile.TemporaryDirectory(dir='/mnt/scratch' if Path('/mnt/scratch').is_dir() else None) as directory:
            for index, (document, expected) in enumerate(zip(documents(), [True, True, False, False, False])):
                result = nanoda_replay(document, Path(directory)/str(index), NANODA)
                self.assertEqual(result['status'], 'ACCEPT' if expected else 'REJECT', result)
