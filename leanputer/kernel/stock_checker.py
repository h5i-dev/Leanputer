"""Standalone shared stock checker: syntax transport and identity feedback.

No reference evaluator is imported. Weights contain the whole fixed checker;
the host never dispatches a control instruction or computes an inference answer.
"""
import time
import torch
from .stock_datapath import build
from .stock_control import main_address


def syntax_packets(chip,config,documents):
    # Existing parser/packer preserves raw declarations and universe schemes.
    # prepare only copies syntax and initializes the source controller.
    from . import source_transition as source
    states=[source.prepare(config,*source.parse_document(document))for document in documents]
    from .traversal_machine import RegisterLayout,StateLayout
    fields=[name for name,width in RegisterLayout(StateLayout(config)).fields]
    banks=[(0,'rf',136,7),(1,'heap',config.heap,4),(2,'stack',config.stack,6),(3,'context',config.context,1),(4,'constants',config.constants,6)]
    packets=[]
    for kind,bank,rows,width in banks:
        for row in range(rows):
            batch=[]
            for state in states:
                if bank=='rf':
                    values=[int(state['regs'][fields[row*7+slot]])if row*7+slot<len(fields)else 0 for slot in range(7)];address=2*row
                else:values=state[bank][row];address=row
                payload=[int(value)>>i&1 for value in values for i in range(16)]+[0]*(126-width*16)
                batch.append(chip.packet(boot=[1],pending_kind=[kind>>i&1 for i in range(3)],pending_row=[address>>i&1 for i in range(9)],pending_enable=[1],pending_payload=payload))
            packets.append(torch.stack(batch))
    return torch.stack(packets,dim=1)


def run(program,documents,device='cuda',max_forwards=512,progress=None,prefill_chunk=32,execution='cuda_graph',compile_stock=True):
    if not program.report['pc16_encoding_met']:raise ValueError('whole native program exceeds16bit control ROM; no emission')
    started=time.perf_counter();chip=build(program.records,device='cpu',rom_layout='byte_pages',compact_attention=True)
    chip.model.to(device);chip.report['full_current_rule_control_mapped']=True;chip.report['checker_commit_layout']['reserved_arena_buffers_implemented']=True
    built=time.perf_counter();batch=len(documents)
    packets=syntax_packets(chip,program.store.compiler.cfg,documents);cache=chip.new_cache()
    masks={'full_attention':None,'linear_attention':None}
    def forward(embeddings,**extra):
        return chip.model(inputs_embeds=embeddings,past_key_values=cache,use_cache=True,position_ids=torch.zeros((batch,embeddings.shape[1]),dtype=torch.long,device=device),attention_mask=masks,**extra)
    with torch.inference_mode():
        for first in range(0,packets.shape[1],prefill_chunk):
            out=forward(chip.embeddings(packets[:,first:first+prefill_chunk]));cache=out.past_key_values
        loaded=time.perf_counter();state=chip.embeddings(torch.zeros(batch,1,chip.slots.next-13))
        from .stock_execution import cache_tensors
        native_cache=cache_tensors(cache)
        chip.report.update(weight_tensor_bytes=sum(p.numel()*p.element_size()for p in chip.model.parameters()),native_cache_tensor_bytes_for_batch=sum(t.numel()*t.element_size()for t in native_cache),native_cache_tensor_count=len(native_cache),batch_items=batch,syntax_boot_packets_per_item=packets.shape[1])
        executor=None
        if execution=='cuda_graph':
            from .stock_execution import StockCudaGraph,snapshot,restore
            if compile_stock:
                # Stock Transformers lazily installs output-capture hooks.
                # Install them with its own eager forward before Dynamo traces
                # the model; restore every native tensor/counter afterwards.
                saved=snapshot(cache,state)
                forward(state,output_hidden_states=True)
                restore(cache,state,saved)
            model=torch.compile(chip.model,fullgraph=True,dynamic=False,options={'emulate_precision_casts':True})if compile_stock else chip.model
            executor=StockCudaGraph(model,cache,state)
        elif execution!='eager':raise ValueError('unknown stock execution schedule')
        decoding_started=time.perf_counter()
        if progress:progress(dict(event='loaded',build_seconds=built-started,prefill_seconds=loaded-built,capture_seconds=executor.setup_seconds if executor else 0,compiled_stock_operations=bool(executor and compile_stock),model=chip.report,control=program.report))
        completed=False
        for step in range(1,max_forwards+1):
            if executor:executor.replay()
            else:
                out=forward(state,output_hidden_states=True);cache=out.past_key_values;state=out.hidden_states[-2]
            # Completion observation only. Every instruction and semantic
            # action is selected inside the same stock forward/cache.
            if step%32==0 or step==max_forwards:
                logits=(executor.logits if executor else out.logits)[:,0].float();powers=2.**torch.arange(16,device=device)
                if not bool(((logits==0)|(logits==1)).all()):raise RuntimeError('stock checker emitted nonbinary diagnostic bits')
                output=logits.reshape(batch,4,16).matmul(powers).to(torch.int64).cpu().tolist()
                completed=all(row[1]for row in output)
                if progress and(step%256==0 or completed or step==max_forwards):progress(dict(event='progress',forwards=step,seconds=time.perf_counter()-decoding_started,outputs=output,completed=completed))
                if completed:break
        elapsed=time.perf_counter()-decoding_started
    return dict(chip=chip,cache=cache,state=state,outputs=output,completed=completed,forwards=step,inference_seconds=elapsed,build_seconds=built-started,prefill_seconds=loaded-built,execution=execution,compiled_stock_operations=bool(executor and compile_stock),immutable_weight_freezing=bool(executor and compile_stock and torch._inductor.config.freezing),capture_seconds=executor.setup_seconds if executor else 0)


def read_main_and_banks(chip,cache,batch_index):
    """Output diagnostics only; never used to feed the model or decide types."""
    from .traversal_machine import RegisterLayout,StateLayout,MachineConfig
    from ..native_vendor.qwenputer.ir import A_BIT
    layout=RegisterLayout(StateLayout(MachineConfig(heap=512,stack=32,context=8,constants=4,word_bits=16)))
    locations={(h['port'],h['page']):h['layer']for h in chip.report['rf_heads']}
    def word(bits):
        if any(value not in(0,1)for value in bits):raise AssertionError('nonbinary stock cache payload')
        return sum(int(value)<<i for i,value in enumerate(bits))
    regs={}
    for index,(name,width)in enumerate(layout.fields):
        address=main_address(index);row,slot=address>>3,address&7;layer=locations[0,row//128]
        data=cache.layers[layer].recurrent_states[0][batch_index,0,row%128,2+16*slot:18+16*slot]/A_BIT
        regs[name]=word(data.cpu().float().tolist())
    banks={}
    for h in chip.report['arena_heads']:
        cells={'heap':512,'stack':32,'context':8,'constants':4}[h['bank']]
        if h['bank']not in banks:banks[h['bank']]=[[0]*h['words']for _ in range(cells)]
        data=(cache.layers[h['layer']].recurrent_states[0][batch_index,0,:min(128,cells),2:2+16*h['words']]/A_BIT).cpu().float().tolist()
        for row,values in enumerate(data):banks[h['bank']][128*h['page']+row]=[word(values[i:i+16])for i in range(0,len(values),16)]
    return dict(regs=regs,**banks)
