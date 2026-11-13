"""Boolean lowering of the COMPLETE pinned symbolic Max/IMax constructors.

Each operation calls shared structural equality/nonzero/offset services. All
operands are level DAG data, never names, declaration classes or supplied
normalization answers. This module emits IR only; it has no Python evaluator
or runtime reduction path. Canonical normalization is a subsequent caller.
"""
from .native_cells import CellTag
from .traversal_machine import (Mode, Outcome, Reason, Task, CALL_MAX_COMPARE,
    CALL_MAX_LEFT_OFFSET, CALL_MAX_RIGHT_OFFSET, CALL_IMAX_NONZERO,
    CALL_IMAX_COMPARE)


PRIVATE_PHASES = (CALL_MAX_COMPARE, CALL_MAX_LEFT_OFFSET, CALL_MAX_RIGHT_OFFSET,
                  CALL_IMAX_NONZERO, CALL_IMAX_COMPARE)


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']
    a, b, x, result = n['a'], n['b'], r['x'], r['r']
    left, right = r['constructor_left'], r['constructor_right']
    top, room = c.sub(r['sp'], 1), c.lt(r['sp'], c.cfg.stack)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)))

    def call(guard, phase, task, x, peer=0, stage=0):
        c.stop(c.AND(guard, c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
        guard = c.AND(guard, room)
        c.write('stack', guard, r['sp'], (phase, 0, 0, Task.LEVEL_MAX, stage, 0))
        c.emit(guard, sp=c.add(r['sp'], 1), mode=Mode.WALK, task=task, x=x, peer=peer)
        return guard

    def offset(guard):
        guard = call(guard, CALL_MAX_LEFT_OFFSET, Task.LEVEL_OFFSET, left)
        c.emit(guard, level_offset=0)

    equal_return = c.AND(returning, c.eq(f['phase'], CALL_MAX_COMPARE))
    c.emit(equal_return, sp=top, mode=Mode.MAX_EQUAL_RESULT,
        x=c.mux(c.eq(f['first'], 3), left, right), task=Task.LEVEL_MAX, constructor_stage=f['first'])
    left_offset_return = c.AND(returning, c.eq(f['phase'], CALL_MAX_LEFT_OFFSET))
    c.write('stack', left_offset_return, top, (CALL_MAX_RIGHT_OFFSET, 0, 0, Task.LEVEL_MAX, 0, 0))
    c.emit(left_offset_return, left_base=result, left_offset=r['level_offset'], level_offset=0,
        task=Task.LEVEL_OFFSET, mode=Mode.WALK, x=right)
    right_offset_return = c.AND(returning, c.eq(f['phase'], CALL_MAX_RIGHT_OFFSET))
    c.write('stack', right_offset_return, top, (CALL_MAX_COMPARE, 0, 0, Task.LEVEL_MAX, 5, 0))
    c.emit(right_offset_return, right_offset=r['level_offset'], peer=result, x=r['left_base'],
        task=Task.LEVEL_EQUAL, mode=Mode.WALK)
    nonzero_return = c.AND(returning, c.eq(f['phase'], CALL_IMAX_NONZERO))
    nonzero = c.NOT(c.eq(result, 0))
    c.emit(nonzero_return, sp=top, x=c.mux(nonzero, left, right),
        mode=c.mux(nonzero, Mode.WALK, Mode.IMAX_RIGHT),
        task=c.mux(nonzero, Task.LEVEL_MAX, Task.LEVEL_IMAX))
    c.emit(c.AND(nonzero_return, nonzero), peer=right)
    imax_return = c.AND(returning, c.eq(f['phase'], CALL_IMAX_COMPARE))
    c.emit(imax_return, sp=top)
    c.ret(c.AND(imax_return, nonzero), left)
    c.alloc(c.AND(imax_return, c.NOT(nonzero)), (CellTag.LEVEL_IMAX, left, right, 0))

    entering = c.AND(c.mode(Mode.WALK), c.OR(c.task(Task.LEVEL_MAX), c.task(Task.LEVEL_IMAX)))
    valid_peer = c.AND(c.NOT(c.eq(r['peer'], 0)), c.lt(r['peer'], r['free']))
    c.stop(c.AND(entering, c.NOT(valid_peer)), Outcome.INVALID, Reason.SYNTAX)
    entering = c.AND(entering, valid_peer)
    c.emit(entering, constructor_left=x, constructor_right=r['peer'])
    c.emit(c.AND(entering, c.task(Task.LEVEL_MAX)), mode=Mode.MAX_LEFT)
    call(c.AND(entering, c.task(Task.LEVEL_IMAX)), CALL_IMAX_NONZERO, Task.LEVEL_NOT_ZERO, r['peer'])

    checking_left = c.mode(Mode.MAX_LEFT)
    c.ret(c.AND(checking_left, c.tag(CellTag.LEVEL_ZERO)), right)
    c.emit(c.AND(checking_left, c.NOT(c.tag(CellTag.LEVEL_ZERO))), mode=Mode.MAX_RIGHT, x=right)
    checking_right = c.mode(Mode.MAX_RIGHT)
    c.ret(c.AND(checking_right, c.tag(CellTag.LEVEL_ZERO)), left)
    call(c.AND(checking_right, c.NOT(c.tag(CellTag.LEVEL_ZERO))), CALL_MAX_COMPARE, Task.LEVEL_EQUAL, left, right)
    right_children = c.mode(Mode.MAX_RIGHT_CHILDREN)
    call(c.AND(right_children, c.tag(CellTag.LEVEL_MAX)), CALL_MAX_COMPARE, Task.LEVEL_EQUAL, left, a, 1)
    c.emit(c.AND(right_children, c.NOT(c.tag(CellTag.LEVEL_MAX))), mode=Mode.MAX_LEFT_CHILDREN, x=left)
    left_children = c.mode(Mode.MAX_LEFT_CHILDREN)
    call(c.AND(left_children, c.tag(CellTag.LEVEL_MAX)), CALL_MAX_COMPARE, Task.LEVEL_EQUAL, right, a, 3)
    offset(c.AND(left_children, c.NOT(c.tag(CellTag.LEVEL_MAX))))
    resumed = c.mode(Mode.MAX_EQUAL_RESULT)
    equal = c.NOT(c.eq(result, 0))
    stage = r['constructor_stage']
    at = lambda k: c.AND(resumed, c.eq(stage, k))
    c.stop(c.AND(resumed, c.lt(5, stage)), Outcome.INVALID, Reason.SYNTAX)
    c.ret(c.AND(at(0), equal), left)
    c.emit(c.AND(at(0), c.NOT(equal)), mode=Mode.MAX_RIGHT_CHILDREN, x=right)
    c.ret(c.AND(c.OR(at(1), at(2)), equal), right)
    call(c.AND(at(1), c.NOT(equal)), CALL_MAX_COMPARE, Task.LEVEL_EQUAL, left, b, 2)
    c.emit(c.AND(at(2), c.NOT(equal)), mode=Mode.MAX_LEFT_CHILDREN, x=left)
    c.ret(c.AND(c.OR(at(3), at(4)), equal), left)
    call(c.AND(at(3), c.NOT(equal)), CALL_MAX_COMPARE, Task.LEVEL_EQUAL, right, b, 4)
    offset(c.AND(at(4), c.NOT(equal)))
    c.ret(c.AND(at(5), equal), c.mux(c.lt(r['left_offset'], r['right_offset']), right, left))
    c.alloc(c.AND(at(5), c.NOT(equal)), (CellTag.LEVEL_MAX, left, right, 0))

    imax_right = c.mode(Mode.IMAX_RIGHT)
    c.ret(c.AND(imax_right, c.tag(CellTag.LEVEL_ZERO)), right)
    c.emit(c.AND(imax_right, c.NOT(c.tag(CellTag.LEVEL_ZERO))), mode=Mode.IMAX_LEFT, x=left)
    imax_left = c.mode(Mode.IMAX_LEFT)
    c.ret(c.AND(imax_left, c.tag(CellTag.LEVEL_ZERO)), right)
    c.emit(c.AND(imax_left, c.tag(CellTag.LEVEL_SUCC)), mode=Mode.IMAX_ONE, x=a)
    call(c.AND(imax_left, c.NOT(c.tag(CellTag.LEVEL_ZERO, CellTag.LEVEL_SUCC))),
        CALL_IMAX_COMPARE, Task.LEVEL_EQUAL, left, right)
    imax_one = c.mode(Mode.IMAX_ONE)
    c.ret(c.AND(imax_one, c.tag(CellTag.LEVEL_ZERO)), right)
    call(c.AND(imax_one, c.NOT(c.tag(CellTag.LEVEL_ZERO))), CALL_IMAX_COMPARE, Task.LEVEL_EQUAL, left, right)
