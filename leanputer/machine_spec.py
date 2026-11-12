"""Bounded explicit small-step dependent checker specification.

The separate recursive Oracle is a differential reference. This specification
has no dependency on torch, Boolean gates, or the weighted implementation.
"""
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum

from .dependent import Declaration, Exhausted, TAGS, Tag, parse_expr


class Outcome(IntEnum):
    RUNNING = 0
    ACCEPT = 1
    REJECT = 2
    RESOURCE = 3


class Reason(IntEnum):
    NONE = 0
    SYNTAX = 1
    UNBOUND = 2
    EXPECT_SORT = 3
    EXPECT_PI = 4
    CONVERSION = 5
    HEAP = 6
    STACK = 7
    CONTEXT = 8
    UNIVERSE = 9
    FUEL = 10
    INDEX = 11
    INTERNAL = 12


class Op(IntEnum):
    VALIDATE = 0
    ENV = 1
    TYPE = 2
    VALUE = 3
    COMMIT = 4
    ROOT_TYPE = 5
    ROOT_TERM = 6
    ROOT_EQ = 7
    FINISH = 8
    INFER = 9
    I_DOM = 10
    I_BIND = 11
    I_LAM = 12
    I_PI = 13
    I_SORT = 14
    I_APP = 15
    I_FUN = 16
    I_ARG = 17
    I_CHECK = 18
    WHNF = 19
    W_APP = 20
    W_BETA = 21
    SHIFT = 22
    SUBST = 23
    TREE_LEFT = 24
    TREE_RIGHT = 25
    CONV = 26
    C_LEFT = 27
    C_RIGHT = 28
    C_CHILD = 29
    RET = 30
    ENV_EQ = 31
    FALLBACK = 32
    C_AFTER_CHILD = 33
    F_TYPE = 34
    F_TYPE_WHNF = 35
    F_SORT = 36
    F_SORT_WHNF = 37
    F_Y = 38
    F_PROOF_RESULT = 39
    ETA = 40
    E_TYPE = 41
    E_TYPE_WHNF = 42
    E_DOMAIN = 43
    E_SHIFT = 44
    E_VAR = 45
    E_BUILD = 46
    E_MAKE_APP = 47
    E_COMPARE = 48


@dataclass(frozen=True)
class MachineConfig:
    heap: int = 128
    stack: int = 32
    context: int = 32
    constants: int = 16
    universe: int = 4
    fuel: int = 1024

    def __post_init__(self):
        for name in ('heap', 'stack', 'context', 'constants'):
            value = getattr(self, name)
            if type(value) is not int or value < 2 or value & (value-1):
                raise ValueError(f'{name} capacity must be a power of two >= 2')
        if self.heap < 16 or type(self.universe) is not int or not 0 <= self.universe < self.heap-1:
            raise ValueError('heap >= 16 and universe below heap-1 required')
        if type(self.fuel) is not int or self.fuel < 1:
            raise ValueError('positive fuel required')

    @property
    def word_bits(self):
        return max(6, max(self.heap, self.stack, self.context, self.constants).bit_length())


REGISTERS = ('mode', 'x', 'y', 'z', 'w', 'r', 'ctx', 'sp', 'free', 'scan',
             'decl', 'decl_count', 'term', 'claim', 'fuel', 'status', 'reason')
HEAP_FIELDS = ('tag', 'a', 'b', 'v')
FRAME_FIELDS = ('mode', 'x', 'y', 'z', 'w', 'ctx')


