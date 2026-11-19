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


def run(program,documents,device='cuda',max_forwards=512,progress=None,prefill_chunk=32,execution='cuda_graph',compile_stock=True,grouped_memory=False,model_hidden=None,intermediate=256,reuse_transient_features=False):
    if not program.report['pc16_encoding_met']:raise ValueError('whole native program exceeds16bit control ROM; no emission')
    bundled=bool(program.report.get('guard_bundling'));direct=program.preflight_plan is not None
    if direct:raise RuntimeError('GAP: fixed-preflight diagnostic source prefix diverges at forward19 (stockPC37966/reference37965); it is not a verified source checker')
    grouped_memory=grouped_memory or direct;reuse_transient_features=reuse_transient_features or direct
    started=time.perf_counter();chip=build(program.records,device='cpu',rom_layout='byte_pages',compact_attention=True,hidden=model_hidden or(1024 if direct or(bundled and grouped_memory)else 960 if bundled else 768),intermediate=intermediate,datapath_layers=90 if direct else 45 if bundled else 35,parallel_carry=bundled,grouped_memory=grouped_memory,bounds_schema=program.bounds_schema,reuse_transient_features=reuse_transient_features,preflight_plan=program.preflight_plan)
    chip.model.to(device);chip.report['full_current_rule_control_mapped']=True;chip.report['checker_commit_layout']['reserved_arena_buffers_implemented']=True
    built=time.perf_counter();batch=len(documents)
    packets=syntax_packets(chip,program.store.compiler.cfg,documents);cache=chip.new_cache()
    masks={'full_attention':None,'linear_attention':None}
    def forward(embeddings,**extra):
        return chip.model(inputs_embeds=embeddings,past_key_values=cache,use_cache=True,position_ids=torch.zeros((batch,embeddings.shape[1]),dtype=torch.long,device=device),attention_mask=masks,**extra)
    with torch.inference_mode():
        for first in range(0,packets.shape[1],prefill_chunk):
            out=forward(chip.embeddings(packets[:,first:first+prefill_chunk]));cache=out.past_key_values
        loaded=time.perf_counter();state=chip.embeddings(torch.zeros(batch,1,chip.slots.next-chip.slots.prefix))
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


