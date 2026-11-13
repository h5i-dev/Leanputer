"""Development transition reference of pinned is_geq/is_geq_core.

The MAX-left alternatives must fall back to the remaining IMAX/offset rules
when BOTH alternatives fail. This is a conservative symbolic source predicate,
not an enumeration of parameter assignments. Never used for native inference.
"""
from .native_cells import CellTag
from .traversal_machine import (Mode, Task, Outcome, Reason, CALL_GEQ_LEFT,
    CALL_GEQ_RIGHT, CALL_GEQ_EQUAL, CALL_GEQ_AND, CALL_GEQ_MAX_FIRST,
    CALL_GEQ_MAX_SECOND, CALL_GEQ_OFFSET_LEFT, CALL_GEQ_OFFSET_RIGHT,
    CALL_GEQ_BASE_EQUAL)

PRIVATE_PHASES = (CALL_GEQ_LEFT, CALL_GEQ_RIGHT, CALL_GEQ_EQUAL, CALL_GEQ_AND,
    CALL_GEQ_MAX_FIRST, CALL_GEQ_MAX_SECOND, CALL_GEQ_OFFSET_LEFT,
    CALL_GEQ_OFFSET_RIGHT, CALL_GEQ_BASE_EQUAL)


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    phase, original, depth, task, first, second = frame
    if phase == CALL_GEQ_LEFT:
        s['stack'][r['sp']-1] = [CALL_GEQ_RIGHT, r['r'], 0, Task.LEVEL_GEQ, 0, 0]
        r.update(mode=Mode.WALK, task=Task.LEVEL_NORMALIZE, x=original)
    elif phase == CALL_GEQ_RIGHT:
        r.update(sp=r['sp']-1, mode=Mode.WALK, task=Task.LEVEL_GEQ_CORE, x=original, peer=r['r'])
    elif phase == CALL_GEQ_EQUAL:
        r['sp'] -= 1
        if r['r']: ret(1)
        else: r.update(mode=Mode.GEQ_RIGHT, task=Task.LEVEL_GEQ_CORE, x=depth, geq_left=original, geq_right=depth)
    elif phase == CALL_GEQ_AND:
        r['sp'] -= 1
        if not r['r']: ret(0)
        else: r.update(mode=Mode.WALK, task=Task.LEVEL_GEQ, x=original, peer=depth)
    elif phase == CALL_GEQ_MAX_FIRST:
        if r['r']:
            r['sp'] -= 1; ret(1)
        else:
            s['stack'][r['sp']-1] = [CALL_GEQ_MAX_SECOND, first, depth, Task.LEVEL_GEQ, 0, 0]
            r.update(mode=Mode.WALK, task=Task.LEVEL_GEQ, x=original, peer=depth)
    elif phase == CALL_GEQ_MAX_SECOND:
        r['sp'] -= 1
        if r['r']: ret(1)
        else: r.update(mode=Mode.GEQ_FALLBACK_RIGHT, task=Task.LEVEL_GEQ_CORE,
                       x=depth, geq_left=original, geq_right=depth)
    elif phase == CALL_GEQ_OFFSET_LEFT:
        s['stack'][r['sp']-1] = [CALL_GEQ_OFFSET_RIGHT, r['r'], 0, Task.LEVEL_GEQ_CORE, r['level_offset'], 0]
        r.update(mode=Mode.WALK, task=Task.LEVEL_OFFSET, x=original, level_offset=0)
    elif phase == CALL_GEQ_OFFSET_RIGHT:
        r.update(sp=r['sp']-1, mode=Mode.GEQ_OFFSET_BASE, task=Task.LEVEL_GEQ_CORE,
            x=r['r'], left_base=original, left_offset=first, right_offset=r['level_offset'])
    elif phase == CALL_GEQ_BASE_EQUAL:
        r['sp'] -= 1
        if r['r']: ret(int(first >= second))
        elif first == second and first > 0:
            r.update(mode=Mode.WALK, task=Task.LEVEL_GEQ, x=original, peer=depth)
        else: ret(0)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] not in (Task.LEVEL_GEQ, Task.LEVEL_GEQ_CORE): return False
    def call(phase, task, left, right=0, original=0, depth=0, first=0, second=0):
        if r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [phase, original, depth, Task.LEVEL_GEQ, first, second]
            r.update(sp=r['sp']+1, mode=Mode.WALK, task=task, x=left, peer=right)
    if r['mode'] == Mode.WALK:
        if not 0 < r['peer'] < r['free']: stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['task'] == Task.LEVEL_GEQ:
            call(CALL_GEQ_LEFT, Task.LEVEL_NORMALIZE, r['x'], original=r['peer'])
        else:
            call(CALL_GEQ_EQUAL, Task.LEVEL_EQUAL, r['x'], r['peer'], original=r['x'], depth=r['peer'])
    elif r['mode'] == Mode.GEQ_RIGHT:
        if tag == CellTag.LEVEL_ZERO: ret(1)
        elif tag == CellTag.LEVEL_MAX:
            call(CALL_GEQ_AND, Task.LEVEL_GEQ, r['geq_left'], a, original=r['geq_left'], depth=b)
        else: r.update(mode=Mode.GEQ_LEFT, x=r['geq_left'])
    elif r['mode'] == Mode.GEQ_LEFT:
        if tag == CellTag.LEVEL_MAX:
            call(CALL_GEQ_MAX_FIRST, Task.LEVEL_GEQ, a, r['geq_right'], original=b,
                depth=r['geq_right'], first=r['geq_left'])
        else: r.update(mode=Mode.GEQ_FALLBACK_RIGHT, x=r['geq_right'])
    elif r['mode'] == Mode.GEQ_FALLBACK_RIGHT:
        if tag == CellTag.LEVEL_IMAX:
            call(CALL_GEQ_AND, Task.LEVEL_GEQ, r['geq_left'], a, original=r['geq_left'], depth=b)
        else: r.update(mode=Mode.GEQ_FALLBACK_LEFT, x=r['geq_left'])
    elif r['mode'] == Mode.GEQ_FALLBACK_LEFT:
        if tag == CellTag.LEVEL_IMAX:
            r.update(mode=Mode.WALK, task=Task.LEVEL_GEQ, x=b, peer=r['geq_right'])
        else:
            call(CALL_GEQ_OFFSET_LEFT, Task.LEVEL_OFFSET, r['geq_left'], original=r['geq_right'])
            if not r['status']: r['level_offset'] = 0
    elif r['mode'] == Mode.GEQ_OFFSET_BASE:
        if tag == CellTag.LEVEL_ZERO: ret(int(r['left_offset'] >= r['right_offset']))
        else: call(CALL_GEQ_BASE_EQUAL, Task.LEVEL_EQUAL, r['left_base'], r['x'],
            original=r['left_base'], depth=r['x'], first=r['left_offset'], second=r['right_offset'])
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
