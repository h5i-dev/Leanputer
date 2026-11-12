import shutil
import subprocess
import unittest
from copy import deepcopy
from pathlib import Path

import torch

from leanputer.dependent import Declaration, Oracle
from leanputer.machine_spec import MachineConfig, Op, Outcome, SpecMachine, prepare
from leanputer.transition import compile_machine


torch.set_num_threads(1)
S0, S1 = ('sort', 0), ('sort', 1)
V0, V1 = ('var', 0), ('var', 1)
POLY_ID = ('lam', S1, ('lam', V0, V0))
POLY_TYPE = ('pi', S1, ('pi', V0, V1))


class WeightedTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = MachineConfig(heap=64, stack=16, context=8, constants=4, fuel=512)
        cls.model = compile_machine(cls.config)

    def compare_traces(self, inputs, model=None):
        model = model or self.model
        specs = [SpecMachine(model.config, state) for state in inputs]
        tensor = torch.cat([model.layout.encode(state) for state in inputs]).to(next(model.buffers()).device)
        modes, steps = set(), 0
        identity = {name: buffer.values().data_ptr() if buffer.is_sparse else buffer.data_ptr()
                    for name, buffer in model.named_buffers()}
        with torch.inference_mode():
            for index in range(model.config.fuel+1):
                modes.update(spec.state['regs']['mode'] for spec in specs if not spec.state['regs']['status'])
                expected = torch.cat([model.layout.encode(spec.step()) for spec in specs])
                tensor = model(tensor)
                if not torch.equal(tensor.cpu(), expected):
                    for row, spec in enumerate(specs):
                        actual = model.layout.decode(tensor[row].cpu().tolist())
                        if actual != spec.state:
                            differing = [bank for bank in actual if actual[bank] != spec.state[bank]]
                            self.fail(f'step={index+1} case={row} banks={differing} actual_regs={actual["regs"]} expected_regs={spec.state["regs"]}')
                steps += 1
                if all(spec.state['regs']['status'] for spec in specs):
                    break
            self.assertTrue(all(spec.state['regs']['status'] for spec in specs))
            final = tensor.clone()
            for _ in range(3):
                tensor = model(tensor)
                self.assertTrue(torch.equal(tensor, final), 'terminal state changed')
        self.assertEqual(identity, {name: buffer.values().data_ptr() if buffer.is_sparse else buffer.data_ptr()
                                    for name, buffer in model.named_buffers()})
        return specs, modes, steps

    def cases(self):
        alias = [Declaration('T', S1, S0)]
        environment = [Declaration('A', S1), Declaration('x', ('const', 'A')),
                       Declaration('id', POLY_TYPE, POLY_ID)]
        return [
            (POLY_ID, POLY_TYPE, ()),
            (('lam', S0, ('lam', V0, V0)), ('pi', S0, ('pi', V0, V1)), ()),
            (('app', POLY_ID, S0), ('pi', S0, S0), ()),
            (('lam', S0, V0), ('app', ('lam', S1, V0), ('pi', S0, S0)), ()),
            (('lam', ('const', 'T'), V0), ('pi', S0, S0), alias),
            (('app', ('app', ('const', 'id'), ('const', 'A')), ('const', 'x')), ('const', 'A'), environment),
            (('lam', S1, ('app', POLY_ID, V0)), POLY_TYPE, ()),
            (('lam', ('pi', S0, S0), V0), ('pi', ('pi', S0, S0), ('pi', S0, S0)), ()),
        ]

    def test_full_state_traces_and_weight_sharing(self):
        inputs = [prepare(self.config, term, claim, declarations) for term, claim, declarations in self.cases()]
        for term, claim, declarations in self.cases():
            self.assertTrue(Oracle(declarations).check(term, claim))
        specs, modes, steps = self.compare_traces(inputs)
        self.assertTrue(all(spec.state['regs']['status'] == Outcome.ACCEPT for spec in specs), [spec.state['regs'] for spec in specs])
        self.assertEqual(modes, set(Op), 'an operational rule lacks trace coverage')
        self.assertGreater(steps, 90)

    def test_invalid_inputs_and_resource_traces(self):
        inputs = [prepare(self.config, term, claim) for term, claim in
                  [(V0, S0), (S0, S0), (POLY_ID, ('pi', S0, ('pi', V0, V1))), (('app', S0, S0), S0)]]
        bad = prepare(self.config, POLY_ID, POLY_TYPE)
        bad['heap'][1][1] = 1
        inputs.append(bad)
        low_fuel = prepare(self.config, POLY_ID, POLY_TYPE)
        low_fuel['regs']['fuel'] = 1
        inputs.append(low_fuel)
        specs, _, _ = self.compare_traces(inputs)
        self.assertEqual([spec.state['regs']['status'] for spec in specs], [Outcome.REJECT]*5+[Outcome.RESOURCE])

    @unittest.skipUnless(torch.cuda.is_available(), 'CUDA unavailable')
    def test_cuda_full_trace_agreement(self):
        gpu = compile_machine(self.config).cuda()
        cases = self.cases()[2:5]
        inputs = [prepare(self.config, term, claim, env) for term, claim, env in cases]
        specs, _, _ = self.compare_traces(inputs, gpu)
        self.assertTrue(all(spec.state['regs']['status'] == Outcome.ACCEPT for spec in specs))

    @unittest.skipUnless(shutil.which('lean'), 'Lean unavailable')
    def test_integer_compiler_lemmas(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['lean', str(root/'proofs/Logic.lean')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertNotIn('sorryAx', result.stdout)
