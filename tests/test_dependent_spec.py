import random
import unittest
from copy import deepcopy

from leanputer.dependent import Declaration, Oracle, Rejected
from leanputer.machine_spec import MachineConfig, Op, Outcome, Reason, SpecMachine, prepare


S0, S1 = ('sort', 0), ('sort', 1)
V0, V1 = ('var', 0), ('var', 1)
POLY_ID = ('lam', S1, ('lam', V0, V0))
POLY_TYPE = ('pi', S1, ('pi', V0, V1))
PROP_ID = ('lam', S0, ('lam', V0, V0))
PROP_TYPE = ('pi', S0, ('pi', V0, V1))


class DependentSpecificationTests(unittest.TestCase):
    def run_case(self, term, claim, declarations=(), config=None):
        cfg = config or MachineConfig()
        return SpecMachine(cfg, prepare(cfg, term, claim, declarations)).run()

    def test_dependent_and_conversion_examples(self):
        cases = [
            (POLY_ID, POLY_TYPE),
            (PROP_ID, PROP_TYPE),
            (('app', POLY_ID, S0), ('pi', S0, S0)),
            (('lam', S0, V0), ('app', ('lam', S1, V0), ('pi', S0, S0))),
        ]
        for term, claim in cases:
            self.assertTrue(Oracle().check(term, claim))
            state = self.run_case(term, claim)
            self.assertEqual(state['regs']['status'], Outcome.ACCEPT, (term, claim, state['regs']))
        # Actual ground Lean imax: forall P:Prop, P -> P inhabits Prop.
        self.assertEqual(Oracle().infer(PROP_TYPE), S0)
        self.assertEqual(Oracle().infer(POLY_TYPE), ('sort', 2))

    def test_environment_types_values_delta_and_cycles(self):
        declarations = [Declaration('T', S1, S0)]
        term = ('lam', ('const', 'T'), V0)
        claim = ('pi', S0, S0)
        self.assertTrue(Oracle(declarations).check(term, claim))
        self.assertEqual(self.run_case(term, claim, declarations)['regs']['status'], Outcome.ACCEPT)
        declarations = [Declaration('A', S1), Declaration('x', ('const', 'A')),
                        Declaration('id', POLY_TYPE, POLY_ID)]
        term = ('app', ('app', ('const', 'id'), ('const', 'A')), ('const', 'x'))
        self.assertTrue(Oracle(declarations).check(term, ('const', 'A')))
        self.assertEqual(self.run_case(term, ('const', 'A'), declarations)['regs']['status'], Outcome.ACCEPT)
        bad = [Declaration('loop', S1, ('const', 'loop'))]
        self.assertEqual(self.run_case(S0, S1, bad)['regs']['status'], Outcome.REJECT)
        bad = [Declaration('bad', S1, ('lam', S0, V0))]
        self.assertEqual(self.run_case(S0, S1, bad)['regs']['status'], Outcome.REJECT)

    def test_rejections_and_absorbing_outcomes(self):
        for term, claim in [(S0, S0), (V0, S0), (POLY_ID, PROP_TYPE),
                            (('app', S0, S0), S0), (('lam', V0, V0), S0)]:
            state = self.run_case(term, claim)
            self.assertEqual(state['regs']['status'], Outcome.REJECT, state['regs'])
            machine = SpecMachine(MachineConfig(), state)
            before = deepcopy(machine.state)
            for _ in range(5):
                machine.step()
                self.assertEqual(machine.state, before)

    def test_resources(self):
        for config, expected in [(MachineConfig(fuel=1), Reason.FUEL),
                                 (MachineConfig(stack=2), Reason.STACK),
                                 (MachineConfig(universe=1), Reason.UNIVERSE)]:
            state = self.run_case(POLY_ID, POLY_TYPE, config=config)
            self.assertEqual(state['regs']['status'], Outcome.RESOURCE, state['regs'])
            self.assertEqual(state['regs']['reason'], expected, state['regs'])
        state = self.run_case(('app', POLY_ID, S0), ('pi', S0, S0), config=MachineConfig(heap=16))
        self.assertEqual(state['regs']['status'], Outcome.RESOURCE)
        self.assertEqual(state['regs']['reason'], Reason.HEAP)

    def test_seeded_recursive_differential(self):
        rng = random.Random(8147)
        def generate(depth):
            if not depth or rng.random() < .4:
                return rng.choice([S0, S1, V0, V1])
            return (rng.choice(['lam', 'pi', 'app']), generate(depth-1), generate(depth-1))
        accepted = rejected = resource = 0
        cases = [(generate(2), rng.choice([S0, S1, PROP_TYPE, POLY_TYPE])) for _ in range(250)]
        cases += [(PROP_ID, PROP_TYPE), (POLY_ID, POLY_TYPE)] * 10
        for term, claim in cases:
            try:
                expected = Oracle().check(term, claim)
            except Rejected:
                expected = False
            state = self.run_case(term, claim)
            outcome = state['regs']['status']
            if outcome == Outcome.RESOURCE:
                resource += 1
                continue
            self.assertEqual(outcome == Outcome.ACCEPT, expected, (term, claim, state['regs']))
            accepted += int(expected); rejected += int(not expected)
        self.assertGreaterEqual(accepted, 20)
        self.assertGreater(rejected, 200)
        self.assertLess(resource, 15)

    def test_substitution_capture_and_shift(self):
        oracle = Oracle()
        # Replacing the outer binder beneath an inner lambda must shift the
        # free variable in the replacement, preserving its original scope.
        term = ('lam', S0, ('app', ('var', 1), ('var', 0)))
        self.assertEqual(oracle.substitute(term, V0), term)
        self.assertEqual(oracle.substitute(('var', 1), S0), V0)
        self.assertEqual(oracle.shift(('lam', V0, V1), 2), ('lam', ('var', 2), ('var', 3)))
        cfg = MachineConfig()
        initial = prepare(cfg, term, V0)
        initial['regs'].update(mode=int(Op.SUBST), x=initial['regs']['term'],
                               y=initial['regs']['claim'], z=0)
        machine = SpecMachine(cfg, initial)
        for _ in range(300):
            if machine.state['regs']['mode'] == Op.RET and machine.state['regs']['sp'] == 0:
                break
            machine.step()
        def decode(pointer):
            tag, a, b, v = machine.state['heap'][pointer]
            if tag in (1, 2):
                return ('var' if tag == 1 else 'sort', v)
            return ({3:'pi', 4:'lam', 5:'app'}[tag], decode(a), decode(b))
        self.assertEqual(decode(machine.state['regs']['r']), oracle.substitute(term, V0))
