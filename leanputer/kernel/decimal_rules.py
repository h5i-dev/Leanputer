"""Compile counter decimal formatting, no host conversion/lookup schedule."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def divmod10(c, value):
    """Binary long division by the formatting radix, fixed by word width.

    The partial remainder is below10, so appending one bit fits five bits.
    This is combinational unsigned arithmetic, not a CPU instruction emulator.
    """
    g = c.g; remainder = g.const(0, 5); quotient = [g.zero]*len(value)
    radix = g.const(10, 5)
    for index in reversed(range(len(value))):
        candidate = (value[index],)+remainder[:4]
        take = g.NOT(g.lt(candidate, radix)); quotient[index] = take
        remainder = g.mux(take, g.sub(candidate, radix)[0], candidate)
    return tuple(quotient), g.fit(remainder, c.width)


def emit_rules(c):
    r = c.r; active = c.task(Task.WORD_DECIMAL); at = lambda m: c.AND(active, c.mode(m))
    allowed = c.OR(*(c.eq(r['mode'], mode) for mode in (Mode.WALK, Mode.DECIMAL_STEP, Mode.DECIMAL_FINISH, Mode.RETURN)))
    c.stop(c.AND(c.active, active, c.NOT(allowed)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(at(Mode.WALK), decimal_number=r['decimal_value'], decimal_head=0, decimal_count=0, mode=Mode.DECIMAL_STEP)
    digit = at(Mode.DECIMAL_STEP); room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(digit, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); digit = c.AND(digit, room)
    quotient, remainder = divmod10(c, r['decimal_number']); more = c.NOT(c.eq(quotient, 0))
    c.write('heap', digit, r['free'], (CellTag.VECTOR_CELL, c.add(48, remainder), r['decimal_head'], 0))
    c.emit(digit, free=c.add(r['free'], 1), decimal_head=r['free'], decimal_count=c.add(r['decimal_count'], 1),
        decimal_number=quotient, mode=c.mux(more, Mode.DECIMAL_STEP, Mode.DECIMAL_FINISH))
    c.alloc(at(Mode.DECIMAL_FINISH), (CellTag.VECTOR, r['decimal_count'], r['decimal_head'], VectorKind.BYTES))
