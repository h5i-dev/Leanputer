"""General expression traversal as bounded, explicit kernel transitions.

This is a kernel operation controller, not a proof-supplied instruction stream.
LIFT/INSTANTIATE/ABSTRACT/OCCURS use one stack and the same all-tag child walk.
The beta/literal-Let/metadata subservice calls that substitution operation via
private continuations. Checked-environment/local-let and other WHNF rules are
not implemented by this subservice.
The stock compiler receives capacities only. Syntax and operand vectors are
loaded as data. Python step() is solely a development reference.
"""
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum
import torch
from ..bitvec import pack_words, unpack_words
from .arena import Arena, KernelError, LevelTag, Limits, ResourceError, Tag, children
from .native_cells import CellTag, VectorKind


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
    SCOPE = 6
    CONTEXT = 7
    EXPECT_PI = 8
    EXPECT_LAM = 9
    UNIVERSE = 10
    UNSUPPORTED_DECLARATION = 15  # Shared reporting ABI; never emitted here.


class Task(IntEnum):
    LIFT = 0
    INSTANTIATE = 1
    ABSTRACT = 2
    OCCURS = 3
    BETA_ZETA = 4
    INSTANTIATE_ONE = 5          # Internal service call, no proof-data entry.
    OPEN_TELESCOPE = 6          # Declared Pi/Lam prefix, closed raw syntax input.
    VARIABLE_SCOPE = 7          # BVar/Local scope only, not universe checking.
    ROUNDTRIP_TELESCOPE = 8     # Wrapper tests OPEN then the internal FOLD.
    ABSTRACT_ONE = 9            # Internal semantic subroutine only.
    FOLD_TELESCOPE = 10         # Internal: consumes derived Local records.
    LEVEL_SCOPE = 11            # Internal typed-cell level walk/membership.
    LEVEL_SUBSTITUTE = 12       # Simultaneous raw level substitution.
    EXPR_LEVEL_SUBSTITUTE = 13  # All Expr tags; Sort/Const call the same level op.


class Mode(IntEnum):
    WALK = 0
    RETURN = 1
    RESUME = 2
    FIND = 3
    BETA_ZETA = 4
    TELESCOPE = 5
    BINDER_RECORD = 6
    FOLD_SELECT = 7
    FOLD_RECORD = 8
    FOLD_LOCAL = 9
    FOLD_BUILD = 10
    LEVEL_SELECT = 11
    LEVEL_BINDING = 12
    SORT_RESULT = 13
    CONST_VECTOR = 14
    CONST_CELL = 15
    CONST_RESULT = 16
    CONST_BUILD = 17
    CONST_FINISH = 18


CALL_BETA_ZETA = 16
PENDING_ARGUMENT = 17
CALL_TELESCOPE = 18
CALL_FOLD = 19
CALL_SORT_LEVEL = 20
CALL_CONST_LEVEL = 21
VECTOR_VALUE = 22
LOCAL_DECL_TAG = int(CellTag.LOCAL_DECL)  # Internal record, never an input Expr.


REGISTERS = ('mode', 'status', 'reason', 'fuel', 'free', 'sp', 'decl',
    'decl_count', 'ctx', 'x', 'depth', 'task', 'r', 'delta', 'cutoff', 'start',
    'count', 'i', 'found', 'root', 'substitution', 'limit', 'bounded', 'pending_open',
    'pending_fold', 'fold_body', 'domain', 'binder_info', 'abstract_uid', 'open_tag', 'fold_tag',
    'arg_base', 'parameter', 'lookup_level', 'const_original', 'expr_depth',
    'vec_length', 'vec_left', 'vec_build', 'vec_head', 'vec_changed', 'vector_result')
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
        if not 7 <= self.word_bits <= 21 or max(self.heap, self.stack, self.context, self.constants) >= 1 << self.word_bits:
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
    if task in (Task.INSTANTIATE_ONE, Task.ABSTRACT_ONE, Task.FOLD_TELESCOPE, Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.EXPR_LEVEL_SUBSTITUTE):
        raise KernelError('internal service has no raw-data entry point')
    operands = tuple(a.word(v) for v in doc.get('operands', ()))
    if task == Task.INSTANTIATE:
        for value in operands:
            a.expr(value)
    elif task == Task.ABSTRACT and any(not v for v in operands):
        raise KernelError('zero local identity')
    if task in (Task.OPEN_TELESCOPE, Task.ROUNDTRIP_TELESCOPE, Task.VARIABLE_SCOPE) and operands:
        raise KernelError('closed variable-scope/telescope entry has no outer locals')
    limit = doc.get('limit')
    if limit is not None:
        a.word(limit)
    binder_tags = {'pi': Tag.PI, 'lam': Tag.LAM}
    open_kind = doc.get('open_binder', 'pi')
    fold_kind = doc.get('fold_binder', open_kind)
    if open_kind not in binder_tags or fold_kind not in binder_tags:
        raise KernelError('telescope binder kind must be pi or lam')
    request = dict(arena=a, root=doc['root'], task=task, operands=operands,
        delta=a.word(doc.get('amount', 0)), cutoff=a.word(doc.get('cutoff', 0)),
        start=a.word(doc.get('start', 0)), limit=limit,
        open_tag=int(binder_tags[open_kind]), fold_tag=int(binder_tags[fold_kind]))
    return request, None, ()


