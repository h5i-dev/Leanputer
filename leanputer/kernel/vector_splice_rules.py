"""Compile generic typed vector splicing with immutable suffix sharing."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason

NO_NODE = (Mode.SPLICE_FINISH,)
TAGS = {Mode.WALK: CellTag.VECTOR, Mode.SPLICE_SUFFIX: CellTag.VECTOR,
    Mode.SPLICE_SKIP: CellTag.VECTOR_CELL, Mode.SPLICE_REVERSED: CellTag.VECTOR,
    Mode.SPLICE_COPY: CellTag.VECTOR_CELL}


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)), c.eq(f['task'], Task.VECTOR_SPLICE))
    valid = c.eq(f['phase'], 0)
    c.stop(c.AND(returning, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(returning, valid), task=Task.VECTOR_SPLICE, mode=Mode.SPLICE_REVERSED, x=r['r'])
    active = c.task(Task.VECTOR_SPLICE); at = lambda m: c.AND(active, c.mode(m))
    wb = lambda v: c.mux(c.eq(v, 0), 0, 1)
    shape = c.AND(c.eq(n['c'], r['splice_role']), c.eq(wb(n['a']), wb(n['b'])))
    def reverse(guard):
        c.emit(guard, task=Task.REVERSE_LIST, mode=Mode.WALK, x=r['splice_prefix_head'], reverse_length=r['splice_prefix_length'], depth=0)
    init = at(Mode.WALK)
    valid = c.AND(shape, c.OR(*(c.eq(r['splice_role'], role) for role in VectorKind)), c.NOT(c.eq(r['peer'], 0)), c.lt(r['peer'], r['free']))
    c.stop(c.AND(init, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, valid, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, valid, room)
    c.write('stack', init, r['sp'], (0, 0, 0, Task.VECTOR_SPLICE, 0, 0))
    c.emit(init, sp=c.add(r['sp'], 1), splice_prefix_length=n['a'], splice_prefix_head=n['b'], mode=Mode.SPLICE_SUFFIX, x=r['peer'])
    suffix = at(Mode.SPLICE_SUFFIX); valid = c.AND(shape, c.NOT(c.lt(n['a'], r['splice_skip'])))
    c.stop(c.AND(suffix, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    suffix, length = c.checked_add(c.AND(suffix, valid), r['splice_prefix_length'], c.sub(n['a'], r['splice_skip']))
    c.emit(suffix, splice_length=length, splice_suffix_remaining=n['a'], splice_tail=n['b'])
    skipping = c.NOT(c.eq(r['splice_skip'], 0))
    c.emit(c.AND(suffix, skipping), mode=Mode.SPLICE_SKIP, x=n['b']); reverse(c.AND(suffix, c.NOT(skipping)))
    skip = at(Mode.SPLICE_SKIP)
    valid = c.AND(c.NOT(c.eq(r['splice_skip'], 0)), c.NOT(c.eq(r['splice_suffix_remaining'], 0)),
        c.eq(wb(n['b']), c.mux(c.lt(1, r['splice_suffix_remaining']), 1, 0)))
    c.stop(c.AND(skip, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX); skip = c.AND(skip, valid)
    more = c.lt(1, r['splice_skip'])
    c.emit(skip, splice_skip=c.sub(r['splice_skip'], 1), splice_suffix_remaining=c.sub(r['splice_suffix_remaining'], 1), splice_tail=n['b'])
    c.emit(c.AND(skip, more), x=n['b']); reverse(c.AND(skip, c.NOT(more)))
    reversed_ = at(Mode.SPLICE_REVERSED)
    valid = c.AND(c.eq(n['c'], VectorKind.REFERENCES), c.eq(n['a'], r['splice_prefix_length']), c.eq(wb(n['a']), wb(n['b'])))
    c.stop(c.AND(reversed_, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    empty = c.eq(n['a'], 0)
    c.emit(c.AND(reversed_, valid, empty), mode=Mode.SPLICE_FINISH)
    c.emit(c.AND(reversed_, valid, c.NOT(empty)), splice_remaining=n['a'], mode=Mode.SPLICE_COPY, x=n['b'])
    copy = at(Mode.SPLICE_COPY); more = c.lt(1, r['splice_remaining'])
    valid = c.AND(c.NOT(c.eq(r['splice_remaining'], 0)), c.eq(wb(n['b']), c.mux(more, 1, 0)))
    c.stop(c.AND(copy, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(copy, valid, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); copy = c.AND(copy, valid, room)
    c.write('heap', copy, r['free'], (CellTag.VECTOR_CELL, n['a'], r['splice_tail'], 0))
    c.emit(copy, free=c.add(r['free'], 1), splice_tail=r['free'], splice_remaining=c.sub(r['splice_remaining'], 1), mode=c.mux(more, Mode.SPLICE_COPY, Mode.SPLICE_FINISH))
    c.emit(c.AND(copy, more), x=n['b'])
    finish = at(Mode.SPLICE_FINISH); room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(finish, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); finish = c.AND(finish, room)
    c.write('heap', finish, r['free'], (CellTag.VECTOR, r['splice_length'], r['splice_tail'], r['splice_role']))
    c.emit(finish, free=c.add(r['free'], 1), sp=top); c.ret(finish, r['free'])
