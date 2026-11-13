"""Fresh-process pinned-mathlib benchmark, with complete cold/steady boundaries."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

from .mathlib_benchmark import prepare_mathlib


def run_pipeline(checkout, config, directory, device='cuda', count=1000000,
                 cold_repeats=1, steady_repeats=3, nanoda=None):
    if cold_repeats < 1 or steady_repeats < 0:
        raise ValueError('positive cold repeats and nonnegative steady repeats required')
    directory = Path(directory).resolve(); directory.mkdir(parents=True, exist_ok=True)
    trials = []
    for index in range(cold_repeats):
        trial = directory/f'cold-{index:02d}'; trial.mkdir(exist_ok=True)
        started = time.perf_counter()
        preparation = prepare_mathlib(checkout, trial/'preparation', count=count)
        export_complete = time.perf_counter()
        command = [sys.executable, '-m', 'leanputer.evaluation',
                   '--input', str(trial/'preparation/corpus.jsonl'),
                   '--config', str(Path(config).resolve()), '--output', str(trial/'evaluation'),
                   '--device', device, '--memory-update', 'attention_delta',
                   '--execution', 'cuda_graph' if device == 'cuda' else 'eager',
                   '--lean', '--repeats', str(steady_repeats), '--progress-events']
        if nanoda: command += ['--nanoda', str(Path(nanoda).resolve())]
        child_started = time.perf_counter()
        checking_wall, internal_check = None, None
        with (trial/'checker-process.log').open('w') as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                log.write(line); log.flush()
                try: event = json.loads(line)
                except json.JSONDecodeError: continue
                if event.get('event') == 'checking_complete':
                    checking_wall = time.perf_counter()-child_started
                    internal_check = event['elapsed_seconds']
                    print(json.dumps(dict(event='cold_checking_complete', trial=index,
                                          full_cold_seconds=time.perf_counter()-started)), flush=True)
            code = process.wait()
        if code or checking_wall is None:
            raise RuntimeError(f'checker child failed ({code}); inspect {trial}/checker-process.log')
        evaluation = json.loads((trial/'evaluation/evaluation.json').read_text())
        trials.append(dict(preparation_seconds=export_complete-started,
                           enumeration_seconds=preparation['selection']['enumeration_seconds'],
                           export_seconds=preparation['export_seconds'],
                           checker_fresh_process_to_check_seconds=checking_wall,
                           process_startup_and_input_seconds=checking_wall-internal_check,
                           full_cold_to_check_seconds=export_complete-started+checking_wall,
                           all_evaluation_process_seconds=time.perf_counter()-child_started,
                           counts=evaluation['counts'], mismatches=evaluation['mismatches'],
                           steady=evaluation['steady'],
                           evaluation=str(trial/'evaluation/evaluation.json'), command=command))
        (directory/'pipeline.json').write_text(json.dumps(dict(
            format='leanputer.pipeline.v1', trials=trials,
            cold_median_seconds=statistics.median(t['full_cold_to_check_seconds'] for t in trials),
            setup_boundary='Existing pinned Lean/mathlib checkout and module cache; no checkout/download cost. Each trial reruns enumeration/export and starts a fresh Python checking process. Parent harness startup excluded.',
            cold_boundary='Enumeration + syntax export + child process startup/input + weight compilation/device placement + encoding + graph setup + initialization + fixed-budget checking. Stops before steady repeats and independent references.',
            steady_boundary='Same weights/graphs, inputs re-encoded; forward-only and total-batch samples retained. No dependency cache or proof-answer cache.',
            percentile_boundary='Use evaluation raw samples and nearest-rank p95; small-repeat p95 is descriptive, not a tail estimate.'), indent=2)+'\n')
    return trials


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mathlib', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', choices=['cpu','cuda'], default='cuda')
    parser.add_argument('--count', type=int, default=1000000)
    parser.add_argument('--cold-repeats', type=int, default=1)
    parser.add_argument('--steady-repeats', type=int, default=3)
    parser.add_argument('--nanoda', type=Path)
    args = parser.parse_args(argv)
    run_pipeline(args.mathlib, args.config, args.output, args.device, args.count,
                 args.cold_repeats, args.steady_repeats, args.nanoda)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
