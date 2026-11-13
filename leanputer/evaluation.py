"""Reproducible evaluation only: weights, references, corpus and trace checks."""
import argparse
from collections import Counter
import dataclasses
import hashlib
import json
from pathlib import Path
import platform
import resource
import math
import statistics
import subprocess
import time

import torch

from .dependent import Oracle, Rejected
from .machine_spec import MachineConfig
from .references import lean_replay, nanoda_replay
from .research_artifacts import compiler_fingerprint
from .runner import check_batch, check_corpus
from .transition import compile_machine
from .validation import minimize, reference_result, trace_discrepancy


def provenance():
    def output(command):
        try:
            completed = subprocess.run(command, capture_output=True, text=True)
            return completed.stdout.strip() if completed.returncode == 0 else None
        except OSError:
            return None
    cpu = platform.processor()
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.exists():
        cpu = next((line.partition(':')[2].strip() for line in cpuinfo.read_text().splitlines()
                    if line.startswith('model name')), cpu)
    return dict(python=platform.python_version(), torch=torch.__version__, cpu=cpu,
                torch_cpu_threads=torch.get_num_threads(),
                cuda_runtime=torch.version.cuda, gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                cuda_driver=output(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader']),
                float32_matmul_precision=torch.get_float32_matmul_precision(),
                cuda_matmul_tf32=torch.backends.cuda.matmul.allow_tf32,
                lean_version=output(['lean', '--version']),
                git_commit=output(['git', 'rev-parse', 'HEAD']), git_status=output(['git', 'status', '--porcelain']),
                compiler=compiler_fingerprint(), platform=platform.platform())


def evaluate(documents, config, device, directory, batch_size=16, optimized=True,
             with_lean=False, nanoda=None, traces=0, minimize_budget=25, execution='eager', memory_update='logic', repeats=1, events=False):
    if repeats < 0 or traces < 0:
        raise ValueError('nonnegative repeat and trace counts required')
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    model = compile_machine(config, optimized=optimized, memory_update=memory_update).to(device).eval()
    if device == 'cuda': torch.cuda.synchronize()
    compile_seconds = time.perf_counter()-started
    # All model runs precede references, which cannot affect checking inputs,
    # capacities, weights, branch decisions, fuel or scheduling.
    def progress(completed, total):
        (directory/'progress.json').write_text(json.dumps(dict(completed=completed, total=total, device=device)))
    report = check_corpus(model, documents, batch_size, execution, progress)
    weighted, batches, model_info = report['results'], report['batches'], report['model']
    (directory/'progress.json').write_text(json.dumps(dict(completed=len(weighted), total=len(documents), device=device)))
    cold_check_seconds = time.perf_counter()-started
    if events: print(json.dumps(dict(event='checking_complete', documents=len(documents), elapsed_seconds=cold_check_seconds)), flush=True)
    steady = []
    for _ in range(repeats):
        repeated = check_corpus(model, documents, batch_size, execution)
        if repeated['results'] != weighted:
            raise RuntimeError('reused weights/graphs changed checker outcomes')
        steady.append(dict(forward_seconds=sum(b['forward_seconds'] for b in repeated['batches']),
                           total_batch_seconds=sum(b['total_batch_seconds'] for b in repeated['batches']),
                           graph_setup_seconds=sum(b.get('graph_setup_seconds', 0.) for b in repeated['batches'])))
    ref_start = time.perf_counter()
    references = [reference_result(d, config) for d in documents]
    reference_seconds = time.perf_counter()-ref_start
    mismatches = []
    for index, (actual, expected) in enumerate(zip(weighted, references)):
        if actual['status'] != expected['status']:
            mismatches.append(dict(index=index, name=actual['name'], model=actual['status'], specification=expected['status']))
        if ('operational_state_sha256' in actual
                and actual['operational_state_sha256'] != expected.get('operational_state_sha256')):
            mismatches.append(dict(index=index, name=actual['name'], final_state=dict(model=actual['operational_state_sha256'], specification=expected.get('operational_state_sha256'))))
        if actual['status'] in ('ACCEPT', 'REJECT') and expected.get('recursive') != actual['status']:
            mismatches.append(dict(index=index, name=actual['name'], model=actual['status'], recursive=expected.get('recursive')))
    lean_results, lean_seconds = None, None
    if with_lean:
        lean_results, lean_seconds = lean_replay(documents, directory/'lean')
        for index, (actual, expected) in enumerate(zip(weighted, lean_results)):
            if actual['status'] in ('ACCEPT', 'REJECT') and expected['status'] != actual['status']:
                mismatches.append(dict(index=index, name=actual['name'], model=actual['status'], lean=expected['status']))
    nanoda_results = []
    if nanoda:
        for index, (document, actual) in enumerate(zip(documents, weighted)):
            if actual['status'] not in ('ACCEPT', 'REJECT'):
                continue
            result = nanoda_replay(document, directory/f'nanoda/{index:05d}', nanoda)
            nanoda_results.append(dict(index=index, **result))
            if result['status'] != actual['status']:
                mismatches.append(dict(index=index, name=actual['name'], model=actual['status'], nanoda=result['status']))
    checked = 0
    for index, (document, actual) in enumerate(zip(documents, weighted)):
        if checked >= traces: break
        if actual['status'] not in ('ACCEPT', 'REJECT'): continue
        discrepancy = trace_discrepancy(model, document, execution)
        checked += 1
        if discrepancy:
            mismatches.append(dict(index=index, name=actual['name'], trace=discrepancy))
    counts = dict(Counter(row['status'] for row in weighted))
    families = {}
    for document, actual in zip(documents, weighted):
        metadata = document.get('provenance', {}) if isinstance(document, dict) else {}
        if not isinstance(metadata, dict): metadata = {}
        family = metadata.get('family', 'elaborated_lean' if metadata.get('source_constant') else 'other')
        if not isinstance(family, str): family = 'other'
        families.setdefault(family, Counter())[actual['status']] += 1
    op_counts = Counter()
    for reference in references: op_counts.update(reference.get('op_counts', {}))
    forward_seconds = sum(batch['forward_seconds'] for batch in batches)
    counterexamples = []
    for mismatch in mismatches[:3]:
        index = mismatch['index']
        def predicate(candidate):
            try:
                checked_candidate = check_batch(model, [candidate], execution)['results'][0]
                actual = checked_candidate['status']
                reference = reference_result(candidate, config)
                if 'final_state' in mismatch:
                    return ('operational_state_sha256' in checked_candidate
                            and checked_candidate['operational_state_sha256'] != reference.get('operational_state_sha256'))
                if 'trace' in mismatch:
                    return trace_discrepancy(model, candidate, execution) is not None
                if actual != reference['status']:
                    return True
                if actual not in ('ACCEPT', 'REJECT'):
                    return False
                if actual != reference.get('recursive'):
                    return True
                if 'lean' in mismatch:
                    replay, _ = lean_replay([candidate], directory/'minimization-replay')
                    return replay[0]['status'] != actual
                if 'nanoda' in mismatch:
                    return nanoda_replay(candidate, directory/'minimization-nanoda', nanoda)['status'] != actual
                return False
            except (ValueError, TypeError, RecursionError):
                return False
        smaller, attempts = minimize(documents[index], predicate, minimize_budget)
        counterexamples.append(dict(index=index, attempts=attempts, document=smaller))
        (directory/f'counterexample-{index:05d}.json').write_text(json.dumps(smaller, indent=2)+'\n')
    unique = {json.dumps({key:d.get(key) for key in ('term','claim','environment','status')} if isinstance(d, dict) else d, sort_keys=True) for d in documents}
    source_constants = {d.get('provenance', {}).get('source_constant') for d in documents
                        if isinstance(d, dict) and isinstance(d.get('provenance', {}), dict)
                        and isinstance(d.get('provenance', {}).get('source_constant'), str)}
    source_constants.discard(None)
    corpus_digest = hashlib.sha256(json.dumps(documents, sort_keys=True).encode()).hexdigest()
    encoded = sum('input_heap_nodes' in row for row in weighted)
    accepted = sum(row['status'] == 'ACCEPT' for row in weighted)
    result = dict(format='leanputer.evaluation.v1', provenance=provenance(), config=dataclasses.asdict(config),
                  device=device, lowering='optimized' if optimized else 'reference', compile_seconds=compile_seconds,
                  execution=execution,
                  documents=len(documents), unique_syntax_judgments=len(unique), real_source_constants=len(source_constants),
                  corpus_sha256=corpus_digest, batch_size=batch_size, counts=counts,
                  resource_reasons=dict(Counter(row['reason'] for row in weighted if row['status'] == 'RESOURCE')),
                  cold_compile_and_check_seconds=cold_check_seconds, steady=steady,
                  steady_forward_median_seconds=statistics.median(s['forward_seconds'] for s in steady) if steady else None,
                  steady_forward_p95_seconds=sorted(s['forward_seconds'] for s in steady)[math.ceil(.95*len(steady))-1] if steady else None,
                  percentile_method='Nearest-rank p95 over the reported repeats; raw samples retained.',
                  families={family:dict(values) for family, values in families.items()},
                  results=weighted, operational=references, model=model_info, batches=batches,
                  forward_seconds=forward_seconds,
                  model_checked_items=encoded,
                  model_checked_items_per_forward_second=encoded/forward_seconds if forward_seconds else None,
                  accepted_proofs_per_forward_second=accepted/forward_seconds if forward_seconds else 0.,
                  python_reference_seconds=reference_seconds, lean_process_seconds=lean_seconds,
                  lean=lean_results, nanoda=nanoda_results, traced_documents=checked,
                  operational_phase_counts=dict(op_counts), mismatches=mismatches, counterexamples=counterexamples,
                  host_process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    (directory/'evaluation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--reference-lowering', action='store_true')
    parser.add_argument('--lean', action='store_true')
    parser.add_argument('--nanoda', type=Path)
    parser.add_argument('--traces', type=int, default=0)
    parser.add_argument('--execution', choices=['eager', 'cuda_graph'], default='eager')
    parser.add_argument('--memory-update', choices=['logic', 'attention_delta'], default='logic')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--progress-events', action='store_true')
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    documents = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    if args.limit is not None: documents = documents[:args.limit]
    config = MachineConfig(**json.loads(args.config.read_text())) if args.config else MachineConfig()
    result = evaluate(documents, config, args.device, args.output, args.batch_size,
                      not args.reference_lowering, args.lean, args.nanoda, args.traces, execution=args.execution,
                      memory_update=args.memory_update, repeats=args.repeats, events=args.progress_events)
    print(json.dumps({key:result[key] for key in ('documents', 'counts', 'forward_seconds', 'mismatches')}))
    return int(bool(result['mismatches']))


if __name__ == '__main__':
    raise SystemExit(main())
