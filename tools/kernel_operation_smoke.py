"""One matched-operation stock-forward/cache smoke, not a kernel benchmark.

Run from a source checkout with the native optional environment. Python spec
and cache decoding are offline validation only; the native operation runner
loads syntax, calls stock forward/cache and feeds hidden state back unchanged.
No checker/reduction answers enter its model input.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
import torch

from leanputer.bitvec import unpack_words
from leanputer.kernel import traversal_machine as spec
from leanputer.kernel import traversal_transition as program
from leanputer.native_machine import compile_native_machine
from tests.test_kernel_traversal_machine import cases


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--device', default='cuda', choices=('cpu', 'cuda'))
    args = p.parse_args()
    torch.set_num_threads(1)
    cfg = spec.MachineConfig(heap=64, stack=16, context=8, constants=2, fuel=128, word_bits=8)
    docs = cases()
    references = []
    for doc in docs:
        machine = spec.SpecMachine(cfg, spec.prepare(cfg, *spec.parse_document(doc)))
        for _ in range(cfg.fuel+2):
            machine.step()
            if machine.state['regs']['status']:
                break
        references.append(machine.state)
    print(json.dumps({'phase': 'reference', 'registers': [r['regs'] for r in references]}), flush=True)
    started = time.perf_counter()
    machine = compile_native_machine(cfg, intermediate=512, device=args.device, program=program)
    compile_seconds = time.perf_counter()-started
    print(json.dumps({'phase': 'compiled', 'seconds': compile_seconds,
        'parameters': sum(p.numel() for p in machine.model.parameters())}), flush=True)
    report = machine.check(docs, diagnostic_cache=True)
    cache = report.pop('diagnostic_cache')
    if report['registers'] != [r['regs'] for r in references]:
        raise AssertionError(('native registers differ', report['registers'], [r['regs'] for r in references]))
    # Posthoc only: decode exact stored bits, including output syntax and stack.
    # Each cache head has value columns [reference,reference,word bits...].
    verified = []
    for head in machine.native_heads:
        bank, part = head['bank'], head['row_bank']
        if bank == 'constants':
            continue
        memory = cache.layers[head['layer']].recurrent_states[0]
        width = spec.BANK_FIELDS[bank]*cfg.word_bits
        count = min(128, getattr(cfg, bank)-128*part)
        stored = memory[:, 0, :count, 2:2+width].float().cpu()/128
        if not torch.all((stored == 0) | (stored == 1)):
            raise AssertionError(('nonbinary cache', head, torch.unique(stored).tolist()))
        for i, reference in enumerate(references):
            actual = [unpack_words(row, [cfg.word_bits]*spec.BANK_FIELDS[bank]) for row in stored[i].tolist()]
            expected = reference[bank][128*part:128*part+count]
            if actual != expected:
                raise AssertionError(('cache differs', head, i, actual, expected))
        verified.append({'bank': bank, 'row_bank': part, 'rows': count, 'word_fields': spec.BANK_FIELDS[bank]})
    report.update(format='leanputer.kernel-operation-stock-smoke.v1', config=asdict(cfg),
        compile_seconds=compile_seconds, device=args.device, input_documents=docs,
        exact_register_match=True, exact_cache_match=True, verified_cache_banks=verified,
        validation_scope='Eight general traversal operation probes, not declaration admission or proof coverage',
        full_kernel_native_support=False)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'phase': 'passed', 'report': str(args.report),
        'statuses': [r['status'] for r in report['results']], 'forward_seconds': report['forward_seconds']}), flush=True)


if __name__ == '__main__':
    main()
