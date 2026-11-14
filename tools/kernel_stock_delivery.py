"""Whole fixed source-program accounting and targeted STOCK validation.

Development tool, not the production checker. References run strictly after
model inference and compare every register/cache row; they supply no inputs or
answers to the model. --plan constructs only meta tensors, without GPU weights.
Run as python -m tools.kernel_stock_delivery from the repository root.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

import torch

from leanputer.kernel import source_transition as program
from leanputer.kernel_check import read_documents
from leanputer.native_machine import compile_native_machine


def plan(config, intermediate,control_digit_bits=8,bank_control=False,native_word_ops=False):
    from transformers import Qwen3_5ForCausalLM, Qwen3_5TextConfig
    from transformers.initialization import no_init_weights
    start = time.perf_counter()
    p = compile_native_machine(config, intermediate=intermediate,
        reset_layers=64, program=program, pack_control=True, plan_only=True,control_digit_bits=control_digit_bits,
        bank_control=bank_control,native_word_ops=native_word_ops)
    with torch.device('meta'), no_init_weights():
        model = Qwen3_5ForCausalLM(Qwen3_5TextConfig(**p['stock_config']))
    groups = {}
    for name, value in model.named_parameters():
        group = ('mlp' if '.mlp.' in name else 'linear_attention'
            if '.linear_attn.' in name else 'full_attention'
            if '.self_attn.' in name else 'embeddings_and_head'
            if name.endswith(('embed_tokens.weight', 'lm_head.weight')) else 'norms')
        groups[group] = groups.get(group, 0) + value.numel()
    return dict(format='leanputer.full-source-stock-plan.v1', config=asdict(config),
        logical_parameters=sum(groups.values()), bf16_dense_equivalent_bytes=2*sum(groups.values()),
        parameter_groups=groups, hidden_size=p['layout'].hidden,
        native_layers=model.config.num_hidden_layers, persistent_channels=p['persistent_channels'],
        allocated_slots=p['allocation'].n_slots, scratch_reset_channels=p['clear_channels'],
        reset_layers=p['reset_layers'], graph=p['graph'].stats(),
        commit_statistics=p['commit_statistics'],control_digit_bits=control_digit_bits,
        control_bank=p['control_bank'],word_operations=p['word_operations'],seconds=time.perf_counter()-start,
        small_model_target_met=False, evidence='Whole fixed program/meta shapes only; no GPU weights or inference')


def verify(machine, documents):
    # The production model runs to completion before reference state exists.
    report = machine.check(documents, diagnostic_cache=True, early_stop=True)
    cache = report.pop('diagnostic_cache')
    print(json.dumps(dict(phase='model_inference_returned',results=report['results'])),flush=True)
    from leanputer.kernel import traversal_machine as spec
    from leanputer.bitvec import unpack_words
    config = machine.config
    references = []
    for document in documents:
        reference = spec.SpecMachine(config, program.prepare(config, *program.parse_document(document)))
        for _ in range(config.fuel+2):
            reference.step()
            if reference.state['regs']['status']:
                break
        references.append(reference.state)
    if report['registers'] != [s['regs'] for s in references]:
        raise AssertionError('final semantic registers differ from offline reference')
    verified = []
    for head in machine.native_heads:
        bank, part = head['bank'], head['row_bank']
        memory = cache.layers[head['layer']].recurrent_states[0]
        if bank=='control':
            first=head['column_offset'];count=head['columns'];control=machine.control_bank
            values=memory[:,0,:128,2:2+count].float().cpu()/128
            if not torch.all((values==0)|(values==1)):raise AssertionError('private control cache domain')
            expected=torch.zeros_like(values)
            for i,state in enumerate(references):
                for owner,names in control.groups.items():
                    for slot,name in enumerate(names):
                        for bit in range(config.word_bits):
                            column=slot*config.word_bits+bit
                            if first<=column<first+count:expected[i,owner,column-first]=float(bool(state['regs'][name]&(1<<bit)))
            if not torch.equal(values,expected):raise AssertionError(('private cache mismatch',first))
            verified.append(dict(bank=bank,column_offset=first,columns=count,rows=128,encoding='binary'))
            continue
        count = min(128, getattr(config, bank)-128*part)
        fields = spec.BANK_FIELDS[bank]
        values = memory[:, 0, :count, 2:2+fields*config.word_bits].float().cpu()/128
        if not torch.all((values == 0) | (values == 1)):
            raise AssertionError(('cache domain', bank, part))
        for i, expected in enumerate(references):
            actual = [unpack_words(row, [config.word_bits]*fields) for row in values[i].tolist()]
            if actual != expected[bank][128*part:128*part+count]:
                raise AssertionError(('cache mismatch', bank, part, i))
        verified.append(dict(bank=bank, row_bank=part, rows=count, fields=fields))
    report.update(config=asdict(config), input_documents=documents,
        exact_register_match=True, exact_cache_match=True, verified_cache_banks=verified,
        full_kernel_native_support=False, small_model_target_met=False,
        validation_scope='Full fixed source checker; only supplied source witnesses validated. References computed after inference; not all Lean coverage.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--intermediate', type=int, default=512)
    parser.add_argument('--control-digit-bits',type=int,choices=(2,4,8),default=8)
    parser.add_argument('--bank-control',action='store_true')
    parser.add_argument('--native-word-ops',action='store_true')
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    parser.add_argument('--load-model', type=Path)
    parser.add_argument('--save-model', type=Path)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.plan:
        if not args.config:
            parser.error('--plan requires --config')
        report = plan(program.MachineConfig(**json.loads(args.config.read_text())), args.intermediate,args.control_digit_bits,args.bank_control,args.native_word_ops)
    else:
        if not args.input or not (args.config or args.load_model):
            parser.error('validation requires --input and --config or --load-model')
        start = time.perf_counter()
        if args.load_model:
            from leanputer.source_model import load_source_machine
            machine = load_source_machine(args.load_model, args.device)
            if args.config and program.MachineConfig(**json.loads(args.config.read_text())) != machine.config:
                parser.error('config differs from compiled model')
        else:
            config = program.MachineConfig(**json.loads(args.config.read_text()))
            machine = compile_native_machine(config, intermediate=args.intermediate,
                reset_layers=64, device=args.device, program=program,
                pack_control=True, weight_storage='sparse_csr',control_digit_bits=args.control_digit_bits,
                bank_control=args.bank_control,native_word_ops=args.native_word_ops)
        compile_seconds = time.perf_counter()-start
        if args.save_model:
            from leanputer.source_model import save_source_machine
            save_source_machine(machine, args.save_model)
        print(json.dumps(dict(phase='compiled_or_loaded',seconds=compile_seconds,
            hidden=machine.layout.hidden,layers=machine.model.config.num_hidden_layers)),flush=True)
        report = verify(machine, read_documents(args.input.read_text()))
        report.update(compile_or_load_seconds=compile_seconds)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('logical_parameters', 'small_model_target_met')}))


if __name__ == '__main__':
    main()
