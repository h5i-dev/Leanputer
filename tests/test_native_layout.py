"""Native compiler regression: repeated data selected by overlapping guards."""
import importlib.util
import itertools
import sys
import unittest


@unittest.skipUnless(sys.version_info>=(3,11) and importlib.util.find_spec('transformers'),
                     'native layout requires Python3.11+ and transformers extra')
class NativeLayoutSmoke(unittest.TestCase):
    def test_factoring_retains_boolean_or_for_overlapping_guards(self):
        import torch
        from leanputer.bitvec import Builder
        from leanputer.native import emit_stock
        from leanputer.native_machine import NativeBuilder
        torch.set_num_threads(1)
        source=Builder(['first','second','data'])
        first,second,data=source.inputs
        output=source.masked_or([(first,data),(second,data)])
        plan=source.compile([output],target=lambda circuit,outputs:(circuit,outputs))
        native=NativeBuilder(intermediate=16,reset_layers=0)
        features=[native.feature(name)for name in source.c.inputs]
        value=native.circuit(plan,features,'overlapping-guards')[0]
        value=native.graph.ffn([(1,native.graph.one,value)],name='result')
        dim=next(iter(value.terms))
        model,layout,_=emit_stock(native.graph,[dim],16,torch.float32,'cpu')
        rows=list(itertools.product((0,1),repeat=3))
        state=torch.zeros(8,1,layout.hidden)
        state[:,:,:layout.m]=layout.ballast
        for index,feature in enumerate(features):
            state[:,0,layout.dim(next(iter(feature.terms)))]=torch.tensor([r[index]for r in rows])
        with torch.inference_mode():actual=model(inputs_embeds=state,use_cache=False).logits[:,0,0].tolist()
        self.assertEqual(actual,[0.,0.,0.,1.,0.,1.,0.,1.])
