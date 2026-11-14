"""Compile generic raw Pi parameter specialization using shared bulk substitution."""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason

TAGS = {Mode.PI_PARAMS_HEADER: CellTag.VECTOR, Mode.PI_PARAMS_CELL: CellTag.VECTOR_CELL}
EXPRESSION_MODES = (Mode.WALK, Mode.PI_PARAMS_ARGUMENT, Mode.PI_PARAMS_STRIP)


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)), c.eq(f['task'], Task.INSTANTIATE_PI_PARAMETERS))
    valid = c.eq(f['phase'], 0)
    c.stop(c.AND(returning, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(returning, valid), task=Task.INSTANTIATE_PI_PARAMETERS, sp=top, ctx=f['depth'], count=f['first'], arg_base=f['second'])
    c.ret(c.AND(returning, valid), r['r'])
    active = c.task(Task.INSTANTIATE_PI_PARAMETERS); at = lambda m: c.AND(active, c.mode(m))
    init = at(Mode.WALK); room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, room)
    c.write('stack', init, r['sp'], (0, r['x'], r['ctx'], Task.INSTANTIATE_PI_PARAMETERS, r['count'], r['arg_base']))
    c.emit(init, sp=c.add(r['sp'], 1), mode=Mode.PI_PARAMS_HEADER, x=r['pi_parameter_vector'])
    header = at(Mode.PI_PARAMS_HEADER)
    valid = c.AND(c.eq(n['c'], VectorKind.REFERENCES), c.eq(c.mux(c.eq(n['a'], 0), 0, 1), c.mux(c.eq(n['b'], 0), 0, 1)), c.NOT(c.lt(n['a'], r['pi_parameter_limit'])))
    c.stop(c.AND(header, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    wide = c.g.add(c.g.fit(r['ctx'], c.width+1), c.g.fit(r['pi_parameter_limit'], c.width+1))
    fits = c.NOT(c.g.lt(c.g.const(c.cfg.context, c.width+1), wide))
    c.stop(c.AND(header, valid, c.NOT(fits)), Outcome.RESOURCE, Reason.CONTEXT)
    header = c.AND(header, valid, fits); empty = c.eq(r['pi_parameter_limit'], 0)
    c.emit(c.AND(header, empty), sp=top); c.ret(c.AND(header, empty), f['original'])
    c.emit(c.AND(header, c.NOT(empty)), pi_parameter_count=r['pi_parameter_limit'], pi_parameter_remaining=r['pi_parameter_limit'], pi_parameter_vector_remaining=n['a'],
        pi_parameter_cursor=c.sub(c.add(r['ctx'], r['pi_parameter_limit']), 1), mode=Mode.PI_PARAMS_CELL, x=n['b'])
    cell = at(Mode.PI_PARAMS_CELL); more = c.lt(1, r['pi_parameter_remaining'])
    valid = c.AND(c.NOT(c.eq(r['pi_parameter_remaining'], 0)), c.eq(c.mux(c.eq(n['b'], 0), 0, 1), c.mux(c.lt(1,r['pi_parameter_vector_remaining']), 1, 0)),
        c.NOT(c.eq(n['a'], 0)), c.lt(n['a'], r['free']))
    c.stop(c.AND(cell, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(cell, valid), pi_parameter_next=n['b'], mode=Mode.PI_PARAMS_ARGUMENT, x=n['a'])
    argument = at(Mode.PI_PARAMS_ARGUMENT)
    c.write('context', argument, r['pi_parameter_cursor'], (r['x'],))
    c.emit(argument,pi_parameter_vector_remaining=c.sub(r['pi_parameter_vector_remaining'],1))
    c.emit(c.AND(argument, more), pi_parameter_remaining=c.sub(r['pi_parameter_remaining'], 1),
        pi_parameter_cursor=c.sub(r['pi_parameter_cursor'], 1), mode=Mode.PI_PARAMS_CELL, x=r['pi_parameter_next'])
    c.emit(c.AND(argument, c.NOT(more)), pi_parameter_remaining=r['pi_parameter_count'], mode=Mode.PI_PARAMS_STRIP, x=f['original'])
    strip = at(Mode.PI_PARAMS_STRIP); empty = c.eq(r['pi_parameter_remaining'], 0)
    c.emit(c.AND(strip, empty), task=Task.INSTANTIATE, mode=Mode.WALK, count=r['pi_parameter_count'], arg_base=f['depth'], start=0, depth=0)
    c.stop(c.AND(strip, c.NOT(empty), c.NOT(c.tag(Tag.PI))), Outcome.INVALID, Reason.EXPECT_PI)
    c.emit(c.AND(strip, c.NOT(empty), c.tag(Tag.PI)), pi_parameter_remaining=c.sub(r['pi_parameter_remaining'], 1), x=n['b'])
