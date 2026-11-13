"""Reentrant source recursor reduction and existing WHNF-stack bridge, DEVELOPMENT."""
from .arena import Tag
from .native_cells import CellTag
from .traversal_machine import (Mode, Task, Outcome, Reason,
    PENDING_ARGUMENT, CALL_INFER_CONSTANT_LOOKUP)
from .recursor_reduce_rules import Phase, REDUCE_TAGS, GATHER_TAGS, NO_NODE


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    phase, original, metadata, owner, rec_spine, signature = frame
    if owner == Task.GATHER_RECURSOR_ARGUMENTS:
        if phase: stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(task=owner, mode=Mode.GATHER_RESTORE, x=original, gather_result=r['r'])
        return
    def call(p, task, x, **updates):
        s['stack'][r['sp']-1] = [p, original, metadata, Task.REDUCE_RECURSOR, rec_spine, signature]
        r.update(task=task, mode=Mode.WALK, x=x, depth=0, **updates)
    def finish(value=0):
        r.update(task=Task.REDUCE_RECURSOR, sp=r['sp']-1); ret(value)
    if phase == Phase.SPINE:
        s['stack'][r['sp']-1][4] = r['r']
        r.update(task=Task.REDUCE_RECURSOR, mode=Mode.REDUCE_SPINE, x=r['r'])
    elif phase == Phase.LOOKUP:
        if not r['r']: finish()
        else:
            s['stack'][r['sp']-1][5] = r['r']
            r.update(task=Task.REDUCE_RECURSOR, mode=Mode.REDUCE_SIGNATURE, x=r['r'])
    elif phase == Phase.SELECT:
        if not r['r']: finish()
        else: call(Phase.PREPARED, Task.PREPARE_RECURSOR_MAJOR, metadata, major_value=r['r'])
    elif phase == Phase.PREPARED: call(Phase.PREPARED_SPINE, Task.APPLICATION_SPINE, r['r'])
    elif phase == Phase.PREPARED_SPINE:
        call(Phase.APPLIED, Task.APPLY_RECURSOR_RULE, signature,
            reduction_rec_spine=rec_spine, reduction_major_spine=r['r'])
    elif phase == Phase.APPLIED: finish(r['r'])
    else: stop(Outcome.INVALID, Reason.SYNTAX)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    mode = r['mode']; frame = s['stack'][r['sp']-1] if r['sp'] else None
    if r['task'] == Task.GATHER_RECURSOR_ARGUMENTS:
        if mode == Mode.WALK:
            if frame is None or frame[0] != CALL_INFER_CONSTANT_LOOKUP or frame[3] != Task.BETA_ZETA:
                stop(Outcome.INVALID, Reason.SYNTAX)
            else:
                frame[0] = 0; frame[3] = Task.GATHER_RECURSOR_ARGUMENTS
                r.update(gather_saved_sp=r['sp'], gather_expression=frame[1], sp=r['sp']-1, mode=Mode.GATHER_SCAN)
        elif mode == Mode.GATHER_SCAN:
            if frame is not None and frame[0] == PENDING_ARGUMENT and frame[3] == Task.BETA_ZETA:
                if r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
                else:
                    ref = r['free']; s['heap'][ref] = [Tag.APP, r['gather_expression'], frame[4], 0]
                    r.update(free=ref+1, gather_expression=ref, sp=r['sp']-1)
            else: r.update(gather_base_sp=r['sp'], sp=r['gather_saved_sp'], mode=Mode.GATHER_SAVE)
        elif mode == Mode.GATHER_SAVE:
            if r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                ref = r['free']; s['heap'][ref] = [CellTag.REDUCER_CALL, frame[1], r['gather_base_sp'], 0]
                frame[1] = ref
                r.update(free=ref+1, task=Task.REDUCE_RECURSOR, mode=Mode.WALK, x=r['gather_expression'], depth=0)
        elif mode == Mode.GATHER_RESTORE:
            r.update(task=Task.BETA_ZETA, ctx=frame[2], arg_base=frame[4], count=frame[5], depth=0)
            if not r['gather_result']:
                r['sp'] -= 1; ret(a)
            else: r.update(sp=b, mode=Mode.BETA_ZETA, x=r['gather_result'])
        else: stop(Outcome.INVALID, Reason.SYNTAX)
        return True
    if r['task'] != Task.REDUCE_RECURSOR: return False
    def finish():
        r.update(sp=r['sp']-1); ret(0)
    if mode == Mode.WALK:
        if not r['env_ready']: stop(Outcome.GAP, Reason.GAP_ENVIRONMENT)
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [Phase.SPINE, r['x'], 0, Task.REDUCE_RECURSOR, 0, 0]
            r.update(sp=r['sp']+1, task=Task.APPLICATION_SPINE)
    elif mode == Mode.REDUCE_SPINE: r.update(mode=Mode.REDUCE_HEAD, x=a)
    elif mode == Mode.REDUCE_HEAD:
        if tag != Tag.CONST: finish()
        else:
            frame[0] = Phase.LOOKUP
            r.update(task=Task.ENV_LOOKUP, mode=Mode.WALK, query_symbol=a,
                lookup_head=r['typing_head'] if r['typing_active'] else r['env_head'])
    elif mode == Mode.REDUCE_SIGNATURE: r.update(mode=Mode.REDUCE_SCHEME, x=c)
    elif mode == Mode.REDUCE_SCHEME:
        if b != 10: finish()
        else:
            frame[2] = c; r.update(mode=Mode.REDUCE_METADATA, x=c)
    elif mode == Mode.REDUCE_METADATA: r.update(mode=Mode.REDUCE_COUNTS, x=b)
    elif mode == Mode.REDUCE_COUNTS:
        total = a+b
        if total >= 1 << cfg.word_bits: stop(Outcome.RESOURCE, Reason.INDEX)
        else: r.update(reduce_major_index=total, mode=Mode.REDUCE_SHARED, x=c)
    elif mode == Mode.REDUCE_SHARED:
        total = r['reduce_major_index']+a+b
        if total >= 1 << cfg.word_bits: stop(Outcome.RESOURCE, Reason.INDEX)
        else: r.update(reduce_major_index=total, mode=Mode.REDUCE_ARGUMENTS, x=frame[4])
    elif mode == Mode.REDUCE_ARGUMENTS:
        frame[0] = Phase.SELECT
        r.update(task=Task.VECTOR_REFERENCE, mode=Mode.WALK, x=b, vector_index=r['reduce_major_index'])
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
