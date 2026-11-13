"""Composed typed CORE stock smoke; NEVER full original-source admission evidence.

Inputs are raw declarations, no supplied headers/Locals/descriptors/types/check
answers. Stock weights derive all metadata through the genuine typed controller.
Original nested-source transformation and recursor generation remain unfinished.
"""
import argparse
from pathlib import Path
import torch
from leanputer.kernel import core_transition as program
from leanputer.kernel.traversal_machine import MachineConfig
from tests.test_kernel_constructor_transition import native_cases
from tools.kernel_level_smoke import run_smoke


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',choices=('cpu','cuda'),default='cuda')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();torch.set_num_threads(1)
    cfg=MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=768,word_bits=9)
    run_smoke(cfg,native_cases(),program,args.device,args.report,'typed-inductive-core',
        '2 raw CORE block operations: actual Eq header/constructor and functional recursive field; '
        'weighted scope/type/universe/positivity/recursive descriptor checks then GAP_RECURSOR_GENERATION; '
        'original-source nested staging and generation/restoration incomplete; NO declaration/theorem acceptance',early_stop=True)


if __name__=='__main__':main()
