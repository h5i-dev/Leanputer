"""Bounded stock launch-scheduling sample; NEVER a whole-proof admission run."""
import argparse,json,time
from pathlib import Path
import torch
from leanputer.kernel.control_capture import capture
from leanputer.kernel.control_store import ControlStore
from leanputer.kernel.stock_control import NativeControl
from leanputer.kernel.stock_datapath import build
from leanputer.kernel.stock_checker import syntax_packets
from leanputer.kernel.stock_execution import cache_tensors,snapshot,restore,StockCudaGraph
from leanputer.kernel.traversal_machine import MachineConfig


def main():
    p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=128);p.add_argument('--report',type=Path,required=True);p.add_argument('--compile-stock',action='store_true');p.add_argument('--all-gdn',action='store_true');p.add_argument('--check-native-pcs',action='store_true');p.add_argument('--save-prefix',type=Path);p.add_argument('--compare-prefix',type=Path);a=p.parse_args()
    if not 1<=a.steps<=512:raise ValueError('diagnostic prefix is bounded to512forwards')
    cfg=MachineConfig(**json.loads(Path('benchmarks/kernel-full-source-stock/config.json').read_text()));c,addresses=capture(cfg);program=NativeControl(ControlStore(c,role_dispatch=True),addresses)
    print(json.dumps(dict(event='compiled',control=program.report)),flush=True)
    chip=build(program.records,rom_layout='byte_pages',compact_attention=not a.all_gdn);chip.model.cuda();docs=[json.loads(line)for line in Path('benchmarks/kernel-full-source-stock/source.jsonl').read_text().splitlines()]
    print(json.dumps(dict(event='model-built',model=chip.report)),flush=True)
    packets=syntax_packets(chip,cfg,docs);cache=chip.new_cache();masks={'full_attention':None,'linear_attention':None};positions=torch.zeros(2,1,dtype=torch.long,device='cuda')
    with torch.inference_mode():
        for first in range(0,packets.shape[1],32):
            embeddings=chip.embeddings(packets[:,first:first+32]);out=chip.model(inputs_embeds=embeddings,past_key_values=cache,use_cache=True,position_ids=torch.zeros(embeddings.shape[:2],dtype=torch.long,device='cuda'),attention_mask=masks);cache=out.past_key_values
        state=chip.embeddings(torch.zeros(2,1,chip.slots.next-13));initial=snapshot(cache,state)
        print(json.dumps(dict(event='prefilled')),flush=True)
        torch.cuda.synchronize();started=time.perf_counter();pc_history=[]
        for _ in range(a.steps):
            out=chip.model(inputs_embeds=state,past_key_values=cache,use_cache=True,position_ids=positions,attention_mask=masks,output_hidden_states=True);state.copy_(out.hidden_states[-2])
            if a.check_native_pcs:pc_history.append(out.logits[:,0,:16].clone())
        torch.cuda.synchronize();eager_seconds=time.perf_counter()-started;eager=snapshot(cache,state);logits=out.logits.clone()
        if a.save_prefix:torch.save(dict(cache=eager[0],state=eager[1],logits=logits),a.save_prefix)
        print(json.dumps(dict(event='eager-prefix',seconds=eager_seconds)),flush=True)
        restore(cache,state,initial)
        model=torch.compile(chip.model,fullgraph=True,dynamic=False,options={'emulate_precision_casts':True})if a.compile_stock else chip.model
        executor=StockCudaGraph(model,cache,state,progress=lambda event:print(json.dumps(event),flush=True))
        torch.cuda.synchronize();started=time.perf_counter()
        for _ in range(a.steps):executor.replay()
        torch.cuda.synchronize();graph_seconds=time.perf_counter()-started
        equal_state=torch.equal(state,eager[1]);equal_cache=all(torch.equal(x,y)for x,y in zip(cache_tensors(cache),eager[0]));equal_logits=torch.equal(logits,executor.logits)
        if not(equal_state and equal_cache and equal_logits):raise AssertionError('captured stock prefix differs from eager')
        reference_match=None
        if a.compare_prefix:
            reference=torch.load(a.compare_prefix,weights_only=True,map_location='cuda')
            reference_match=torch.equal(state,reference['state'])and torch.equal(executor.logits,reference['logits'])and len(reference['cache'])==len(cache_tensors(cache))and all(torch.equal(x,y)for x,y in zip(cache_tensors(cache),reference['cache']))
            if not reference_match:raise AssertionError('optional stock kernel backend differs from Torch reference prefix')
    native_pc_boundaries=None
    if a.check_native_pcs:
        # AFTER inference only. The reference supplies neither operands, cache
        # values, control flow nor answers to either stock execution.
        from leanputer.kernel.stock_control_reference import NativeControlReference
        from leanputer.kernel import source_transition as source
        history=torch.stack(pc_history).cpu().float().tolist();native_pc_boundaries=[]
        for item,doc in enumerate(docs):
            ref=NativeControlReference(program,source.prepare(cfg,*source.parse_document(doc)));checked=0
            while ref.forwards<a.steps and not ref.status:
                ref.step()
                if ref.forwards>a.steps:break
                actual=sum(int(value)<<i for i,value in enumerate(history[ref.forwards-1][item]))
                if actual!=ref.pc:raise AssertionError(('stock/native prefix PC divergence',doc.get('name'),ref.forwards,actual,ref.pc))
                checked+=1
            native_pc_boundaries.append(checked)
    report=dict(format='leanputer.stock-prefix-launch-timing.v1',prefix_forwards=a.steps,batch=2,whole_source_completed=False,model=chip.report,control=program.report,
        eager_seconds=eager_seconds,cuda_graph_seconds=graph_seconds,capture_seconds=executor.setup_seconds,
        eager_forwards_per_second=a.steps/eager_seconds,cuda_graph_forwards_per_second=a.steps/graph_seconds,
        exact_all_hidden_state=equal_state,exact_all_stock_cache_tensors=equal_cache,exact_logits=equal_logits,
        baseline_control_forwards=[1185877,1218203],projected_baseline_longer_seconds=1218203*graph_seconds/a.steps,
        compiled_stock_operations=a.compile_stock,immutable_weight_freezing=bool(torch._inductor.config.freezing)if a.compile_stock else False,
        exact_external_native_prefix=reference_match,exact_native_pc_boundaries=native_pc_boundaries,
        execution='torch.cuda.CUDAGraph of stock Qwen3_5ForCausalLM.forward/cache plus identity feedback; optional standard torch.compile with eager precision casts')
    a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='model'}),flush=True)


if __name__=='__main__':main()
