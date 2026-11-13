"""Canonical structured-name interning as data, DEVELOPMENT reference only."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason

NO_NODE = (Mode.INTERN_STORE_ENTRY, Mode.INTERN_STORE_CELL, Mode.INTERN_STORE_VECTOR)


def resume(machine, frame, stop, ret, alloc):
    r = machine.state['regs']
    if frame[0] == 0:
        if not r['r']: stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(task=Task.INTERN_NAME_PATH, mode=Mode.INTERN_ROOT, x=r['symbols_root'])
    elif frame[0] != 1: stop(Outcome.INVALID, Reason.SYNTAX)
    elif r['r']:
        r.update(task=Task.INTERN_NAME_PATH, sp=r['sp']-1); ret(r['intern_candidate'])
    elif r['intern_remaining'] > 1:
        r.update(task=Task.INTERN_NAME_PATH, mode=Mode.INTERN_CELL, x=r['intern_next'], intern_remaining=r['intern_remaining']-1)
    else: r.update(task=Task.INTERN_NAME_PATH, mode=Mode.INTERN_STORE_ENTRY)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.INTERN_NAME_PATH: return False
    mode = r['mode']
    if mode == Mode.WALK:
        if r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [0, r['x'], 0, Task.INTERN_NAME_PATH, 0, 0]
            r.update(sp=r['sp']+1, task=Task.COMPARE_NAME_PATH, peer=r['x'], path_prefix=0)
    elif mode == Mode.INTERN_ROOT:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        else:
            r.update(intern_length=a, intern_head=b, intern_maximum=0, intern_remaining=a,
                mode=Mode.INTERN_CELL if a else Mode.INTERN_STORE_ENTRY)
            if a: r['x'] = b
    elif mode == Mode.INTERN_CELL:
        if not r['intern_remaining'] or bool(b) != (r['intern_remaining'] > 1): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(intern_next=b, mode=Mode.INTERN_ENTRY, x=a)
    elif mode == Mode.INTERN_ENTRY:
        if not a: stop(Outcome.INVALID, Reason.SYNTAX)
        else:
            frame = s['stack'][r['sp']-1]; frame[0] = 1
            r.update(intern_candidate=a, intern_maximum=max(a, r['intern_maximum']),
                task=Task.COMPARE_NAME_PATH, mode=Mode.WALK, x=frame[1], peer=b, path_prefix=0)
    elif mode == Mode.INTERN_STORE_ENTRY:
        if r['intern_maximum'] == (1 << cfg.word_bits)-1: stop(Outcome.RESOURCE, Reason.INDEX)
        elif r['free']+3 > cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            ref = r['free']; symbol = r['intern_maximum']+1
            s['heap'][ref] = [CellTag.SYMBOL_ENTRY, symbol, s['stack'][r['sp']-1][1], 0]
            r.update(free=ref+1, intern_symbol=symbol, intern_entry=ref, mode=Mode.INTERN_STORE_CELL)
    elif mode == Mode.INTERN_STORE_CELL:
        ref = r['free']; s['heap'][ref] = [CellTag.VECTOR_CELL, r['intern_entry'], r['intern_head'], 0]
        r.update(free=ref+1, intern_link=ref, mode=Mode.INTERN_STORE_VECTOR)
    elif mode == Mode.INTERN_STORE_VECTOR:
        ref = r['free']; s['heap'][ref] = [CellTag.VECTOR, r['intern_length']+1, r['intern_link'], VectorKind.REFERENCES]
        r.update(free=ref+1, symbols_root=ref, sp=r['sp']-1); ret(r['intern_symbol'])
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