def execute_window(chip,config,document,execution='cuda_graph',max_total_forwards=5000,progress=None):
    """Boot one source case and run tied slots until the stock model publishes.

    Every model() call is counted, including boot and CUDA-graph setup. The host
    only moves the original syntax, the identity residual, and the shared GDN
    memory tensors. It does not decode an instruction or choose a branch.
    """
    lanes=chip.report.get('window_lanes',1)
    if lanes<2:raise ValueError('windowed stock execution needs tied slots')
    device=next(chip.model.parameters()).device
    packets=syntax_packets(chip,config,[document])
    # Boot is 692 tokens and the check is a few thousand more. Inactive KV
    # rows are unused; the bound only keeps the static cache in range.
    cache=chip.new_cache(max_cache_len=8192)
    masks={'full_attention':None,'linear_attention':None}
    started=time.perf_counter();boot_forwards=0
    def step(embeddings,**extra):
        return chip.model(inputs_embeds=embeddings,past_key_values=cache,use_cache=True,position_ids=torch.zeros(embeddings.shape[:2],dtype=torch.long,device=device),attention_mask=masks,**extra)
    with torch.inference_mode():
        for first in range(0,packets.shape[1],32):
            out=step(chip.embeddings(packets[:,first:first+32]));cache=out.past_key_values;boot_forwards+=1
            if boot_forwards==1:chip.share_memory(cache)
            shared=cache.layers[chip.report['memory_layers'][0]].recurrent_states[0]
            other=cache.layers[chip.report['memory_layers'][0]+chip.report['template_layers']].recurrent_states[0]
            if other is not shared:raise RuntimeError('stock memory alias broke during boot')
        booted=time.perf_counter()
        state=chip.embeddings(torch.zeros(1,1,chip.slots.next-chip.slots.prefix))
        setup_forwards=0;executor=None
        if execution=='cuda_graph':
            from .stock_execution import StockCudaGraph,snapshot,restore
            saved=snapshot(cache,state)
            step(state,output_hidden_states=True);setup_forwards+=1
            restore(cache,state,saved)
            executor=StockCudaGraph(chip.model,cache,state,progress=progress)
            setup_forwards+=executor.model_calls
        elif execution!='eager':raise ValueError('unknown stock execution schedule')
        powers=2.**torch.arange(16,device=device)
        check_forwards=0;completed=False;output=None
        budget=max_total_forwards-boot_forwards-setup_forwards
        if budget<1:raise RuntimeError('boot and setup already exhausted the stock forward budget')
        decoding=time.perf_counter()
        while check_forwards<budget:
            if executor:executor.replay()
            else:
                out=step(state,output_hidden_states=True);cache=out.past_key_values;state=out.hidden_states[-2]
            check_forwards+=1
            logits=(executor.logits if executor else out.logits)[0,0].float()
            if not bool(((logits==0)|(logits==1)).all()):raise RuntimeError('stock checker emitted nonbinary diagnostic bits')
            fields=logits.reshape(4,16).matmul(powers).to(torch.int64).tolist()
            output=[int(v) for v in fields]
            completed=output[1]!=0
            if progress and (check_forwards in (1,8) or check_forwards%32==0 or completed):
                progress(dict(event='progress',check_forwards=check_forwards,total_forwards=boot_forwards+setup_forwards+check_forwards,seconds=time.perf_counter()-decoding,output=output,completed=completed))
            if completed:break
        elapsed=time.perf_counter()-decoding
    return dict(cache=cache,state=state,output=output,completed=completed,boot_forwards=boot_forwards,setup_forwards=setup_forwards,check_forwards=check_forwards,total_forwards=boot_forwards+setup_forwards+check_forwards,boot_seconds=booted-started,setup_seconds=(decoding-booted),check_seconds=elapsed,execution=execution,logical_dense_parameters=chip.report['logical_dense_parameters'],window_lanes=lanes,layers=chip.report['layers'])


def read_main_and_banks(chip,cache,batch_index):
    """Output diagnostics only; never used to feed the model or decide types."""
    from .traversal_machine import RegisterLayout,StateLayout,MachineConfig
    from ..native_vendor.qwenputer.ir import A_BIT
    layout=RegisterLayout(StateLayout(MachineConfig(heap=512,stack=32,context=8,constants=4,word_bits=16)))
    locations={(h['port'],h['page']):h for h in chip.report['rf_heads']}
    def word(bits):
        if any(value not in(0,1)for value in bits):raise AssertionError('nonbinary stock cache payload')
        return sum(int(value)<<i for i,value in enumerate(bits))
    regs={}
    for index,(name,width)in enumerate(layout.fields):
        address=main_address(index);row,slot=address>>3,address&7;head=locations[0,row//128]
        data=cache.layers[head['layer']].recurrent_states[0][batch_index,head.get('value_head',0),row%128,2+16*slot:18+16*slot]/A_BIT
        regs[name]=word(data.cpu().float().tolist())
    banks={}
    for h in chip.report['arena_heads']:
        cells={'heap':512,'stack':32,'context':8,'constants':4}[h['bank']]
        if h['bank']not in banks:banks[h['bank']]=[[0]*h['words']for _ in range(cells)]
        data=(cache.layers[h['layer']].recurrent_states[0][batch_index,h.get('value_head',0),h.get('row_offset',0):h.get('row_offset',0)+min(128,cells),2:2+16*h['words']]/A_BIT).cpu().float().tolist()
        for row,values in enumerate(data):banks[h['bank']][128*h['page']+row]=[word(values[i:i+16])for i in range(0,len(values),16)]
    return dict(regs=regs,**banks)
