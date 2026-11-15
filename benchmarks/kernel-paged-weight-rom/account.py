"""Dense stock META accounting for byte-page program lookup; no kernel emission."""
import json,math
from pathlib import Path
import torch
from transformers import Qwen3_5ForCausalLM,Qwen3_5TextConfig
from transformers.initialization import no_init_weights
rows=[]
for records in(135,4096,16384,46245,65536):
 pages=math.ceil(records/128);rom_layers=math.ceil(15*pages/256);layers=rom_layers+7+30
 cfg=Qwen3_5TextConfig(hidden_size=768,intermediate_size=256,num_hidden_layers=layers,layer_types=['linear_attention']*layers,vocab_size=64,linear_key_head_dim=128,linear_value_head_dim=128,linear_num_key_heads=1,linear_num_value_heads=1,linear_conv_kernel_dim=4,num_attention_heads=1,num_key_value_heads=1,head_dim=2,hidden_act='silu',tie_word_embeddings=False,rope_parameters=dict(rope_type='default',rope_theta=10000000,partial_rotary_factor=1.,mrope_section=[1,0,0],mrope_interleaved=True))
 with torch.device('meta'),no_init_weights():model=Qwen3_5ForCausalLM(cfg)
 count=sum(p.numel()for p in model.parameters());formula=layers*(3*768*256+644*768+1666)+129*768;assert count==formula
 rows.append(dict(records=records,record_bits=112,low_row_values=128,bytes_per_record=14,units_per_page=15,rom_layers=rom_layers,decode_layers=7,other_layers=30,layers=layers,logical_dense_parameters=count,bf16_parameter_bytes=2*count,recurrent_fp32_cache_bytes=layers*128*128*4,evidence='Stock meta shape only; complete native kernel action/scratch/encoding not proved'))
Path(__file__).with_name('shapes.json').write_text(json.dumps(dict(rows=rows),indent=2)+'\n')
for r in rows:print(r)
