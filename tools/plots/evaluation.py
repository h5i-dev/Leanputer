"""Render recorded measurements with matplotlib; no checking or relabeling."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scaling', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(args.scaling.read_text())
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), layout='constrained')
    for device, ax in zip(('cpu', 'cuda'), axes):
        rows = [r for r in records['shared'] if r['device'] == device and r['optimized']]
        for batch in sorted({r['batch'] for r in rows}):
            ordered = sorted((r for r in rows if r['batch'] == batch), key=lambda r:r['capacity'])
            ax.plot([r['capacity'] for r in ordered], [r['proofs_per_second'] for r in ordered],
                    marker='o', label=f'batch {batch}')
        ax.set(xscale='log', yscale='log', xlabel='Heap capacity (cells)', ylabel='Accepted judgments / forward second',
               title=device.upper())
        ax.grid(alpha=.2); ax.legend(fontsize=8)
    steps = sorted({r['applied_steps'] for r in records['shared']})
    fig.suptitle(f'Shared checker: replicated identity, fixed {steps} transitions')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('pdf', 'svg', 'png'):
        fig.savefig(args.output.with_suffix('.'+suffix), dpi=180)


if __name__ == '__main__': main()
