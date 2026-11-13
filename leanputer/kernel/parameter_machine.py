"""General symbolic-scheme parameter traversal/uniqueness, development reference.

Counts and identities are DATA. One bounds-controlled scan handles every list
length; no arity/field-count classes. Native syntax loading does not decide
membership or uniqueness and supplies no admitted declarations/types.
"""
from .native_cells import VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.LOAD_PARAMETERS: return False
    if r['mode'] == Mode.WALK:
        if c != VectorKind.SYMBOLS or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif a > cfg.context: stop(Outcome.RESOURCE, Reason.CONTEXT)
        else:
            r.update(ctx=0, count=a, arg_base=0, local_base=0, zip_count=a, zip_remaining=a, parameter_head=b)
            if not a: ret(0)
            else: r.update(mode=Mode.PARAMETER_CELL, x=b)
    elif r['mode'] == Mode.PARAMETER_CELL:
        if not a or not r['zip_remaining'] or bool(b) != (r['zip_remaining'] > 1):
            stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(zip_symbol=a, zip_parameter_next=b, mode=Mode.PARAMETER_DUPLICATE, i=0)
    elif r['mode'] == Mode.PARAMETER_DUPLICATE:
        if r['i'] < r['ctx']:
            if s['context'][r['i']][0] == r['zip_symbol']: stop(Outcome.INVALID, Reason.DUPLICATE_PARAMETER)
            else: r['i'] += 1
        else:
            s['context'][r['ctx']] = [r['zip_symbol']]
            more = r['zip_remaining'] > 1
            r.update(ctx=r['ctx']+1, zip_remaining=r['zip_remaining']-1)
            if more: r.update(mode=Mode.PARAMETER_CELL, x=r['zip_parameter_next'])
            else: ret(r['count'])
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
