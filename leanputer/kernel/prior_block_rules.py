"""Compile pure original-block ownership lookup, never a source-admission flag."""
from .native_cells import CellTag
from .traversal_machine import Mode, Task, Outcome, Reason

TAGS = {Mode.PRIOR_BLOCK_CELL: CellTag.VECTOR_CELL, Mode.PRIOR_BLOCK_ORIGIN: CellTag.BLOCK_ORIGIN}


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)), c.eq(f['task'], Task.PRIOR_BLOCK_LOOKUP))
    valid = c.eq(f['phase'], 0); found = c.NOT(c.eq(r['r'], 0)); more = c.NOT(c.eq(f['second'], 0))
    c.stop(c.AND(returning, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    done = c.AND(returning, valid, c.OR(found, c.NOT(more)))
    c.emit(done, task=Task.PRIOR_BLOCK_LOOKUP, sp=top); c.ret(done, c.mux(found, f['original'], 0))
    c.emit(c.AND(returning, valid, c.NOT(found), more), task=Task.PRIOR_BLOCK_LOOKUP, mode=Mode.PRIOR_BLOCK_CELL, x=f['second'])
    active = c.task(Task.PRIOR_BLOCK_LOOKUP); at = lambda m: c.AND(active, c.mode(m))
    init = at(Mode.WALK); empty = c.eq(r['x'], 0); room = c.lt(r['sp'], c.cfg.stack)
    c.ret(c.AND(init, empty), 0)
    c.stop(c.AND(init, c.NOT(empty), c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
    init = c.AND(init, c.NOT(empty), room)
    c.write('stack', init, r['sp'], (0, 0, 0, Task.PRIOR_BLOCK_LOOKUP, 0, 0))
    c.emit(init, sp=c.add(r['sp'], 1), mode=Mode.PRIOR_BLOCK_CELL)
    c.emit(at(Mode.PRIOR_BLOCK_CELL), prior_block_next=n['b'], mode=Mode.PRIOR_BLOCK_ORIGIN, x=n['a'])
    origin = at(Mode.PRIOR_BLOCK_ORIGIN)
    c.write('stack', origin, top, (0, r['x'], 0, Task.PRIOR_BLOCK_LOOKUP, 0, r['prior_block_next']))
    c.emit(origin, task=Task.SIGNATURE_VECTOR_LOOKUP, mode=Mode.WALK, x=n['c'], depth=0)
