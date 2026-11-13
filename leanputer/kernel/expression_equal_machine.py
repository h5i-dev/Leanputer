"""Development reference: all-tag erased-syntax and typed-vector comparison.

This result is a positive representation-equality test, NOT full conversion.
A false result must never be promoted to definitional inequality. Native lowering
never calls this evaluator or supplies its result in the syntax capsule.
"""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import (Mode, Task, Outcome, Reason,
    EXPR_EQUAL_REST, CALL_VECTOR_LEVEL_EQUAL)

PRIVATE_PHASES = (EXPR_EQUAL_REST, CALL_VECTOR_LEVEL_EQUAL)


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    phase, original, depth, task, first, second = frame
    if phase == EXPR_EQUAL_REST:
        if not r['r']:
            r['sp'] -= 1; ret(0)
        else:
            if first:
                s['stack'][r['sp']-1] = [EXPR_EQUAL_REST, first, second, Task.EXPR_EQUAL, 0, 0]
            else: r['sp'] -= 1
            r.update(mode=Mode.WALK, task=Task.EXPR_EQUAL, x=original, peer=depth)
    else:
        r['sp'] -= 1
        if not r['r']: ret(0)
        elif not first: ret(1)
        else: r.update(mode=Mode.VECTOR_CELL_LEFT, task=Task.VECTOR_EQUAL, x=original, peer=depth,
                       vector_remaining=first, vector_expected_role=second)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] == Task.EXPR_EQUAL:
        if r['mode'] == Mode.WALK:
            if not 0 < r['peer'] < r['free']: stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['x'] == r['peer']: ret(1)
            else: r.update(mode=Mode.EXPR_EQUAL_RIGHT, left_tag=tag, left_a=a, left_b=b, left_c=c, x=r['peer'])
        elif r['mode'] == Mode.EXPR_EQUAL_RIGHT:
            lt, la, lb, lc = (r[k] for k in ('left_tag', 'left_a', 'left_b', 'left_c'))
            if tag != lt: ret(0)
            elif tag in (Tag.BVAR, Tag.LOCAL): ret(int(la == a))
            elif tag == Tag.SORT: r.update(mode=Mode.WALK, task=Task.LEVEL_EQUAL, x=la, peer=a)
            elif tag == Tag.CONST:
                if la != a: ret(0)
                else: r.update(mode=Mode.WALK, task=Task.VECTOR_EQUAL, x=lb, peer=b, vector_expected_role=VectorKind.LEVELS)
            elif tag in (Tag.NAT, Tag.STRING):
                r.update(mode=Mode.WALK, task=Task.VECTOR_EQUAL, x=la, peer=a,
                    vector_expected_role=VectorKind.LIMBS if tag == Tag.NAT else VectorKind.BYTES)
            elif tag == Tag.PROJ:
                if (la, lb) != (a, b): ret(0)
                else: r.update(mode=Mode.WALK, x=lc, peer=c)
            elif tag == Tag.MDATA: r.update(mode=Mode.WALK, x=la, peer=a)
            elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
            else:
                # The complete remaining constructor cases: App/Pi/Lam/Let.
                s['stack'][r['sp']] = [EXPR_EQUAL_REST, lb, b, Task.EXPR_EQUAL,
                    lc if tag == Tag.LET else 0, c if tag == Tag.LET else 0]
                r.update(sp=r['sp']+1, mode=Mode.WALK, x=la, peer=a)
        else: stop(Outcome.INVALID, Reason.SYNTAX)
        return True
    if r['task'] != Task.VECTOR_EQUAL: return False
    if r['mode'] == Mode.WALK:
        if not 0 < r['peer'] < r['free']: stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(mode=Mode.VECTOR_HEADER_RIGHT, left_a=a, left_b=b, left_c=c, x=r['peer'])
    elif r['mode'] == Mode.VECTOR_HEADER_RIGHT:
        if (c != r['vector_expected_role'] or r['left_c'] != c or
                c not in (VectorKind.LEVELS, VectorKind.LIMBS, VectorKind.BYTES) or
                bool(a) != bool(b) or bool(r['left_a']) != bool(r['left_b'])):
            stop(Outcome.INVALID, Reason.SYNTAX)
        elif a != r['left_a']: ret(0)
        elif not a: ret(1)
        else: r.update(mode=Mode.VECTOR_CELL_LEFT, x=r['left_b'], peer=b, vector_remaining=a)
    elif r['mode'] == Mode.VECTOR_CELL_LEFT:
        r.update(mode=Mode.VECTOR_CELL_RIGHT, left_a=a, left_b=b, x=r['peer'])
    elif r['mode'] == Mode.VECTOR_CELL_RIGHT:
        more = r['vector_remaining'] > 1
        if not r['vector_remaining'] or bool(b) != more or bool(r['left_b']) != more:
            stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['vector_expected_role'] == VectorKind.LEVELS:
            if r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
            else:
                s['stack'][r['sp']] = [CALL_VECTOR_LEVEL_EQUAL, r['left_b'], b, Task.VECTOR_EQUAL,
                                      r['vector_remaining']-1, r['vector_expected_role']]
                r.update(sp=r['sp']+1, mode=Mode.WALK, task=Task.LEVEL_EQUAL, x=r['left_a'], peer=a)
        elif r['left_a'] != a: ret(0)
        elif not more: ret(1)
        else: r.update(mode=Mode.VECTOR_CELL_LEFT, x=r['left_b'], peer=b, vector_remaining=r['vector_remaining']-1)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
