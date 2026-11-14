"""Save/load compiled stock source-checker weights, including sparse tensors.

Only model/ABI transport: no checker SPEC, inference answer, normalization or
admission is called. Runtime remains the stock Qwen forward/cache with identity
feedback; source preparation is the existing syntax-only codec.
"""
from dataclasses import asdict
import json
from pathlib import Path
import torch


def save_source_machine(machine,directory):
    from .kernel import source_transition as program
    if machine.program is not program:raise ValueError('expected general source program')
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    metadata=dict(format='leanputer.compiled-stock-source.v1',physical_config=asdict(machine.config),
        stock_config=machine.model.config.to_dict(),parameter_dtype=str(next(machine.model.parameters()).dtype).split('.')[-1],
        layout=dict(hidden=machine.layout.hidden,m=machine.layout.m,off=machine.layout.off,log2_ballast=machine.layout.log2_ballast),
        feature_slots=machine.feature_slots,offsets=machine.offsets,native_heads=machine.native_heads,
        semantic_registers=list(machine.register_layout.slices),packed_control=machine.control_packing is not None,
        control_digit_bits=machine.control_packing.digit_bits if machine.control_packing else None,
        control_bank=machine.control_bank.metadata()if machine.control_bank else None,
        weight_storage=getattr(machine.model,'_leanputer_weight_storage','dense'),layout_policy=machine.layout_policy,
        layout_statistics=machine.layout_statistics,bank_layout=machine.bank_layout,max_ballast=machine.max_ballast,
        semantic_program=program.program_name,small_model_target_met=False,full_kernel_native_support=False)
    torch.save({name:value.detach().cpu()for name,value in machine.model.state_dict().items()},root/'weights.pt')
    (root/'model.json').write_text(json.dumps(metadata,indent=2)+'\n')


def load_source_machine(directory,device='cuda'):
    from transformers import Qwen3_5ForCausalLM,Qwen3_5TextConfig
    from transformers.initialization import no_init_weights
    from .kernel import source_transition as program
    from .native_machine import NativeMachine
    from .native_vendor.qwenputer.emit import Layout
    from .control_packing import ControlPacking
    root=Path(directory);metadata=json.loads((root/'model.json').read_text())
    if metadata.get('format')!='leanputer.compiled-stock-source.v1'or metadata.get('semantic_program')!=program.program_name:raise ValueError('unsupported compiled source model format')
    cfg=program.MachineConfig(**metadata['physical_config']);state_layout=program.StateLayout(cfg);registers=program.RegisterLayout(state_layout)
    if list(registers.slices)!=metadata['semantic_registers']:raise ValueError('compiled source register ABI differs')
    config=Qwen3_5TextConfig.from_dict(metadata['stock_config']);config._attn_implementation='eager'
    dtype=getattr(torch,metadata['parameter_dtype']);prior_dtype=torch.get_default_dtype()
    try:
        torch.set_default_dtype(dtype)
        with torch.device('meta'),no_init_weights():model=Qwen3_5ForCausalLM(config)
    finally:torch.set_default_dtype(prior_dtype)
    state=torch.load(root/'weights.pt',map_location=device,weights_only=True)
    model.load_state_dict(state,strict=True,assign=True)
    for module in model.modules():
        if hasattr(module,'compute_default_rope_parameters')and hasattr(module,'inv_freq'):
            with torch.device(device):inv,scale=module.compute_default_rope_parameters(config)
            module.inv_freq=inv.to(device);module.original_inv_freq=inv.clone().to(device);module.attention_scaling=scale
    if any(p.device.type=='meta'for p in model.parameters())or any(b.device.type=='meta'for b in model.buffers()):raise ValueError('unmaterialized compiled stock tensor')
    model._leanputer_weight_storage=metadata['weight_storage'];model.requires_grad_(False);model.eval()
    control_bank=None
    if metadata.get('control_bank'):
        from .control_banking import ControlBank
        control_bank=ControlBank(**metadata['control_bank'])
        if control_bank.word_bits!=cfg.word_bits:raise ValueError('private control word ABI differs')
        common=dict(control_bank.common_fields);private=control_bank.private
        if set(common)&set(private)or set(common)|set(private)!=set(registers.slices):raise ValueError('private/shared control ABI partition differs')
        if any(width!=common[name]for name,width in registers.fields if name in common):raise ValueError('shared control width ABI differs')
    packing=ControlPacking(control_bank.common if control_bank else registers,metadata.get('control_digit_bits',2))if metadata['packed_control']else None
    return NativeMachine(model,Layout(**metadata['layout']),state_layout,registers,metadata['feature_slots'],cfg,
        metadata['offsets'],metadata['native_heads'],metadata['layout_policy'],metadata['layout_statistics'],metadata['bank_layout'],metadata['max_ballast'],program,packing,control_bank)
