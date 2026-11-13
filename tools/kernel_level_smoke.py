"""Matched typed-cell symbolic scope + Pi/Lam stock operation smoke.

Offline references/cache decoding are validation only. This is not proof or
declaration admission, and the Python spec never supplies inference answers.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
import torch
from leanputer.bitvec import unpack_words
from leanputer.kernel import level_transition as program
from leanputer.kernel import traversal_machine as spec
from leanputer.native_machine import compile_native_machine
from tests.test_kernel_inference_transition import cases as inference_cases
from tests.test_kernel_level_transition import cases, telescope_cases, substitution_cases, expression_cases, predicate_cases, constructor_cases, source_instantiation_cases, ordering_cases, normalization_cases, geq_cases, expression_scope_cases, expression_equality_cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--device', default='cuda', choices=('cpu', 'cuda'))
    parser.add_argument('--group', choices=('syntax', 'constructors', 'instantiation', 'normalization', 'geq', 'scope', 'comparison', 'inference'), default='syntax')
    args = parser.parse_args()
    torch.set_num_threads(1)
    cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=512 if args.group == 'geq' else 160 if args.group == 'inference' else 128, word_bits=8)
    if args.group == 'inference':
        documents = inference_cases()
    elif args.group == 'comparison':
        documents = expression_equality_cases()
    elif args.group == 'scope':
        documents = expression_scope_cases()
    elif args.group == 'geq':
        documents = geq_cases()
    elif args.group == 'normalization':
        documents = normalization_cases()
    elif args.group == 'instantiation':
        documents = source_instantiation_cases()+ordering_cases()
    elif args.group == 'constructors':
        predicates, constructors = predicate_cases(), constructor_cases()
        documents = [predicates[i] for i in (4, 6, 7, 9)]+[constructors[i] for i in (3, 4, 6, 8, 11, 12, 14, 17)]
    else:
        documents = cases()+telescope_cases()+substitution_cases()+expression_cases()
    references = []
    for document in documents:
        machine = spec.SpecMachine(cfg, program.prepare(cfg, *program.parse_document(document)))
        for _ in range(cfg.fuel+2):
            machine.step()
            if machine.state['regs']['status']:
                break
        references.append(machine.state)
    print(json.dumps({'phase': 'reference', 'registers': [s['regs'] for s in references]}), flush=True)
    started = time.perf_counter()
    machine = compile_native_machine(cfg, intermediate=512, device=args.device, program=program)
    compilation = time.perf_counter()-started
    print(json.dumps({'phase': 'compiled', 'seconds': compilation,
        'parameters': sum(p.numel() for p in machine.model.parameters())}), flush=True)
    report = machine.check(documents, diagnostic_cache=True)
    cache = report.pop('diagnostic_cache')
    if report['registers'] != [s['regs'] for s in references]:
        raise AssertionError(('register mismatch', report['registers'], [s['regs'] for s in references]))
    verified = []
    for head in machine.native_heads:
        bank, part = head['bank'], head['row_bank']
        if bank == 'constants':
            continue
        memory = cache.layers[head['layer']].recurrent_states[0]
        count = min(128, getattr(cfg, bank)-128*part)
        fields = spec.BANK_FIELDS[bank]
        values = memory[:, 0, :count, 2:2+fields*cfg.word_bits].float().cpu()/128
        if not torch.all((values == 0) | (values == 1)):
            raise AssertionError('cache left exact binary domain')
        for i, expected in enumerate(references):
            actual = [unpack_words(row, [cfg.word_bits]*fields) for row in values[i].tolist()]
            if actual != expected[bank][128*part:128*part+count]:
                raise AssertionError(('cache mismatch', bank, part, i))
        verified.append(dict(bank=bank, row_bank=part, rows=count, fields=fields))
    report.update(format='leanputer.typed-symbolic-services-stock-smoke.v1',
        config=asdict(cfg), device=args.device, compile_seconds=compilation,
        input_documents=documents, exact_register_match=True, exact_cache_match=True,
        verified_cache_banks=verified,
        validation_scope=f'{len(documents)} typed-memory {args.group} operation probes; not full typing, declaration admission or mathlib coverage',
        operation_group=args.group,
        full_kernel_native_support=False)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'phase': 'passed', 'statuses': [r['status'] for r in report['results']],
        'forward_seconds': report['forward_seconds'], 'report': str(args.report)}), flush=True)


if __name__ == '__main__':
    main()
