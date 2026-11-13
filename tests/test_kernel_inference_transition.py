"""Focused contracts for generic typed inference's shared stock controller.

Complete inference/admission is unfinished. Callbacks without implementations
must produce GAP, never accept a supplied inferred type or pretend false.
"""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from leanputer.kernel.arena import KernelError, LocalContext
from leanputer.kernel.services import KernelServices
from leanputer.kernel import level_transition as program
from leanputer.kernel import traversal_machine as spec
from tests.test_kernel_traversal_machine import CircuitHarness
from tests.test_kernel_native_cells import decode_syntax


def name(value): return [{'str': value}]


def cases():
    u, z = ['param', name('u')], ['zero']
    prop, type0 = ['sort', z], ['sort', ['succ', z]]
    original = json.loads((Path(__file__).parent/'fixtures/kernel-source-smoke.jsonl').read_text().splitlines()[0])
    def source(expr):
        return dict(format='leanputer.kernel-source.v1', status='EXPORTED', declarations=[],
            target=dict(kind='definition', name=name('inference'), level_params=[name('u')], type=expr, value=None))
    docs = [dict(format='leanputer.kernel-data-operation.v1', operation='infer',
                 name='inference-original-id-'+root, source=original, root=root) for root in ('type', 'value')]
    shadow = ['lam', 0, ['sort', u], ['lam', 0, ['var', 0], ['lam', 0, ['var', 1], ['var', 1]]]]
    probes = [
        ('sort', ['sort', u]), ('shadow', shadow),
        ('application', ['app', ['lam', 0, type0, ['var', 0]], prop]),
        ('bad-argument', ['app', ['lam', 0, prop, ['var', 0]], prop]),
        ('let', ['let', type0, prop, ['var', 0]]),
        ('bad-let', ['let', prop, prop, ['var', 0]]),
        ('non-type-domain', ['pi', 0, ['lam', 0, prop, ['var', 0]], prop]),
        ('metadata', ['mdata', ['sort', u]]),
        ('environment-gap', ['const', name('f'), []]),
        ('projection-gap', ['proj', name('R'), 0, prop]),
        ('natural-gap', ['nat', '1']), ('string-gap', ['string', 't']),
        ('free-local', ['local', 31]), ('free-variable', ['var', 0])]
    docs += [dict(format='leanputer.kernel-data-operation.v1', operation='infer',
                  name='inference-'+label, source=source(expr)) for label, expr in probes]
    raw = source(['const', name('f'), []])
    raw['declarations'] = [dict(kind='axiom', name=name('f'), level_params=[], type=prop, value=None)]
    docs.append(dict(format='leanputer.kernel-data-operation.v1', operation='infer',
                     name='inference-raw-signature-not-admitted', source=raw))
    return docs


class InferenceTransitionTest(unittest.TestCase):
    def test_generic_inference_uses_private_typed_scope_and_shared_services(self):
        cfg = spec.MachineConfig(heap=128, stack=16, context=8, constants=2, fuel=160, word_bits=8)
        circuit = CircuitHarness(cfg)
        expected = [('DONE', 'NONE'), ('DONE', 'NONE'), ('DONE', 'NONE'), ('DONE', 'NONE'),
            ('DONE', 'NONE'), ('INVALID', 'TYPE_MISMATCH'), ('DONE', 'NONE'), ('INVALID', 'TYPE_MISMATCH'),
            ('INVALID', 'EXPECT_SORT'), ('DONE', 'NONE'), ('GAP', 'GAP_ENVIRONMENT'), ('GAP', 'GAP_PROJECTION'),
            ('GAP', 'GAP_PRIMITIVE'), ('GAP', 'GAP_PRIMITIVE'), ('INVALID', 'SCOPE'), ('INVALID', 'SCOPE'),
            ('GAP', 'GAP_ENVIRONMENT')]
        for doc, want in zip(cases(), expected):
            source, arguments, declarations = program.parse_document(doc)
            state = program.prepare(cfg, source, arguments, declarations)
            self.assertEqual(state['regs']['task'], spec.Task.EXPR_SCOPE)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (doc['name'], step))
                state = actual
                if state['regs']['status']: break
            got = (spec.Outcome(state['regs']['status']).name, spec.Reason(state['regs']['reason']).name)
            self.assertEqual(got, want, (doc['name'], state['regs']))
            root = source.target.value if arguments['root'] == 'value' else source.target.type
            services = KernelServices(source.arena, LocalContext(source.arena))
            if want[0] == 'DONE':
                _, decoded = decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]), source.arena)
                expected_type = services.infer(root)
                self.assertTrue(services.convert(decoded[state['regs']['r']], expected_type), doc['name'])
                self.assertEqual(state['regs']['ctx'], len(source.target.universe_parameters))
                self.assertEqual(state['regs']['sp'], 0)
            elif want[0] == 'INVALID':
                with self.assertRaises(KernelError): services.infer(root)
            # GAP cases deliberately do NOT take a raw signature's type as an
            # inferred result. Even supplied raw axiom syntax needs admission.
            self.assertEqual(circuit.step(state), state)

    def test_physical_inference_exhaustion_is_absorbing_resource(self):
        doc = cases()[3]  # Generic nested dependent binders, no count dispatch.
        configs = [(dict(stack=2, context=8, fuel=256), 'STACK'),
                   (dict(stack=16, context=2, fuel=256), 'CONTEXT'),
                   (dict(stack=16, context=8, fuel=3), 'FUEL')]
        for capacities, reason in configs:
            cfg = spec.MachineConfig(heap=128, constants=2, word_bits=8, **capacities)
            state = program.prepare(cfg, *program.parse_document(doc))
            circuit, machine = CircuitHarness(cfg), spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (reason, step))
                state = actual
                if state['regs']['status']: break
            self.assertEqual((state['regs']['status'], state['regs']['reason']),
                             (spec.Outcome.RESOURCE, getattr(spec.Reason, reason)))
            self.assertEqual(circuit.step(state), state)


if __name__ == '__main__': unittest.main()
