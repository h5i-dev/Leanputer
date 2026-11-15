"""Stock feasibility probe for whole checker continuation frames.

This is NOT a kernel checker. A fixed recursive call/return protocol exercises
28-word frame spill/restore and one-unit masked row updates. Frames/depth are
raw data; no host dispatch, semantic answers or input instruction tape is used.
"""
import math
from collections import Counter
import torch
from ..native_machine import NativeBuilder
from ..native_vendor.qwenputer.expr import Expr
from ..native_vendor.qwenputer.ir import K,A_REF,A_BIT,Head
from ..native_vendor.qwenputer.emit import Layout,allocate,emit_layers,reads,row
from .stock_datapath import FixedSlots,StockDatapath
from .macro_budget import BASELINE_DENSE


def build_continuation_probe(device='cpu',plan_only=False):
    from transformers import Qwen3_5ForCausalLM,Qwen3_5TextConfig
    from transformers.initialization import no_init_weights
    h,inter=1536,192;torch.set_num_threads(1)
    b=NativeBuilder(intermediate=inter,reset_layers=0);g=b.graph;g.target.value_heads=4
    # Reserve the same 24 physical handover units per layer as the joint plan.
    g.target.intermediate=inter-24
    slots=FixedSlots(h//64+1);physical={}
    def feature(name,width):
        positions=slots.add(name,width);values=[b.feature(f'{name}/{i}')for i in range(width)]
        physical.update((next(iter(value.terms)),position)for value,position in zip(values,positions));return values
    frame=feature('frame',448);pending=feature('pending',448);sp=feature('sp',16);pc=feature('pc',2)
    key=feature('pending_row',5);enable=feature('pending_enable',1)[0];status=feature('status',2);result=feature('result',16);boot=feature('boot',1)[0]
    one=g.one
    def AND(values,name):return b.gate('and',values,name)
    def OR(values,name):return b.gate('or',values,name)
    def matches(bits,value):return[bit if value>>i&1 else one-bit for i,bit in enumerate(bits)]
    run=AND([one-boot,one-status[0],one-status[1]],'continuation-run')
    call=AND([run]+matches(pc,0),'call-phase');ret=AND([run]+matches(pc,2),'return-phase')
    nonzero=OR(frame[:16],'argument-nonzero');overflow=OR(sp[5:],'stack-full')
    enter=AND([call,nonzero,one-overflow],'call-enter');fault=AND([call,nonzero,overflow],'call-overflow')
    leaf=AND([call,one-nonzero],'leaf');has_parent=OR(sp,'has-parent')
    returning=AND([ret,has_parent],'return-to-parent');finish=OR([AND([leaf,one-has_parent],'root-leaf'),AND([returning]+matches(sp,1),'last-return')],'finish')
    def increment(bits,name):
        return[one-bits[0]]+[bits[i]+AND(bits[:i],name+'-carry')-2*AND(bits[:i+1],name+'-both')for i in range(1,len(bits))]
    def decrement(bits,name):
        return[one-bits[0]]+[bits[i]+AND([one-bit for bit in bits[:i]],name+'-borrow')-2*AND([bits[i]]+[one-bit for bit in bits[:i]],name+'-both')for i in range(1,len(bits))]
    read_address=decrement(sp[:5],'read-parent')
    def form(values):return K*(2*(sum(values,Expr())-(len(values)-1)*one)-one)
    q={i:form(matches(read_address,i)+[returning])for i in range(32)}
    k={i:form(matches(key,i))for i in range(32)}
    heads=[]
    for page in range(4):
        values={0:A_REF*one,1:A_REF*one};values.update({2+i:A_BIT*pending[112*page+i]for i in range(112)})
        heads.append(dict(v=values,a=0,z={2+i:K*one for i in range(112)},outs=[(2+i,128.)for i in range(112)],beta=enable,into=pending[112*page:112*(page+1)]))
    first=heads[0];g.head('continuation.frames',q,k,first['v'],0,first['z'],first['outs'],beta=first['beta'],into=first['into'],vx=heads[1:]);memory_layer=g.nodes[-1].level//2
    # A return query is only issued after a leaf/return zeroed pending. The
    # same columns therefore hold outgoing spill data or incoming caller data.
    def barrier():b.barrier=2*g.n_layers()
    for target,value in zip(pending,frame):g.ffn([(1,value-target,enter)],name='frame-spill',into=target,min_level=b.barrier)
    barrier()
    child=decrement(frame[:16],'child-depth');next_result=increment(result,'return-result')
    # Preserve exact old operands until each vector operation has finished.
    for i,target in enumerate(frame):
        new_child=child[i]if i<16 else Expr()
        g.ffn([(1,new_child-target,enter),(1,pending[i]-target,returning)],name='working-frame',into=target,min_level=b.barrier)
    barrier()
    clear=one-enter
    for target in pending:g.ffn([(-1,target,clear)],name='clear-pending-frame',into=target,min_level=b.barrier)
    barrier()
    # Save the CALL key before updating SP. Both are generated in weights.
    for i,target in enumerate(key):g.ffn([(1,sp[i]-target,enter),(-1,target,one-enter)],name='spill-key',into=target,min_level=b.barrier)
    barrier()
    up=increment(sp,'stack-up');down=decrement(sp,'stack-down')
    for old,u,d in zip(sp,up,down):g.ffn([(1,u-old,enter),(1,d-old,returning)],name='stack-pointer',into=old,min_level=b.barrier)
    for old,new in zip(result,next_result):g.ffn([(1,new-old,returning),(-1,old,leaf)],name='return-value',into=old,min_level=b.barrier)
    g.ffn([(1,enter-enable,one)],name='spill-enable',into=enable,min_level=b.barrier)
    g.ffn([(1,one,finish)],name='finished',into=status[0],min_level=b.barrier)
    g.ffn([(1,one,fault)],name='overflow',into=status[1],min_level=b.barrier)
    terminal=OR([finish,fault],'terminal')
    # CALL recurses at PC0; LEAF and intermediate returns use PC2; done is PC3.
    next_pc=[terminal,OR([leaf,returning,fault],'next-phase-high')]
    active=OR([enter,leaf,returning,fault],'advance-phase')
    for old,new in zip(pc,next_pc):g.ffn([(1,new,one),(-1,old,active)],name='phase',into=old,min_level=b.barrier)
    allocation=allocate(g,None,set(physical),inter)
    mapping={d:position-slots.prefix for d,position in physical.items()};count=len(physical)
    for d,color in allocation.slots.items():
        if d not in mapping:mapping[d]=slots.next+color-count-slots.prefix
    high=max(mapping.values())+slots.prefix+1
    if high>h:raise ValueError(f'continuation probe exceedsH{h}:needs{high}')
    allocation.slots=mapping;layout=Layout(hidden=h,m=h//64,slots=mapping)
    body=g.n_layers();keep=set(physical.values());clear_columns=[i for i in range(layout.m,h)if i not in keep]
    layers=body+math.ceil(len(clear_columns)/inter)+1
    active_layers={node.level//2 for node in g.nodes if isinstance(node,Head)}
    kinds=['linear_attention'if i in active_layers else'full_attention'for i in range(layers)]
    expected=sum(3*h*inter+(1802*h+3208 if kind=='linear_attention'else 12*h+4)for kind in kinds)+129*h
    from ..native_vendor.qwenputer.ir import FFN
    units=Counter()
    for node in g.nodes:
        if isinstance(node,FFN):units[node.name]+=len(node.terms)
    report=dict(format='leanputer.continuation-row-probe.v1',full_checker=False,stock_operator_probe=True,logical_dense_parameters=expected,hidden=h,intermediate=inter,layers=layers,active_gdn_layers=len(active_layers),allocated_channels=high,frame_words=28,stack_capacity=32,frame_layer=memory_layer,one_forward_per_operator=True,joint_full_rule_gate=False,parameter_limit=BASELINE_DENSE,graph_layers=body,scratch_clear_layers=math.ceil(len(clear_columns)/inter),ffn_units=sum(units.values()),ffn_units_by_operation=dict(sorted(units.items())),logic_units_per_layer=inter-24)
    if expected>BASELINE_DENSE:raise ValueError('continuation probe exceeds original dense parameter cap before allocation')
    if plan_only:return report
    config=Qwen3_5TextConfig(hidden_size=h,intermediate_size=inter,num_hidden_layers=layers,layer_types=kinds,vocab_size=64,linear_key_head_dim=128,linear_value_head_dim=128,linear_num_key_heads=1,linear_num_value_heads=4,linear_conv_kernel_dim=4,num_attention_heads=1,num_key_value_heads=1,head_dim=2,hidden_act='silu',tie_word_embeddings=False,rope_parameters=dict(rope_type='default',rope_theta=10000000,partial_rotary_factor=1.,mrope_section=[1,0,0],mrope_interleaved=True))
    prior=torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.bfloat16)
        with torch.device(device),no_init_weights():model=Qwen3_5ForCausalLM(config)
    finally:torch.set_default_dtype(prior)
    with torch.no_grad():
        for p in model.parameters():p.zero_()
        for layer in model.model.layers:
            if hasattr(layer,'linear_attn'):layer.linear_attn.dt_bias.fill_(-110.);layer.linear_attn.norm.weight.fill_(1.)
        for index in range(g.n_layers()):
            weights=emit_layers(g,layout,config.to_dict(),0,'model.',allocation,only_layer=index)
            _,unexpected=model.load_state_dict(weights,strict=False)
            if unexpected:raise ValueError('unexpected stock continuation parameter')
        for first_column in range(0,len(clear_columns),inter):
            layer=model.model.layers[body+first_column//inter];columns=clear_columns[first_column:first_column+inter]
            for unit,column in enumerate(columns):
                row(one,layout,layer.mlp.gate_proj.weight[unit],128.);layer.mlp.up_proj.weight[unit,column]=1/(128*layout.scale);layer.mlp.down_proj.weight[column,unit]=-1.
        for layer in model.model.layers:
            # Qwen3.5 RMSNorm uses (1 + weight); zero is unit gain.
            layer.input_layernorm.weight.zero_();layer.post_attention_layernorm.weight.zero_()
            layer.input_layernorm.weight[layout.tau]=-1;layer.post_attention_layernorm.weight[layout.tau]=-1
        output=pc+[Expr()]*14+sp+status+[Expr()]*14+result
        for index,value in enumerate(output):row(value,layout,model.lm_head.weight[index],1.)
        # Output logits are read before the final identity-feedback boundary.
        model.model.norm.weight.zero_();model.model.norm.weight[layout.tau]=-1
        # row() already cancels the final RMS scale on input projections.
    model.eval();model.requires_grad_(False);model.set_attn_implementation('eager')
    if sum(p.numel()for p in model.parameters())!=expected:raise AssertionError('continuation dense accounting differs')
    report.update(compact_inactive_attention=True,gdn_value_heads=4)
    return StockDatapath(model,slots,layout,report)
