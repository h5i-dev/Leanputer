"""General expression traversal as bounded, explicit kernel transitions.

This is a kernel operation controller, not a proof-supplied instruction stream.
LIFT/INSTANTIATE/ABSTRACT/OCCURS use one stack and the same all-tag child walk.
The stock compiler receives capacities only. Syntax and operand vectors are
loaded as data. Python step() is solely a development reference.
"""
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum
import torch
from ..bitvec import pack_words, unpack_words
from .arena import Arena, KernelError, LevelTag, Limits, ResourceError, Tag, children


class Outcome(IntEnum):
    RUNNING = 0
    DONE = 1                     # Operation completed, NOT proof acceptance.
    INVALID = 2
    RESOURCE = 3


class Reason(IntEnum):
    NONE = 0
    SYNTAX = 1
    HEAP = 2
    STACK = 3
    INDEX = 4
    FUEL = 5
    UNSUPPORTED_DECLARATION = 15  # Shared reporting ABI; never emitted here.


class Task(IntEnum):
    LIFT = 0
    INSTANTIATE = 1
    ABSTRACT = 2
    OCCURS = 3


class Mode(IntEnum):
    WALK = 0
    RETURN = 1
    RESUME = 2
    FIND = 3


REGISTERS = ('mode', 'status', 'reason', 'fuel', 'free', 'sp', 'decl',
    'decl_count', 'ctx', 'x', 'depth', 'task', 'r', 'delta', 'cutoff', 'start',
    'count', 'i', 'found', 'root')
BANK_FIELDS = {'heap': 4, 'stack': 6, 'context': 1, 'constants': 6}


@dataclass(frozen=True)
class MachineConfig:
    heap: int = 64
    stack: int = 16
    context: int = 8
    constants: int = 2
    fuel: int = 256
    # Data symbols need not be smaller than a pointer. This bound is physical,
    # shared across all input names, not a compiled symbol whitelist.
    word_bits: int = 10

    def __post_init__(self):
        for field in ('heap', 'stack', 'context', 'constants'):
            n = getattr(self, field)
            if type(n) is not int or n < 2 or n & (n-1):
                raise ValueError('memory capacities must be powers of two >=2')
        if type(self.fuel) is not int or self.fuel < 1:
            raise ValueError('positive fuel required')
        if not 4 <= self.word_bits <= 21 or max(self.heap, self.stack, self.context, self.constants) >= 1 << self.word_bits:
            raise ValueError('memory pointers do not fit word width')


class StateLayout:
    def __init__(self, config):
        self.config = config
        self.fields = [(n, max(config.word_bits, config.fuel.bit_length()) if n == 'fuel' else config.word_bits)
                       for n in REGISTERS]
        self.banks = {}
        for bank, fields in BANK_FIELDS.items():
            start = sum(w for _, w in self.fields)
            self.fields.extend((f'{bank}/{i}/{j}', config.word_bits)
                for i in range(getattr(config, bank)) for j in range(fields))
            self.banks[bank] = (start, getattr(config, bank), fields*config.word_bits)
        self.names, self.slices = [], {}
        for name, width in self.fields:
            start = len(self.names)
            self.names.extend(f'{name}/{i}' for i in range(width))
            self.slices[name] = slice(start, len(self.names))
        self.widths = [w for _, w in self.fields]
        self.width = len(self.names)

    def encode(self, state):
        words = [state['regs'][n] for n in REGISTERS]
        words.extend(v for bank in BANK_FIELDS for row in state[bank] for v in row)
        return torch.tensor([pack_words(words, self.widths)], dtype=torch.float32)

    def decode(self, bits):
        if len(bits) != self.width or any(b not in (0, 1) for b in bits):
            raise ValueError('exact Boolean state required')
        words = unpack_words(bits, self.widths)
        state = {'regs': dict(zip(REGISTERS, words[:len(REGISTERS)]))}
        offset = len(REGISTERS)
        for bank, width in BANK_FIELDS.items():
            size = getattr(self.config, bank)
            state[bank] = [words[offset+i*width:offset+(i+1)*width] for i in range(size)]
            offset += size*width
        return state


class RegisterLayout:
    def __init__(self, state_layout):
        self.config = state_layout.config
        self.fields = state_layout.fields[:len(REGISTERS)]
        self.width = sum(w for _, w in self.fields)
        self.names = state_layout.names[:self.width]
        self.slices = {n: state_layout.slices[n] for n in REGISTERS}


