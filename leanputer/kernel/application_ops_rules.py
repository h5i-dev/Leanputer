"""Compile get_app_fn/get_app_args and generic contiguous vector application."""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason

NO_NODE = (Mode.SPINE_VECTOR, Mode.SPINE_RESULT)
SLICE_TAGS = {Mode.WALK: CellTag.VECTOR, Mode.SLICE_CELL: CellTag.VECTOR_CELL}


def emit_rules(c):
    r, n = c.r, c.read['node']
    spine = c.task(Task.APPLICATION_SPINE)
    at = lambda mode: c.AND(spine, c.mode(mode))
    c.emit(at(Mode.WALK), spine_head=0, spine_count=0, mode=Mode.SPINE_SCAN)
    scan = at(Mode.SPINE_SCAN); app = c.tag(Tag.APP); room = c.lt(r['free'], c.cfg.heap)
    c.emit(c.AND(scan, c.NOT(app)), spine_function=r['x'], mode=Mode.SPINE_VECTOR)
    c.stop(c.AND(scan, app, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP)
    step = c.AND(scan, app, room)
    c.write('heap', step, r['free'], (CellTag.VECTOR_CELL, n['b'], r['spine_head'], 0))
    c.emit(step, free=c.add(r['free'], 1), spine_head=r['free'], spine_count=c.add(r['spine_count'], 1), x=n['a'])
    vector = at(Mode.SPINE_VECTOR); room = c.lt(c.add(r['free'], 1), c.cfg.heap)
    c.stop(c.AND(vector, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); vector = c.AND(vector, room)
    c.write('heap', vector, r['free'], (CellTag.VECTOR, r['spine_count'], r['spine_head'], VectorKind.REFERENCES))
    c.emit(vector, free=c.add(r['free'], 1), spine_arguments=r['free'], mode=Mode.SPINE_RESULT)
    done = at(Mode.SPINE_RESULT)
    c.write('heap', done, r['free'], (CellTag.APPLICATION_SPINE, r['spine_function'], r['spine_arguments'], 0))
    c.emit(done, free=c.add(r['free'], 1)); c.ret(done, r['free'])
    apply = c.task(Task.APPLY_VECTOR_SLICE); at = lambda mode: c.AND(apply, c.mode(mode))
    init = at(Mode.WALK)
    valid = c.AND(c.eq(n['c'], VectorKind.REFERENCES), c.eq(c.mux(c.eq(n['a'], 0), 0, 1), c.mux(c.eq(n['b'], 0), 0, 1)),
        c.NOT(c.lt(n['a'], r['slice_start'])), c.NOT(c.lt(c.sub(n['a'], r['slice_start']), r['slice_take'])))
    c.stop(c.AND(init, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    empty = c.eq(r['slice_take'], 0)
    c.ret(c.AND(init, valid, empty), r['slice_body'])
    c.emit(c.AND(init, valid, c.NOT(empty)), slice_remaining=n['a'], mode=Mode.SLICE_CELL, x=n['b'])
    cell = at(Mode.SLICE_CELL); more = c.lt(1, r['slice_remaining'])
    valid = c.AND(c.NOT(c.eq(r['slice_remaining'], 0)), c.eq(c.mux(c.eq(n['b'], 0), 0, 1), c.mux(more, 1, 0)))
    c.stop(c.AND(cell, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    skip = c.NOT(c.eq(r['slice_start'], 0))
    c.emit(c.AND(cell, valid, skip), slice_start=c.sub(r['slice_start'], 1), slice_remaining=c.sub(r['slice_remaining'], 1), x=n['b'])
    c.emit(c.AND(cell, valid, c.NOT(skip)), slice_next=n['b'], mode=Mode.SLICE_ARGUMENT, x=n['a'])
    argument = at(Mode.SLICE_ARGUMENT); room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(argument, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); argument = c.AND(argument, room)
    c.write('heap', argument, r['free'], (Tag.APP, r['slice_body'], r['x'], 0))
    c.emit(argument, free=c.add(r['free'], 1), slice_body=r['free'], slice_take=c.sub(r['slice_take'], 1), slice_remaining=c.sub(r['slice_remaining'], 1))
    more = c.lt(1, r['slice_take'])
    c.emit(c.AND(argument, more), mode=Mode.SLICE_CELL, x=r['slice_next'])
    c.ret(c.AND(argument, c.NOT(more)), r['free'])

    reference = c.task(Task.VECTOR_REFERENCE); at = lambda mode: c.AND(reference, c.mode(mode))
    init = at(Mode.WALK)
    valid = c.AND(c.eq(n['c'], VectorKind.REFERENCES), c.eq(c.mux(c.eq(n['a'], 0), 0, 1), c.mux(c.eq(n['b'], 0), 0, 1)))
    c.stop(c.AND(init, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    present = c.lt(r['vector_index'], n['a'])
    c.ret(c.AND(init, valid, c.NOT(present)), 0)
    c.emit(c.AND(init, valid, present), reference_remaining=n['a'], mode=Mode.SLICE_CELL, x=n['b'])
    cell = at(Mode.SLICE_CELL); more = c.lt(1, r['reference_remaining'])
    valid = c.AND(c.NOT(c.eq(r['reference_remaining'], 0)), c.eq(c.mux(c.eq(n['b'], 0), 0, 1), c.mux(more, 1, 0)))
    c.stop(c.AND(cell, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    found = c.eq(r['vector_index'], 0)
    c.ret(c.AND(cell, valid, found), n['a'])
    c.emit(c.AND(cell, valid, c.NOT(found)), vector_index=c.sub(r['vector_index'], 1), reference_remaining=c.sub(r['reference_remaining'], 1), x=n['b'])
