"""Ground conversion on the same node-transition table as WHNF."""
import unittest

from leanputer.corpus import exhaustive_small
from leanputer.dependent_examples import conversion_cases
from leanputer.kernel.node_ground import check_ground, ground_table
from leanputer.kernel.node_transition import validate_table
from leanputer.machine_spec import MachineConfig, SpecMachine, prepare


CFG = MachineConfig()


def _ground(term, claim, declarations=()):
    return check_ground(
        term, claim, declarations,
        fuel=CFG.fuel, heap_cap=CFG.heap, stack_cap=CFG.stack, universe_cap=CFG.universe,
    )


def _spec_status(term, claim, declarations=()):
    state = SpecMachine(CFG, prepare(CFG, term, claim, declarations)).run()
    return state['regs']['status']


class GroundTableTests(unittest.TestCase):
    def test_corpus_outcome_class_matches_spec(self):
        accepts = []
        for doc in exhaustive_small():
            spec = _spec_status(doc['term'], doc['claim'])
            machine, report = _ground(doc['term'], doc['claim'])
            self.assertEqual(machine.regs.status, spec, doc['name'])
            self.assertEqual(report['fuel_detections'], 0, doc['name'])
            self.assertFalse(report['truncated'], doc['name'])
            if spec == 1:
                accepts.append((doc['name'], doc['term'], doc['claim'], report))
        self.assertEqual(
            [item[0] for item in accepts],
            ['exhaustive/000/1', 'exhaustive/004/1', 'exhaustive/006/0'],
        )
        # SpecMachine spends 22, 35, and 36 steps on these three. The table does not.
        self.assertEqual([item[3]['steps'] for item in accepts], [14, 23, 23])
        self.assertEqual([item[3]['fueled_rows'] for item in accepts], [14, 23, 23])

        for name, term, claim, env, expected in conversion_cases():
            spec = _spec_status(term, claim, env)
            machine, report = _ground(term, claim, env)
            self.assertEqual(machine.regs.status, spec, name)
            self.assertEqual(machine.regs.status, 1 if expected else 2, name)
            self.assertEqual(report['fuel_detections'], 0, name)
            self.assertNotIn('E-delta', [event['row'] for event in report['trace']], name)
        # Let and a non-dependent lambda are in the fragment and outside that corpus.
        for term, claim in (
            (('lam', ('sort', 0), ('var', 0)), ('pi', ('sort', 0), ('sort', 0))),
            (('let', ('sort', 1), ('sort', 0), ('var', 0)), ('sort', 1)),
            (('let', ('sort', 1), ('sort', 0), ('var', 0)), ('sort', 0)),
        ):
            machine, _report = _ground(term, claim)
            self.assertEqual(machine.regs.status, _spec_status(term, claim), (term, claim))

        machine, report = _ground(('sort', 4), ('sort', 5))
        self.assertEqual(machine.regs.status, _spec_status(('sort', 4), ('sort', 5)))
        self.assertEqual(report['trace'][-1]['cause'], 'UNIVERSE')
        # Inferring the claim Sort 4 asks for Sort 5, which is outside the cap.
        machine, _report = _ground(('sort', 3), ('sort', 4))
        self.assertEqual(machine.regs.status, _spec_status(('sort', 3), ('sort', 4)))
        machine, _report = _ground(('sort', 2), ('sort', 3))
        self.assertEqual(machine.regs.status, _spec_status(('sort', 2), ('sort', 3)))
        self.assertEqual(machine.regs.status, 1)

    def test_ground_table_budget_gate(self):
        report = validate_table(ground_table())
        self.assertEqual(report['n_rows'], 206)
        self.assertEqual(report['u_mux'], 3208)
        self.assertEqual(report['layers'], 21)
        self.assertEqual(report['control_width'], 65)
        self.assertEqual(report['residual_bits']['total'], 796)
        self.assertEqual(report['residual_bits']['estimate'], 'conservative_static')
        self.assertFalse(report['residual_bits']['stock_placement'])
        by_hidden = {shape['hidden']: shape for shape in report['shapes']}
        self.assertFalse(by_hidden[768]['channel_gate'])
        self.assertTrue(by_hidden[768]['dense_gate'])
        self.assertEqual(by_hidden[768]['logical_dense_parameters'], 28_795_224)
        self.assertEqual(by_hidden[768]['channels_needed'], 809)
        self.assertTrue(by_hidden[896]['channel_gate'])
        self.assertEqual(by_hidden[896]['logical_dense_parameters'], 33_592_792)
        self.assertEqual(report['selected_shape']['hidden'], 896)
        self.assertTrue(report['within_40_layers'])
        self.assertTrue(report['within_working_dense'])
        self.assertTrue(report['modeled_one_transition_per_forward'])
        self.assertFalse(report['stock_forward_equivalence'])
        self.assertFalse(report['weights_emitted'])
        self.assertFalse(report['gpu_measured'])
        self.assertTrue(report['original_source_requires_inductive'])
        self.assertEqual(
            report['static_checks'],
            ('bounds', 'exclusive', 'sort', 'write', 'stop', 'budget'),
        )


if __name__ == '__main__':
    unittest.main()
