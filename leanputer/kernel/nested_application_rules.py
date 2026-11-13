"""Compile the generic source nested-application condition, counts as data."""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason

NO_NODE = (Mode.NESTED_APP_SELECT, Mode.NESTED_APP_RESULT)
TAGS = {Mode.NESTED_APP_SPINE: CellTag.APPLICATION_SPINE, Mode.NESTED_APP_ORIGIN: CellTag.BLOCK_ORIGIN,
    Mode.NESTED_APP_BLOCK: CellTag.RAW_BLOCK, Mode.NESTED_APP_ARGUMENTS: CellTag.VECTOR}


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)), c.eq(f['task'], Task.IS_NESTED_APPLICATION))
    phase = lambda p: c.AND(returning, c.eq(f['phase'], p))
    def call(guard, p, task, x, parameter=None, **updates):
        c.write('stack', guard, top, (p, f['original'] if parameter is None else parameter, f['depth'], Task.IS_NESTED_APPLICATION, f['first'], f['second']))
        c.emit(guard, task=task, mode=Mode.WALK, x=x, depth=0, **updates)
    def finish(guard):
        c.emit(guard, task=Task.IS_NESTED_APPLICATION, sp=top); c.ret(guard, 0)
    split = phase(0)
    c.write('stack', split, top, (0, f['original'], f['depth'], Task.IS_NESTED_APPLICATION, r['r'], f['second']))
    c.emit(split, task=Task.IS_NESTED_APPLICATION, mode=Mode.NESTED_APP_SPINE, x=r['r'])
    looked = phase(1); found = c.NOT(c.eq(r['r'], 0))
    finish(c.AND(looked, c.NOT(found))); looked = c.AND(looked, found)
    c.write('stack', looked, top, (1, f['original'], r['r'], Task.IS_NESTED_APPLICATION, f['first'], f['second']))
    c.emit(looked, task=Task.IS_NESTED_APPLICATION, mode=Mode.NESTED_APP_ORIGIN, x=r['r'])
    call(phase(2), 3, Task.HAS_RAW_FAMILIES, r['r'], parameter=r['r'])
    current = c.OR(c.NOT(c.eq(r['nested_has_current'], 0)), c.NOT(c.eq(r['r'], 0)))
    c.emit(phase(3), nested_has_current=c.mux(current, 1, 0))
    call(phase(3), 4, Task.HAS_LOOSE_BVARS, f['original'])
    checked = phase(4); loose = c.OR(c.NOT(c.eq(r['nested_has_loose'], 0)), c.NOT(c.eq(r['r'], 0)))
    more = c.lt(c.add(r['nested_parameter_index'], 1), r['nested_parameter_count'])
    c.emit(checked, nested_has_loose=c.mux(loose, 1, 0))
    c.emit(c.AND(checked, more), task=Task.IS_NESTED_APPLICATION, mode=Mode.NESTED_APP_SELECT, nested_parameter_index=c.add(r['nested_parameter_index'], 1))
    has_current = c.NOT(c.eq(r['nested_has_current'], 0)); last = c.AND(checked, c.NOT(more))
    finish(c.AND(last, c.NOT(has_current)))
    c.stop(c.AND(last, has_current, loose), Outcome.INVALID, Reason.INVALID_NESTED_PARAMETERS)
    c.emit(c.AND(last, has_current, c.NOT(loose)), task=Task.IS_NESTED_APPLICATION, mode=Mode.NESTED_APP_RESULT)
    c.stop(c.AND(returning, c.NOT(c.OR(*(c.eq(f['phase'], p) for p in range(5))))), Outcome.INVALID, Reason.SYNTAX)
    active = c.task(Task.IS_NESTED_APPLICATION); at = lambda m: c.AND(active, c.mode(m))
    init = at(Mode.WALK); app = c.tag(Tag.APP); room = c.lt(r['sp'], c.cfg.stack)
    c.ret(c.AND(init, c.NOT(app)), 0)
    c.stop(c.AND(init, app, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, app, room)
    c.write('stack', init, r['sp'], (0, 0, 0, Task.IS_NESTED_APPLICATION, 0, 0))
    c.emit(init, sp=c.add(r['sp'], 1), task=Task.APPLICATION_SPINE)
    split = at(Mode.NESTED_APP_SPINE)
    c.write('stack', split, top, (f['phase'], f['original'], f['depth'], Task.IS_NESTED_APPLICATION, f['first'], n['b']))
    c.emit(split, mode=Mode.NESTED_APP_HEAD, x=n['a'])
    head = at(Mode.NESTED_APP_HEAD); constant = c.tag(Tag.CONST)
    finish(c.AND(head, c.NOT(constant)))
    call(c.AND(head, constant), 1, Task.PRIOR_BLOCK_LOOKUP, r['nested_registry_head'], query_symbol=n['a'])
    c.emit(at(Mode.NESTED_APP_ORIGIN), mode=Mode.NESTED_APP_BLOCK, x=n['a'])
    c.emit(at(Mode.NESTED_APP_BLOCK), nested_parameter_count=n['a'], mode=Mode.NESTED_APP_ARGUMENTS, x=f['second'])
    arguments = at(Mode.NESTED_APP_ARGUMENTS)
    valid = c.AND(c.eq(n['c'], VectorKind.REFERENCES), c.eq(c.mux(c.eq(n['a'], 0), 0, 1), c.mux(c.eq(n['b'], 0), 0, 1)))
    c.stop(c.AND(arguments, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    enough = c.AND(c.NOT(c.lt(n['a'], r['nested_parameter_count'])), c.NOT(c.eq(r['nested_parameter_count'], 0)))
    finish(c.AND(arguments, valid, c.NOT(enough)))
    c.emit(c.AND(arguments, valid, enough), nested_parameter_index=0, nested_has_current=0, nested_has_loose=0, mode=Mode.NESTED_APP_SELECT)
    call(at(Mode.NESTED_APP_SELECT), 2, Task.VECTOR_REFERENCE, f['second'], vector_index=r['nested_parameter_index'])
    result = at(Mode.NESTED_APP_RESULT); room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(result, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); result = c.AND(result, room)
    c.write('heap', result, r['free'], (CellTag.NESTED_APPLICATION, f['depth'], f['first'], 0))
    c.emit(result, free=c.add(r['free'], 1), sp=top); c.ret(result, r['free'])
