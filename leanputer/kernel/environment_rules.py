"""Compile private checked-signature traversal. No raw types are inferred."""
from .traversal_machine import Mode, Task, Outcome, Reason


def emit_rules(c):
    r, n = c.r, c.read['node']
    entering = c.AND(c.mode(Mode.WALK), c.task(Task.ENV_LOOKUP))
    empty = c.eq(r['env_head'], 0)
    c.ret(c.AND(entering, empty), 0)
    c.emit(c.AND(entering, c.NOT(empty)), mode=Mode.ENV_CELL, x=r['env_head'])
    cell = c.mode(Mode.ENV_CELL)
    valid = c.AND(c.NOT(c.eq(n['a'], 0)), c.lt(n['a'], r['free']), c.lt(n['b'], r['free']))
    c.stop(c.AND(cell, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(cell, valid), mode=Mode.ENV_SIGNATURE, x=n['a'], env_next=n['b'])
    signature = c.mode(Mode.ENV_SIGNATURE)
    valid = c.AND(c.NOT(c.eq(n['b'], 0)), c.lt(n['b'], r['free']), c.NOT(c.eq(n['c'], 0)), c.lt(n['c'], r['free']))
    c.stop(c.AND(signature, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    signature = c.AND(signature, valid)
    matched = c.eq(n['a'], r['query_symbol'])
    c.ret(c.AND(signature, matched), r['x'])
    tail_empty = c.eq(r['env_next'], 0)
    c.ret(c.AND(signature, c.NOT(matched), tail_empty), 0)
    c.emit(c.AND(signature, c.NOT(matched), c.NOT(tail_empty)), mode=Mode.ENV_CELL, x=r['env_next'])
