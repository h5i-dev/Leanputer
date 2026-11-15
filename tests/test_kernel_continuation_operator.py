"""Tiny stock hardware protocol evidence; this does not check a Lean source."""
import importlib.util
import sys
import unittest


@unittest.skipUnless(sys.version_info >= (3, 11) and importlib.util.find_spec('transformers'), 'native stock environment')
class ContinuationOperatorTest(unittest.TestCase):
    def test_reentrant_full_frame_spill_restore_and_overflow(self):
        import torch
        from leanputer.kernel.continuation_operator import build_continuation_probe
        from leanputer.native_vendor.qwenputer.ir import A_BIT

        chip = build_continuation_probe()
        self.assertLessEqual(chip.report['logical_dense_parameters'], 48_290_654)
        words = [[depth] + [(i * 3907 + depth * 31) & 65535 for i in range(1, 28)]
                 for depth in (0, 1, 3, 1)]
        words[2][7], words[2][14], words[2][21] = 65535, 0, 32768
        bits = lambda values: [value >> bit & 1 for value in values for bit in range(16)]
        packets = torch.stack([chip.packet(frame=bits(frame), sp=bits([32 if i == 3 else 0]))
                               for i, frame in enumerate(words)])
        state = chip.embeddings(packets[:, None])
        cache = chip.new_cache()
        with torch.no_grad():
            for _ in range(7):
                out = chip.model(inputs_embeds=state, past_key_values=cache, use_cache=True,
                                 output_hidden_states=True, position_ids=torch.zeros(4, 1, dtype=torch.long),
                                 attention_mask={'full_attention': None, 'linear_attention': None})
                state = out.hidden_states[-2]  # Identity only; no host dispatch.
        logits = out.logits[:, 0].float()
        expected = [[3, 0, 1, 0], [3, 0, 1, 1], [3, 0, 1, 3], [3, 32, 2, 0]]
        self.assertTrue(torch.equal(logits, torch.tensor([bits(row) for row in expected]).float()))
        self.assertTrue(torch.equal(state[:, 0, chip.slots.groups['frame']].float(),
                                    torch.tensor([bits(frame) for frame in words]).float()))
        self.assertTrue(torch.equal(state[:, 0, chip.slots.groups['pending']], torch.zeros(4, 448)))
        memory = cache.layers[chip.report['frame_layer']].recurrent_states[0]
        for batch, depth in enumerate((0, 1, 3, 0)):
            for row in range(depth):
                expected = words[batch] if row == 0 else [depth-row] + [0]*27
                actual = torch.cat([memory[batch, page, row, 2:114] / A_BIT for page in range(4)])
                self.assertTrue(torch.equal(actual.float(), torch.tensor(bits(expected)).float()),
                                (batch, row, 'all four frame pages'))
        print(chip.report, flush=True)
