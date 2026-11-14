"""Numerical boundaries introduced by compact stock control lowering."""
import importlib.util
import sys
import unittest


@unittest.skipUnless(sys.version_info >= (3,11) and importlib.util.find_spec('transformers'),
                     'stock backend requires native environment')
class CompactControlTest(unittest.TestCase):
    def test_tail_clear_reclaims_boot_input_and_preserves_identity_feedback(self):
        import torch
        from leanputer.native_machine import NativeBuilder,commit_native_outputs
        from leanputer.native import emit_stock
        torch.set_num_threads(1)
        builder=NativeBuilder(intermediate=32,reset_layers=0)
        value=builder.feature('value');boot=builder.feature('boot')
        temporary=builder.gate('or',[value,boot],'temporary')
        commit_native_outputs(builder,[value],[builder.graph.one-value])
        # The boot feature can be handed to a later scratch value. Tail clears
        # remove that value as well, before the hidden-state identity feedback.
        builder.graph.ffn([(1,builder.graph.one,temporary)],name='late-use',min_level=8)
        dim=next(iter(value.terms));bootdim=next(iter(boot.terms))
        model,layout,allocation=emit_stock(builder.graph,[dim],32,torch.bfloat16,'cpu',keep_dims={dim},tail_clear=True)
        state=torch.zeros(2,1,layout.hidden,dtype=torch.bfloat16);state[:,:,:layout.m]=layout.ballast
        state[:,0,layout.dim(dim)]=torch.tensor([0.,1.],dtype=torch.bfloat16)
        state[:,0,layout.dim(bootdim)]=1
        cache=None
        with torch.no_grad():
            for step in range(4):
                out=model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True)
                state=out.hidden_states[-2];cache=out.past_key_values
                self.assertEqual(out.logits[:,0,0].float().tolist(),[float((step+1)%2),float(step%2)])
                self.assertTrue(torch.all(state[:,0,layout.dim(bootdim)]==0))
                cleared=[i for i in range(layout.m,layout.hidden)if i!=layout.dim(dim)]
                self.assertTrue(torch.all(state[:,0,cleared]==0))

    def test_scoped_native_words_keep_inactive_arithmetic_and_mux_quiet(self):
        from types import SimpleNamespace
        import torch
        from leanputer.bitvec import Builder,pack_words
        from leanputer.control_packing import ControlPacking
        from leanputer.native_machine import NativeBuilder,commit_native_outputs
        from leanputer.native import emit_stock
        torch.set_num_threads(1)
        packing=ControlPacking(SimpleNamespace(fields=[('owner',1),('a',17),('b',17),('out',17)],width=52),8)
        logic=Builder([str(i)for i in range(52)]);owner=logic.inputs[0];a=logic.inputs[1:18];b=logic.inputs[18:35]
        summed=logic.add(a,b);decremented=logic.sub(a,logic.const(1,17))[0]
        picked=logic.mux(a[0],summed,b)
        result=[logic.OR(logic.AND(logic.NOT(owner),x),logic.AND(owner,y))for x,y in zip(picked,decremented)]
        logic.c.native_phase_context=dict(zero=[7]+[63]*51,one=[56]+[63]*51,forced_zero={},forced_one={},count=2,owners=[0,1])
        builder=NativeBuilder(intermediate=128,reset_layers=8,native_word_ops=True);physical,inputs=packing.features(builder)
        latched=builder.graph.ffn([(1,builder.graph.one,physical[0])],min_level=builder.barrier)
        builder.scratch_guards=[builder.graph.one-latched,latched];builder.graph.scratch_guards=builder.scratch_guards;builder.graph.phase_scratch=True
        bits=builder.circuit((logic.c,result),inputs,'word-scopes')
        outputs=list(physical);outputs[0]=builder.graph.one-physical[0]
        for digit in range(3):outputs[7+digit]=sum(((1<<i)*value for i,value in enumerate(bits[8*digit:8*digit+8])),builder.graph.one*0)
        commit_native_outputs(builder,physical,outputs)
        dims=[next(iter(v.terms))for v in physical];results=dims[7:10]+[dims[0]]
        model,layout,_=emit_stock(builder.graph,results,128,torch.bfloat16,'cpu',keep_dims=set(dims),reset_layers=8)
        self.assertTrue(any(n.name.startswith('word-')and getattr(n,'scope',None)is not None for n in builder.graph.nodes))
        rows=[(owner,a,b)for owner in (0,1)for a,b in ((0,131071),(1,65535),(15,16),(65535,65536),(131071,1))]
        data=packing.encode(torch.tensor([pack_words([owner,a,b,0],[1,17,17,17])for owner,a,b in rows]))
        state=torch.zeros(len(rows),1,layout.hidden,dtype=torch.bfloat16);state[:,:,:layout.m]=layout.ballast
        for i,d in enumerate(dims):state[:,0,layout.dim(d)]=data[:,i].to(torch.bfloat16)
        cache=None
        with torch.no_grad():
            for step in range(4):
                out=model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True)
                state=out.hidden_states[-2];cache=out.past_key_values
                expected=[]
                for owner,a,b in rows:
                    current=owner^(step%2);value=(a-1)%131072 if current else (a+b)%131072 if a&1 else b
                    expected.append([float(value&255),float((value>>8)&255),float(value>>16),float(1-current)])
                self.assertEqual(out.logits[:,0,:].float().tolist(),expected)

    def test_scoped_scratch_clears_conditionally_and_exports_across_owner_changes(self):
        import itertools
        import torch
        from leanputer.bitvec import Builder
        from leanputer.native_machine import NativeBuilder,commit_native_outputs
        from leanputer.native import emit_stock
        torch.set_num_threads(1)
        logic=Builder(['owner','a','b','out','inverse']);owner,a,b,_,_=logic.inputs
        chosen=logic.OR(logic.AND(logic.NOT(owner),a),logic.AND(owner,b))
        logic.c.native_phase_context=dict(zero=[7,63,63,63,63],one=[56,63,63,63,63],
            forced_zero={},forced_one={},count=2,owners=[0,1])
        builder=NativeBuilder(intermediate=32,reset_layers=4)
        features=[builder.feature(n)for n in logic.c.inputs]
        latched=builder.graph.ffn([(1,builder.graph.one,features[0])],min_level=builder.barrier)
        builder.scratch_guards=[builder.graph.one-latched,latched]
        builder.graph.scratch_guards=builder.scratch_guards;builder.graph.phase_scratch=True
        values=builder.circuit((logic.c,[chosen,logic.NOT(chosen)]),features,'scope')
        commit_native_outputs(builder,features,[builder.graph.one-features[0],features[1],features[2]]+values)
        all_dims=[next(iter(v.terms))for v in features];dims=[all_dims[i]for i in (3,4,0)]
        model,layout,allocation=emit_stock(builder.graph,dims,32,torch.bfloat16,'cpu',keep_dims=set(all_dims),reset_layers=4)
        self.assertGreater(builder.graph.scratch_statistics['private_window'],0)
        scoped={}
        for node in builder.graph.nodes:
            scope=getattr(node,'scope',None)
            if scope is not None:scoped.setdefault(scope,set()).add(allocation.slots[node.out])
        self.assertTrue(scoped[0]&scoped[1])
        rows=list(itertools.product((0,1),repeat=3));state=torch.zeros(8,1,layout.hidden,dtype=torch.bfloat16)
        state[:,:,:layout.m]=layout.ballast
        for i,d in enumerate(all_dims):state[:,0,layout.dim(d)]=torch.tensor([r[i]if i<3 else 0 for r in rows],dtype=torch.bfloat16)
        cache=None
        with torch.no_grad():
            for step in range(4):
                output=model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True)
                state=output.hidden_states[-2];cache=output.past_key_values
                expected=[]
                for owner,a,b in rows:
                    current=owner^(step%2);value=b if current else a
                    expected.append([float(value),float(1-value),float(1-current)])
                self.assertEqual(output.logits[:,0,:].float().tolist(),expected)

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
