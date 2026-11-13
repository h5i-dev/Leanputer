"""Small empty-datatype smoke; broad differential release checks are deferred."""
import unittest
import torch
from leanputer.machine_spec import MachineConfig
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


class EmptyPropositionSmoke(unittest.TestCase):
    def test_primitive_type_eliminator_and_false_claim(self):
        torch.set_num_threads(1)
        false=['builtin','False']
        rec=['builtin','False.rec',1]
        rec_type=['pi',['pi',false,['sort',1]],['pi',false,['app',['var',1],['var',0]]]]
        true=['builtin','True'];intro=['builtin','True.intro']
        documents=[dict(format='leanputer.dependent.v1',term=false,claim=['sort',0]),
                   dict(format='leanputer.dependent.v1',term=rec,claim=rec_type),
                   dict(format='leanputer.dependent.v1',term=['sort',0],claim=false),
                   dict(format='leanputer.dependent.v1',term=true,claim=['sort',0]),
                   dict(format='leanputer.dependent.v1',term=intro,claim=true),
                   dict(format='leanputer.dependent.v1',term=['sort',0],claim=true)]
        model=compile_machine(MachineConfig(heap=64,stack=16,context=8,constants=4,fuel=256),memory_update='attention_delta')
        self.assertEqual([r['status']for r in check_batch(model,documents)['results']],['ACCEPT','ACCEPT','REJECT','ACCEPT','ACCEPT','REJECT'])
