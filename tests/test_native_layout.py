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

    def test_dependency_commit_preserves_simultaneous_swap_and_identity_feedback(self):
        import torch
        from leanputer.native import emit_stock
        from leanputer.native_machine import NativeBuilder,commit_native_outputs,validate_native_schedule
        torch.set_num_threads(1)
        builder=NativeBuilder(intermediate=32,reset_layers=4)
        a,b,c,d=features=[builder.feature(name)for name in ('a','b','c','d')]
        disjunction=builder.gate('or',[a,b],'one-unit-or')
        stats=commit_native_outputs(builder,features,[b,a,disjunction,d])
        self.assertEqual(stats,dict(output_channels=4,snapshots=2,unchanged=1,direct_commits=1))
        validate_native_schedule(builder.graph)
        dims=[next(iter(f.terms))for f in features]
        model,layout,_=emit_stock(builder.graph,dims,32,torch.bfloat16,'cpu',reset_layers=4)
        rows=list(itertools.product((0,1),repeat=4));state=torch.zeros(16,1,layout.hidden,dtype=torch.bfloat16)
        state[:,:,:layout.m]=layout.ballast
        for i,dim in enumerate(dims):state[:,0,layout.dim(dim)]=torch.tensor([r[i]for r in rows],dtype=torch.bfloat16)
        with torch.inference_mode():
            cache=None
            for step in range(3):
                out=model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True)
                cache=out.past_key_values;state=out.hidden_states[-2]
                expected=[[float(b if step%2==0 else a),float(a if step%2==0 else b),float(bool(a or b)),float(d)]for a,b,c,d in rows]
                self.assertEqual(out.logits[:,0,:].float().tolist(),expected)

    def test_lossless_packed_control_overlapping_updates_and_identity_feedback(self):
        from types import SimpleNamespace
        import torch
        from leanputer.bitvec import Builder,pack_words
        from leanputer.control_packing import ControlPacking,packed_update_outputs
        from leanputer.native import emit_stock
        from leanputer.native_machine import NativeBuilder,commit_native_outputs,validate_native_schedule
        torch.set_num_threads(1)
        for width,digit_bits in ((3,2),(8,8)):
            packing=ControlPacking(SimpleNamespace(fields=[('a',width),('b',width),('flags',2)],width=2*width+2),digit_bits)
            logic=Builder([str(i)for i in range(2*width+2)]);a=logic.inputs[:width];b=logic.inputs[width:2*width];f=logic.inputs[2*width:]
            fields=[];updated=[]
            for name,bits,choices in [('a',a,[(f[0],b),(f[1],b)]),('b',b,[(f[1],logic.add(a,logic.const(1,width)))]),('flags',f,[(logic.one,tuple(logic.NOT(v)for v in f))])]:
                keep=logic.NOT(logic.OR(*(g for g,v in choices)))
                fresh=[logic.masked_or([(g,v[i])for g,v in choices])for i in range(len(bits))]
                fields.append((name,keep,fresh));updated.extend(fresh)
            logic.c.native_packed_fields=fields
            builder=NativeBuilder(intermediate=64,reset_layers=4);physical,logical=packing.features(builder)
            values=packed_update_outputs(builder,(logic.c,[logic.zero]*(2*width+2)),logical,physical,2*width+2,digit_bits)
            commit_native_outputs(builder,physical,values);validate_native_schedule(builder.graph)
            dims=[next(iter(v.terms))for v in physical];model,layout,_=emit_stock(builder.graph,dims,64,torch.bfloat16,'cuda'if torch.cuda.is_available()else'cpu',reset_layers=4,weight_storage='sparse_csr')
            rows=list(itertools.product(range(8),range(8),range(4))) if width==3 else [(a,(73*a+19)%256,f)for a in range(256)for f in range(4)]
            source=torch.tensor([pack_words([a,b,f],[width,width,2])for a,b,f in rows]);digits=packing.encode(source)
            self.assertEqual(packing.decode(digits).tolist(),source.tolist())
            state=torch.zeros(len(rows),1,layout.hidden,dtype=torch.bfloat16,device=next(model.parameters()).device);state[:,:,:layout.m]=layout.ballast
            for i,dim in enumerate(dims):state[:,0,layout.dim(dim)]=digits[:,i].to(torch.bfloat16)
            with torch.no_grad():
                cache=None
                for step in range(3):
                    out=model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True);cache=out.past_key_values;state=out.hidden_states[-2]
                    rows=[(b if f else a,(a+1)&((1<<width)-1) if f&2 else b,f^3)for a,b,f in rows]
                    expected=torch.tensor([pack_words([a,b,f],[width,width,2])for a,b,f in rows])
                    self.assertEqual(packing.decode(out.logits[:,0,:].float().cpu()).tolist(),expected.tolist())