def prepare(config, term, claim, declarations=()):
    """Syntax-only postorder DAG encoding, including all environment assumptions."""
    declarations = tuple(d if isinstance(d, Declaration) else Declaration(**d) for d in declarations)
    if len(declarations) > config.constants:
        raise Exhausted('constant table capacity')
    names = {d.name: i for i, d in enumerate(declarations)}
    if len(names) != len(declarations):
        raise ValueError('duplicate declaration names')
    heap, cache = [[0, 0, 0, 0]], {}
    def visit(expr):
        expr = parse_expr(expr)
        if expr in cache:
            return cache[expr]
        tag = expr[0]
        a = b = v = 0
        if tag in ('pi', 'lam', 'app'):
            a, b = visit(expr[1]), visit(expr[2])
        elif tag == 'const':
            if expr[1] not in names:
                raise ValueError(f'undeclared constant: {expr[1]}')
            v = names[expr[1]]
        else:
            v = expr[1]
        if v >= 1 << config.word_bits:
            raise Exhausted('syntax scalar encoding capacity')
        if len(heap) >= config.heap:
            raise Exhausted('input heap capacity')
        idx = len(heap)
        heap.append([int(TAGS[tag]), a, b, v]); cache[expr] = idx
        return idx
    constants = []
    for d in declarations:
        ty = visit(d.type)
        value = visit(d.value) if d.value is not None else 0
        constants.append([2 if d.opaque else int(d.value is not None), ty, value])
    term_id, claim_id = visit(term), visit(claim)
    regs = {name: 0 for name in REGISTERS}
    regs.update(free=len(heap), scan=1, decl_count=len(constants), term=term_id,
                claim=claim_id, fuel=config.fuel)
    heap.extend([[0]*4 for _ in range(config.heap-len(heap))])
    constants.extend([[0]*3 for _ in range(config.constants-len(constants))])
    return dict(regs=regs, heap=heap, stack=[[0]*6 for _ in range(config.stack)],
                context=[[0] for _ in range(config.context)], constants=constants)


