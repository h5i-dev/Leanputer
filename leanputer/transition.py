"""Compile bounded dependent-checker transitions into shared fixed weights.

Python branches in the compiler depend only on configuration and rule tags.
Runtime forward passes do addressed attention and fixed Boolean FFNs. There is
no runtime dispatch to the operational or recursive reference implementations.
"""
import torch
from torch import nn

from .bitvec import Builder
from .machine_spec import FRAME_FIELDS, HEAP_FIELDS, MachineConfig, Op, Outcome, Reason
from .memory import AddressedRead
from .state_layout import StateLayout
from .dependent import Tag


PORTS = [('hx', HEAP_FIELDS), ('hy', HEAP_FIELDS), ('hr', HEAP_FIELDS), ('hs', HEAP_FIELDS),
         ('back', FRAME_FIELDS), ('declrow', ('kind', 'type', 'value')),
         ('lookup', ('type',)), ('constant', ('kind', 'type', 'value'))]


def port_names(width, ports):
    return [f'read/{port}/{field}/{i}' for port, fields in ports for field in fields for i in range(width)]


def state_words(builder, layout):
    return {name: tuple(builder.inputs[layout.slices[name]]) for name, _ in layout.fields}


def compile_addresses(layout):
    cfg, width = layout.config, layout.config.word_bits
    first = Builder(layout.names)
    r = state_words(first, layout)
    outputs = []
    for name in ('x', 'y', 'r', 'scan'):
        outputs.extend(r[name][:cfg.heap.bit_length()-1])
    outputs.extend(first.sub(r['sp'], first.const(1, width))[0][:cfg.stack.bit_length()-1])
    outputs.extend(r['decl'][:cfg.constants.bit_length()-1])
    address1 = first.compile(outputs)
    names1 = port_names(width, PORTS[:6])
    second = Builder(layout.names + names1)
    r = state_words(second, layout)
    v_start = len(layout.names) + 3*width  # hx/v
    index = tuple(second.inputs[v_start:v_start+width])
    before = second.sub(r['ctx'], second.const(1, width))[0]
    index = second.sub(before, index)[0]
    outputs = list(index[:cfg.context.bit_length()-1])
    outputs += list(second.inputs[v_start:v_start+cfg.constants.bit_length()-1])
    return address1, second.compile(outputs)


