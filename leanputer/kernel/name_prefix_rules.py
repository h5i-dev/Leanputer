"""Compile source structured prefix replacement using shared generic services."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)), c.eq(f['task'], Task.REPLACE_NAME_PREFIX))
    phase = lambda p: c.AND(returning, c.eq(f['phase'], p))
    def call(guard, p, task, x, old=None, new=None, path=None, **updates):
        c.write('stack', guard, top, (p, f['original'], f['depth'] if old is None else old, Task.REPLACE_NAME_PREFIX,
            f['first'] if new is None else new, f['second'] if path is None else path))
        c.emit(guard, task=task, mode=Mode.WALK, x=x, depth=0, **updates)
    call(phase(0), 1, Task.GET_NAME_PATH, r['symbols_root'], path=r['r'], query_symbol=f['depth'])
    call(phase(1), 2, Task.COMPARE_NAME_PATH, r['r'], old=r['r'], peer=f['second'], path_prefix=1)
    checked = phase(2); matched = c.NOT(c.eq(r['r'], 0))
    c.emit(c.AND(checked, c.NOT(matched)), task=Task.REPLACE_NAME_PREFIX, sp=top); c.ret(c.AND(checked, c.NOT(matched)), f['original'])
    call(c.AND(checked, matched), 3, Task.GET_NAME_PATH, r['symbols_root'], query_symbol=f['first'])
    c.write('stack', phase(3), top, (3, f['original'], f['depth'], Task.REPLACE_NAME_PREFIX, r['r'], f['second']))
    c.emit(phase(3), task=Task.REPLACE_NAME_PREFIX, mode=Mode.REPLACE_PREFIX_HEADER, x=f['depth'])
    call(phase(4), 5, Task.INTERN_NAME_PATH, r['r'])
    c.emit(phase(5), task=Task.REPLACE_NAME_PREFIX, sp=top); c.ret(phase(5), r['r'])
    valid_phase = c.OR(*(c.eq(f['phase'], p) for p in range(6)))
    c.stop(c.AND(returning, c.NOT(valid_phase)), Outcome.INVALID, Reason.SYNTAX)
    active = c.task(Task.REPLACE_NAME_PREFIX); init = c.AND(active, c.mode(Mode.WALK)); room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, room)
    c.write('stack', init, r['sp'], (0, r['query_symbol'], r['name_parent_symbol'], Task.REPLACE_NAME_PREFIX, r['name_candidate_symbol'], 0))
    c.emit(init, sp=c.add(r['sp'], 1), task=Task.GET_NAME_PATH, x=r['symbols_root'])
    header = c.AND(active, c.mode(Mode.REPLACE_PREFIX_HEADER))
    valid = c.AND(c.eq(n['c'], VectorKind.REFERENCES), c.eq(c.mux(c.eq(n['a'], 0), 0, 1), c.mux(c.eq(n['b'], 0), 0, 1)))
    c.stop(c.AND(header, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    call(c.AND(header, valid), 4, Task.VECTOR_SPLICE, f['first'], peer=f['second'], splice_role=VectorKind.REFERENCES, splice_skip=n['a'])