def prepare(config, request, _unused=None, _declarations=()):
    a, operands = request['arena'], request['operands']
    if len(a.rows) > config.heap or len(operands) > config.context:
        raise ResourceError('input arena/vector capacity')
    words = [v for row in a.rows[1:] for v in (int(row.tag), row.a, row.b, row.c)]
    words += list(operands)+[request[n] for n in ('delta', 'cutoff', 'start')]
    if request['limit'] is not None:
        words.append(request['limit'])
    if any(v >= 1 << config.word_bits for v in words):
        raise ResourceError('input word width')
    state = {'regs': dict.fromkeys(REGISTERS, 0)}
    for bank, fields in BANK_FIELDS.items():
        state[bank] = [[0]*fields for _ in range(getattr(config, bank))]
    state['heap'][1:len(a.rows)] = [[int(r.tag), r.a, r.b, r.c] for r in a.rows[1:]]
    state['context'][:len(operands)] = [[v] for v in operands]
    state['regs'].update(fuel=config.fuel, free=len(a.rows), x=request['root'],
        root=request['root'], task=int(request['task']), count=len(operands), ctx=len(operands),
        **{n: request[n] for n in ('delta', 'cutoff', 'start', 'open_tag', 'fold_tag')})
    if request['task'] == Task.BETA_ZETA:
        state['regs']['mode'] = int(Mode.BETA_ZETA)
    if request['task'] in (Task.OPEN_TELESCOPE, Task.ROUNDTRIP_TELESCOPE):
        state['regs'].update(task=int(Task.VARIABLE_SCOPE), pending_open=1,
            bounded=int(request['limit'] is not None), limit=request['limit'] or 0,
            pending_fold=int(request['task'] == Task.ROUNDTRIP_TELESCOPE))
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
        if (not 0 < r['free'] <= cfg.heap or r['sp'] > cfg.stack or r['count'] > cfg.context or r['ctx'] > cfg.context
                or r['mode'] > Mode.CONST_FINISH or r['task'] > Task.EXPR_LEVEL_SUBSTITUTE
                or r['bounded'] > 1 or r['pending_open'] > 1 or r['pending_fold'] > 1
                or r['vec_changed'] > 1
                or r['open_tag'] not in (Tag.PI, Tag.LAM) or r['fold_tag'] not in (Tag.PI, Tag.LAM)):
            stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        uses_arguments = r['task'] in (Task.INSTANTIATE, Task.ABSTRACT, Task.OCCURS, Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.EXPR_LEVEL_SUBSTITUTE)
        if uses_arguments and r['arg_base']+r['count'] > cfg.context:
            stop(Outcome.RESOURCE, Reason.CONTEXT)
            return s
        if r['mode'] == Mode.RETURN:
            if not r['sp']:
                if r['pending_open']:
                    r.update(mode=Mode.TELESCOPE, x=r['root'], task=Task.OPEN_TELESCOPE, depth=0, pending_open=0)
                elif r['pending_fold']:
                    r.update(mode=Mode.FOLD_SELECT, x=r['r'], fold_body=r['r'],
                        task=Task.FOLD_TELESCOPE, pending_fold=0)
                else:
                    stop(Outcome.DONE)
            else:
                phase, original, depth, task, first, second = s['stack'][r['sp']-1]
                if phase == CALL_BETA_ZETA:
                    r.update(sp=r['sp']-1, mode=Mode.BETA_ZETA, x=r['r'], depth=0, task=Task.BETA_ZETA)
                elif phase == CALL_TELESCOPE:
                    r.update(sp=r['sp']-1, mode=Mode.TELESCOPE, x=r['r'], depth=0, task=Task.OPEN_TELESCOPE)
                elif phase == CALL_FOLD:
                    r.update(sp=r['sp']-1, mode=Mode.FOLD_BUILD, x=r['r'], task=Task.FOLD_TELESCOPE)
                elif phase == CALL_SORT_LEVEL:
                    r.update(sp=r['sp']-1, mode=Mode.SORT_RESULT, x=original, depth=depth, task=Task.EXPR_LEVEL_SUBSTITUTE)
                elif phase == CALL_CONST_LEVEL:
                    r.update(sp=r['sp']-1, mode=Mode.CONST_RESULT, x=original, depth=depth, task=Task.EXPR_LEVEL_SUBSTITUTE)
                elif phase == PENDING_ARGUMENT:
                    r.update(mode=Mode.RESUME, x=original, depth=depth, task=task)
                else:
                    r.update(mode=Mode.RESUME, x=original, depth=depth, task=task)
            return s
        if not 0 < r['x'] < r['free']:
            stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        tag, a, b, c = s['heap'][r['x']]
        level_scope = r['task'] == Task.LEVEL_SCOPE
        level_task = r['task'] in (Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE)
        valid_tag = (tag == LOCAL_DECL_TAG if r['mode'] == Mode.FOLD_RECORD else
            tag == CellTag.LEVEL_BINDING if r['mode'] == Mode.LEVEL_BINDING else
            tag == CellTag.VECTOR if r['mode'] == Mode.CONST_VECTOR else
            tag == CellTag.VECTOR_CELL if r['mode'] in (Mode.CONST_CELL, Mode.CONST_RESULT) else
            CellTag.LEVEL_ZERO <= tag <= CellTag.LEVEL_PARAM if level_task else Tag.BVAR <= tag <= Tag.MDATA)
        if not valid_tag:
            stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        task, depth = r['task'], r['depth']
        if r['mode'] == Mode.SORT_RESULT:
            if tag != Tag.SORT:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif a == r['r']:
                ret(r['x'])
            else:
                alloc((Tag.SORT, r['r'], 0, 0))
            return s
        if r['mode'] == Mode.CONST_VECTOR:
            if c != VectorKind.LEVELS or bool(a) != bool(b):
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif not a:
                ret(r['const_original'])
            else:
                r.update(vec_length=a, vec_left=a, vec_build=a, vec_head=0, vec_changed=0,
                    mode=Mode.CONST_CELL, x=b)
            return s
        if r['mode'] == Mode.CONST_CELL:
            if not r['vec_left'] or bool(b) != (r['vec_left'] > 1):
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['sp'] >= cfg.stack:
                stop(Outcome.RESOURCE, Reason.STACK)
            else:
                s['stack'][r['sp']] = [CALL_CONST_LEVEL, r['x'], r['expr_depth'], Task.EXPR_LEVEL_SUBSTITUTE, 0, 0]
                r.update(sp=r['sp']+1, mode=Mode.WALK, x=a, depth=0, task=Task.LEVEL_SUBSTITUTE)
            return s
        if r['mode'] == Mode.CONST_RESULT:
            changed = bool(r['vec_changed'] or a != r['r'])
            more = r['vec_left'] > 1
            if not r['vec_left']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif more or changed:
                if r['sp'] >= cfg.stack:
                    stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [VECTOR_VALUE, r['r'], 0, Task.EXPR_LEVEL_SUBSTITUTE, 0, 0]
                    r.update(sp=r['sp']+1, vec_left=r['vec_left']-1, vec_changed=int(changed),
                        mode=Mode.CONST_CELL if more else Mode.CONST_BUILD,
                        x=b if more else r['const_original'])
            else:
                r['sp'] -= r['vec_length']-1
                ret(r['const_original'])
            return s
        if r['mode'] == Mode.CONST_BUILD:
            if r['vec_build'] and (not r['sp'] or s['stack'][r['sp']-1][0] != VECTOR_VALUE):
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['free'] >= cfg.heap:
                stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                ref = r['free']
                if r['vec_build']:
                    value = s['stack'][r['sp']-1][1]
                    s['heap'][ref] = [CellTag.VECTOR_CELL, value, r['vec_head'], 0]
                    r.update(free=ref+1, vec_head=ref, vec_build=r['vec_build']-1, sp=r['sp']-1)
                else:
                    s['heap'][ref] = [CellTag.VECTOR, r['vec_length'], r['vec_head'], VectorKind.LEVELS]
                    r.update(free=ref+1, vector_result=ref, mode=Mode.CONST_FINISH)
            return s
        if r['mode'] == Mode.CONST_FINISH:
            if tag != Tag.CONST:
                stop(Outcome.INVALID, Reason.SYNTAX)
            else:
                alloc((Tag.CONST, a, r['vector_result'], 0))
            return s
        if r['mode'] == Mode.LEVEL_SELECT:
            r.update(mode=Mode.LEVEL_BINDING, x=s['context'][r['arg_base']+r['i']][0])
            return s
        if r['mode'] == Mode.LEVEL_BINDING:
            if not 0 < b < r['free']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif a == r['parameter']:
                ret(b)  # Simultaneous substitution: do NOT traverse replacement.
            elif r['i']+1 < r['count']:
                r.update(mode=Mode.LEVEL_SELECT, x=r['lookup_level'], i=r['i']+1)
            else:
                ret(r['lookup_level'])
            return s
        if r['mode'] == Mode.FOLD_SELECT:
            if not r['ctx']:
                ret(r['fold_body'])
            else:
                r.update(mode=Mode.FOLD_RECORD, x=s['context'][r['ctx']-1][0])
            return s
        if r['mode'] == Mode.FOLD_RECORD:
            if not 0 < a < r['free'] or not 0 < b < r['free']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            else:
                r.update(mode=Mode.FOLD_LOCAL, x=a, domain=b, binder_info=c)
            return s
        if r['mode'] == Mode.FOLD_LOCAL:
            if tag != Tag.LOCAL:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['sp'] >= cfg.stack:
                stop(Outcome.RESOURCE, Reason.STACK)
            else:
                s['stack'][r['sp']] = [CALL_FOLD, 0, 0, Task.FOLD_TELESCOPE, 0, 0]
                r.update(sp=r['sp']+1, mode=Mode.WALK, x=r['fold_body'], depth=0,
                    task=Task.ABSTRACT_ONE, abstract_uid=a)
            return s
        if r['mode'] == Mode.FOLD_BUILD:
            if not r['ctx']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['free'] >= cfg.heap:
                stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                binder = r['free']
                s['heap'][binder] = [r['fold_tag'], r['domain'], r['r'], r['binder_info']]
                r.update(free=binder+1, fold_body=binder, ctx=r['ctx']-1,
                    mode=Mode.FOLD_SELECT, x=binder)
            return s
        if r['mode'] == Mode.TELESCOPE:
            if r['bounded'] and r['ctx'] == r['limit']:
                ret(r['x'])
            elif tag != r['open_tag']:
                if r['bounded']: stop(Outcome.INVALID, Reason.EXPECT_PI if r['open_tag'] == Tag.PI else Reason.EXPECT_LAM)
                else: ret(r['x'])
            elif r['ctx'] >= cfg.context:
                stop(Outcome.RESOURCE, Reason.CONTEXT)
            elif r['sp'] >= cfg.stack:
                stop(Outcome.RESOURCE, Reason.STACK)
            elif r['free']+1 >= cfg.heap:
                stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                local = r['free']
                s['heap'][local] = [Tag.LOCAL, local, 0, 0]
                r.update(free=local+1, r=local, mode=Mode.BINDER_RECORD)
            return s
        if r['mode'] == Mode.BINDER_RECORD:
            # The Local is already allocated. Its UID is its immutable arena
            # address, hence fresh relative to every earlier generated Local.
            record = r['free']
            s['heap'][record] = [LOCAL_DECL_TAG, r['r'], a, c]
            s['context'][r['ctx']] = [record]
            s['stack'][r['sp']] = [CALL_TELESCOPE, 0, 0, Task.OPEN_TELESCOPE, 0, 0]
            r.update(free=record+1, ctx=r['ctx']+1, sp=r['sp']+1,
                mode=Mode.WALK, x=b, depth=0, task=Task.INSTANTIATE_ONE, substitution=r['r'])
            return s
        if r['mode'] == Mode.BETA_ZETA:
            if tag == Tag.MDATA:
                r['x'] = a
            elif tag == Tag.APP:
                if r['sp'] == cfg.stack:
                    stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [PENDING_ARGUMENT, r['x'], 0, Task.BETA_ZETA, b, 0]
                    r.update(sp=r['sp']+1, x=a)
            elif tag == Tag.LAM and r['sp'] and s['stack'][r['sp']-1][0] == PENDING_ARGUMENT:
                argument = s['stack'][r['sp']-1][4]
                s['stack'][r['sp']-1] = [CALL_BETA_ZETA, 0, 0, Task.BETA_ZETA, 0, 0]
                r.update(mode=Mode.WALK, x=b, substitution=argument, depth=0, task=Task.INSTANTIATE_ONE)
            elif tag == Tag.LET:
                if r['sp'] == cfg.stack:
                    stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [CALL_BETA_ZETA, 0, 0, Task.BETA_ZETA, 0, 0]
                    r.update(sp=r['sp']+1, mode=Mode.WALK, x=c, substitution=b, depth=0, task=Task.INSTANTIATE_ONE)
            else:
                ret(r['x'])
            return s
        if r['mode'] == Mode.FIND:
            if r['i'] >= r['count']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif s['context'][r['arg_base']+r['i']][0] == a:
                if task == Task.OCCURS:
                    r.update(found=1, sp=0, r=r['root']); stop(Outcome.DONE)
                elif level_scope:
                    ret(r['x'])
                else:
                    value = depth+r['count']-1-r['i']
                    if bounded(value):
                        alloc((Tag.BVAR, value, 0, 0))
            elif not r['i']:
                if level_scope: stop(Outcome.INVALID, Reason.UNIVERSE)
                else: ret(r['x'])
            else:
                r['i'] -= 1
            return s
        # Children have exactly the increments in arena.children, but no host
        # walk or supplied traversal schedule drives the actual transition.
        child_list = (((a, b) if tag in (CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX) else
                       (a,) if tag == CellTag.LEVEL_SUCC else ()) if level_task else
                      (a, b, c) if tag == Tag.LET else (a, b) if tag in (Tag.APP, Tag.PI, Tag.LAM)
                      else (c,) if tag == Tag.PROJ else (a,) if tag == Tag.MDATA else ())
        if r['mode'] == Mode.WALK and task == Task.EXPR_LEVEL_SUBSTITUTE:
            if not r['count']:
                ret(r['x'])
                return s
            if tag == Tag.SORT:
                if r['sp'] >= cfg.stack:
                    stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [CALL_SORT_LEVEL, r['x'], depth, Task.EXPR_LEVEL_SUBSTITUTE, 0, 0]
                    r.update(sp=r['sp']+1, mode=Mode.WALK, x=a, depth=0, task=Task.LEVEL_SUBSTITUTE)
                return s
            if tag == Tag.CONST:
                r.update(const_original=r['x'], expr_depth=depth, mode=Mode.CONST_VECTOR, x=b)
                return s
        if r['mode'] == Mode.RESUME:
            if not r['sp']:
                stop(Outcome.INVALID, Reason.SYNTAX)
                return s
            frame = s['stack'][r['sp']-1]
            phase, original, old_depth, old_task, first, second = frame
            if phase == PENDING_ARGUMENT:
                if tag != Tag.APP:
                    stop(Outcome.INVALID, Reason.SYNTAX)
                else:
                    r['sp'] -= 1
                    if a == r['r']: ret(original)
                    else: alloc((Tag.APP, r['r'], first, 0))
                return s
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
                elif tag in (Tag.APP, Tag.PI, Tag.LAM, CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX):
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
        elif task == Task.ABSTRACT_ONE and tag == Tag.LOCAL and a == r['abstract_uid']:
            alloc((Tag.BVAR, depth, 0, 0))
        elif level_scope and tag == CellTag.LEVEL_PARAM:
            if not r['count']: stop(Outcome.INVALID, Reason.UNIVERSE)
            else: r.update(mode=Mode.FIND, i=r['count']-1)
        elif task == Task.LEVEL_SUBSTITUTE and tag == CellTag.LEVEL_PARAM:
            if not r['count']: ret(r['x'])
            else: r.update(mode=Mode.LEVEL_SELECT, i=0, parameter=a, lookup_level=r['x'])
        elif task == Task.VARIABLE_SCOPE and (tag == Tag.LOCAL or tag == Tag.BVAR and a >= depth):
            stop(Outcome.INVALID, Reason.SCOPE)
        elif tag == Tag.BVAR and task in (Task.LIFT, Task.INSTANTIATE, Task.INSTANTIATE_ONE):
            start = 0 if task == Task.INSTANTIATE_ONE else r['cutoff'] if task == Task.LIFT else r['start']
            count = 1 if task == Task.INSTANTIATE_ONE else r['count']
            offset = depth+start
            if not bounded(offset):
                return s
            if a < offset:
                ret(r['x'])
            elif task == Task.LIFT:
                value = a+r['delta']
                if bounded(value):
                    if value == a: ret(r['x'])
                    else: alloc((Tag.BVAR, value, 0, 0))
            elif a-offset >= count:
                if not count: ret(r['x'])
                else: alloc((Tag.BVAR, a-count, 0, 0))
            else:
                value = r['substitution'] if task == Task.INSTANTIATE_ONE else s['context'][r['arg_base']+a-offset][0]
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


program_name = 'kernel.general-telescope-services.v4'
constant_fields = 6
first_banks = (('heap', 1), ('stack', 1))
second_banks = ('context',)
primitive_basis = ()
