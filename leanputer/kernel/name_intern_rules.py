"""Compile content-based symbol lookup/allocation, no host name generation."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason

NO_NODE = (Mode.INTERN_STORE_ENTRY, Mode.INTERN_STORE_CELL, Mode.INTERN_STORE_VECTOR)
TAGS = {Mode.WALK: CellTag.VECTOR, Mode.INTERN_ROOT: CellTag.VECTOR,
    Mode.INTERN_CELL: CellTag.VECTOR_CELL, Mode.INTERN_ENTRY: CellTag.SYMBOL_ENTRY}


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)), c.eq(f['task'], Task.INTERN_NAME_PATH))
    validate = c.AND(returning, c.eq(f['phase'], 0)); truth = c.NOT(c.eq(r['r'], 0))
    c.stop(c.AND(validate, c.NOT(truth)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(validate, truth), task=Task.INTERN_NAME_PATH, mode=Mode.INTERN_ROOT, x=r['symbols_root'])
    searched = c.AND(returning, c.eq(f['phase'], 1)); more = c.lt(1, r['intern_remaining'])
    c.emit(c.AND(searched, truth), task=Task.INTERN_NAME_PATH, sp=top); c.ret(c.AND(searched, truth), r['intern_candidate'])
    c.emit(c.AND(searched, c.NOT(truth), more), task=Task.INTERN_NAME_PATH, mode=Mode.INTERN_CELL, x=r['intern_next'], intern_remaining=c.sub(r['intern_remaining'], 1))
    c.emit(c.AND(searched, c.NOT(truth), c.NOT(more)), task=Task.INTERN_NAME_PATH, mode=Mode.INTERN_STORE_ENTRY)
    c.stop(c.AND(returning, c.NOT(c.OR(c.eq(f['phase'], 0), c.eq(f['phase'], 1)))), Outcome.INVALID, Reason.SYNTAX)
    active = c.task(Task.INTERN_NAME_PATH); at = lambda m: c.AND(active, c.mode(m))
    init = at(Mode.WALK); room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, room)
    c.write('stack', init, r['sp'], (0, r['x'], 0, Task.INTERN_NAME_PATH, 0, 0))
    c.emit(init, sp=c.add(r['sp'], 1), task=Task.COMPARE_NAME_PATH, peer=r['x'], path_prefix=0)
    root = at(Mode.INTERN_ROOT); valid = c.AND(c.eq(n['c'], VectorKind.REFERENCES), c.eq(c.mux(c.eq(n['a'], 0), 0, 1), c.mux(c.eq(n['b'], 0), 0, 1)))
    c.stop(c.AND(root, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    root = c.AND(root, valid); empty = c.eq(n['a'], 0)
    c.emit(root, intern_length=n['a'], intern_head=n['b'], intern_maximum=0, intern_remaining=n['a'])
    c.emit(c.AND(root, empty), mode=Mode.INTERN_STORE_ENTRY)
    c.emit(c.AND(root, c.NOT(empty)), mode=Mode.INTERN_CELL, x=n['b'])
    cell = at(Mode.INTERN_CELL); valid = c.AND(c.NOT(c.eq(r['intern_remaining'], 0)),
        c.eq(c.mux(c.eq(n['b'], 0), 0, 1), c.mux(c.lt(1, r['intern_remaining']), 1, 0)))
    c.stop(c.AND(cell, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(cell, valid), intern_next=n['b'], mode=Mode.INTERN_ENTRY, x=n['a'])
    entry = at(Mode.INTERN_ENTRY); valid = c.NOT(c.eq(n['a'], 0))
    c.stop(c.AND(entry, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX); entry = c.AND(entry, valid)
    c.write('stack', entry, top, (1, f['original'], 0, Task.INTERN_NAME_PATH, 0, 0))
    c.emit(entry, intern_candidate=n['a'], intern_maximum=c.mux(c.lt(r['intern_maximum'], n['a']), n['a'], r['intern_maximum']),
        task=Task.COMPARE_NAME_PATH, mode=Mode.WALK, x=f['original'], peer=n['b'], path_prefix=0)
    store = at(Mode.INTERN_STORE_ENTRY); overflow = c.eq(r['intern_maximum'], (1 << c.width)-1)
    c.stop(c.AND(store, overflow), Outcome.RESOURCE, Reason.INDEX)
    room = c.lt(c.add(r['free'], 2), c.cfg.heap)
    c.stop(c.AND(store, c.NOT(overflow), c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); store = c.AND(store, c.NOT(overflow), room)
    symbol = c.add(r['intern_maximum'], 1)
    c.write('heap', store, r['free'], (CellTag.SYMBOL_ENTRY, symbol, f['original'], 0))
    c.emit(store, free=c.add(r['free'], 1), intern_symbol=symbol, intern_entry=r['free'], mode=Mode.INTERN_STORE_CELL)
    cell = at(Mode.INTERN_STORE_CELL)
    c.write('heap', cell, r['free'], (CellTag.VECTOR_CELL, r['intern_entry'], r['intern_head'], 0))
    c.emit(cell, free=c.add(r['free'], 1), intern_link=r['free'], mode=Mode.INTERN_STORE_VECTOR)
    vector = at(Mode.INTERN_STORE_VECTOR)
    c.write('heap', vector, r['free'], (CellTag.VECTOR, c.add(r['intern_length'], 1), r['intern_link'], VectorKind.REFERENCES))
    c.emit(vector, free=c.add(r['free'], 1), symbols_root=r['free'], sp=top); c.ret(vector, r['intern_symbol'])
