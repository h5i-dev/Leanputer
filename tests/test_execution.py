import unittest

import torch

from leanputer.corpus import generate
from leanputer.execution import cuda_executor
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine
from leanputer.validation import trace_discrepancy
from leanputer.dependent_examples import conversion_cases
from dataclasses import asdict


torch.set_num_threads(1)


@unittest.skipUnless(torch.cuda.is_available(), 'CUDA unavailable')
class CudaGraphExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = MachineConfig(heap=64, stack=16, context=8, constants=8, fuel=512)
        cls.model = compile_machine(cls.config).cuda()

    def test_different_proofs_reuse_graph_with_exact_traces(self):
        for name, term, claim, env, expected in conversion_cases()[:2]:
            document = dict(format='leanputer.dependent.v1', name=name, term=term, claim=claim,
                            environment=[asdict(d) for d in env])
            self.assertIsNone(trace_discrepancy(self.model, document, execution='cuda_graph'))
        first, _ = cuda_executor(self.model, 1)
        second, setup = cuda_executor(self.model, 1)
        self.assertIs(first, second)
        self.assertEqual(setup, 0.)

    def test_graph_eager_outcomes_and_initialization_are_identical(self):
        docs = generate(synthetic=2, mutations=2, fuzz=2)
        eager = check_batch(self.model, docs)
        graph = check_batch(self.model, docs, execution='cuda_graph')
        self.assertEqual(eager['results'], graph['results'])
        self.assertEqual(eager['runtime']['applied_steps'], graph['runtime']['applied_steps'])
        self.assertEqual(graph['runtime']['execution'], 'cuda_graph')
        again = check_batch(self.model, list(reversed(docs)), execution='cuda_graph')
        self.assertEqual(list(reversed(graph['results'])), again['results'])
        self.assertEqual(again['runtime']['graph_setup_seconds'], 0.)
