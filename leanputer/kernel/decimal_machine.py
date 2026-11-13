"""Unsigned bounded counter -> decimal byte vector, DEVELOPMENT reference."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.WORD_DECIMAL: return False
    if r['mode'] == Mode.WALK:
        r.update(decimal_number=r['decimal_value'], decimal_head=0, decimal_count=0, mode=Mode.DECIMAL_STEP)
    elif r['mode'] == Mode.DECIMAL_STEP:
        if r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            quotient, remainder = divmod(r['decimal_number'], 10)
            ref = r['free']; s['heap'][ref] = [CellTag.VECTOR_CELL, 48+remainder, r['decimal_head'], 0]
            r.update(free=ref+1, decimal_head=ref, decimal_count=r['decimal_count']+1,
                decimal_number=quotient, mode=Mode.DECIMAL_STEP if quotient else Mode.DECIMAL_FINISH)
    elif r['mode'] == Mode.DECIMAL_FINISH: alloc((CellTag.VECTOR, r['decimal_count'], r['decimal_head'], VectorKind.BYTES))
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
