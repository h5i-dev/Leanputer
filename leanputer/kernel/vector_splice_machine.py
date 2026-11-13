"""Typed word-vector prefix + suffix[skip:] operation, DEVELOPMENT reference."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason

NO_NODE = (Mode.SPLICE_FINISH,)


def resume(machine, frame, stop, ret, alloc):
    r = machine.state['regs']
    if frame[0] != 0: stop(Outcome.INVALID, Reason.SYNTAX)
    else: r.update(task=Task.VECTOR_SPLICE, mode=Mode.SPLICE_REVERSED, x=r['r'])


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.VECTOR_SPLICE: return False
    def reverse():
        r.update(task=Task.REVERSE_LIST, mode=Mode.WALK, x=r['splice_prefix_head'], reverse_length=r['splice_prefix_length'], depth=0)
    def shape(): return c == r['splice_role'] and bool(a) == bool(b)
    mode = r['mode']
    if mode == Mode.WALK:
        if r['splice_role'] not in tuple(VectorKind) or not shape() or not 0 < r['peer'] < r['free']:
            stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [0, 0, 0, Task.VECTOR_SPLICE, 0, 0]
            r.update(sp=r['sp']+1, splice_prefix_length=a, splice_prefix_head=b, mode=Mode.SPLICE_SUFFIX, x=r['peer'])
    elif mode == Mode.SPLICE_SUFFIX:
        if not shape() or r['splice_skip'] > a: stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['splice_prefix_length']+a-r['splice_skip'] >= 1 << cfg.word_bits: stop(Outcome.RESOURCE, Reason.INDEX)
        else:
            r.update(splice_length=r['splice_prefix_length']+a-r['splice_skip'], splice_suffix_remaining=a, splice_tail=b)
            if r['splice_skip']: r.update(mode=Mode.SPLICE_SKIP, x=b)
            else: reverse()
    elif mode == Mode.SPLICE_SKIP:
        if not r['splice_skip'] or not r['splice_suffix_remaining'] or bool(b) != (r['splice_suffix_remaining'] > 1):
            stop(Outcome.INVALID, Reason.SYNTAX)
        else:
            more = r['splice_skip'] > 1
            r.update(splice_skip=r['splice_skip']-1, splice_suffix_remaining=r['splice_suffix_remaining']-1, splice_tail=b, x=b)
            if not more: reverse()
    elif mode == Mode.SPLICE_REVERSED:
        if c != VectorKind.REFERENCES or a != r['splice_prefix_length'] or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif not a: r['mode'] = Mode.SPLICE_FINISH
        else: r.update(splice_remaining=a, mode=Mode.SPLICE_COPY, x=b)
    elif mode == Mode.SPLICE_COPY:
        if not r['splice_remaining'] or bool(b) != (r['splice_remaining'] > 1): stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            ref = r['free']; s['heap'][ref] = [CellTag.VECTOR_CELL, a, r['splice_tail'], 0]
            more = r['splice_remaining'] > 1
            r.update(free=ref+1, splice_tail=ref, splice_remaining=r['splice_remaining']-1,
                mode=Mode.SPLICE_COPY if more else Mode.SPLICE_FINISH)
            if more: r['x'] = b
    elif mode == Mode.SPLICE_FINISH:
        if r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            ref = r['free']; s['heap'][ref] = [CellTag.VECTOR, r['splice_length'], r['splice_tail'], r['splice_role']]
            r.update(free=ref+1, sp=r['sp']-1); ret(ref)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
