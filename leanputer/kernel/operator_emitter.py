"""Dense stock emitter for bounded checker-operator modules.

All semantics are circuits built before emission. This supplies no runtime
dispatch, evaluator, instruction tape, special forward or replacement cache.
"""
import math
import torch
from ..native_vendor.qwenputer.emit import Layout, allocate, emit_layers, row
from ..native_vendor.qwenputer.ir import Head
from .macro_budget import BASELINE_DENSE
from .stock_datapath import StockDatapath


def emit_operator(builder, slots, physical, output, *, hidden, intermediate, report,
                  device='cpu', plan_only=False):
    from transformers import Qwen3_5ForCausalLM, Qwen3_5TextConfig
    from transformers.initialization import no_init_weights
    graph=builder.graph
    if len(output)>64:raise ValueError('operator readout exceeds fixed stock vocabulary')
    allocation=allocate(graph,None,set(physical),intermediate)
    mapping={d:position-slots.prefix for d,position in physical.items()}
    for d,color in allocation.slots.items():
        if d not in mapping:mapping[d]=slots.next+color-len(physical)-slots.prefix
    high=max(mapping.values())+slots.prefix+1
    if high>hidden:raise ValueError(f'operator exceeds H{hidden}: needs {high}')
    allocation.slots=mapping;layout=Layout(hidden=hidden,m=hidden//64,slots=mapping)
    body=graph.n_layers();keep=set(physical.values())
    clear=[i for i in range(layout.m,hidden)if i not in keep]
    layers=body+math.ceil(len(clear)/intermediate)+1
    active={node.level//2 for node in graph.nodes if isinstance(node,Head)}
    kinds=['linear_attention'if i in active else'full_attention'for i in range(layers)]
    expected=sum(3*hidden*intermediate+(1802*hidden+3208 if kind=='linear_attention'else 12*hidden+4)for kind in kinds)+129*hidden
    metadata=dict(report,logical_dense_parameters=expected,hidden=hidden,intermediate=intermediate,
                  layers=layers,active_gdn_layers=len(active),allocated_channels=high,
                  graph_layers=body,scratch_clear_layers=math.ceil(len(clear)/intermediate),
                  compact_inactive_attention=True,gdn_value_heads=4,parameter_limit=BASELINE_DENSE,
                  stock_class='transformers.Qwen3_5ForCausalLM',full_checker=False,joint_delivery_gate=False)
    if expected>BASELINE_DENSE:raise ValueError('operator exceeds baseline dense cap before allocation')
    if plan_only:return metadata
    config=Qwen3_5TextConfig(hidden_size=hidden,intermediate_size=intermediate,num_hidden_layers=layers,
                           layer_types=kinds,vocab_size=64,linear_key_head_dim=128,linear_value_head_dim=128,
                           linear_num_key_heads=1,linear_num_value_heads=4,linear_conv_kernel_dim=4,
                           num_attention_heads=1,num_key_value_heads=1,head_dim=2,hidden_act='silu',
                           tie_word_embeddings=False,rope_parameters=dict(rope_type='default',rope_theta=10000000,
                           partial_rotary_factor=1.,mrope_section=[1,0,0],mrope_interleaved=True))
    prior=torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.bfloat16)
        with torch.device(device),no_init_weights():model=Qwen3_5ForCausalLM(config)
    finally:torch.set_default_dtype(prior)
    with torch.no_grad():
        for p in model.parameters():p.zero_()
        for layer in model.model.layers:
            if hasattr(layer,'linear_attn'):layer.linear_attn.dt_bias.fill_(-110.);layer.linear_attn.norm.weight.fill_(1.)
        for index in range(body):
            weights=emit_layers(graph,layout,config.to_dict(),0,'model.',allocation,only_layer=index)
            _,unexpected=model.load_state_dict(weights,strict=False)
            if unexpected:raise ValueError('unexpected stock operator parameter')
        for start in range(0,len(clear),intermediate):
            mlp=model.model.layers[body+start//intermediate].mlp
            for unit,column in enumerate(clear[start:start+intermediate]):
                row(graph.one,layout,mlp.gate_proj.weight[unit],128.)
                mlp.up_proj.weight[unit,column]=1/(128*layout.scale)
                mlp.down_proj.weight[column,unit]=-1.
        for layer in model.model.layers:
            layer.input_layernorm.weight.zero_();layer.post_attention_layernorm.weight.zero_()
            layer.input_layernorm.weight[layout.tau]=-1;layer.post_attention_layernorm.weight[layout.tau]=-1
        model.model.norm.weight.zero_();model.model.norm.weight[layout.tau]=-1
        for index,value in enumerate(output):row(value,layout,model.lm_head.weight[index])
    model.eval();model.requires_grad_(False);model.set_attn_implementation('eager')
    if sum(p.numel()for p in model.parameters())!=expected:raise AssertionError('dense operator shape differs')
    return StockDatapath(model,slots,layout,metadata)
