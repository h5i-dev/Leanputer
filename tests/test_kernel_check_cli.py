"""Input ledger boundaries: unavailable/bad/over-limit rows cannot become proofs."""
import unittest
from unittest.mock import patch
from leanputer.kernel_check import read_documents,check_sources
from leanputer.kernel.traversal_machine import MachineConfig
from tests.test_kernel_source_transition import cases


class KernelCheckLedgerTest(unittest.TestCase):
    def test_all_rows_retained_and_no_model_for_noninferable_inputs(self):
        rows=read_documents('not json\nnull\n{"format":"leanputer.kernel-source.v1","status":"SOURCE_UNAVAILABLE","reason":"missing dependency"}\n')
        limited=cases()[0]
        cfg=MachineConfig(heap=2,stack=2,context=2,constants=2,fuel=2,word_bits=8)
        with patch('leanputer.kernel_check.compile_native_machine',side_effect=AssertionError('no native-capable inputs')):
            report=check_sources(rows+[limited],cfg,device='cpu')
        self.assertEqual(report['denominator'],4)
        self.assertEqual([r['index'] for r in report['results']],[0,1,2,3])
        self.assertEqual(report['counts'],{'MALFORMED_INPUT':2,'SOURCE_UNAVAILABLE':1,'RESOURCE':1})
        self.assertEqual((report['native_attempted'],report['compile_seconds']),(0,0.))
        self.assertTrue(all(not row['target_checked'] and not row['native_attempted'] for row in report['results']))
        self.assertTrue(all(row['assumptions']==[] for row in report['results']))

    def test_missing_runtime_is_not_rejection_or_a_dropped_row(self):
        cfg=MachineConfig(heap=128,stack=16,context=8,constants=2,fuel=256,word_bits=8)
        with patch('leanputer.kernel_check.compile_native_machine',side_effect=RuntimeError('runtime unavailable')):
            report=check_sources([cases()[0]],cfg,device='cpu')
        self.assertEqual((report['denominator'],report['syntax_transport_ready'],report['native_attempted']),(1,1,0))
        self.assertEqual(report['counts'],{'INFERENCE_UNAVAILABLE':1})
        self.assertFalse(report['results'][0]['target_checked'])


if __name__=='__main__':unittest.main()
