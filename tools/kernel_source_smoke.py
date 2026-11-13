"""Targeted DEVELOPMENT stock source-transaction validation, not production CLI.

Offline references are diagnostics only and never supply model answers. The
production inference API is NativeMachine.check with source_transition program.
"""
import argparse
from pathlib import Path
import torch
from leanputer.kernel import source_transition as program
from leanputer.kernel.traversal_machine import MachineConfig
from tests.test_kernel_source_transition import cases
from tools.kernel_level_smoke import run_smoke


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',default='cuda',choices=('cpu','cuda'))
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--early-stop',action='store_true',help='observe only native completion flags and flush once')
    args=parser.parse_args()
    torch.set_num_threads(1)
    cfg=MachineConfig(heap=256,stack=16,context=8,constants=4,fuel=512,word_bits=9)
    docs=cases()
    run_smoke(cfg,docs,program,args.device,args.report,'source-transactions',
        '15 source declaration transaction probes; checked private environment, original schemes and body checking; '
        'missing general inductive/recursor/primitive/full-conversion services GAP; not full Lean or mathlib coverage',
        early_stop=args.early_stop)


if __name__=='__main__':main()
