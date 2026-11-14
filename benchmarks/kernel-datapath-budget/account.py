"""Stock META shapes only. No model weights, inference, source pruning or checker run."""
import json
from pathlib import Path
import torch
from transformers import Qwen3_5ForCausalLM,Qwen3_5TextConfig
from transformers.initialization import no_init_weights
rows=[]
for hidden,records in ((768,4096),(768,6144),(768,8192),(768,16384),(768,17920),(1024,16384)):
 width=256;rom_layers=(records+width-1)//width;layers=rom_layers+27
 config=Qwen3_5TextConfig(hidden_size=hidden,intermediate_size=width,num_hidden_layers=layers,layer_types=['linear_attention']*layers,vocab_size=64,linear_key_head_dim=128,linear_value_head_dim=128,linear_num_key_heads=1,linear_num_value_heads=1,linear_conv_kernel_dim=4,num_attention_heads=1,num_key_value_heads=1,head_dim=2,hidden_act='silu',tie_word_embeddings=False,rope_parameters=dict(rope_type='default',rope_theta=10000000,partial_rotary_factor=1.,mrope_section=[1,0,0],mrope_interleaved=True))
 with torch.device('meta'),no_init_weights():model=Qwen3_5ForCausalLM(config)
 groups={}
 for name,p in model.named_parameters():
  group='mlp'if '.mlp.'in name else'linear_attention'if '.linear_attn.'in name else'embeddings_and_head'if name.endswith(('embed_tokens.weight','lm_head.weight'))else'norms'
  groups[group]=groups.get(group,0)+p.numel()
 formula=layers*(3*hidden*width+644*hidden+1666)+129*hidden
 total=sum(groups.values());assert total==formula,(total,formula)
 rows.append(dict(hidden=hidden,intermediate=width,layers=layers,rom_layers=rom_layers,datapath_layers=22,protocol_reset_layers=4,output_layer=1,rom_records_capacity=records,record_bits=112,logical_dense_parameters=total,bf16_parameter_bytes=2*total,groups=groups,gdn_cache_recurrent_fp32_bytes_per_item=layers*128*128*4,ordinary_record_forward_budget=1,register_commit_forward_budget_per_candidate_word=2,evidence='Stock meta shapes/formula only; no datapath implementation, compiled kernel mapping or inference'))
root=Path(__file__).resolve().parent;(root/'stock-shapes.json').write_text(json.dumps(dict(format='leanputer.kernel-datapath-budget.v1',rows=rows),indent=2)+'\n');print(json.dumps(rows,indent=2))
