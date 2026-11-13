"""Focused executable-spec / Boolean-transition correspondence.

Host reads in this test are an IR verification harness, never native inference.
Native emission uses the SAME address/rule circuits with stock cache heads.
"""
from copy import deepcopy
import unittest
from dataclasses import replace
from leanputer.bitvec import pack_words, unpack_words
from leanputer.kernel.arena import Arena, KernelError, LocalContext, Tag
from leanputer.kernel.operations import abstract, has_constant, instantiate, lift
from leanputer.kernel.reduction import BetaZeta
from leanputer.kernel.telescope import fold_telescope, open_telescope
from leanputer.kernel import traversal_machine as spec
from leanputer.kernel import traversal_transition as weighted


def cases():
    a = Arena()
    c = LocalContext(a)
    sort = a.mk(Tag.SORT, a.zero)
    local = c.fresh(sort)
    other = c.fresh(sort)
    free = a.mk(Tag.BVAR, 1)
    const = a.const(73)
    nat = a.mk(Tag.NAT, a.vec((17,)))
    string = a.mk(Tag.STRING, a.vec((67,)))
    body = a.app(a.mk(Tag.BVAR, 3), (local,))
    body = a.mk(Tag.LAM, sort, a.mk(Tag.PROJ, 29, 5, a.mk(Tag.MDATA, body, 31)), 2)
    body = a.mk(Tag.LET, sort, a.app(local, (free, nat, string)), body)
    root = a.mk(Tag.PI, const, body, 1)
    docs = [spec.document(a, root, spec.Task.LIFT, amount=2),
            spec.document(a, root, spec.Task.INSTANTIATE, (free, nat)),
            spec.document(a, root, spec.Task.ABSTRACT, (c.lookup(other).identity, c.lookup(local).identity)),
            spec.document(a, root, spec.Task.OCCURS, (29, 73)),
            spec.document(a, root, spec.Task.OCCURS, (19, 23)),
            spec.document(a, root, spec.Task.INSTANTIATE, (), start=2)]
    b = Arena()
    high = b.mk(Tag.BVAR, 255)
    docs.append(spec.document(b, high, spec.Task.LIFT, amount=1))
    # Names and list lengths are data in the same compiled transition.
    docs.append(spec.document(a, local, spec.Task.ABSTRACT, (2, 3, 4, 5, 1)))
    # Internal service calls exercise capture avoidance, zeta substitution and
    # the pending-application spine. These are the finite beta/zeta rules, not
    # names, datatype shapes or precomputed reduction answers.
    z = Arena()
    ty = z.mk(Tag.SORT, z.zero)
    b0, b1 = z.mk(Tag.BVAR, 0), z.mk(Tag.BVAR, 1)
    const = z.const(37)
    capturing = z.app(z.mk(Tag.LAM, ty, z.mk(Tag.LAM, ty, b1)), (b0,))
    docs.append(spec.document(z, capturing, spec.Task.BETA_ZETA))
    let = z.mk(Tag.LET, ty, z.mk(Tag.MDATA, const, 19),
        z.app(z.mk(Tag.LAM, ty, b0), (b0,)))
    docs.append(spec.document(z, let, spec.Task.BETA_ZETA))
    stuck = z.app(z.mk(Tag.LAM, ty, const), (z.const(41), z.const(43)))
    docs.append(spec.document(z, stuck, spec.Task.BETA_ZETA))
    z = Arena()
    ctx = LocalContext(z)
    ty = z.mk(Tag.SORT, z.level(2, z.zero))
    carrier = ctx.fresh(ty, binder_info=1)
    first = ctx.fresh(carrier)
    second = ctx.fresh(carrier, binder_info=3)
    telescope = fold_telescope(z, ctx, (carrier, first, second), carrier)
    docs.append(spec.document(z, telescope, spec.Task.OPEN_TELESCOPE))
    docs.append(spec.document(z, telescope, spec.Task.OPEN_TELESCOPE, limit=2))
    docs.append(spec.document(z, telescope, spec.Task.OPEN_TELESCOPE, limit=4))
    docs.append(spec.document(z, z.mk(Tag.BVAR, 0), spec.Task.VARIABLE_SCOPE))
    docs.append(spec.document(z, z.mk(Tag.LOCAL, 37), spec.Task.OPEN_TELESCOPE))
    for i, doc in enumerate(docs):
        doc['name'] = f'kernel-operation-{i}'
    return docs