def document(arena, root, task, operands=(), **arguments):
    """Serialize immutable raw syntax and operation arguments, with no answers."""
    return dict(format='leanputer.kernel-operation.v1', task=Task(task).name,
        levels=[[int(r.tag), r.a, r.b] for r in arena.levels[1:]],
        vectors=[list(v) for v in arena.vectors[1:]],
        rows=[[int(r.tag), r.a, r.b, r.c] for r in arena.rows[1:]],
        root=root, operands=list(operands), **arguments)


def parse_document(doc):
    """Syntax-only reconstruction. No scope/type/positivity/reduction calls."""
    if doc.get('format') != 'leanputer.kernel-operation.v1':
        raise ValueError('expected kernel-operation document')
    limits = Limits(expressions=max(1, len(doc['rows'])), levels=max(1, len(doc['levels'])),
        vector_cells=max(1, sum(1+len(v) for v in doc['vectors'])))
    a = Arena(limits)
    for i, row in enumerate(doc['levels'], 1):
        if a.level(*row) != i:
            raise KernelError('noncanonical level table')
    for i, vector in enumerate(doc['vectors'], 1):
        if a.vec(vector) != i:
            raise KernelError('noncanonical vector table')
    for i, row in enumerate(doc['rows'], 1):
        if a.mk(*row) != i:
            raise KernelError('noncanonical expression table')
    a.expr(doc['root'])
    task = Task[doc['task']]
    operands = tuple(a.word(v) for v in doc.get('operands', ()))
    if task == Task.INSTANTIATE:
        for value in operands:
            a.expr(value)
    elif task == Task.ABSTRACT and any(not v for v in operands):
        raise KernelError('zero local identity')
    request = dict(arena=a, root=doc['root'], task=task, operands=operands,
        delta=a.word(doc.get('amount', 0)), cutoff=a.word(doc.get('cutoff', 0)),
        start=a.word(doc.get('start', 0)))
    return request, None, ()


def prepare(config, request, _unused=None, _declarations=()):
    a, operands = request['arena'], request['operands']
    if len(a.rows) > config.heap or len(operands) > config.context:
        raise ResourceError('input arena/vector capacity')
    words = [v for row in a.rows[1:] for v in (int(row.tag), row.a, row.b, row.c)]
    words += list(operands)+[request[n] for n in ('delta', 'cutoff', 'start')]
    if any(v >= 1 << config.word_bits for v in words):
        raise ResourceError('input word width')
    state = {'regs': dict.fromkeys(REGISTERS, 0)}
    for bank, fields in BANK_FIELDS.items():
        state[bank] = [[0]*fields for _ in range(getattr(config, bank))]
    state['heap'][1:len(a.rows)] = [[int(r.tag), r.a, r.b, r.c] for r in a.rows[1:]]
    state['context'][:len(operands)] = [[v] for v in operands]
    state['regs'].update(fuel=config.fuel, free=len(a.rows), x=request['root'],
        root=request['root'], task=int(request['task']), count=len(operands), ctx=len(operands),
        **{n: request[n] for n in ('delta', 'cutoff', 'start')})
    return state


def boot_length(bank, state):
    return state['regs']['free'] if bank == 'heap' else state['regs']['count'] if bank == 'context' else 0


