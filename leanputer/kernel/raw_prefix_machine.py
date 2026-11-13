"""Exact raw dependent binder-prefix opening, DEVELOPMENT reference only.

Source nested get_params/restore_nested: no WHNF, inference or type approval.
Generated Locals are syntax variables for rewriting; Γ is never modified.
"""
from .traversal_machine import Mode, Task, Outcome, Reason
from .arena import Tag


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']; phase, body, remaining, _, _, _ = frame
    if phase == 0:
        s['stack'][r['sp']-1] = [1, 0, remaining, Task.OPEN_RAW_PREFIX, 0, 0]
        r.update(task=Task.INSTANTIATE_ONE, mode=Mode.WALK, x=body, substitution=r['r'], depth=0)
    elif phase == 1:
        r.update(task=Task.OPEN_RAW_PREFIX, mode=Mode.RAW_PREFIX_LOOP, x=r['r'], raw_prefix_remaining=remaining-1)
    else: stop(Outcome.INVALID, Reason.SYNTAX)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.OPEN_RAW_PREFIX: return False
    if r['mode'] == Mode.WALK:
        end = r['ctx']+r['raw_prefix_count']
        if end >= 1 << cfg.word_bits: stop(Outcome.RESOURCE, Reason.INDEX)
        elif end > cfg.context: stop(Outcome.RESOURCE, Reason.CONTEXT)
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [0, 0, 0, Task.OPEN_RAW_PREFIX, 0, 0]
            r.update(sp=r['sp']+1, raw_prefix_remaining=r['raw_prefix_count'], mode=Mode.RAW_PREFIX_LOOP)
    elif r['mode'] == Mode.RAW_PREFIX_LOOP:
        if not r['raw_prefix_remaining']:
            r['sp'] -= 1; ret(r['x'])
        elif tag != r['open_tag']:
            stop(Outcome.INVALID, Reason.EXPECT_PI if r['open_tag'] == Tag.PI else Reason.EXPECT_LAM)
        else:
            s['stack'][r['sp']-1] = [0, b, r['raw_prefix_remaining'], Task.OPEN_RAW_PREFIX, 0, 0]
            r.update(task=Task.FRESH_LOCAL, mode=Mode.WALK, x=a, binder_info=c)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
