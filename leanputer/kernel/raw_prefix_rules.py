"""Compile raw Pi/Lam prefix traversal using shared fresh/instantiate services."""
from .arena import Tag
from .traversal_machine import Mode, Task, Outcome, Reason


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)), c.eq(f['task'], Task.OPEN_RAW_PREFIX))
    fresh = c.AND(returning, c.eq(f['phase'], 0))
    c.write('stack', fresh, top, (1, 0, f['depth'], Task.OPEN_RAW_PREFIX, 0, 0))
    c.emit(fresh, task=Task.INSTANTIATE_ONE, mode=Mode.WALK, x=f['original'], substitution=r['r'], depth=0)
    substituted = c.AND(returning, c.eq(f['phase'], 1))
    c.emit(substituted, task=Task.OPEN_RAW_PREFIX, mode=Mode.RAW_PREFIX_LOOP, x=r['r'], raw_prefix_remaining=c.sub(f['depth'], 1))
    c.stop(c.AND(returning, c.NOT(c.OR(c.eq(f['phase'], 0), c.eq(f['phase'], 1)))), Outcome.INVALID, Reason.SYNTAX)
    active = c.task(Task.OPEN_RAW_PREFIX); at = lambda m: c.AND(active, c.mode(m))
    init, end = c.checked_add(at(Mode.WALK), r['ctx'], r['raw_prefix_count'])
    fits = c.NOT(c.lt(c.cfg.context, end)); room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, c.NOT(fits)), Outcome.RESOURCE, Reason.CONTEXT)
    c.stop(c.AND(init, fits, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, fits, room)
    c.write('stack', init, r['sp'], (0, 0, 0, Task.OPEN_RAW_PREFIX, 0, 0))
    c.emit(init, sp=c.add(r['sp'], 1), raw_prefix_remaining=r['raw_prefix_count'], mode=Mode.RAW_PREFIX_LOOP)
    loop = at(Mode.RAW_PREFIX_LOOP); empty = c.eq(r['raw_prefix_remaining'], 0)
    c.emit(c.AND(loop, empty), sp=top); c.ret(c.AND(loop, empty), r['x'])
    binder = c.eq(n['tag'], r['open_tag'])
    c.stop(c.AND(loop, c.NOT(empty), c.NOT(binder)), Outcome.INVALID, c.mux(c.eq(r['open_tag'], Tag.PI), Reason.EXPECT_PI, Reason.EXPECT_LAM))
    descend = c.AND(loop, c.NOT(empty), binder)
    c.write('stack', descend, top, (0, n['b'], r['raw_prefix_remaining'], Task.OPEN_RAW_PREFIX, 0, 0))
    c.emit(descend, task=Task.FRESH_LOCAL, mode=Mode.WALK, x=n['a'], binder_info=n['c'])
