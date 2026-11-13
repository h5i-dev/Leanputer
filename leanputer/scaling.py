"""Controlled capacity/batch ablation; replicated fixed judgment, no oracle gating."""
import argparse
import gc
import json
import math
from pathlib import Path
import statistics
import time

import torch

from .checker import compile_checker
from .examples import demo_config
from .terms import Lam, Var, encode
from .evaluation import provenance
from .execution import clear_cuda_graphs
from .machine_spec import MachineConfig
from .runner import check_batch, model_statistics
from .transition import compile_machine


COMMON = dict(format='leanputer.dependent.v1', name='common-STLC-identity',
              environment=[dict(name='P', type=['sort', 0], value=None)],
              term=['lam', ['const','P'], ['var',0]], claim=['pi', ['const','P'], ['const','P']])


def measure(capacities, batches, devices, lowerings, fuel, repeats, memory_update='attention_delta', execution='eager'):
    records = []
    for device in devices:
        if device == 'cuda' and not torch.cuda.is_available(): continue
        for optimized in lowerings:
            for capacity in capacities:
                config = MachineConfig(heap=capacity, stack=16, context=16, constants=4, fuel=fuel)
                start = time.perf_counter()
                backend = execution if device == 'cuda' else 'eager'
                model = compile_machine(config, optimized=optimized, memory_update=memory_update).to(device).eval()
                if device == 'cuda': torch.cuda.synchronize()
                compile_seconds = time.perf_counter()-start
                for batch in batches:
                    documents = [COMMON]*batch
                    # Warm each batch shape before timed repeats.
                    cold = check_batch(model, documents, backend)
                    measurements = [check_batch(model, documents, backend) for _ in range(repeats)]
                    if any(result['status'] != 'ACCEPT' for run in measurements for result in run['results']):
                        raise RuntimeError('common-fragment scaling judgment did not accept')
                    times = [run['runtime']['forward_seconds'] for run in measurements]
                    records.append(dict(device=device, optimized=optimized, capacity=capacity, batch=batch,
                                        execution=backend, memory_update=memory_update, cold=cold['runtime'],
                                        compile_seconds=compile_seconds, seconds=times, median_seconds=statistics.median(times),
                                        p95_seconds=sorted(times)[math.ceil(.95*len(times))-1],
                                        proofs_per_second=batch/statistics.median(times), model=model_statistics(model),
                                        semantic_steps=measurements[0]['results'][0]['semantic_steps'],
                                        applied_steps=fuel+1,
                                        cuda_peak_allocated_bytes=max(run['runtime']['cuda_peak_allocated_bytes'] or 0 for run in measurements)))
                    clear_cuda_graphs(model)
                del model
                gc.collect()
                if device == 'cuda': torch.cuda.empty_cache()
    baseline = []
    for device in devices:
        if device == 'cuda' and not torch.cuda.is_available(): continue
        start = time.perf_counter(); model = compile_checker(demo_config()).to(device).eval()
        if device == 'cuda': torch.cuda.synchronize()
        compilation = time.perf_counter()-start
        buffers = list(model.buffers())
        buffer_bytes = sum((b.indices().numel()*b.indices().element_size()+b.values().numel()*b.values().element_size())
                           if b.is_sparse else b.numel()*b.element_size() for b in buffers)
        for batch in batches:
            bits = encode(model, Lam('p', 'P', Var('p')), ('P','P')).repeat(batch, 1).to(device)
            if device == 'cuda': torch.cuda.reset_peak_memory_stats()
            times = []
            with torch.inference_mode():
                model(bits)
                for _ in range(repeats):
                    if device == 'cuda': torch.cuda.synchronize()
                    start = time.perf_counter(); result = model(bits)
                    if device == 'cuda': torch.cuda.synchronize()
                    times.append(time.perf_counter()-start)
                    if not torch.all(result[:,0] == 1): raise RuntimeError('baseline identity rejected')
            baseline.append(dict(device=device, batch=batch, compile_seconds=compilation,
                                 seconds=times, median_seconds=statistics.median(times), proofs_per_second=batch/statistics.median(times),
                                 p95_seconds=sorted(times)[math.ceil(.95*len(times))-1],
                                 distinct_layers=len(model.layers), residual_width=2*model.width,
                                 weight_bytes=buffer_bytes,
                                 cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device == 'cuda' else None,
                                 note='Fixed nominal atoms/type vocabulary; shared checker additionally validates P : Prop.'))
    return dict(format='leanputer.scaling.v1', provenance=provenance(), shared=records, baseline=baseline,
                workload='Replicated single closed STLC identity relative to P : Prop; not a diversity corpus.',
                timing='Forward only; syntax preparation and H2D transfer excluded; one warmup per shape; fixed applied fuel budget.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capacities', default='32,64,128,256')
    parser.add_argument('--batches', default='1,8,32')
    parser.add_argument('--devices', default='cpu,cuda')
    parser.add_argument('--lowerings', default='reference,optimized')
    parser.add_argument('--fuel', type=int, default=128)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--memory-update', choices=['logic', 'attention_delta'], default='attention_delta')
    parser.add_argument('--execution', choices=['eager', 'cuda_graph'], default='cuda_graph', help='CUDA backend; CPU always eager')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    result = measure([int(v) for v in args.capacities.split(',')], [int(v) for v in args.batches.split(',')],
                     args.devices.split(','), [v == 'optimized' for v in args.lowerings.split(',')], args.fuel, args.repeats,
                     args.memory_update, args.execution)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(shared_measurements=len(result['shared']), baseline_measurements=len(result['baseline']))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
