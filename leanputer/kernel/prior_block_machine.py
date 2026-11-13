"""Original-block registry lookup, DEVELOPMENT reference; no admission authority.

The full source transaction must produce registry records only after restored
checking/publication. This pure lookup cannot turn CORE output into that proof.
"""
from .traversal_machine import Mode, Task, Outcome, Reason


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    if frame[0] != 0: stop(Outcome.INVALID, Reason.SYNTAX)
    elif r['r']:
        r.update(task=Task.PRIOR_BLOCK_LOOKUP, sp=r['sp']-1); ret(frame[1])
    elif not frame[5]:
        r.update(task=Task.PRIOR_BLOCK_LOOKUP, sp=r['sp']-1); ret(0)
    else: r.update(task=Task.PRIOR_BLOCK_LOOKUP, mode=Mode.PRIOR_BLOCK_CELL, x=frame[5])


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.PRIOR_BLOCK_LOOKUP: return False
    if r['mode'] == Mode.WALK:
        if not r['x']: ret(0)
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [0, 0, 0, Task.PRIOR_BLOCK_LOOKUP, 0, 0]
            r.update(sp=r['sp']+1, mode=Mode.PRIOR_BLOCK_CELL)
    elif r['mode'] == Mode.PRIOR_BLOCK_CELL:
        r.update(prior_block_next=b, mode=Mode.PRIOR_BLOCK_ORIGIN, x=a)
    elif r['mode'] == Mode.PRIOR_BLOCK_ORIGIN:
        s['stack'][r['sp']-1] = [0, r['x'], 0, Task.PRIOR_BLOCK_LOOKUP, 0, r['prior_block_next']]
        r.update(task=Task.SIGNATURE_VECTOR_LOOKUP, mode=Mode.WALK, x=c, depth=0)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
