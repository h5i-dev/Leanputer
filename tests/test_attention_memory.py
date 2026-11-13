import dataclasses
import unittest

import torch

from leanputer.dependent_examples import conversion_cases
from leanputer.machine_spec import MachineConfig
from leanputer.memory import AddressedWrite
from leanputer.runner import check_batch, model_statistics
from leanputer.transition import compile_machine
from leanputer.validation import trace_discrepancy


torch.set_num_threads(1)


class AttentionMemoryTests(unittest.TestCase):
    def test_all_addresses_enable_bits_and_devices(self):
        rng = torch.Generator().manual_seed(841)
        for capacity in (2, 4, 16, 64, 256):
            writer = AddressedWrite(capacity, 7)
            pairs = [(address, enabled) for address in range(capacity) for enabled in (0, 1)]
            memory = torch.randint(0, 2, (len(pairs), capacity, 7), generator=rng).float()
            payload = torch.randint(0, 2, (len(pairs), 7), generator=rng).float()
            control = torch.tensor([[float(bool(address & (1 << bit))) for bit in range(writer.reader.bits)]+[float(enabled)]
                                    for address, enabled in pairs])
            expected = memory.clone()
            for i, (address, enabled) in enumerate(pairs):
                if enabled: expected[i, address] = payload[i]
            with torch.autocast('cpu', dtype=torch.bfloat16):
                self.assertTrue(torch.equal(writer(control, payload, memory), expected))
            if torch.cuda.is_available():
                writer = writer.cuda()
                with torch.autocast('cuda', dtype=torch.float16):
                    self.assertTrue(torch.equal(writer(control.cuda(), payload.cuda(), memory.cuda()).cpu(), expected))

    def test_register_controller_full_state_traces(self):
        cfg = MachineConfig(heap=64, stack=16, context=8, constants=8, fuel=512)
        model = compile_machine(cfg, memory_update='attention_delta')
        for name, term, claim, env, _ in conversion_cases():
            document = dict(format='leanputer.dependent.v1', name=name, term=term, claim=claim,
                            environment=[dataclasses.asdict(d) for d in env])
            self.assertIsNone(trace_discrepancy(model, document), name)
        self.assertLess(model.transition.input_width, model.layout.width)

    @unittest.skipUnless(torch.cuda.is_available(), 'CUDA unavailable')
    def test_cuda_graph_register_controller_trace(self):
        cfg = MachineConfig(heap=64, stack=16, context=8, constants=8, fuel=512)
        model = compile_machine(cfg, memory_update='attention_delta').cuda()
        for name, term, claim, env, _ in conversion_cases()[:2]:
            document = dict(format='leanputer.dependent.v1', name=name, term=term, claim=claim,
                            environment=[dataclasses.asdict(d) for d in env])
            self.assertIsNone(trace_discrepancy(model, document, 'cuda_graph'), name)
