"""Measure the tied-slot stock checker on the two original source cases.

The reference replay runs only after each stock execution and is not an
inference input. Run from the worktree with the native environment.
"""
import json
import pickle
import time
from pathlib import Path
from leanputer.kernel.stock_checker import execute_window, read_main_and_banks
from leanputer.kernel.stock_datapath import build
from leanputer.kernel.traversal_machine import MachineConfig


def reference_outcome(program, config, document):
    from leanputer.kernel import source_transition as source
    from leanputer.kernel.stock_control_reference import NativeControlReference
    state = source.prepare(config, *source.parse_document(document))
    ref = NativeControlReference(program, state)
    steps = 0
    while ref.status == 0:
        ref.step()
        steps += 1
        if steps > 200000:
            raise RuntimeError('reference did not publish')
    return ref


def compare(chip, cache, ref):
    got = read_main_and_banks(chip, cache, 0)
    expected = ref.state()
    mismatches = []
    for name, value in expected['regs'].items():
        if got['regs'].get(name) != value:
            mismatches.append(('reg', name, got['regs'].get(name), value))
    for bank in ('heap', 'stack', 'context', 'constants'):
        for row, values in enumerate(expected[bank]):
            if got[bank][row] != list(values):
                mismatches.append((bank, row, got[bank][row], list(values)))
    return got, mismatches


def main():
    root = Path('benchmarks/kernel-full-source-stock')
    program = pickle.loads(Path('/mnt/scratch/leanputer-runs/architecture-budget/direct-preflight-control-offline.pickle').read_bytes())
    config = MachineConfig(**json.loads((root / 'config.json').read_text()))
    documents = [json.loads(line) for line in (root / 'source.jsonl').read_text().splitlines()]
    started = time.perf_counter()
    chip = build(
        program.records, rom_layout='byte_pages', compact_attention=True, hidden=1024, intermediate=256,
        datapath_layers=90, parallel_carry=True, grouped_memory=True, bounds_schema=program.bounds_schema,
        reuse_transient_features=True, preflight_plan=program.preflight_plan, window_lanes=22,
    )
    chip.model.cuda().eval()
    cases = []
    for document in documents:
        def progress(event):
            print(document['name'], event, flush=True)
            if event.get('check_forwards')==1 and document['name']=='current-general-source-empty-claim-id' and event['output'][0]!=37965:
                raise RuntimeError('first window diverged from the measured prefix')
        result = execute_window(chip, config, document, execution='cuda_graph', max_total_forwards=5000, progress=progress)
        ref = reference_outcome(program, config, document)
        _got, mismatches = compare(chip, result['cache'], ref)
        result = {key: value for key, value in result.items() if key not in ('cache', 'state')}
        # Diagnostic groups are pc, status, reason, result.
        result.update(document_id=document.get('name', document.get('id')), reference_status=ref.status, reference_reason=ref.reason, reference_result=ref.result, reference_forwards=ref.forwards, reference_semantic_steps=ref.semantic_steps, mismatches=len(mismatches), mismatch_preview=[list(item) for item in mismatches[:8]], terminal_match=result['output'][1:] == [ref.status, ref.reason, ref.result])
        cases.append(result)
        print('CASE', json.dumps({k: v for k, v in result.items() if k != 'mismatch_preview'}), flush=True)
        if mismatches:
            print('MISMATCHES', mismatches[:8], flush=True)
    out = dict(format='leanputer.stock-window-run.v1', seconds=time.perf_counter() - started, logical_dense_parameters=chip.report['logical_dense_parameters'], layers=chip.report['layers'], window_lanes=22, allocated_channels=chip.report['allocated_channels'], cases=cases)
    Path('/tmp/stock-window-run.json').write_text(json.dumps(out, indent=2))
    print('WROTE', '/tmp/stock-window-run.json', flush=True)
    if not all(case['completed'] and case['terminal_match'] and case['total_forwards'] <= 5000 and case['mismatches'] == 0 for case in cases):
        raise SystemExit('FAIL window run')
    print('WINDOW_RUN_OK', flush=True)


if __name__ == '__main__':
    main()
