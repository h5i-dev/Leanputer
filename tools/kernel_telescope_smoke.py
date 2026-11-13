"""Focused stock validation of shared dependent telescope operations.

Offline references diagnose every register/cache row; no answers feed inference.
DONE here is a kernel operation result, never declaration/proof acceptance.
"""
import argparse
from pathlib import Path
import torch
from leanputer.kernel import reuse_transition as program
from leanputer.kernel.traversal_machine import MachineConfig
from tests.test_kernel_telescope_reuse import cases
from tools.kernel_level_smoke import run_smoke


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',default='cuda',choices=('cpu','cuda'))
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();torch.set_num_threads(1)
    cfg=MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=384,word_bits=9)
    docs=cases()
    run_smoke(cfg,[docs[i] for i in (0,3,4,5,6,8,10)],program,args.device,args.report,'dependent-telescope',
        '7 shared telescope operation probes: empty/four-dependent-binder prefixes, raw constructor and WHNF policies, '
        'mismatch/scope/resource; no supplied Local/type/uniformity answers; NOT source declaration admission',early_stop=True)


if __name__=='__main__':main()
