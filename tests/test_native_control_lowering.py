"""Numerical boundaries introduced by compact stock control lowering."""
import importlib.util
import sys
import unittest


@unittest.skipUnless(sys.version_info >= (3,11) and importlib.util.find_spec('transformers'),
                     'stock backend requires native environment')
class CompactControlTest(unittest.TestCase):
    def test_word_arithmetic_and_select_preserve_partial_digits_and_borrow_in(self):
        from types import SimpleNamespace
        import torch
        from leanputer.bitvec import Builder,pack_words
        from leanputer.control_packing import ControlPacking
        from leanputer.native_machine import NativeBuilder
        from leanputer.native import emit_stock
        torch.set_num_threads(1)
        packing=ControlPacking(SimpleNamespace(fields=[('a',17),('b',17),('condition',1)],width=35),8)
        logic=Builder([str(i)for i in range(35)]);a=logic.inputs[:17];b=logic.inputs[17:34];condition=logic.inputs[34]
        sub,borrow=logic.sub(a,b);sub1,borrow1=logic.sub(a,b,True)
        outputs=list(logic.add(a,b))+list(sub)+[borrow]+list(sub1)+[borrow1]+list(logic.mux(condition,a,b))+[logic.lt(a,b),logic.eq(a,b)]
        builder=NativeBuilder(intermediate=128,reset_layers=0,native_word_ops=True)
        physical,inputs=packing.features(builder);values=builder.circuit((logic.c,outputs),inputs,'arithmetic')
        self.assertGreaterEqual(builder.word_operation_count,5)
        values=[builder.graph.ffn([(1,builder.graph.one,v)])for v in values]
        dims=[next(iter(v.terms))for v in values];model,layout,_=emit_stock(builder.graph,dims,128,torch.bfloat16,'cpu')
        boundary=(0,1,15,16,255,256,65535,65536,131070,131071)
        rows=[(a,b,c)for a in boundary for b in boundary for c in (0,1)]
        digits=packing.encode(torch.tensor([pack_words(row,[17,17,1])for row in rows]))
        state=torch.zeros(len(rows),1,layout.hidden,dtype=torch.bfloat16);state[:,:,:layout.m]=layout.ballast
        for i,v in enumerate(physical):state[:,0,layout.dim(next(iter(v.terms)))]=digits[:,i].to(torch.bfloat16)
        with torch.no_grad():actual=model(inputs_embeds=state,use_cache=False).logits[:,0,:].float().tolist()
        expected=[pack_words([(a+b)%131072,(a-b)%131072,int(a<b),(a-b-1)%131072,int(a<b+1),a if c else b,int(a<b),int(a==b)],
            [17,17,1,17,1,17,1,1])for a,b,c in rows]
        self.assertEqual(actual,expected)

    def test_unsigned_word_comparison_preserves_byte_borrow_and_256_threshold(self):
        from types import SimpleNamespace
        import torch
        from leanputer.bitvec import Builder,pack_words
        from leanputer.control_packing import ControlPacking
        from leanputer.native_machine import NativeBuilder
        from leanputer.native import emit_stock
        torch.set_num_threads(1)
        packing=ControlPacking(SimpleNamespace(fields=[('a',16),('b',16)],width=32),8)
        logic=Builder([str(i)for i in range(32)])
        outputs=[logic.lt(logic.inputs[:16],logic.inputs[16:]),logic.lt(logic.inputs[16:],logic.inputs[:16])]
        builder=NativeBuilder(intermediate=32,reset_layers=0,native_word_ops=True)
        physical,inputs=packing.features(builder)
        values=builder.circuit((logic.c,outputs),inputs,'compare')
        self.assertEqual(builder.word_operation_count,2)
        values=[builder.graph.ffn([(1,builder.graph.one,v)])for v in values]
        dims=[next(iter(v.terms))for v in values]
        model,layout,_=emit_stock(builder.graph,dims,32,torch.bfloat16,'cpu')
        rows=[(a,b)for a in (0,1,254,255,256,257,32767,32768,65280,65534,65535)
              for b in (0,1,254,255,256,257,32767,32768,65280,65534,65535)]
        digits=packing.encode(torch.tensor([pack_words(row,[16,16])for row in rows]))
        state=torch.zeros(len(rows),1,layout.hidden,dtype=torch.bfloat16);state[:,:,:layout.m]=layout.ballast
        for i,v in enumerate(physical):state[:,0,layout.dim(next(iter(v.terms)))]=digits[:,i].to(torch.bfloat16)
        with torch.no_grad():actual=model(inputs_embeds=state,use_cache=False).logits[:,0,:].float().tolist()
        self.assertEqual(actual,[[float(a<b),float(b<a)]for a,b in rows])

    def test_native_cache_stores_full_126_byte_row_and_preserves_other_owner(self):
        import torch
        from leanputer.native_machine import NativeBuilder,banked_native_read
        from leanputer.native import emit_stock
        torch.set_num_threads(1)
        builder=NativeBuilder(intermediate=512,reset_layers=0)
        features=[builder.feature(str(i))for i in range(15+16)]
        from leanputer.control_packing import PackedBit
        memo={}
        data_bits=[PackedBit(features[15+i//8],i%8,8).realize(builder,memo)for i in range(126)]
        values=banked_native_read(builder,128,features[:7],features[7:14],features[14],data_bits,
            'private','control',[])
        values=[builder.graph.ffn([(1,builder.graph.one,v)])for v in values]
        dims=[next(iter(v.terms))for v in values]
        model,layout,_=emit_stock(builder.graph,dims,512,torch.bfloat16,'cpu')
        slots=[layout.dim(next(iter(v.terms)))for v in features]
        full=[255.]*16;zero=[0.]*16;ordinal=list(map(float,range(16)))
        cache=None
        with torch.no_grad():
            for query,address,write,data,expected in [(97,97,1,full,full),(97,94,0,full,full),
                    (94,94,1,ordinal,ordinal),(97,94,1,zero,full),(94,97,0,full,zero)]:
                state=torch.zeros(1,1,layout.hidden,dtype=torch.bfloat16);state[:,:,:layout.m]=layout.ballast
                raw=[float(bool(query&(1<<bit)))for bit in range(7)]+[float(bool(address&(1<<bit)))for bit in range(7)]+[float(write)]+data
                state[0,0,slots]=torch.tensor(raw,dtype=torch.bfloat16)
                output=model(inputs_embeds=state,past_key_values=cache,use_cache=True);cache=output.past_key_values
                self.assertEqual(output.logits[0,0,:].float().tolist(),[float(bool(int(expected[i//8])&(1<<(i%8))))for i in range(126)])
