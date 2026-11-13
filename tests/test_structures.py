"""Minimal structure typing smoke; final broad checks are deferred."""
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class PropositionStructureSmoke(unittest.TestCase):
    def test_projection_and_wrong_family(self):
        torch.set_num_threads(1)
        sort=['sort',0];var=lambda i:['var',i]
        both=['app',['app',['builtin','And'],var(1)],var(0)]
        wrap=lambda body:['lam',sort,['lam',sort,['lam',both,body]]]
        claim=['pi',sort,['pi',sort,['pi',both,var(2)]]]
        documents=[dict(format='leanputer.dependent.v1',term=wrap(['proj',family,0,var(0)]),claim=claim)
                   for family in ('And','Iff')]
        model=compile_machine(MachineConfig(heap=128,stack=16,context=8,constants=4,fuel=512),memory_update='attention_delta')
        self.assertEqual([r['status']for r in check_batch(model,documents)['results']],['ACCEPT','REJECT'])
