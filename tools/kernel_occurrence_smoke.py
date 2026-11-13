"""Focused composable current-family occurrence STOCK operation validation."""
import argparse
from pathlib import Path
import torch
from leanputer.kernel import occurrence_transition as program
from leanputer.kernel.traversal_machine import MachineConfig
from tests.test_kernel_occurrence_transition import cases
from tools.kernel_level_smoke import run_smoke


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',choices=('cpu','cuda'),default='cuda')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();torch.set_num_threads(1)
    docs=cases();cfg=MachineConfig(heap=64,stack=16,context=8,constants=2,fuel=64,word_bits=8)
    run_smoke(cfg,[docs[i] for i in (0,3,4,8)],program,args.device,args.report,'internal-occurrence',
        '4 composable internal symbol-set occurrence probes; early stack-delimited return, no-match literal/level/name cases and empty set; '
        'operation Boolean, NOT positivity/admission/proof acceptance',early_stop=True)


if __name__=='__main__':main()
