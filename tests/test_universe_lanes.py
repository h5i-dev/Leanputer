"""Packed ground universes must not alias when a lane exceeds its bound."""
from copy import deepcopy
import unittest
import torch
from leanputer.dependent import Exhausted
from leanputer.machine_spec import MachineConfig,prepare,Outcome,Reason
from leanputer.transition import compile_machine


class UniverseLaneBoundary(unittest.TestCase):
    def test_fourth_lane_and_matched_word_widths(self):
        torch.set_num_threads(1)
        self.assertEqual(MachineConfig(heap=512).primitive_bits,8)
        self.assertEqual(MachineConfig(heap=512).word_bits,11)
        self.assertEqual(MachineConfig(heap=1024).word_bits,11)
        cfg=MachineConfig(heap=32,stack=8,context=4,constants=2,fuel=32)
        model=compile_machine(cfg,memory_update='attention_delta')
        states=[]
        levels=[(0,1,2,3),(3,2,1,0),(4,1,2,3),(0,4,2,3),(0,1,4,3),(0,1,2,4)]
        for values in levels:states.append(prepare(cfg,('builtin','HAdd.rec')+values,('sort',0)))
        for field,value in [(1,1<<(3*cfg.universe_bits)),(2,1<<cfg.universe_bits)]:
            state=deepcopy(states[0]);state['heap'][1][field]=value;states.append(state)
        with torch.inference_mode():result=model(torch.cat([model.layout.encode(s)for s in states]))
        expected=[(Outcome.RUNNING,Reason.NONE)]*2+[(Outcome.RESOURCE,Reason.UNIVERSE)]*4+[(Outcome.REJECT,Reason.SYNTAX)]*2
        for bits,verdict in zip(result.tolist(),expected):
            regs=model.layout.decode(bits)['regs']
            self.assertEqual((regs['status'],regs['reason']),verdict)
        with self.assertRaises(Exhausted):
            prepare(cfg,('builtin','HAdd.rec',0,1,2,8),('sort',0))

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
