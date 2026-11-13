"""Packed ground universes must not alias when a lane exceeds its bound."""
from copy import deepcopy
import unittest
import torch
from leanputer.dependent import Exhausted
from leanputer.machine_spec import MachineConfig,prepare,Outcome,Reason
from leanputer.transition import compile_machine


class UniverseLaneBoundary(unittest.TestCase):
    def test_each_lane_padding_and_unrepresentable_scalar(self):
        torch.set_num_threads(1)
        cfg=MachineConfig(heap=32,stack=8,context=4,constants=2,fuel=32)
        model=compile_machine(cfg,memory_update='attention_delta')
        states=[];expected=[]
        for levels in [(0,1,2),(1,0,3),(4,0,0),(0,4,0),(0,0,4)]:
            states.append(prepare(cfg,('builtin','PProd.rec')+levels,('sort',0)))
            expected.append((Outcome.RUNNING,Reason.NONE)if max(levels)<4 else (Outcome.RESOURCE,Reason.UNIVERSE))
        old=deepcopy(states[0]);old['heap'][1][2]=1
        states.append(old);expected.append((Outcome.REJECT,Reason.SYNTAX))
        padding=prepare(cfg,('builtin','Eq.rec',0,0),('sort',0))
        padding['heap'][1][1]=1<<(2*cfg.universe_bits)
        states.append(padding);expected.append((Outcome.REJECT,Reason.SYNTAX))
        packed=torch.cat([model.layout.encode(s)for s in states])
        with torch.inference_mode():result=model(packed)
        for bits,(status,reason)in zip(result.tolist(),expected):
            regs=model.layout.decode(bits)['regs']
            self.assertEqual((regs['status'],regs['reason']),(status,reason))
            if status==Outcome.RUNNING:self.assertEqual(regs['scan'],2)
        with self.assertRaises(Exhausted):
            prepare(cfg,('builtin','PProd.rec',8,0,0),('sort',0))
