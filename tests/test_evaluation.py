import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from leanputer.corpus import generate
from leanputer.dependent import Oracle
from leanputer.evaluation import evaluate
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch, parse_document
from leanputer.transition import compile_machine
from leanputer.validation import minimize, reference_result, trace_discrepancy


class EvaluationHarnessTests(unittest.TestCase):
    def test_reports_preserve_malformed_rows_and_opaque_metadata(self):
        doc = generate(synthetic=2, mutations=0, fuzz=0)[1]
        doc['provenance'] = dict(family=[], source_constant=[])
        config = MachineConfig(heap=32, stack=8, context=4, constants=2, fuel=128)
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate([None, doc], config, 'cpu', directory, repeats=0)
        self.assertEqual(result['counts'], {'MALFORMED': 1, 'ACCEPT': 1})
        self.assertEqual(result['mismatches'], [])
        self.assertEqual(result['real_source_constants'], 0)

    def test_seeded_generation_and_positive_recipes(self):
        first = generate(seed=81, synthetic=36, mutations=5, fuzz=5)
        self.assertEqual(first, generate(seed=81, synthetic=36, mutations=5, fuzz=5))
        for document in first[:36]:
            term, claim, environment = parse_document(document)
            self.assertTrue(Oracle(environment).check(term, claim), document['name'])

    def test_minimizer_preserves_predicate_and_reduces(self):
        doc = generate(synthetic=2, mutations=0, fuzz=0)[1]
        original = copy.deepcopy(doc)
        predicate = lambda candidate: 'lam' in str(candidate['term'])
        minimized, attempts = minimize(doc, predicate, attempts=20)
        self.assertTrue(predicate(minimized))
        self.assertLess(len(str(minimized['term'])), len(str(doc['term'])))
        self.assertEqual(doc, original)
        self.assertGreater(attempts, 0)

    def test_no_reference_or_external_checker_in_runtime(self):
        config = MachineConfig(heap=32, stack=8, context=4, constants=2, fuel=128)
        model = compile_machine(config)
        document = generate(synthetic=2, mutations=0, fuzz=0)[1]
        with mock.patch('leanputer.dependent.Oracle.check', side_effect=AssertionError('oracle called')), \
             mock.patch('leanputer.machine_spec.SpecMachine.step', side_effect=AssertionError('spec called')), \
             mock.patch('subprocess.run', side_effect=AssertionError('external checker called')):
            self.assertEqual(check_batch(model, [document])['results'][0]['status'], 'ACCEPT')

    def test_end_to_end_report_and_trace(self):
        config = MachineConfig(heap=32, stack=8, context=4, constants=2, fuel=128)
        docs = generate(synthetic=2, mutations=2, fuzz=2)
        unsupported = dict(format='leanputer.dependent.v1', name='unsupported', status='UNSUPPORTED', reason='fixture')
        docs.append(unsupported)
        with tempfile.TemporaryDirectory(dir='/mnt/scratch' if Path('/mnt/scratch').is_dir() else None) as directory:
            result = evaluate(docs, config, 'cpu', directory, batch_size=8, traces=2)
            self.assertEqual(result['mismatches'], [])
            self.assertEqual(result['counts']['UNSUPPORTED'], 1)
            self.assertGreater(result['unique_syntax_judgments'], 1)
            self.assertEqual(result['traced_documents'], 2)
            self.assertTrue((Path(directory)/'evaluation.json').is_file())
        model = compile_machine(config)
        self.assertIsNone(trace_discrepancy(model, docs[1]))
        self.assertEqual(reference_result(docs[1], config)['status'], 'ACCEPT')

    def test_domain_errors_are_never_rounded_and_faults_have_traces(self):
        config = MachineConfig(heap=32, stack=8, context=4, constants=2, fuel=128)
        model = compile_machine(config)
        with self.assertRaisesRegex(ValueError, 'no rounding'):
            model.layout.decode([.5]*model.layout.width)
        document = generate(synthetic=2, mutations=0, fuzz=0)[1]
        original = model.transition.forward
        model.transition.forward = lambda bits: original(bits).roll(1, dims=1)
        discrepancy = trace_discrepancy(model, document)
        self.assertEqual(discrepancy['step'], 1)
        self.assertTrue(discrepancy['banks'])