class SpecMachine:
    def __init__(self, config, state):
        self.cfg, self.state = config, deepcopy(state)

    def step(self):
        s, cfg = self.state, self.cfg
        r = s['regs']
        if r['status']:
            return s
        def stop(status, reason=Reason.NONE):
            r.update(status=int(status), reason=int(reason))
        if r['fuel'] == 0:
            stop(Outcome.RESOURCE, Reason.FUEL)
            return s
        r['fuel'] -= 1
        def ret(ref):
            r.update(mode=Mode.RETURN, r=ref)
        def alloc(row):
            if r['free'] >= cfg.heap:
                stop(Outcome.RESOURCE, Reason.HEAP)
                return
            ref = r['free']
            s['heap'][ref] = list(row)
            r['free'] += 1
            ret(ref)
        def bounded(value):
            if value >= 1 << cfg.word_bits:
                stop(Outcome.RESOURCE, Reason.INDEX)
                return False
            return True
        if (not 0 < r['free'] <= cfg.heap or r['sp'] > cfg.stack or r['count'] > cfg.context
                or r['mode'] > Mode.FIND or r['task'] > Task.OCCURS):
            stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        if r['mode'] == Mode.RETURN:
            if not r['sp']:
                stop(Outcome.DONE)
            else:
                phase, original, depth, task, first, second = s['stack'][r['sp']-1]
                r.update(mode=Mode.RESUME, x=original, depth=depth, task=task)
            return s
        if not 0 < r['x'] < r['free']:
            stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        tag, a, b, c = s['heap'][r['x']]
        if not Tag.BVAR <= tag <= Tag.MDATA:
            stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        task, depth = r['task'], r['depth']
        if r['mode'] == Mode.FIND:
            if r['i'] >= r['count']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif s['context'][r['i']][0] == a:
                if task == Task.OCCURS:
                    r.update(found=1, sp=0, r=r['root']); stop(Outcome.DONE)
                else:
                    value = depth+r['count']-1-r['i']
                    if bounded(value):
                        alloc((Tag.BVAR, value, 0, 0))
            elif not r['i']:
                ret(r['x'])
            else:
                r['i'] -= 1
            return s
        # Children have exactly the increments in arena.children, but no host
        # walk or supplied traversal schedule drives the actual transition.
        child_list = ((a, b, c) if tag == Tag.LET else (a, b) if tag in (Tag.APP, Tag.PI, Tag.LAM)
                      else (c,) if tag == Tag.PROJ else (a,) if tag == Tag.MDATA else ())
        if r['mode'] == Mode.RESUME:
            if not r['sp']:
                stop(Outcome.INVALID, Reason.SYNTAX)
                return s
            frame = s['stack'][r['sp']-1]
            phase, original, old_depth, old_task, first, second = frame
            if not 1 <= phase <= len(child_list):
                stop(Outcome.INVALID, Reason.SYNTAX)
                return s
            if phase < len(child_list):
                increment = int(tag in (Tag.PI, Tag.LAM) and phase == 1 or tag == Tag.LET and phase == 2)
                if bounded(depth+increment):
                    frame[0] += 1
                    frame[3+phase] = r['r']
                    r.update(mode=Mode.WALK, x=child_list[phase], depth=depth+increment)
            else:
                refs = [first, second][:phase-1]+[r['r']]
                r['sp'] -= 1
                if tuple(refs) == child_list:
                    ret(original)
                elif tag in (Tag.APP, Tag.PI, Tag.LAM):
                    alloc((tag, refs[0], refs[1], c))
                elif tag == Tag.LET:
                    alloc((tag, *refs))
                elif tag == Tag.PROJ:
                    alloc((tag, a, b, refs[0]))
                else:
                    alloc((tag, refs[0], b, 0))
            return s
        if child_list:
            if r['sp'] == cfg.stack:
                stop(Outcome.RESOURCE, Reason.STACK)
            else:
                s['stack'][r['sp']] = [1, r['x'], depth, task, 0, 0]
                r.update(sp=r['sp']+1, mode=Mode.WALK, x=child_list[0])
        elif tag == Tag.BVAR and task in (Task.LIFT, Task.INSTANTIATE):
            offset = depth+(r['cutoff'] if task == Task.LIFT else r['start'])
            if not bounded(offset):
                return s
            if a < offset:
                ret(r['x'])
            elif task == Task.LIFT:
                value = a+r['delta']
                if bounded(value):
                    if value == a: ret(r['x'])
                    else: alloc((Tag.BVAR, value, 0, 0))
            elif a-offset >= r['count']:
                if not r['count']: ret(r['x'])
                else: alloc((Tag.BVAR, a-r['count'], 0, 0))
            else:
                value = s['context'][a-offset][0]
                if not 0 < value < r['free']:
                    stop(Outcome.INVALID, Reason.SYNTAX)
                elif not depth:
                    ret(value)
                else:
                    r.update(x=value, depth=0, task=Task.LIFT, delta=depth, cutoff=0)
        elif ((tag == Tag.LOCAL and task == Task.ABSTRACT)
              or (tag == Tag.CONST and task == Task.OCCURS)) and r['count']:
            r.update(mode=Mode.FIND, i=r['count']-1)
        else:
            ret(r['x'])
        return s


def assumptions(_):
    return []


program_name = 'kernel.general-expression-traversal.v1'
constant_fields = 6
first_banks = (('heap', 1), ('stack', 1))
second_banks = ('context',)
primitive_basis = ()
