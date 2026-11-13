"""Lower the general raw scheme-parameter list and uniqueness scan."""
from .native_cells import VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def emit_rules(c):
    r, n = c.r, c.read['node']
    a, b = n['a'], n['b']
    word_bool = lambda word: c.mux(c.eq(word, 0), 0, 1)
    entering = c.AND(c.mode(Mode.WALK), c.task(Task.LOAD_PARAMETERS))
    shape = c.AND(c.eq(n['c'], VectorKind.SYMBOLS), c.eq(word_bool(a), word_bool(b)))
    c.stop(c.AND(entering, c.NOT(shape)), Outcome.INVALID, Reason.SYNTAX)
    enough = c.NOT(c.lt(c.cfg.context, a))
    c.stop(c.AND(entering, shape, c.NOT(enough)), Outcome.RESOURCE, Reason.CONTEXT)
    entering = c.AND(entering, shape, enough)
    c.emit(entering, ctx=0, count=a, arg_base=0, local_base=0, zip_count=a, zip_remaining=a, parameter_head=b)
    c.ret(c.AND(entering, c.eq(a, 0)), 0)
    c.emit(c.AND(entering, c.NOT(c.eq(a, 0))), mode=Mode.PARAMETER_CELL, x=b)
    cell = c.mode(Mode.PARAMETER_CELL)
    more = c.lt(1, r['zip_remaining'])
    valid = c.AND(c.NOT(c.eq(a, 0)), c.NOT(c.eq(r['zip_remaining'], 0)), c.eq(word_bool(b), c.mux(more, 1, 0)))
    c.stop(c.AND(cell, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(cell, valid), zip_symbol=a, zip_parameter_next=b, mode=Mode.PARAMETER_DUPLICATE, i=0)
    scanning = c.mode(Mode.PARAMETER_DUPLICATE)
    within = c.lt(r['i'], r['ctx'])
    matched = c.eq(c.read['operand']['value'], r['zip_symbol'])
    c.stop(c.AND(scanning, within, matched), Outcome.INVALID, Reason.DUPLICATE_PARAMETER)
    c.emit(c.AND(scanning, within, c.NOT(matched)), i=c.add(r['i'], 1))
    append = c.AND(scanning, c.NOT(within))
    c.write('context', append, r['ctx'], (r['zip_symbol'],))
    c.emit(append, ctx=c.add(r['ctx'], 1), zip_remaining=c.sub(r['zip_remaining'], 1))
    c.emit(c.AND(append, more), mode=Mode.PARAMETER_CELL, x=r['zip_parameter_next'])
    c.ret(c.AND(append, c.NOT(more)), r['count'])