class RuleCompiler:
    def __init__(self, layout):
        self.layout, self.cfg = layout, layout.config
        self.width = self.cfg.word_bits
        self.g = Builder(layout.names + port_names(self.width, PORTS))
        self.c = self.g.c
        self.old = state_words(self.g, layout)
        self.r = {name: self.old[name] for name in self.old if '/' not in name}
        self.choices = {name: [] for name in self.old}
        self.writes = {'heap': [], 'stack': [], 'context': []}
        offset = layout.width
        self.read = {}
        for port, fields in PORTS:
            self.read[port] = {}
            for field in fields:
                self.read[port][field] = tuple(self.g.inputs[offset:offset+self.width])
                offset += self.width
        self.hx, self.hy, self.hr, self.hs = (self.read[p] for p in ('hx', 'hy', 'hr', 'hs'))
        self.running = self.eq(self.r['status'], 0)
        fuel = self.r['fuel']
        self.active = self.AND(self.running, self.NOT(self.eq(fuel, 0)))
        self.emit(self.AND(self.running, self.eq(fuel, 0)), status=Outcome.RESOURCE, reason=Reason.FUEL)
        self.choices['fuel'].append((self.active, self.g.sub(fuel, self.g.const(1, len(fuel)))[0]))
        bad = self.OR(self.eq(self.r['free'], 0), self.lt(self.cfg.heap, self.r['free']),
                      self.lt(self.cfg.stack, self.r['sp']), self.lt(self.cfg.context, self.r['ctx']),
                      self.lt(self.r['decl_count'], self.r['decl']), self.lt(self.cfg.constants, self.r['decl_count']))
        needs_x = (Op.INFER, Op.I_BIND, Op.WHNF, Op.W_APP, Op.SHIFT, Op.SUBST,
                   Op.TREE_LEFT, Op.TREE_RIGHT, Op.CONV, Op.C_RIGHT)
        needs_r = (Op.VALUE, Op.ROOT_TERM, Op.I_BIND, Op.I_SORT, Op.I_FUN, Op.W_APP, Op.C_RIGHT)
        for value, modes in ((self.r['x'], needs_x), (self.r['r'], needs_r), (self.r['y'], (Op.CONV,))):
            required = self.OR(*(self.eq(self.r['mode'], op) for op in modes))
            invalid = self.OR(self.eq(value, 0), self.NOT(self.lt(value, self.r['free'])))
            bad = self.OR(bad, self.AND(required, invalid))
        self.stop(self.AND(self.active, bad), Outcome.REJECT, Reason.SYNTAX)
        self.active = self.AND(self.active, self.NOT(bad))

    def vec(self, value, width=None):
        return self.g.const(int(value), width or self.width) if isinstance(value, int) else value

    def AND(self, *bits): return self.c.AND(*bits)
    def OR(self, *bits): return self.c.OR(*bits)
    def NOT(self, bit): return self.c.NOT(bit)
    def eq(self, x, y): return self.g.eq(self.vec(x), self.vec(y))
    def lt(self, x, y): return self.g.lt(self.vec(x), self.vec(y))
    def add(self, x, y): return self.g.add(self.vec(x), self.vec(y))
    def sub(self, x, y): return self.g.sub(self.vec(x), self.vec(y))[0]
    def mux(self, bit, x, y): return self.g.mux(bit, self.vec(x), self.vec(y))
    def mode(self, op): return self.AND(self.active, self.eq(self.r['mode'], op))
    def tag(self, node, *tags): return self.OR(*(self.eq(node['tag'], t) for t in tags))

    def emit(self, condition, **updates):
        for name, value in updates.items():
            value = self.vec(value, len(self.old[name]))
            self.choices[name].append((condition, value))

    def stop(self, condition, status, reason=Reason.NONE):
        self.emit(condition, status=status, reason=reason)

    def tail(self, condition, op, x=0, y=0, z=0, w=0):
        self.emit(condition, mode=op, x=x, y=y, z=z, w=w)

    def ret(self, condition, result):
        self.emit(condition, mode=Op.RET, r=result)

    def call(self, condition, op, x, y=0, z=0, w=0, continuation=(), context=None):
        available = self.lt(self.r['sp'], self.cfg.stack)
        self.stop(self.AND(condition, self.NOT(available)), Outcome.RESOURCE, Reason.STACK)
        good = self.AND(condition, available)
        frame = [self.vec(v) for v in continuation]
        frame += [self.vec(0)] * (5-len(frame))
        frame.append(self.r['ctx'])
        self.writes['stack'].append((good, self.r['sp'], frame))
        self.emit(good, sp=self.add(self.r['sp'], 1))
        self.tail(good, op, x, y, z, w)
        if context is not None:
            self.emit(good, ctx=context)

    def allocate(self, condition, tag, a=0, b=0, v=0, overflow=None):
        available = self.lt(self.r['free'], self.cfg.heap)
        self.stop(self.AND(condition, self.NOT(available)), Outcome.RESOURCE, Reason.HEAP)
        good = self.AND(condition, available)
        if overflow is not None:
            self.stop(self.AND(good, overflow), Outcome.RESOURCE, Reason.INDEX)
            good = self.AND(good, self.NOT(overflow))
        self.writes['heap'].append((good, self.r['free'], [self.vec(t) for t in (tag, a, b, v)]))
        self.emit(good, free=self.add(self.r['free'], 1))
        self.ret(good, self.r['free'])

    def rules(self):
        r, hx, hr, hs = self.r, self.hx, self.hr, self.hs
        x, y, z, w, result = (r[k] for k in ('x', 'y', 'z', 'w', 'r'))
        # Initial syntax and topological validation, before any inference.
        op = self.mode(Op.VALIDATE)
        more = self.lt(r['scan'], r['free'])
        self.tail(self.AND(op, self.NOT(more)), Op.ENV)
        binary = self.tag(hs, Tag.PI, Tag.LAM, Tag.APP)
        atomic = self.tag(hs, Tag.VAR, Tag.SORT, Tag.CONST)
        children = self.AND(self.NOT(self.eq(hs['a'], 0)), self.lt(hs['a'], r['scan']),
                            self.NOT(self.eq(hs['b'], 0)), self.lt(hs['b'], r['scan']), self.eq(hs['v'], 0))
        atom_ok = self.AND(self.eq(hs['a'], 0), self.eq(hs['b'], 0),
                           self.OR(self.NOT(self.tag(hs, Tag.CONST)), self.lt(hs['v'], r['decl_count'])))
        valid = self.OR(self.AND(binary, children), self.AND(atomic, atom_ok))
        check = self.AND(op, more)
        self.stop(self.AND(check, self.NOT(valid)), Outcome.REJECT, Reason.SYNTAX)
        high = self.AND(self.tag(hs, Tag.SORT), self.lt(self.cfg.universe, hs['v']))
        self.stop(self.AND(check, valid, high), Outcome.RESOURCE, Reason.UNIVERSE)
        self.emit(self.AND(check, valid, self.NOT(high)), scan=self.add(r['scan'], 1))
        # Environment and root-check orchestration.
        op = self.mode(Op.ENV)
        done = self.eq(r['decl'], r['decl_count'])
        self.call(self.AND(op, done), Op.INFER, r['claim'], continuation=(Op.ROOT_TYPE,))
        row = self.read['declrow']
        kind_ok = self.OR(self.eq(row['kind'], 0), self.eq(row['kind'], 1))
        type_ok = self.AND(self.NOT(self.eq(row['type'], 0)), self.lt(row['type'], r['free']))
        value_ok = self.OR(self.eq(row['kind'], 0), self.AND(self.NOT(self.eq(row['value'], 0)), self.lt(row['value'], r['free'])))
        valid = self.AND(kind_ok, type_ok, value_ok)
        self.stop(self.AND(op, self.NOT(done), self.NOT(valid)), Outcome.REJECT, Reason.SYNTAX)
        self.call(self.AND(op, self.NOT(done), valid), Op.INFER, row['type'],
                  continuation=(Op.TYPE, row['type'], row['value'], row['kind']))
        self.call(self.mode(Op.TYPE), Op.WHNF, result, continuation=(Op.VALUE, x, y, z))
        self.call(self.mode(Op.ROOT_TYPE), Op.WHNF, result, continuation=(Op.ROOT_TERM,))
        for operation in (Op.VALUE, Op.ROOT_TERM):
            op = self.mode(operation)
            is_sort = self.tag(hr, Tag.SORT)
            self.stop(self.AND(op, self.NOT(is_sort)), Outcome.REJECT, Reason.EXPECT_SORT)
            if operation == Op.ROOT_TERM:
                self.call(self.AND(op, is_sort), Op.INFER, r['term'], continuation=(Op.ROOT_EQ,))
            else:
                axiom = self.eq(z, 0)
                cond = self.AND(op, is_sort, axiom)
                self.emit(cond, decl=self.add(r['decl'], 1)); self.tail(cond, Op.ENV)
                self.call(self.AND(op, is_sort, self.NOT(axiom)), Op.INFER, y, continuation=(Op.COMMIT, x))
        self.call(self.mode(Op.COMMIT), Op.CONV, result, x, continuation=(Op.ENV_EQ,))
        self.call(self.mode(Op.ROOT_EQ), Op.CONV, result, r['claim'], continuation=(Op.FINISH,))
        for operation in (Op.ENV_EQ, Op.FINISH):
            op, success = self.mode(operation), self.NOT(self.eq(result, 0))
            self.stop(self.AND(op, self.NOT(success)), Outcome.REJECT, Reason.CONVERSION)
            if operation == Op.FINISH:
                self.stop(self.AND(op, success), Outcome.ACCEPT)
            else:
                cond = self.AND(op, success)
                self.emit(cond, decl=self.add(r['decl'], 1)); self.tail(cond, Op.ENV)
        # Return restores the explicit continuation, including context depth.
        op = self.mode(Op.RET)
        empty = self.eq(r['sp'], 0)
        self.stop(self.AND(op, empty), Outcome.REJECT, Reason.INTERNAL)
        cond = self.AND(op, self.NOT(empty))
        self.emit(cond, sp=self.sub(r['sp'], 1), **self.read['back'])
        # Inference.
        op = self.mode(Op.INFER)
        var = self.AND(op, self.tag(hx, Tag.VAR))
        bound = self.lt(hx['v'], r['ctx'])
        self.stop(self.AND(var, self.NOT(bound)), Outcome.REJECT, Reason.UNBOUND)
        self.tail(self.AND(var, bound), Op.SHIFT, self.read['lookup']['type'], 0, self.add(hx['v'], 1))
        sort = self.AND(op, self.tag(hx, Tag.SORT))
        level_ok = self.lt(hx['v'], self.cfg.universe)
        self.stop(self.AND(sort, self.NOT(level_ok)), Outcome.RESOURCE, Reason.UNIVERSE)
        self.allocate(self.AND(sort, level_ok), Tag.SORT, v=self.add(hx['v'], 1))
        self.call(self.AND(op, self.tag(hx, Tag.LAM, Tag.PI)), Op.INFER, hx['a'], continuation=(Op.I_DOM, x))
        self.call(self.AND(op, self.tag(hx, Tag.APP)), Op.INFER, hx['a'], continuation=(Op.I_APP, hx['b']))
        const = self.AND(op, self.tag(hx, Tag.CONST), self.lt(hx['v'], r['decl']))
        self.ret(const, self.read['constant']['type'])
        legal = self.OR(self.tag(hx, Tag.VAR, Tag.SORT, Tag.PI, Tag.LAM, Tag.APP),
                        self.AND(self.tag(hx, Tag.CONST), self.lt(hx['v'], r['decl'])))
        self.stop(self.AND(op, self.NOT(legal)), Outcome.REJECT, Reason.SYNTAX)
        self.call(self.mode(Op.I_DOM), Op.WHNF, result, continuation=(Op.I_BIND, x))
        op, is_sort = self.mode(Op.I_BIND), self.tag(hr, Tag.SORT)
        self.stop(self.AND(op, self.NOT(is_sort)), Outcome.REJECT, Reason.EXPECT_SORT)
        room = self.lt(r['ctx'], self.cfg.context)
        self.stop(self.AND(op, is_sort, self.NOT(room)), Outcome.RESOURCE, Reason.CONTEXT)
        cond = self.AND(op, is_sort, room)
        self.writes['context'].append((cond, r['ctx'], [hx['a']]))
        lam = self.tag(hx, Tag.LAM)
        self.call(self.AND(cond, lam), Op.INFER, hx['b'], continuation=(Op.I_LAM, hx['a']), context=self.add(r['ctx'], 1))
        self.call(self.AND(cond, self.NOT(lam)), Op.INFER, hx['b'], continuation=(Op.I_PI, hr['v']), context=self.add(r['ctx'], 1))
        self.allocate(self.mode(Op.I_LAM), Tag.PI, x, result)
        self.call(self.mode(Op.I_PI), Op.WHNF, result, continuation=(Op.I_SORT, x))
        op, is_sort = self.mode(Op.I_SORT), self.tag(hr, Tag.SORT)
        self.stop(self.AND(op, self.NOT(is_sort)), Outcome.REJECT, Reason.EXPECT_SORT)
        maximum = self.mux(self.lt(x, hr['v']), hr['v'], x)
        universe = self.mux(self.eq(hr['v'], 0), 0, maximum)
        self.allocate(self.AND(op, is_sort), Tag.SORT, v=universe)
        self.call(self.mode(Op.I_APP), Op.WHNF, result, continuation=(Op.I_FUN, x))
        op, is_pi = self.mode(Op.I_FUN), self.tag(hr, Tag.PI)
        self.stop(self.AND(op, self.NOT(is_pi)), Outcome.REJECT, Reason.EXPECT_PI)
        self.call(self.AND(op, is_pi), Op.INFER, x, continuation=(Op.I_ARG, hr['a'], hr['b'], x))
        self.call(self.mode(Op.I_ARG), Op.CONV, x, result, continuation=(Op.I_CHECK, y, z))
        op, good = self.mode(Op.I_CHECK), self.NOT(self.eq(result, 0))
        self.stop(self.AND(op, self.NOT(good)), Outcome.REJECT, Reason.CONVERSION)
        self.tail(self.AND(op, good), Op.SUBST, x, y)
        # WHNF, delta unfolding and beta substitution.
        op = self.mode(Op.WHNF)
        self.call(self.AND(op, self.tag(hx, Tag.APP)), Op.WHNF, hx['a'], continuation=(Op.W_APP, x, hx['b']))
        const = self.AND(op, self.tag(hx, Tag.CONST))
        available = self.lt(hx['v'], r['decl'])
        self.stop(self.AND(const, self.NOT(available)), Outcome.REJECT, Reason.SYNTAX)
        definition = self.NOT(self.eq(self.read['constant']['kind'], 0))
        self.tail(self.AND(const, available, definition), Op.WHNF, self.read['constant']['value'])
        self.ret(self.AND(const, available, self.NOT(definition)), x)
        self.ret(self.AND(op, self.tag(hx, Tag.VAR, Tag.SORT, Tag.PI, Tag.LAM)), x)
        self.stop(self.AND(op, self.NOT(self.tag(hx, Tag.VAR, Tag.SORT, Tag.PI, Tag.LAM, Tag.APP, Tag.CONST))), Outcome.REJECT, Reason.SYNTAX)
        op, lam = self.mode(Op.W_APP), self.tag(hr, Tag.LAM)
        self.call(self.AND(op, lam), Op.SUBST, hr['b'], y, continuation=(Op.W_BETA,))
        same = self.eq(result, hx['a'])
        self.ret(self.AND(op, self.NOT(lam), same), x)
        self.allocate(self.AND(op, self.NOT(lam), self.NOT(same)), Tag.APP, result, y)
        self.tail(self.mode(Op.W_BETA), Op.WHNF, result)
        # Capture-avoiding structural shift/substitution with explicit frames.
        for operation in (Op.SHIFT, Op.SUBST):
            op = self.mode(operation)
            trivial = self.tag(hx, Tag.SORT, Tag.CONST)
            if operation == Op.SHIFT:
                trivial = self.OR(trivial, self.eq(z, 0))
            self.ret(self.AND(op, trivial), x)
            work = self.AND(op, self.NOT(trivial))
            var = self.AND(work, self.tag(hx, Tag.VAR))
            if operation == Op.SHIFT:
                unchanged = self.lt(hx['v'], y)
                self.ret(self.AND(var, unchanged), x)
                total = self.add(hx['v'], z)
                self.allocate(self.AND(var, self.NOT(unchanged)), Tag.VAR, v=total, overflow=self.lt(total, hx['v']))
            else:
                below, equal = self.lt(hx['v'], z), self.eq(hx['v'], z)
                self.ret(self.AND(var, below), x)
                self.tail(self.AND(var, equal), Op.SHIFT, y, 0, z)
                self.allocate(self.AND(var, self.NOT(below), self.NOT(equal)), Tag.VAR, v=self.sub(hx['v'], 1))
            tree = self.tag(hx, Tag.PI, Tag.LAM, Tag.APP)
            self.call(self.AND(work, tree), operation, hx['a'], y, z,
                      continuation=(Op.TREE_LEFT, x, y, z, operation))
            self.stop(self.AND(work, self.NOT(self.tag(hx, Tag.VAR, Tag.PI, Tag.LAM, Tag.APP))), Outcome.REJECT, Reason.SYNTAX)
        op = self.mode(Op.TREE_LEFT)
        binder = self.tag(hx, Tag.PI, Tag.LAM)
        shift, subst = self.eq(w, Op.SHIFT), self.eq(w, Op.SUBST)
        next_y = self.mux(self.AND(binder, shift), self.add(y, 1), y)
        next_z = self.mux(self.AND(binder, subst), self.add(z, 1), z)
        overflow = self.OR(self.lt(next_y, y), self.lt(next_z, z))
        self.stop(self.AND(op, overflow), Outcome.RESOURCE, Reason.INDEX)
        self.call(self.AND(op, self.NOT(overflow)), w, hx['b'], next_y, next_z,
                  continuation=(Op.TREE_RIGHT, x, result))
        op = self.mode(Op.TREE_RIGHT)
        same = self.AND(self.eq(hx['a'], y), self.eq(hx['b'], result))
        self.ret(self.AND(op, same), x)
        self.allocate(self.AND(op, self.NOT(same)), hx['tag'], y, result)
        # Beta/delta definitional conversion; no eta/proof-irrelevance shortcut.
        op, same = self.mode(Op.CONV), self.eq(x, y)
        self.ret(self.AND(op, same), 1)
        self.call(self.AND(op, self.NOT(same)), Op.WHNF, x, continuation=(Op.C_LEFT, y))
        self.call(self.mode(Op.C_LEFT), Op.WHNF, x, continuation=(Op.C_RIGHT, result))
        op, same = self.mode(Op.C_RIGHT), self.eq(x, result)
        self.ret(self.AND(op, same), 1)
        work = self.AND(op, self.NOT(same))
        matching = self.eq(hx['tag'], hr['tag'])
        self.ret(self.AND(work, self.NOT(matching)), 0)
        self.ret(self.AND(work, matching, self.tag(hx, Tag.VAR, Tag.SORT, Tag.CONST)),
                 (self.eq(hx['v'], hr['v']),) + (self.g.zero,)*(self.width-1))
        self.call(self.AND(work, matching, self.tag(hx, Tag.PI, Tag.LAM, Tag.APP)), Op.CONV,
                  hx['a'], hr['a'], continuation=(Op.C_CHILD, hx['b'], hr['b']))
        self.stop(self.AND(work, matching, self.NOT(self.tag(hx, Tag.VAR, Tag.SORT, Tag.CONST, Tag.PI, Tag.LAM, Tag.APP))), Outcome.REJECT, Reason.SYNTAX)
        op, good = self.mode(Op.C_CHILD), self.NOT(self.eq(result, 0))
        self.tail(self.AND(op, good), Op.CONV, x, y)
        self.ret(self.AND(op, self.NOT(good)), 0)
        self.stop(self.AND(self.active, self.NOT(self.OR(*(self.eq(r['mode'], op) for op in Op)))), Outcome.REJECT, Reason.INTERNAL)

    def finish(self):
        self.rules()
        # Masked memory writes are control FFNs, with one write per bank/step.
        for bank, choices in self.writes.items():
            if not choices:
                continue
            fields = {'heap': HEAP_FIELDS, 'stack': FRAME_FIELDS, 'context': ('type',)}[bank]
            for row in range(getattr(self.cfg, bank)):
                conditions = [self.AND(condition, self.eq(address, row)) for condition, address, _ in choices]
                for field_index, field in enumerate(fields):
                    name = f'{bank}/{row}/{field}'
                    self.choices[name].extend((condition, values[field_index]) for condition, (_, _, values) in zip(conditions, choices))
        outputs = []
        for name, _ in self.layout.fields:
            choices = self.choices[name]
            if not choices:
                outputs.extend(self.old[name]); continue
            keep = self.NOT(self.OR(*(condition for condition, _ in choices)))
            for i, old in enumerate(self.old[name]):
                outputs.append(self.OR(self.AND(keep, old),
                    *(self.AND(condition, value[i]) for condition, value in choices)))
        return self.g.compile(outputs)


