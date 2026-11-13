"""Explicit development reference for COMPLETE symbolic normalization.

Not an inference evaluator: native lowering is in level_normalize_rules.py.
Normalization is bottom-up, merging canonical Max chains with the source base/
offset order. A deferred explicit argument implements the global subsumption
rule. All recursion and list iteration have physical stack/heap/fuel bounds.
"""
from .native_cells import CellTag
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_NORMAL_IMAX, CALL_MERGE_ORDER, CALL_MERGE_OFFSET,
    CALL_EQUIVALENT_LEFT, CALL_EQUIVALENT_RIGHT)

PRIVATE_PHASES = (CALL_NORMAL_IMAX, CALL_MERGE_ORDER, CALL_MERGE_OFFSET,
                  CALL_EQUIVALENT_LEFT, CALL_EQUIVALENT_RIGHT)


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    phase, original, depth, task, first, second = frame
    if phase == CALL_NORMAL_IMAX:
        r.update(sp=r['sp']-1, mode=Mode.NORMAL_IMAX_RESULT, task=Task.LEVEL_NORMALIZE, x=r['r'])
    elif phase == CALL_MERGE_ORDER:
        pick_right = r['r'] == 2 if not r['order_same_base'] else r['r'] == 1
        chosen = r['merge_hr'] if pick_right else r['merge_hl']
        if r['order_same_base'] or not pick_right: r['merge_l'] = r['merge_tl']
        if r['order_same_base'] or pick_right: r['merge_r'] = r['merge_tr']
        s['stack'][r['sp']-1] = [CALL_MERGE_OFFSET, 0, 0, Task.LEVEL_MERGE, 0, 0]
        r.update(mode=Mode.WALK, task=Task.LEVEL_OFFSET, x=chosen, level_offset=0, merge_chosen=chosen)
    elif phase == CALL_MERGE_OFFSET:
        r.update(sp=r['sp']-1, mode=Mode.MERGE_RECORD, task=Task.LEVEL_MERGE, x=r['r'])
    elif phase == CALL_EQUIVALENT_LEFT:
        s['stack'][r['sp']-1] = [CALL_EQUIVALENT_RIGHT, r['r'], 0, Task.LEVEL_EQUIVALENT, 0, 0]
        r.update(mode=Mode.WALK, task=Task.LEVEL_NORMALIZE, x=original)
    elif phase == CALL_EQUIVALENT_RIGHT:
        r.update(sp=r['sp']-1, mode=Mode.WALK, task=Task.LEVEL_EQUAL, x=original, peer=r['r'])


def finish(machine, tag, refs):
    """Consume completed normalization children, shared caller stack already popped."""
    s, r = machine.state, machine.state['regs']
    if tag == CellTag.LEVEL_MAX:
        r.update(mode=Mode.WALK, task=Task.LEVEL_MERGE, x=refs[0], peer=refs[1])
    elif tag == CellTag.LEVEL_IMAX:
        s['stack'][r['sp']] = [CALL_NORMAL_IMAX, 0, 0, Task.LEVEL_NORMALIZE, 0, 0]
        r.update(sp=r['sp']+1, mode=Mode.WALK, task=Task.LEVEL_IMAX, x=refs[0], peer=refs[1])
    else:
        r.update(mode=Mode.WALK, task=Task.LEVEL_NORMAL_SUCC, x=refs[0])


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['mode'] == Mode.NORMAL_IMAX_RESULT:
        if tag == CellTag.LEVEL_MAX:
            r.update(mode=Mode.WALK, task=Task.LEVEL_MERGE, x=a, peer=b)
        else: ret(r['x'])
        return True
    if r['task'] == Task.LEVEL_EQUIVALENT:
        if not 0 < r['peer'] < r['free']: stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [CALL_EQUIVALENT_LEFT, r['peer'], 0, Task.LEVEL_EQUIVALENT, 0, 0]
            r.update(sp=r['sp']+1, mode=Mode.WALK, task=Task.LEVEL_NORMALIZE)
        return True
    if r['task'] != Task.LEVEL_MERGE: return False
    def next_left():
        r.update(mode=Mode.MERGE_LEFT, x=r['merge_l'] or r['merge_anchor'])
    if r['mode'] == Mode.WALK:
        if not 0 < r['peer'] < r['free']: stop(Outcome.INVALID, Reason.SYNTAX)
        else:
            r.update(merge_anchor=r['x'], merge_l=r['x'], merge_r=r['peer'],
                merge_rev=0, merge_acc=0, merge_explicit=0, merge_exp_offset=0, merge_max_offset=0)
            next_left()
    elif r['mode'] == Mode.MERGE_LEFT:
        r.update(merge_hl=0 if not r['merge_l'] else a if tag == CellTag.LEVEL_MAX else r['x'],
            merge_tl=b if r['merge_l'] and tag == CellTag.LEVEL_MAX else 0,
            mode=Mode.MERGE_RIGHT, x=r['merge_r'] or r['merge_anchor'])
    elif r['mode'] == Mode.MERGE_RIGHT:
        head = 0 if not r['merge_r'] else a if tag == CellTag.LEVEL_MAX else r['x']
        tail = b if r['merge_r'] and tag == CellTag.LEVEL_MAX else 0
        r.update(merge_hr=head, merge_tr=tail)
        if not r['merge_hl'] and not head:
            r.update(mode=Mode.MERGE_FOLD if r['merge_rev'] else Mode.MERGE_FINISH,
                x=r['merge_rev'] or r['merge_anchor'])
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            both = bool(r['merge_hl'] and head)
            chosen = r['merge_hl'] or head
            s['stack'][r['sp']] = [CALL_MERGE_ORDER if both else CALL_MERGE_OFFSET, 0, 0, Task.LEVEL_MERGE, 0, 0]
            r.update(sp=r['sp']+1, mode=Mode.WALK, task=Task.LEVEL_ORDER if both else Task.LEVEL_OFFSET,
                x=chosen, peer=head if both else 0)
            if not both:
                if r['merge_hl']: r['merge_l'] = r['merge_tl']
                else: r['merge_r'] = tail
                r.update(merge_chosen=chosen, level_offset=0)
    elif r['mode'] == Mode.MERGE_RECORD:
        if tag == CellTag.LEVEL_ZERO:
            if not r['merge_explicit'] or r['level_offset'] > r['merge_exp_offset']:
                r.update(merge_explicit=r['merge_chosen'], merge_exp_offset=r['level_offset'])
            next_left()
        elif r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            s['heap'][r['free']] = [CellTag.VECTOR_CELL, r['merge_chosen'], r['merge_rev'], 0]
            r.update(merge_rev=r['free'], free=r['free']+1,
                merge_max_offset=max(r['merge_max_offset'], r['level_offset']))
            next_left()
    elif r['mode'] == Mode.MERGE_FOLD:
        if r['merge_acc'] and r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            if r['merge_acc']:
                s['heap'][r['free']] = [CellTag.LEVEL_MAX, a, r['merge_acc'], 0]
                r.update(merge_acc=r['free'], free=r['free']+1)
            else: r['merge_acc'] = a
            r.update(merge_rev=b, mode=Mode.MERGE_FOLD if b else Mode.MERGE_FINISH, x=b or r['merge_anchor'])
    elif r['mode'] == Mode.MERGE_FINISH:
        if not r['merge_acc']: ret(r['merge_explicit'])
        elif r['merge_explicit'] and r['merge_exp_offset'] > r['merge_max_offset']:
            alloc((CellTag.LEVEL_MAX, r['merge_explicit'], r['merge_acc'], 0))
        else: ret(r['merge_acc'])
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
