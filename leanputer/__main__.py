"""Compile a fixed checker, run the demo, or check a JSON term."""
import argparse
import json
import time
from pathlib import Path

import torch

from .artifacts import load_checker, save_checker
from .checker import Config, compile_checker
from .examples import CASES, demo_config
from .terms import ResourceLimit, encode


def statistics(model, device, compile_seconds, forward_seconds):
    return dict(device=device, nodes=model.config.nodes, types=len(model.config.types),
                layers=len(model.layers), residual_width=2 * model.width,
                weight_nonzeros=sum(b._nnz() for b in model.buffers() if b.is_sparse),
                compile_or_load_seconds=compile_seconds, batch_forward_seconds=forward_seconds)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--config', type=Path, help='JSON configuration with nodes and types')
    source.add_argument('--load', type=Path, help='load and verify a fixed-weight artifact')
    parser.add_argument('--save', type=Path, help='save fixed weights and configuration')
    parser.add_argument('--check', type=Path, help='JSON object with term and claim; default runs demo')
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    try:
        if args.device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('CUDA is unavailable')
        start = time.perf_counter()
        if args.load:
            model = load_checker(args.load)
        else:
            config = Config(**json.loads(args.config.read_text())) if args.config else demo_config()
            model = compile_checker(config)
        model = model.to(args.device).eval()
        if args.device == 'cuda':
            torch.cuda.synchronize()
        compiled_seconds = time.perf_counter() - start
        if args.save:
            save_checker(model, args.save)
        if args.check:
            item = json.loads(args.check.read_text())
            if not isinstance(item, dict) or set(item) != {'term', 'claim'}:
                raise ValueError('check input must contain exactly term and claim')
            cases = [('check', item['term'], item['claim'])]
        else:
            cases = CASES + [
                ('wrong_statement', CASES[0][1], ('P', 'Q')),
                ('unbound', ('lam', 'p', 'P', ('var', 'missing')), ('P', 'P')),
                ('wrong_application', ('lam', 'p', 'P', ('app', ('var', 'p'), ('var', 'p'))), ('P', 'P')),
            ]
        try:
            bits = torch.cat([encode(model, term, claim) for _, term, claim in cases]).to(args.device)
        except ResourceLimit as error:
            if not args.check:
                raise
            print(json.dumps({'status': 'RESOURCE_LIMIT', 'reason': str(error)}))
            return 2
        with torch.inference_mode():
            if args.device == 'cuda':
                torch.cuda.synchronize()
            start = time.perf_counter()
            output = model(bits)
            if args.device == 'cuda':
                torch.cuda.synchronize()
            seconds = time.perf_counter() - start
        rows = output.cpu().tolist()
        statuses = ['ACCEPT' if r[0] == 1 else 'RESOURCE_LIMIT' if r[1] == 1 else 'REJECT' for r in rows]
        stats = statistics(model, args.device, compiled_seconds, seconds)
        if args.check:
            inferred = next((t for t, bit in zip(model.config.types, rows[0][2:]) if bit == 1), None)
            print(json.dumps(dict(status=statuses[0], inferred=inferred, stats=stats), indent=2))
            return {'ACCEPT': 0, 'REJECT': 1, 'RESOURCE_LIMIT': 2}[statuses[0]]
        for (name, _, _), status in zip(cases, statuses):
            print(f'{name}: {status}')
        print(json.dumps(stats, indent=2))
        return 0 if statuses == ['ACCEPT'] * len(CASES) + ['REJECT'] * 3 else 1
    except (ValueError, TypeError, OSError, RecursionError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