class SharedChecker(nn.Module):
    def __init__(self, config=MachineConfig()):
        super().__init__()
        self.config = config
        self.layout = StateLayout(config)
        self.address1, self.address2 = compile_addresses(self.layout)
        self.heap_read = AddressedRead(config.heap)
        self.stack_read = AddressedRead(config.stack)
        self.context_read = AddressedRead(config.context)
        self.constant_read = AddressedRead(config.constants)
        self.transition = RuleCompiler(self.layout).finish()
        self.requires_grad_(False)

    def bank(self, state, name):
        start, rows, width = self.layout.banks[name]
        return state[:, start:start+rows*width].reshape(state.shape[0], rows, width)

    def forward(self, state):
        with torch.autocast(device_type=state.device.type, enabled=False):
            query = self.address1(state)
            offset = 0
            reads = []
            for bank, ports, module in [('heap', 4, self.heap_read), ('stack', 1, self.stack_read),
                                        ('constants', 1, self.constant_read)]:
                size = ports*module.bits
                address = query[:, offset:offset+size].reshape(state.shape[0], ports, module.bits)
                reads.append(module(address, self.bank(state, bank)).flatten(1))
                offset += size
            first = torch.cat([state] + reads, dim=1)
            query = self.address2(first)
            offset = self.context_read.bits
            reads.append(self.context_read(query[:, :offset].unsqueeze(1), self.bank(state, 'context')).flatten(1))
            reads.append(self.constant_read(query[:, offset:].unsqueeze(1), self.bank(state, 'constants')).flatten(1))
            return self.transition(torch.cat([state] + reads, dim=1))


def compile_machine(config=MachineConfig()):
    return SharedChecker(config).eval()