class SpecMachine:
    def __init__(self, config, state):
        self.config, self.state = config, deepcopy(state)

    def node(self, pointer):
        if not 0 < pointer < self.state['regs']['free']:
            self.stop(Outcome.REJECT, Reason.SYNTAX)
            return [0]*4
        return self.state['heap'][pointer]

    def stop(self, status, reason=Reason.NONE):
        self.state['regs'].update(status=int(status), reason=int(reason))

    def ret(self, result):
        self.state['regs'].update(mode=int(Op.RET), r=result)

    def tail(self, op, x=0, y=0, z=0, w=0):
        self.state['regs'].update(mode=int(op), x=x, y=y, z=z, w=w)

    def call(self, op, x, y=0, z=0, w=0, continuation=None, context=None):
        r = self.state['regs']
        if r['sp'] >= self.config.stack:
            self.stop(Outcome.RESOURCE, Reason.STACK); return
        frame = [int(continuation[0])] + list(continuation[1:])
        frame += [0] * (5-len(frame))
        self.state['stack'][r['sp']] = frame + [r['ctx']]
        r['sp'] += 1
        self.tail(op, x, y, z, w)
        if context is not None:
            r['ctx'] = context

    def allocate(self, tag, a=0, b=0, v=0):
        r = self.state['regs']
        if r['free'] >= self.config.heap:
            self.stop(Outcome.RESOURCE, Reason.HEAP); return
        if v >= 1 << self.config.word_bits:
            self.stop(Outcome.RESOURCE, Reason.INDEX); return
        pointer = r['free']
        self.state['heap'][pointer] = [int(tag), a, b, v]
        r['free'] += 1
        self.ret(pointer)

    def step(self):
        s, cfg = self.state, self.config
        r = s['regs']
        if r['status']:
            return s
        if r['fuel'] == 0:
            self.stop(Outcome.RESOURCE, Reason.FUEL); return s
        r['fuel'] -= 1
        op, x, y, z, w, result = (r[k] for k in ('mode', 'x', 'y', 'z', 'w', 'r'))
        # Check address domains before any semantic read or update. The weighted
        # engine uses the same guards before interpreting an attention result.
        if (not 1 <= r['free'] <= cfg.heap or r['sp'] > cfg.stack or r['ctx'] > cfg.context
                or not r['decl'] <= r['decl_count'] <= cfg.constants):
            self.stop(Outcome.REJECT, Reason.SYNTAX); return s
        pointers = []
        if op in (Op.INFER, Op.I_BIND, Op.WHNF, Op.W_APP, Op.SHIFT, Op.SUBST,
                  Op.TREE_LEFT, Op.TREE_RIGHT, Op.CONV, Op.C_RIGHT, Op.C_CHILD,
                  Op.FALLBACK, Op.ETA, Op.E_TYPE_WHNF, Op.E_COMPARE):
            pointers.append(x)
        if op in (Op.VALUE, Op.ROOT_TERM, Op.I_BIND, Op.I_SORT, Op.I_FUN, Op.W_APP,
                  Op.C_RIGHT, Op.F_TYPE_WHNF, Op.F_SORT_WHNF, Op.E_TYPE_WHNF):
            pointers.append(result)
        if op in (Op.CONV, Op.FALLBACK, Op.ETA):
            pointers.append(y)
        if any(not 0 < pointer < r['free'] for pointer in pointers):
            self.stop(Outcome.REJECT, Reason.SYNTAX); return s
        if op == Op.VALIDATE:
            if r['scan'] >= r['free']:
                self.tail(Op.ENV)
            else:
                i = r['scan']; tag, a, b, v = s['heap'][i]
                valid = 1 <= tag <= 6
                if tag in (Tag.PI, Tag.LAM, Tag.APP):
                    valid &= 0 < a < i and 0 < b < i and v == 0
                else:
                    valid &= a == b == 0
                if tag == Tag.CONST:
                    valid &= v < r['decl_count']
                if not valid:
                    self.stop(Outcome.REJECT, Reason.SYNTAX)
                elif tag == Tag.SORT and v > cfg.universe:
                    self.stop(Outcome.RESOURCE, Reason.UNIVERSE)
                else:
                    r['scan'] += 1
        elif op == Op.ENV:
            if r['decl'] == r['decl_count']:
                self.call(Op.INFER, r['claim'], continuation=(Op.ROOT_TYPE,))
            else:
                kind, ty, value = s['constants'][r['decl']]
                if kind not in (0, 1, 2) or not 0 < ty < r['free'] or (kind and not 0 < value < r['free']):
                    self.stop(Outcome.REJECT, Reason.SYNTAX)
                else:
                    self.call(Op.INFER, ty, continuation=(Op.TYPE, ty, value, kind))
        elif op in (Op.TYPE, Op.ROOT_TYPE):
            cont = (Op.VALUE, x, y, z) if op == Op.TYPE else (Op.ROOT_TERM,)
            self.call(Op.WHNF, result, continuation=cont)
        elif op in (Op.VALUE, Op.ROOT_TERM):
            if self.node(result)[0] != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            elif op == Op.ROOT_TERM:
                self.call(Op.INFER, r['term'], continuation=(Op.ROOT_EQ,))
            elif z == 0:
                r['decl'] += 1; self.tail(Op.ENV)
            else:
                self.call(Op.INFER, y, continuation=(Op.COMMIT, x))
        elif op in (Op.COMMIT, Op.ROOT_EQ):
            self.call(Op.CONV, result, x if op == Op.COMMIT else r['claim'],
                      continuation=(Op.ENV_EQ if op == Op.COMMIT else Op.FINISH,))
        elif op in (Op.ENV_EQ, Op.FINISH):
            if not result:
                self.stop(Outcome.REJECT, Reason.CONVERSION)
            elif op == Op.FINISH:
                self.stop(Outcome.ACCEPT)
            else:
                r['decl'] += 1; self.tail(Op.ENV)
        elif op == Op.RET:
            if not r['sp']:
                self.stop(Outcome.REJECT, Reason.INTERNAL)
            else:
                r['sp'] -= 1
                for key, value in zip(FRAME_FIELDS, s['stack'][r['sp']]):
                    r[key] = value
        elif op == Op.INFER:
            tag, a, b, v = self.node(x)
            if tag == Tag.VAR:
                if v >= r['ctx']:
                    self.stop(Outcome.REJECT, Reason.UNBOUND)
                else:
                    self.tail(Op.SHIFT, s['context'][r['ctx']-1-v][0], 0, v+1)
            elif tag == Tag.SORT:
                if v >= cfg.universe:
                    self.stop(Outcome.RESOURCE, Reason.UNIVERSE)
                else:
                    self.allocate(Tag.SORT, v=v+1)
            elif tag in (Tag.LAM, Tag.PI):
                self.call(Op.INFER, a, continuation=(Op.I_DOM, x))
            elif tag == Tag.APP:
                self.call(Op.INFER, a, continuation=(Op.I_APP, b))
            elif tag == Tag.CONST and v < r['decl']:
                self.ret(s['constants'][v][1])
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op == Op.I_DOM:
            self.call(Op.WHNF, result, continuation=(Op.I_BIND, x))
        elif op == Op.I_BIND:
            if self.node(result)[0] != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            elif r['ctx'] >= cfg.context:
                self.stop(Outcome.RESOURCE, Reason.CONTEXT)
            else:
                tag, a, b, _ = self.node(x)
                s['context'][r['ctx']][0] = a
                cont = (Op.I_LAM, a) if tag == Tag.LAM else (Op.I_PI, self.node(result)[3])
                self.call(Op.INFER, b, continuation=cont, context=r['ctx']+1)
        elif op == Op.I_LAM:
            self.allocate(Tag.PI, x, result)
        elif op == Op.I_PI:
            self.call(Op.WHNF, result, continuation=(Op.I_SORT, x))
        elif op == Op.I_SORT:
            tag, _, _, v = self.node(result)
            if tag != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            else:
                self.allocate(Tag.SORT, v=0 if v == 0 else max(x, v))
        elif op == Op.I_APP:
            self.call(Op.WHNF, result, continuation=(Op.I_FUN, x))
        elif op == Op.I_FUN:
            tag, a, b, _ = self.node(result)
            if tag != Tag.PI:
                self.stop(Outcome.REJECT, Reason.EXPECT_PI)
            else:
                self.call(Op.INFER, x, continuation=(Op.I_ARG, a, b, x))
        elif op == Op.I_ARG:
            self.call(Op.CONV, x, result, continuation=(Op.I_CHECK, y, z))
        elif op == Op.I_CHECK:
            if not result:
                self.stop(Outcome.REJECT, Reason.CONVERSION)
            else:
                self.tail(Op.SUBST, x, y)
        elif op == Op.WHNF:
            tag, a, b, v = self.node(x)
            if tag == Tag.APP:
                self.call(Op.WHNF, a, continuation=(Op.W_APP, x, b))
            elif tag == Tag.CONST:
                if v >= r['decl']:
                    self.stop(Outcome.REJECT, Reason.SYNTAX)
                elif s['constants'][v][0] == 1:
                    self.tail(Op.WHNF, s['constants'][v][2])
                else:
                    self.ret(x)
            elif tag in (Tag.VAR, Tag.SORT, Tag.PI, Tag.LAM):
                self.ret(x)
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op == Op.W_APP:
            tag, _, body, _ = self.node(result)
            if tag == Tag.LAM:
                self.call(Op.SUBST, body, y, continuation=(Op.W_BETA,))
            elif result == self.node(x)[1]:
                self.ret(x)
            else:
                self.allocate(Tag.APP, result, y)
        elif op == Op.W_BETA:
            self.tail(Op.WHNF, result)
        elif op in (Op.SHIFT, Op.SUBST):
            tag, a, b, v = self.node(x)
            if tag in (Tag.SORT, Tag.CONST) or (op == Op.SHIFT and z == 0):
                self.ret(x)
            elif tag == Tag.VAR:
                if op == Op.SHIFT:
                    if v < y:
                        self.ret(x)
                    else:
                        self.allocate(Tag.VAR, v=v+z)
                elif v < z:
                    self.ret(x)
                elif v == z:
                    self.tail(Op.SHIFT, y, 0, z)
                else:
                    self.allocate(Tag.VAR, v=v-1)
            elif tag in (Tag.PI, Tag.LAM, Tag.APP):
                self.call(op, a, y, z, continuation=(Op.TREE_LEFT, x, y, z, op))
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op == Op.TREE_LEFT:
            tag, _, b, _ = self.node(x)
            binder = int(tag in (Tag.PI, Tag.LAM))
            next_y, next_z = y + (binder if w == Op.SHIFT else 0), z + (binder if w == Op.SUBST else 0)
            if max(next_y, next_z) >= 1 << cfg.word_bits:
                self.stop(Outcome.RESOURCE, Reason.INDEX)
            else:
                self.call(w, b, next_y, next_z, continuation=(Op.TREE_RIGHT, x, result))
        elif op == Op.TREE_RIGHT:
            tag, a, b, _ = self.node(x)
            if a == y and b == result:
                self.ret(x)
            else:
                self.allocate(tag, y, result)
        elif op == Op.CONV:
            if x == y:
                self.ret(1)
            else:
                self.call(Op.WHNF, x, continuation=(Op.C_LEFT, y))
        elif op == Op.C_LEFT:
            self.call(Op.WHNF, x, continuation=(Op.C_RIGHT, result))
        elif op == Op.C_RIGHT:
            tx, ax, bx, vx = self.node(x)
            ty, ay, by, vy = self.node(result)
            if x == result:
                self.ret(1)
            elif tx != ty:
                self.tail(Op.FALLBACK, x, result)
            elif tx in (Tag.VAR, Tag.SORT, Tag.CONST):
                if vx == vy:
                    self.ret(1)
                else:
                    self.tail(Op.FALLBACK, x, result)
            elif tx in (Tag.PI, Tag.LAM, Tag.APP):
                self.call(Op.CONV, ax, ay, continuation=(Op.C_CHILD, x, result, bx, by))
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op == Op.C_CHILD:
            if not result:
                self.tail(Op.FALLBACK, x, y)
            else:
                tag, domain, _, _ = self.node(x)
                binder = tag in (Tag.PI, Tag.LAM)
                if binder and r['ctx'] >= cfg.context:
                    self.stop(Outcome.RESOURCE, Reason.CONTEXT)
                else:
                    if binder:
                        s['context'][r['ctx']][0] = domain
                    self.call(Op.CONV, z, w, continuation=(Op.C_AFTER_CHILD, x, y),
                              context=r['ctx']+int(binder))
        elif op == Op.C_AFTER_CHILD:
            if result:
                self.ret(1)
            else:
                self.tail(Op.FALLBACK, x, y)
        elif op == Op.FALLBACK:
            if self.node(x)[0] in (Tag.SORT, Tag.PI) or self.node(y)[0] in (Tag.SORT, Tag.PI):
                self.ret(0)
            else:
                self.call(Op.INFER, x, continuation=(Op.F_TYPE, x, y))
        elif op == Op.F_TYPE:
            self.call(Op.WHNF, result, continuation=(Op.F_TYPE_WHNF, x, y))
        elif op == Op.F_TYPE_WHNF:
            if self.node(result)[0] == Tag.SORT:
                self.ret(0)
            else:
                self.call(Op.INFER, result, continuation=(Op.F_SORT, x, y, result))
        elif op == Op.F_SORT:
            self.call(Op.WHNF, result, continuation=(Op.F_SORT_WHNF, x, y, z))
        elif op == Op.F_SORT_WHNF:
            tag, _, _, v = self.node(result)
            if tag != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            elif v == 0:
                self.call(Op.INFER, y, continuation=(Op.F_Y, x, y, z))
            else:
                self.tail(Op.ETA, x, y)
        elif op == Op.F_Y:
            self.call(Op.CONV, z, result, continuation=(Op.F_PROOF_RESULT, x, y))
        elif op == Op.F_PROOF_RESULT:
            if result:
                self.ret(1)
            else:
                self.tail(Op.ETA, x, y)
        elif op == Op.ETA:
            left_lam, right_lam = self.node(x)[0] == Tag.LAM, self.node(y)[0] == Tag.LAM
            if left_lam == right_lam:
                self.ret(0)
            elif left_lam:
                self.call(Op.INFER, y, continuation=(Op.E_TYPE, x, y))
            else:
                self.call(Op.INFER, x, continuation=(Op.E_TYPE, y, x))
        elif op == Op.E_TYPE:
            self.call(Op.WHNF, result, continuation=(Op.E_TYPE_WHNF, x, y))
        elif op == Op.E_TYPE_WHNF:
            if self.node(result)[0] != Tag.PI:
                self.ret(0)
            else:
                self.call(Op.CONV, self.node(x)[1], self.node(result)[1], continuation=(Op.E_DOMAIN, x, y))
        elif op == Op.E_DOMAIN:
            if not result:
                self.ret(0)
            else:
                self.call(Op.SHIFT, y, 0, 1, continuation=(Op.E_SHIFT, x))
        elif op == Op.E_SHIFT:
            self.call(Op.E_VAR, 0, continuation=(Op.E_BUILD, x, result))
        elif op == Op.E_VAR:
            self.allocate(Tag.VAR, v=0)
        elif op == Op.E_BUILD:
            self.call(Op.E_MAKE_APP, y, result, continuation=(Op.E_COMPARE, x))
        elif op == Op.E_MAKE_APP:
            self.allocate(Tag.APP, x, y)
        elif op == Op.E_COMPARE:
            if r['ctx'] >= cfg.context:
                self.stop(Outcome.RESOURCE, Reason.CONTEXT)
            else:
                _, domain, body, _ = self.node(x)
                s['context'][r['ctx']][0] = domain
                self.tail(Op.CONV, body, result)
                r['ctx'] += 1
        else:
            self.stop(Outcome.REJECT, Reason.INTERNAL)
        return s

    def run(self, trace=False):
        states = [deepcopy(self.state)] if trace else None
        for _ in range(self.config.fuel+1):
            self.step()
            if trace:
                states.append(deepcopy(self.state))
            if self.state['regs']['status']:
                break
        return states if trace else self.state
