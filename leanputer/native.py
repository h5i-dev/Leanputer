"""Compile checker Boolean IR into unmodified stock Qwen3.5 layers.

Compiler only. Runtime is transformers.Qwen3_5ForCausalLM.forward. No layer
substitution, norm replacement, monkeypatch, pretrained backbone or emulator.
The first native slice is the complete bounded STLC checker; dependent-machine
RAM migration is separate work and is not claimed by this module.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace
import time

import torch

from .checker import Config, build_checker_ir
from .terms import App, Lam, Var, encode
from .native_vendor.qwenputer.emit import Layout, allocate, emit_layers
from .native_vendor.qwenputer.expr import Expr
from .native_vendor.qwenputer.ir import Graph, Target


def pick_layout(slots):
    candidates = []
    for ballast in range(3, 17):
        hidden = ballast
        while hidden < slots+ballast+1 or hidden % 64:
            hidden *= 4
        candidates.append(Layout(hidden=hidden, m=ballast))
    return min(candidates, key=lambda layout: layout.hidden)


@dataclass
class NativeCompilation:
    model: object
    checker_config: Config
    input_names: tuple
    input_slots: tuple
    output_slots: tuple
    layout: object
    graph: object

    def encode(self, term, claim, device=None):
        # Reuse only syntax/name-to-binder packing. No checker answer is read.
        encoder = SimpleNamespace(config=self.checker_config, input_names=self.input_names)
        return self.pack(encode(encoder, term, claim), device)

    def pack(self, bits, device=None):
        if bits.ndim != 2 or bits.shape[1] != len(self.input_names) or not torch.all((bits == 0) | (bits == 1)):
            raise ValueError('native input must have the fixed Boolean syntax shape')
        parameter = next(self.model.parameters())
        inputs = torch.zeros((bits.shape[0], 1, self.layout.hidden), dtype=parameter.dtype, device=device or parameter.device)
        inputs[:, :, :self.layout.m] = self.layout.ballast
        inputs[:, 0, list(self.input_slots)] = bits.to(inputs.device, inputs.dtype)
        return inputs


class ScratchResetCapacity(ValueError):
    def __init__(self, required):
        self.required = required
        super().__init__(f'native scratch reset needs {required} reserved layers')


def emit_stock(graph, result_dims, intermediate, dtype, device, keep_dims=None, reset_layers=0):
    from transformers import Qwen3_5ForCausalLM, Qwen3_5TextConfig
    from transformers.initialization import no_init_weights
    results = result_dims
    keep = set(result_dims) | set(keep_dims or ())
    allocation = allocate(graph, None, keep, intermediate)
    layout = pick_layout(allocation.n_slots)
    layout.slots = allocation.slots
    persistent = {layout.dim(d) for d in keep}
    clear = [d for d in range(layout.m, layout.hidden) if d not in persistent]
    if reset_layers and len(clear) > reset_layers*intermediate:
        raise ScratchResetCapacity((len(clear)+intermediate-1)//intermediate)
    layers = graph.n_layers()
    tc = dict(hidden_size=layout.hidden, vocab_size=len(results), intermediate_size=intermediate,
              num_hidden_layers=layers+1, layer_types=['linear_attention']*layers+['full_attention'],
              hidden_act='silu', linear_conv_kernel_dim=4, linear_key_head_dim=128, linear_value_head_dim=128,
              linear_num_key_heads=graph.target.key_heads, linear_num_value_heads=graph.target.value_heads, num_attention_heads=1, num_key_value_heads=1,
              head_dim=256, rms_norm_eps=1e-6, attn_output_gate=True, tie_word_embeddings=False,
              rope_parameters=dict(rope_type='default', rope_theta=10000000, partial_rotary_factor=.25,
                                   mrope_section=[11,11,10], mrope_interleaved=True), max_position_embeddings=8192)
    native_config = Qwen3_5TextConfig(**tc)
    native_config._attn_implementation = 'eager'
    # Stock initialization context avoids writing an unnecessary random copy
    # of large dense weights; stock rotary/cache buffers still initialize.
    with no_init_weights():
        model = Qwen3_5ForCausalLM(native_config)
    # Every parameter is compiler-generated, including inactive native sublayers.
    state = emit_layers(graph, layout, tc, 0, 'model.', allocation)
    for name,value in model.state_dict().items():
        if name not in state: state[name]=torch.zeros(value.shape,dtype=torch.float32)
    if reset_layers:
        from .native_vendor.qwenputer.emit import row
        for unit, slot in enumerate(clear):
            layer, index = divmod(unit, intermediate)
            prefix = f'model.layers.{layer}.mlp.'
            row(graph.one, layout, state[prefix+'gate_proj.weight'][index], 128.)
            state[prefix+'up_proj.weight'][index, slot] = 1/(128*layout.scale)
            state[prefix+'down_proj.weight'][slot,index] = -1.
    state['model.norm.weight'].fill_(-1.)
    for i, dimension in enumerate(result_dims):
        slot = layout.dim(dimension)
        state['model.norm.weight'][slot] = 1/layout.scale
        state['lm_head.weight'][i, slot] = 1.
    model.load_state_dict(state, strict=True, assign=True)
    model.requires_grad_(False)
    model = model.to(device=device, dtype=dtype).eval()
    return model, layout, allocation


def compile_stlc(config=Config(nodes=5, types=('P', ('P','P'), (('P','P'),('P','P')))),
                 intermediate=256, dtype=torch.float32, device='cpu'):
    from transformers import Qwen3_5ForCausalLM, Qwen3_5TextConfig
    circuit, outputs = build_checker_ir(config)
    graph = Graph(Target(key_heads=1, value_heads=1, intermediate=intermediate))
    values = {i:graph.token_feature(name, lambda token:0) for i, name in enumerate(circuit.inputs)}
    needed = set(outputs)
    live = []
    for gate in reversed(circuit.gates):
        if gate[0] in needed:
            needed.update(gate[2]); live.append(gate)
    for wire, operation, operands in reversed(live):
        total = sum((values[i] for i in operands), Expr())
        if operation == 'not': terms = [(1, graph.one, graph.one-total)]
        elif operation == 'and': terms = [(1, graph.one, total+1-len(operands))]
        else: terms = [(1, graph.one, total), (-1, graph.one, total-1)]
        values[wire] = graph.ffn(terms, name=f'gate/{wire}/{operation}')
    results = [graph.ffn([(1, graph.one, values[wire])], name=f'result/{i}') for i, wire in enumerate(outputs)]
    result_dims = [next(iter(expression.terms)) for expression in results]
    model, layout, allocation = emit_stock(graph, result_dims, intermediate, dtype, device)
    slots = tuple(layout.dim(next(iter(values[i].terms))) for i in range(len(circuit.inputs)))
    return NativeCompilation(model, config, tuple(circuit.inputs), slots,
                             tuple(layout.dim(d) for d in result_dims), layout, graph)


def smoke(device='cpu', save=None):
    torch.set_num_threads(1)
    started = time.perf_counter()
    compilation = compile_stlc(device=device)
    model = compilation.model
    identity = Lam('x','P',Var('x'))
    application = App(Lam('f',('P','P'),Var('f')), identity)
    cases = [('identity',identity,('P','P'),True), ('application',application,('P','P'),True),
             ('wrong-claim',identity,(('P','P'),('P','P')),False),
             ('unbound',Lam('x','P',Var('y')),('P','P'),False)]
    inputs = torch.cat([compilation.encode(term, claim) for _,term,claim,_ in cases])
    if device == 'cuda': torch.cuda.synchronize()
    build_seconds = time.perf_counter()-started
    start = time.perf_counter()
    with torch.inference_mode():
        output = model(inputs_embeds=inputs, use_cache=False).logits[:,0,:]
    if device == 'cuda': torch.cuda.synchronize()
    seconds = time.perf_counter()-start
    actual = output[:,0].cpu().tolist()
    expected = [float(case[-1]) for case in cases]
    if actual != expected: raise AssertionError(dict(actual=actual, expected=expected, logits=output.tolist()))
    if save:
        model.save_pretrained(save)
        Path(save, 'leanputer-native.json').write_text(json.dumps(dict(
            format='leanputer.native-stlc.v1', checker=dict(nodes=compilation.checker_config.nodes, types=compilation.checker_config.types),
            input_names=compilation.input_names, input_slots=compilation.input_slots, output_slots=compilation.output_slots,
            ballast=compilation.layout.ballast, ballast_channels=compilation.layout.m), indent=2)+'\n')
    return dict(stock_class=type(model).__module__+'.'+type(model).__name__, device=device,
                parameters=sum(p.numel() for p in model.parameters()), hidden_size=model.config.hidden_size,
                intermediate_size=model.config.intermediate_size, native_layers=model.config.num_hidden_layers,
                graph_nodes=len(compilation.graph.nodes), input_bits=len(compilation.input_names),
                build_seconds=build_seconds, batch_forward_seconds=seconds,
                cases=[dict(name=case[0], accept=bool(answer)) for case,answer in zip(cases,actual)],
                scope='Complete bounded STLC circuit via stock forward; native dependent RAM port pending. No native GDN RAM claim.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=['cpu','cuda'], default='cpu')
    parser.add_argument('--save', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(smoke(args.device,args.save),indent=2))
    return 0


if __name__ == '__main__': raise SystemExit(main())