def evaluate(plan, inputs):
    circuit, outputs = plan
    values = list(map(int, inputs))+[0]*(len(circuit.depth)-len(inputs))
    for dest, op, args in circuit.gates:
        values[dest] = int(not values[args[0]]) if op == 'not' else int(
            all(values[a] for a in args) if op == 'and' else any(values[a] for a in args))
    return [values[i] for i in outputs]


class CircuitHarness:
    def __init__(self, cfg):
        self.cfg = cfg
        self.layout = spec.StateLayout(cfg)
        self.control = spec.RegisterLayout(self.layout)
        collect = lambda circuit, outputs: (circuit, outputs)
        self.address1, self.address2 = weighted.compile_addresses(self.control, target=collect)
        self.rules = weighted.RuleCompiler(self.control).finish(target=collect)

    def step(self, state):
        cfg = self.cfg
        control = self.layout.encode(state)[0, :self.control.width].tolist()
        first_query = evaluate(self.address1, control)
        addresses = unpack_words(first_query, [cfg.heap.bit_length()-1, cfg.stack.bit_length()-1])
        first = pack_words(state['heap'][addresses[0]]+state['stack'][addresses[1]], [cfg.word_bits]*10)
        operand = unpack_words(evaluate(self.address2, control+first), [cfg.context.bit_length()-1])[0]
        bits = evaluate(self.rules, control+first+pack_words(state['context'][operand], [cfg.word_bits]))
        state = deepcopy(state)
        state['regs'] = dict(zip(spec.REGISTERS, unpack_words(bits[:self.control.width], [w for _, w in self.control.fields])))
        offset = self.control.width
        for bank, fields in (('heap', 4), ('stack', 6), ('context', 1)):
            widths = [getattr(cfg, bank).bit_length()-1, 1]+[cfg.word_bits]*fields
            words = unpack_words(bits[offset:offset+sum(widths)], widths)
            offset += sum(widths)
            if words[1]:
                state[bank][words[0]] = words[2:]
        self.assert_length = offset == len(bits)
        return state


def canonical_heap(state, original, local_replacements=None):
    """Posthoc structural decoding, never used by prepare or a transition."""
    mapping = {0: 0}
    local_replacements = local_replacements or {}
    for i in range(1, state['regs']['free']):
        tag, a, b, c = state['heap'][i]
        if tag == spec.LOCAL_DECL_TAG:
            mapping[i] = None
            continue
        if tag == Tag.LOCAL and a in local_replacements:
            mapping[i] = local_replacements[a]
            continue
        if tag in (Tag.APP, Tag.PI, Tag.LAM):
            a, b = mapping[a], mapping[b]
        elif tag == Tag.LET:
            a, b, c = mapping[a], mapping[b], mapping[c]
        elif tag == Tag.PROJ:
            c = mapping[c]
        elif tag == Tag.MDATA:
            a = mapping[a]
        mapping[i] = original.mk(tag, a, b, c)
    return mapping


def canonical_result(state, original):
    return canonical_heap(state, original)[state['regs']['r']]


