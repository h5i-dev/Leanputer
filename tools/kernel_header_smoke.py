"""Targeted stock previous-environment header-phase evidence, NOT block admission."""
import argparse
from pathlib import Path
import torch
from leanputer.kernel import source_transition as program
from leanputer.kernel.traversal_machine import MachineConfig
from tests.test_kernel_header_transition import cases
from tools.kernel_level_smoke import run_smoke


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',choices=('cpu','cuda'),default='cuda')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();torch.set_num_threads(1)
    docs=cases();cfg=MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=768,word_bits=9)
    run_smoke(cfg,[docs[i] for i in (1,2)],program,args.device,args.report,'general-inductive-headers',
        '2 general raw-block header probes: original symbolic Eq source and mutual dependent parameters/distinct index telescopes; '
        'derive private header metadata IN WEIGHTS, then GAP_INDUCTIVE for unfinished constructor/generation/restoration; '
        'NO block/source theorem admission or mathlib coverage',early_stop=True)


if __name__=='__main__':main()
