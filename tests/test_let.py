"""Small let smoke, including binder traversal and an unused invalid value."""
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


def cases():
    s0,s1,v0,v1=['sort',0],['sort',1],['var',0],['var',1]
    identity=['lam',s0,v0];arrow=['pi',s0,s0]
    rows=[('let-identity',['let',arrow,identity,v0],arrow),
          ('dependent-let',['lam',s1,['lam',v0,['let',v1,v0,v0]]],['pi',s1,['pi',v0,v1]]),
          ('substitute-through-let',['app',['lam',s1,['let',s1,v0,['lam',v0,v0]]],s0],arrow),
          ('shift-through-let',['lam',s1,['lam',['let',s1,v0,v0],v0]],['pi',s1,['pi',v0,v1]]),
          ('bad-unused-let-value',['let',s0,s0,identity],arrow)]
    return [dict(format='leanputer.dependent.v1',name=n,term=t,claim=c)for n,t,c in rows]


class LetSmoke(unittest.TestCase):
    def test_typing_traversal_and_unused_annotation(self):
        torch.set_num_threads(1)
        model=compile_machine(MachineConfig(heap=128,stack=16,context=8,constants=4,fuel=512),
                              memory_update='attention_delta')
        results=check_batch(model,cases())['results']
        self.assertEqual([r['status']for r in results],['ACCEPT']*4+['REJECT'])
        self.assertEqual(results[-1]['reason'],'CONVERSION')
