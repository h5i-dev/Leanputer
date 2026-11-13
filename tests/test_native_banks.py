"""Native RAM bank boundaries, disabled writes and changing query banks."""
import importlib.util
import sys
import unittest


@unittest.skipUnless(sys.version_info >= (3,11) and importlib.util.find_spec('transformers'),
                     'native RAM requires Python3.11+ and transformers extra')
class NativeBankSmoke(unittest.TestCase):
    def test_residual_accumulation_matches_separate_bank_outputs(self):
        import torch
        from leanputer.native import emit_stock
        from leanputer.native_machine import NativeBuilder, banked_native_read, validate_native_schedule
        torch.set_num_threads(1)
        torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction=False
        addresses=[0,127,128,255,256,383,384,511]
        devices=['cpu']+(['cuda']if torch.cuda.is_available()else[])
        for device in devices:
            for policy,ballast_limit in [('separate',16),('accumulate',16),('accumulate',64)]:
                with self.subTest(device=device,policy=policy,ballast_limit=ballast_limit):
                    builder=NativeBuilder(intermediate=512,reset_layers=0)
                    features=[builder.feature(str(i))for i in range(21)]
                    # Force the expanded search to select >16 ballast channels;
                    # otherwise this tiny graph never exercises the new layout.
                    padding=[builder.feature('padding/'+str(i))for i in range(1030)] if ballast_limit>16 else []
                    outputs=banked_native_read(builder,512,features[:9],features[9:18],
                        features[18],features[19:21],'boundary','heap',[],policy)
                    outputs=[builder.graph.ffn([(1,builder.graph.one,value)],name='readout')for value in outputs]
                    validate_native_schedule(builder.graph)
                    dims=[next(iter(value.terms))for value in outputs]
                    keep=[next(iter(value.terms))for value in padding]
                    model,layout,_=emit_stock(builder.graph,dims,512,torch.bfloat16,device,keep_dims=keep,max_ballast=ballast_limit)
                    if padding:self.assertGreater(layout.m,16)
                    slots=[layout.dim(next(iter(feature.terms)))for feature in features]
                    cache=None
                    with torch.inference_mode():
                        for phase in range(3):
                            state=torch.zeros(8,1,layout.hidden,device=device,dtype=torch.bfloat16)
                            state[:,:,:layout.m]=layout.ballast
                            expected=[]
                            for index,address in enumerate(addresses):
                                query=address if phase!=1 else (address+128)%512
                                values=[float(bool(query&(1<<bit)))for bit in range(9)]
                                values += [float(bool(address&(1<<bit)))for bit in range(9)]
                                values += [float(phase==0),1.,float(index%2)]
                                state[index,0,slots]=torch.tensor(values,device=device,dtype=torch.bfloat16)
                                expected.append([1.,float(index%2)]if phase!=1 else [0.,0.])
                            result=model(inputs_embeds=state,past_key_values=cache,use_cache=True)
                            cache=result.past_key_values
                            self.assertEqual(result.logits[:,0,:].float().cpu().tolist(),expected)
                    del model,cache,result
