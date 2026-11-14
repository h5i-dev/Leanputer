"""Source instantiate_pi_params: raw strip then bulk instantiate_rev, DEVELOPMENT.

Actual parameters are Expr syntax. No normalization, inferred type or admission
answer is produced. Scratch operand slots are outside the live caller context.
"""
from .arena import Tag
from .native_cells import VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def resume(machine, frame, stop, ret, alloc):
    r = machine.state['regs']
    if frame[0] != 0: stop(Outcome.INVALID, Reason.SYNTAX)
    else:
        r.update(task=Task.INSTANTIATE_PI_PARAMETERS, sp=r['sp']-1, ctx=frame[2], count=frame[4], arg_base=frame[5]); ret(r['r'])


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.INSTANTIATE_PI_PARAMETERS: return False
    frame = s['stack'][r['sp']-1] if r['sp'] else None
    mode = r['mode']
    if mode == Mode.WALK:
        if r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [0, r['x'], r['ctx'], Task.INSTANTIATE_PI_PARAMETERS, r['count'], r['arg_base']]
            r.update(sp=r['sp']+1, mode=Mode.PI_PARAMS_HEADER, x=r['pi_parameter_vector'])
    elif mode == Mode.PI_PARAMS_HEADER:
        size = r['pi_parameter_limit']; end = r['ctx']+size
        if c != VectorKind.REFERENCES or bool(a) != bool(b) or size > a: stop(Outcome.INVALID, Reason.SYNTAX)
        elif end > cfg.context: stop(Outcome.RESOURCE, Reason.CONTEXT)
        elif not size:
            r['sp'] -= 1; ret(frame[1])
        else: r.update(pi_parameter_count=size, pi_parameter_remaining=size, pi_parameter_vector_remaining=a, pi_parameter_cursor=end-1, mode=Mode.PI_PARAMS_CELL, x=b)
    elif mode == Mode.PI_PARAMS_CELL:
        if not r['pi_parameter_remaining'] or bool(b) != (r['pi_parameter_vector_remaining'] > 1): stop(Outcome.INVALID, Reason.SYNTAX)
        elif not 0 < a < r['free']: stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(pi_parameter_next=b, mode=Mode.PI_PARAMS_ARGUMENT, x=a)
    elif mode == Mode.PI_PARAMS_ARGUMENT:
        s['context'][r['pi_parameter_cursor']] = [r['x']]
        r['pi_parameter_vector_remaining'] -= 1
        more = r['pi_parameter_remaining'] > 1
        if more: r.update(pi_parameter_remaining=r['pi_parameter_remaining']-1, pi_parameter_cursor=r['pi_parameter_cursor']-1, mode=Mode.PI_PARAMS_CELL, x=r['pi_parameter_next'])
        else: r.update(pi_parameter_remaining=r['pi_parameter_count'], mode=Mode.PI_PARAMS_STRIP, x=frame[1])
    elif mode == Mode.PI_PARAMS_STRIP:
        if not r['pi_parameter_remaining']:
            r.update(task=Task.INSTANTIATE, mode=Mode.WALK, count=r['pi_parameter_count'], arg_base=frame[2], start=0, depth=0)
        elif tag != Tag.PI: stop(Outcome.INVALID, Reason.EXPECT_PI)
        else: r.update(pi_parameter_remaining=r['pi_parameter_remaining']-1, x=b)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
