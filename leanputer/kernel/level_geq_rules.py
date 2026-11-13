"""Compile COMPLETE pinned conservative symbolic universe geq rules.

Both inputs are normalized by the SAME weighted service. Recursion, short
circuits, Max fallback, IMax and offset comparisons use private continuations,
never sampled assignments/host comparison/admission answers.
"""
from .native_cells import CellTag
from .traversal_machine import (Mode, Task, Outcome, Reason, CALL_GEQ_LEFT,
    CALL_GEQ_RIGHT, CALL_GEQ_EQUAL, CALL_GEQ_AND, CALL_GEQ_MAX_FIRST,
    CALL_GEQ_MAX_SECOND, CALL_GEQ_OFFSET_LEFT, CALL_GEQ_OFFSET_RIGHT,
    CALL_GEQ_BASE_EQUAL)

PRIVATE_PHASES = (CALL_GEQ_LEFT, CALL_GEQ_RIGHT, CALL_GEQ_EQUAL, CALL_GEQ_AND,
    CALL_GEQ_MAX_FIRST, CALL_GEQ_MAX_SECOND, CALL_GEQ_OFFSET_LEFT,
    CALL_GEQ_OFFSET_RIGHT, CALL_GEQ_BASE_EQUAL)


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']
    result, top = r['r'], c.sub(r['sp'], 1)
    room = c.lt(r['sp'], c.cfg.stack)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)))
    at_return = lambda phase: c.AND(returning, c.eq(f['phase'], phase))
    truth = c.NOT(c.eq(result, 0))
    def call(guard, phase, task, left, right=0, original=0, depth=0, first=0, second=0):
        c.stop(c.AND(guard, c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
        guard = c.AND(guard, room)
        c.write('stack', guard, r['sp'], (phase, original, depth, Task.LEVEL_GEQ, first, second))
        c.emit(guard, sp=c.add(r['sp'], 1), mode=Mode.WALK, task=task, x=left, peer=right)
        return guard

    left_return = at_return(CALL_GEQ_LEFT)
    c.write('stack', left_return, top, (CALL_GEQ_RIGHT, result, 0, Task.LEVEL_GEQ, 0, 0))
    c.emit(left_return, mode=Mode.WALK, task=Task.LEVEL_NORMALIZE, x=f['original'])
    c.emit(at_return(CALL_GEQ_RIGHT), sp=top, mode=Mode.WALK, task=Task.LEVEL_GEQ_CORE, x=f['original'], peer=result)
    equal_return = at_return(CALL_GEQ_EQUAL)
    c.emit(equal_return, sp=top)
    c.ret(c.AND(equal_return, truth), 1)
    c.emit(c.AND(equal_return, c.NOT(truth)), mode=Mode.GEQ_RIGHT, task=Task.LEVEL_GEQ_CORE,
        x=f['depth'], geq_left=f['original'], geq_right=f['depth'])
    and_return = at_return(CALL_GEQ_AND)
    c.emit(and_return, sp=top)
    c.ret(c.AND(and_return, c.NOT(truth)), 0)
    c.emit(c.AND(and_return, truth), mode=Mode.WALK, task=Task.LEVEL_GEQ, x=f['original'], peer=f['depth'])
    first_max = at_return(CALL_GEQ_MAX_FIRST)
    c.emit(c.AND(first_max, truth), sp=top)
    c.ret(c.AND(first_max, truth), 1)
    second_alternative = c.AND(first_max, c.NOT(truth))
    c.write('stack', second_alternative, top, (CALL_GEQ_MAX_SECOND, f['first'], f['depth'], Task.LEVEL_GEQ, 0, 0))
    c.emit(second_alternative, mode=Mode.WALK, task=Task.LEVEL_GEQ, x=f['original'], peer=f['depth'])
    second_max = at_return(CALL_GEQ_MAX_SECOND)
    c.emit(second_max, sp=top)
    c.ret(c.AND(second_max, truth), 1)
    c.emit(c.AND(second_max, c.NOT(truth)), mode=Mode.GEQ_FALLBACK_RIGHT, task=Task.LEVEL_GEQ_CORE,
        x=f['depth'], geq_left=f['original'], geq_right=f['depth'])
    left_offset = at_return(CALL_GEQ_OFFSET_LEFT)
    c.write('stack', left_offset, top, (CALL_GEQ_OFFSET_RIGHT, result, 0, Task.LEVEL_GEQ_CORE, r['level_offset'], 0))
    c.emit(left_offset, mode=Mode.WALK, task=Task.LEVEL_OFFSET, x=f['original'], level_offset=0)
    c.emit(at_return(CALL_GEQ_OFFSET_RIGHT), sp=top, mode=Mode.GEQ_OFFSET_BASE, task=Task.LEVEL_GEQ_CORE,
        x=result, left_base=f['original'], left_offset=f['first'], right_offset=r['level_offset'])
    base_equal = at_return(CALL_GEQ_BASE_EQUAL)
    c.emit(base_equal, sp=top)
    c.ret(c.AND(base_equal, truth), c.mux(c.lt(f['first'], f['second']), 0, 1))
    recurse_base = c.AND(c.eq(f['first'], f['second']), c.NOT(c.eq(f['first'], 0)))
    c.emit(c.AND(base_equal, c.NOT(truth), recurse_base), mode=Mode.WALK, task=Task.LEVEL_GEQ, x=f['original'], peer=f['depth'])
    c.ret(c.AND(base_equal, c.NOT(truth), c.NOT(recurse_base)), 0)

    entering = c.AND(c.mode(Mode.WALK), c.OR(c.task(Task.LEVEL_GEQ), c.task(Task.LEVEL_GEQ_CORE)))
    peer_ok = c.AND(c.NOT(c.eq(r['peer'], 0)), c.lt(r['peer'], r['free']))
    c.stop(c.AND(entering, c.NOT(peer_ok)), Outcome.INVALID, Reason.SYNTAX)
    entering = c.AND(entering, peer_ok)
    call(c.AND(entering, c.task(Task.LEVEL_GEQ)), CALL_GEQ_LEFT, Task.LEVEL_NORMALIZE, r['x'], original=r['peer'])
    call(c.AND(entering, c.task(Task.LEVEL_GEQ_CORE)), CALL_GEQ_EQUAL, Task.LEVEL_EQUAL,
        r['x'], r['peer'], original=r['x'], depth=r['peer'])
    right = c.mode(Mode.GEQ_RIGHT)
    c.ret(c.AND(right, c.tag(CellTag.LEVEL_ZERO)), 1)
    call(c.AND(right, c.tag(CellTag.LEVEL_MAX)), CALL_GEQ_AND, Task.LEVEL_GEQ,
        r['geq_left'], n['a'], original=r['geq_left'], depth=n['b'])
    c.emit(c.AND(right, c.NOT(c.tag(CellTag.LEVEL_ZERO, CellTag.LEVEL_MAX))), mode=Mode.GEQ_LEFT, x=r['geq_left'])
    left = c.mode(Mode.GEQ_LEFT)
    call(c.AND(left, c.tag(CellTag.LEVEL_MAX)), CALL_GEQ_MAX_FIRST, Task.LEVEL_GEQ,
        n['a'], r['geq_right'], original=n['b'], depth=r['geq_right'], first=r['geq_left'])
    c.emit(c.AND(left, c.NOT(c.tag(CellTag.LEVEL_MAX))), mode=Mode.GEQ_FALLBACK_RIGHT, x=r['geq_right'])
    fallback_right = c.mode(Mode.GEQ_FALLBACK_RIGHT)
    call(c.AND(fallback_right, c.tag(CellTag.LEVEL_IMAX)), CALL_GEQ_AND, Task.LEVEL_GEQ,
        r['geq_left'], n['a'], original=r['geq_left'], depth=n['b'])
    c.emit(c.AND(fallback_right, c.NOT(c.tag(CellTag.LEVEL_IMAX))), mode=Mode.GEQ_FALLBACK_LEFT, x=r['geq_left'])
    fallback_left = c.mode(Mode.GEQ_FALLBACK_LEFT)
    c.emit(c.AND(fallback_left, c.tag(CellTag.LEVEL_IMAX)), mode=Mode.WALK, task=Task.LEVEL_GEQ, x=n['b'], peer=r['geq_right'])
    offset_call = call(c.AND(fallback_left, c.NOT(c.tag(CellTag.LEVEL_IMAX))),
        CALL_GEQ_OFFSET_LEFT, Task.LEVEL_OFFSET, r['geq_left'], original=r['geq_right'])
    c.emit(offset_call, level_offset=0)
    base = c.mode(Mode.GEQ_OFFSET_BASE)
    c.ret(c.AND(base, c.tag(CellTag.LEVEL_ZERO)), c.mux(c.lt(r['left_offset'], r['right_offset']), 0, 1))
    call(c.AND(base, c.NOT(c.tag(CellTag.LEVEL_ZERO))), CALL_GEQ_BASE_EQUAL, Task.LEVEL_EQUAL,
        r['left_base'], r['x'], original=r['left_base'], depth=r['x'], first=r['left_offset'], second=r['right_offset'])