class TraversalTransitionTest(unittest.TestCase):
    def test_general_walk_exact_states_and_operation_results(self):
        cfg = spec.MachineConfig(heap=64, stack=16, context=8, constants=2, fuel=256, word_bits=8)
        circuit = CircuitHarness(cfg)
        for doc in cases():
            parsed = spec.parse_document(doc)
            state = spec.prepare(cfg, *parsed)
            machine = spec.SpecMachine(cfg, state)
            for step in range(cfg.fuel+2):
                actual = circuit.step(state)
                expected = machine.step()
                self.assertEqual(actual, expected, (doc['name'], step))
                state = actual
                if state['regs']['status']:
                    self.assertEqual(circuit.step(state), state, 'halt must be absorbing')
                    break
            a, root = parsed[0]['arena'], doc['root']
            # Parser arena is deliberately input-sized. Reference transforms
            # allocate outputs only in this posthoc verification arena.
            a.limits = replace(a.limits, expressions=cfg.heap*2, vector_cells=4096)
            status = state['regs']['status']
            failures = {6: (spec.Outcome.RESOURCE, spec.Reason.INDEX),
                13: (spec.Outcome.INVALID, spec.Reason.EXPECT_PI),
                14: (spec.Outcome.INVALID, spec.Reason.SCOPE),
                15: (spec.Outcome.INVALID, spec.Reason.SCOPE)}
            index = int(doc['name'].rsplit('-', 1)[-1])
            if index in failures:
                self.assertEqual((status, state['regs']['reason']), failures[index])
                continue
            self.assertEqual(status, spec.Outcome.DONE)
            task = spec.Task[doc['task']]
            if task == spec.Task.OCCURS:
                self.assertEqual(bool(state['regs']['found']), has_constant(a, root, doc['operands']))
            elif task == spec.Task.OPEN_TELESCOPE:
                context = LocalContext(a)
                opened = open_telescope(a, context, root, lambda ref: ref, count=doc.get('limit'))
                self.assertEqual(state['regs']['ctx'], len(opened.locals))
                replacements = {}
                records = [state['heap'][state['context'][i][0]] for i in range(state['regs']['ctx'])]
                for record, local in zip(records, opened.locals):
                    self.assertEqual(record[0], spec.LOCAL_DECL_TAG)
                    native_local = state['heap'][record[1]]
                    self.assertEqual(native_local[0], Tag.LOCAL)
                    replacements[native_local[1]] = local
                mapping = canonical_heap(state, a, replacements)
                self.assertEqual(mapping[state['regs']['r']], opened.body)
                for record, local in zip(records, opened.locals):
                    self.assertEqual(mapping[record[2]], context.lookup(local).type)
                    self.assertEqual(record[3], context.lookup(local).binder_info)
            else:
                if task == spec.Task.LIFT:
                    expected = lift(a, root, doc.get('amount', 0), doc.get('cutoff', 0))
                elif task == spec.Task.INSTANTIATE:
                    expected = instantiate(a, root, doc['operands'], doc.get('start', 0))
                elif task == spec.Task.ABSTRACT:
                    locals_ = tuple(a.mk(Tag.LOCAL, uid) for uid in doc['operands'])
                    expected = abstract(a, root, locals_)
                else:
                    expected = BetaZeta(a, LocalContext(a))(root)
                self.assertEqual(canonical_result(state, a), expected)
            self.assertEqual(state['regs']['sp'], 0)
        self.assertTrue(circuit.assert_length)

    def test_telescope_physical_context_and_fuel_bounds(self):
        cfg = spec.MachineConfig(heap=64, stack=16, context=8, constants=2, fuel=512, word_bits=8)
        a = Arena()
        ty = a.mk(Tag.SORT, a.zero)
        root = ty
        for _ in range(9):
            root = a.mk(Tag.PI, ty, root)
        doc = spec.document(a, root, spec.Task.OPEN_TELESCOPE)
        for capacity, expected in ((cfg, spec.Reason.CONTEXT), (replace(cfg, fuel=1), spec.Reason.FUEL)):
            state = spec.prepare(capacity, *spec.parse_document(doc))
            machine = spec.SpecMachine(capacity, state)
            circuit = CircuitHarness(capacity)
            for step in range(capacity.fuel+2):
                actual = circuit.step(state)
                self.assertEqual(actual, machine.step(), (expected, step))
                state = actual
                if state['regs']['status']:
                    break
            self.assertEqual((state['regs']['status'], state['regs']['reason']), (spec.Outcome.RESOURCE, expected))
            self.assertEqual(circuit.step(state), state)
        # Internal substitution calls are inaccessible to raw operation input.
        internal = spec.document(a, root, spec.Task.INSTANTIATE_ONE)
        with self.assertRaises(KernelError):
            spec.parse_document(internal)


if __name__ == '__main__':
    unittest.main()
