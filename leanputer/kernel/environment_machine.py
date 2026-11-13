"""Development reference for PRIVATE checked-environment operations.

No public syntax loader can supply checked signature/list records. Publication
must be dominated by the weighted source driver checks; raw declaration rows
are a different bank/tag space. Lookup is a shared unbounded-by-class list loop.
Source admission/publication integration is still under implementation.
"""
from .traversal_machine import Mode, Task, Outcome, Reason


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    if r['task'] != Task.ENV_LOOKUP: return False
    if r['mode'] == Mode.WALK:
        if not r['env_head']: ret(0)
        else: r.update(mode=Mode.ENV_CELL, x=r['env_head'])
    elif r['mode'] == Mode.ENV_CELL:
        if not 0 < a < r['free'] or b >= r['free']:
            stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(mode=Mode.ENV_SIGNATURE, x=a, env_next=b)
    elif r['mode'] == Mode.ENV_SIGNATURE:
        if not 0 < b < r['free'] or not 0 < c < r['free']:
            stop(Outcome.INVALID, Reason.SYNTAX)
        elif a == r['query_symbol']: ret(r['x'])
        elif not r['env_next']: ret(0)
        else: r.update(mode=Mode.ENV_CELL, x=r['env_next'])
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
