"""Generic total level ordering for canonical Max argument traversal.

Pinned is_norm_lt compares bases recursively and successor offsets last.
Interned symbol IDs provide a stable artifact-local total parameter order.
All work and continuation creation are compiled; no host order/sort answers.
"""
from .native_cells import CellTag
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_ORDER_LEFT_OFFSET, CALL_ORDER_RIGHT_OFFSET, CALL_ORDER_BASE_COMPARE,
    CALL_ORDER_FIRST, CALL_ORDER_SECOND)

PRIVATE_PHASES = (CALL_ORDER_LEFT_OFFSET, CALL_ORDER_RIGHT_OFFSET,
                  CALL_ORDER_BASE_COMPARE, CALL_ORDER_FIRST, CALL_ORDER_SECOND)


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']
    result, top = r['r'], c.sub(r['sp'], 1)
    room = c.lt(r['sp'], c.cfg.stack)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)))
    at_return = lambda phase: c.AND(returning, c.eq(f['phase'], phase))
    left = at_return(CALL_ORDER_LEFT_OFFSET)
    c.write('stack', left, top, (CALL_ORDER_RIGHT_OFFSET, result, 0, Task.LEVEL_ORDER, r['level_offset'], 0))
    c.emit(left, mode=Mode.WALK, task=Task.LEVEL_OFFSET, x=f['original'], level_offset=0)
    right = at_return(CALL_ORDER_RIGHT_OFFSET)
    c.write('stack', right, top, (CALL_ORDER_BASE_COMPARE, f['original'], result, Task.LEVEL_ORDER, f['first'], r['level_offset']))
    c.emit(right, mode=Mode.WALK, task=Task.LEVEL_EQUAL, x=f['original'], peer=result)
    compared = at_return(CALL_ORDER_BASE_COMPARE)
    equal_base = c.NOT(c.eq(result, 0))
    c.emit(compared, sp=top)
    offset_order = c.mux(c.eq(f['first'], f['second']), 0, c.mux(c.lt(f['first'], f['second']), 1, 2))
    c.ret(c.AND(compared, equal_base), offset_order)
    c.emit(c.AND(compared, equal_base), order_same_base=1)
    c.emit(c.AND(compared, c.NOT(equal_base)), mode=Mode.ORDER_READ_LEFT, task=Task.LEVEL_ORDER,
        x=f['original'], peer=f['depth'])
    first = at_return(CALL_ORDER_FIRST)
    c.emit(c.AND(first, c.NOT(c.eq(result, 0))), sp=top, order_same_base=0)
    c.ret(c.AND(first, c.NOT(c.eq(result, 0))), result)
    next_child = c.AND(first, c.eq(result, 0))
    c.write('stack', next_child, top, (CALL_ORDER_SECOND, 0, 0, Task.LEVEL_ORDER, 0, 0))
    c.emit(next_child, mode=Mode.WALK, task=Task.LEVEL_ORDER, x=f['original'], peer=f['depth'])
    second = at_return(CALL_ORDER_SECOND)
    c.emit(second, sp=top, order_same_base=0)
    c.ret(second, result)

    entering = c.AND(c.mode(Mode.WALK), c.task(Task.LEVEL_ORDER))
    valid = c.AND(c.NOT(c.eq(r['peer'], 0)), c.lt(r['peer'], r['free']))
    c.stop(c.AND(entering, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.stop(c.AND(entering, valid, c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
    entering = c.AND(entering, valid, room)
    c.write('stack', entering, r['sp'], (CALL_ORDER_LEFT_OFFSET, r['peer'], 0, Task.LEVEL_ORDER, 0, 0))
    c.emit(entering, sp=c.add(r['sp'], 1), mode=Mode.WALK, task=Task.LEVEL_OFFSET, level_offset=0)
    read_left = c.mode(Mode.ORDER_READ_LEFT)
    c.emit(read_left, mode=Mode.ORDER_READ_RIGHT, left_tag=n['tag'], left_a=n['a'], left_b=n['b'], x=r['peer'])
    read_right = c.mode(Mode.ORDER_READ_RIGHT)
    different = c.NOT(c.eq(n['tag'], r['left_tag']))
    c.ret(c.AND(read_right, different), c.mux(c.lt(r['left_tag'], n['tag']), 1, 2))
    c.emit(c.AND(read_right, different), order_same_base=0)
    param = c.AND(read_right, c.NOT(different), c.tag(CellTag.LEVEL_PARAM))
    c.ret(param, c.mux(c.eq(r['left_a'], n['a']), 0, c.mux(c.lt(r['left_a'], n['a']), 1, 2)))
    c.emit(param, order_same_base=0)
    binary = c.tag(CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX)
    c.stop(c.AND(read_right, c.NOT(different), c.NOT(c.OR(binary, c.tag(CellTag.LEVEL_PARAM)))), Outcome.INVALID, Reason.SYNTAX)
    recurse = c.AND(read_right, c.NOT(different), binary)
    c.stop(c.AND(recurse, c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
    recurse = c.AND(recurse, room)
    c.write('stack', recurse, r['sp'], (CALL_ORDER_FIRST, r['left_b'], n['b'], Task.LEVEL_ORDER, 0, 0))
    c.emit(recurse, sp=c.add(r['sp'], 1), mode=Mode.WALK, x=r['left_a'], peer=n['a'])
