"""Minimal stock-forward migration smoke; broad validation is deferred."""
import importlib.util
import sys
import unittest


@unittest.skipUnless(sys.version_info >= (3, 11) and importlib.util.find_spec('transformers'),
                     'native backend requires Python3.11+ and transformers extra')
class NativeArchitectureSmoke(unittest.TestCase):
    def test_complete_bounded_stlc_uses_stock_forward(self):
        from leanputer.native import smoke
        result = smoke('cpu')
        self.assertEqual([case['accept'] for case in result['cases']], [True, True, False, False])
        self.assertEqual(result['stock_class'], 'transformers.models.qwen3_5.modeling_qwen3_5.Qwen3_5ForCausalLM')
