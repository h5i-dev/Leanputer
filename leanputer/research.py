"""Batch CLI for the shared dependent checker; preparation and weights are separate."""
import argparse
import json
from pathlib import Path
import time

import torch

from .machine_spec import MachineConfig
from .research_artifacts import load_machine, save_machine
from .runner import check_batch, model_statistics
from .transition import compile_machine


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--config', type=Path)
    source.add_argument('--load', type=Path)
    parser.add_argument('--save', type=Path)
    parser.add_argument('--input', type=Path, help='one dependent JSON document or JSONL corpus')
    parser.add_argument('--report', type=Path, help='write machine-readable report')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--reference-lowering', action='store_true', help='unoptimized lowering for semantic/architecture ablation')
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    try:
        if args.batch_size < 1:
            raise ValueError('positive batch size required')
        if args.device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('CUDA unavailable')
        start = time.perf_counter()
        if args.load:
            if args.reference_lowering:
                raise ValueError('artifact specifies lowering; omit --reference-lowering with --load')
            model = load_machine(args.load)
        else:
            config = MachineConfig(**json.loads(args.config.read_text())) if args.config else MachineConfig()
            model = compile_machine(config, optimized=not args.reference_lowering)
        model = model.to(args.device).eval()
        if args.device == 'cuda':
            torch.cuda.synchronize()
        compilation = time.perf_counter()-start
        if args.save:
            save_machine(model, args.save)
        if not args.input:
            report = dict(format='leanputer.report.v1', results=[], model=model_statistics(model))
        else:
            content = args.input.read_text()
            try:
                parsed = json.loads(content)
                documents = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                documents = [json.loads(line) for line in content.splitlines() if line.strip()]
            results, batches = [], []
            for start in range(0, len(documents), args.batch_size):
                batch = documents[start:start+args.batch_size]
                supported, indices, records = [], [], []
                for index, document in enumerate(batch):
                    if isinstance(document, dict) and document.get('status') == 'UNSUPPORTED':
                        records.append(dict(name=document.get('name', str(index)), status='UNSUPPORTED',
                                            reason=document.get('reason', 'exporter rejected unsupported syntax')))
                    else:
                        indices.append(index); supported.append(document); records.append(None)
                checked = check_batch(model, supported)
                for index, record in zip(indices, checked['results']):
                    records[index] = record
                results.extend(records); batches.append(checked['runtime'])
            report = dict(format='leanputer.report.v1', results=results, batches=batches,
                          model=model_statistics(model))
        report['compile_or_load_seconds'] = compilation
        report['device'] = args.device
        output = json.dumps(report, indent=2)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output+'\n')
        else:
            print(output)
        # A mixed corpus reports all categories; return 1 when any claimed
        # judgment is rejected, 2 for unsupported/resource/malformed entries.
        statuses = {r['status'] for r in report['results']}
        return 1 if 'REJECT' in statuses else 2 if statuses-{'ACCEPT'} else 0
    except (ValueError, TypeError, OSError, KeyError, RecursionError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
