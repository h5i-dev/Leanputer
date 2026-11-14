"""Generic native-inference DEVELOPMENT TRANSITION REFERENCE.

No runtime host inference calls. Complete source tag dispatch is explicit; raw
signatures are never accepted as checked signatures. Remaining environment,
literal/Quot and primitive-aware negative conversion callbacks produce GAP. Generic projection
inference/reduction uses the task-owned source controller. Pi/Lam/App/Let
rules reuse the SAME weighted scope/telescope/substitution/abstraction/levels.
This is unfinished typed service integration, NOT a full kernel admission path.
"""
from .arena import Tag
from .native_cells import CellTag
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_INFER_BINDER_DOMAIN, CALL_INFER_DOMAIN_WHNF, CALL_INFER_OPEN,
    CALL_INFER_BODY, CALL_INFER_BODY_WHNF, CALL_INFER_ABSTRACT,
    CALL_INFER_PI_LEVEL, CALL_INFER_FUNCTION, CALL_INFER_FUNCTION_WHNF,
    CALL_INFER_ARGUMENT, CALL_INFER_ARGUMENT_CONVERT, CALL_INFER_LET_TYPE,
    CALL_INFER_LET_TYPE_WHNF, CALL_INFER_LET_VALUE, CALL_INFER_LET_CONVERT,
    CALL_INFER_LET_BODY)

PRIVATE_PHASES = tuple(range(CALL_INFER_BINDER_DOMAIN, CALL_INFER_LET_BODY+1))


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    phase, original, depth, task, first, second = frame
    top = r['sp']-1
    def replace(phase, original=original, depth=depth, first=first, second=second):
        s['stack'][top] = [phase, original, depth, Task.INFER, first, second]
    def whnf(phase):
        replace(phase)
        r.update(mode=Mode.BETA_ZETA, task=Task.BETA_ZETA, x=r['r'], depth=0)
    if phase == CALL_INFER_BINDER_DOMAIN: whnf(CALL_INFER_DOMAIN_WHNF)
    elif phase == CALL_INFER_DOMAIN_WHNF:
        r.update(mode=Mode.INFER_DOMAIN_SORT, task=Task.INFER, x=r['r'])
    elif phase == CALL_INFER_OPEN:
        replace(CALL_INFER_BODY, second=r['substitution'])
        r.update(mode=Mode.WALK, task=Task.INFER, x=r['r'])
    elif phase == CALL_INFER_BODY: whnf(CALL_INFER_BODY_WHNF)
    elif phase == CALL_INFER_BODY_WHNF:
        r.update(mode=Mode.INFER_BINDER_RESULT, task=Task.INFER, x=original)
    elif phase == CALL_INFER_ABSTRACT:
        r.update(sp=top, mode=Mode.INFER_LAM_RESULT, task=Task.INFER, x=original, ctx=depth)
    elif phase == CALL_INFER_PI_LEVEL:
        r.update(sp=top, mode=Mode.INFER_SORT_EXPR, task=Task.INFER, x=original, ctx=depth)
    elif phase == CALL_INFER_FUNCTION: whnf(CALL_INFER_FUNCTION_WHNF)
    elif phase == CALL_INFER_FUNCTION_WHNF:
        r.update(mode=Mode.INFER_FUNCTION_PI, task=Task.INFER, x=r['r'])
    elif phase == CALL_INFER_ARGUMENT:
        r.update(mode=Mode.INFER_ARGUMENT_TYPE, task=Task.INFER, x=original)
    elif phase == CALL_INFER_ARGUMENT_CONVERT:
        if not r['r']: stop(Outcome.INVALID, Reason.TYPE_MISMATCH)
        else: r.update(mode=Mode.INFER_APP_RESULT, task=Task.INFER, x=original)
    elif phase == CALL_INFER_LET_TYPE: whnf(CALL_INFER_LET_TYPE_WHNF)
    elif phase == CALL_INFER_LET_TYPE_WHNF:
        r.update(mode=Mode.INFER_LET_ANNOTATION, task=Task.INFER, x=r['r'])
    elif phase == CALL_INFER_LET_VALUE:
        r.update(mode=Mode.INFER_LET_VALUE_TYPE, task=Task.INFER, x=original)
    elif phase == CALL_INFER_LET_CONVERT:
        if not r['r']: stop(Outcome.INVALID, Reason.TYPE_MISMATCH)
        else: r.update(mode=Mode.INFER_LET_INSTANTIATE, task=Task.INFER, x=original)
    elif phase == CALL_INFER_LET_BODY:
        r.update(sp=top, mode=Mode.WALK, task=Task.INFER, x=r['r'])


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] not in (Task.INFER, Task.CONVERT_POSITIVE): return False
    def push(phase, original=0, depth=0, first=0, second=0):
        if r['sp'] >= cfg.stack:
            stop(Outcome.RESOURCE, Reason.STACK); return False
        s['stack'][r['sp']] = [phase, original, depth, Task.INFER, first, second]
        r['sp'] += 1
        return True
    def replace(phase, original, depth=0, first=0, second=0):
        s['stack'][r['sp']-1] = [phase, original, depth, Task.INFER, first, second]
    def ensure(stable_tag):
        # Only a definitely stable mismatch may reject while WHNF is incomplete.
        if stable_tag in (Tag.BVAR, Tag.LOCAL, Tag.SORT, Tag.PI, Tag.LAM, Tag.NAT, Tag.STRING):
            stop(Outcome.INVALID, Reason.EXPECT_SORT)
        else: stop(Outcome.GAP, Reason.GAP_CONVERSION)
    if r['task'] == Task.CONVERT_POSITIVE:
        if r['mode'] == Mode.WALK:r.update(task=Task.CONVERT,convert_pc=0)
        else:stop(Outcome.INVALID,Reason.SYNTAX)
        return True
    if r['mode'] == Mode.WALK:
        if tag == Tag.BVAR: stop(Outcome.INVALID, Reason.SCOPE)
        elif tag == Tag.LOCAL:
            if r['ctx'] <= r['local_base']: stop(Outcome.INVALID, Reason.SCOPE)
            else: r.update(mode=Mode.INFER_LOCAL_SELECT, lookup_uid=a, lookup_index=r['ctx']-1)
        elif tag == Tag.SORT:
            if r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                s['heap'][r['free']] = [CellTag.LEVEL_SUCC, a, 0, 0]
                r.update(free=r['free']+1, r=r['free'], mode=Mode.INFER_SORT_EXPR)
        elif tag == Tag.CONST: stop(Outcome.GAP, Reason.GAP_ENVIRONMENT)
        elif tag in (Tag.NAT, Tag.STRING): stop(Outcome.GAP, Reason.GAP_PRIMITIVE)
        elif tag == Tag.PROJ: r.update(task=Task.PROJECTION_INFER,projection_pc=0)
        elif tag == Tag.MDATA: r['x'] = a
        elif tag in (Tag.PI, Tag.LAM):
            if push(CALL_INFER_BINDER_DOMAIN, r['x'], r['ctx'], second=tag): r.update(x=a)
        elif tag == Tag.APP:
            if push(CALL_INFER_FUNCTION, b): r.update(x=a)
        elif tag == Tag.LET:
            if push(CALL_INFER_LET_TYPE, r['x']): r.update(x=a)
    elif r['mode'] == Mode.INFER_SORT_EXPR:
        alloc((Tag.SORT, r['r'], 0, 0))
    elif r['mode'] == Mode.INFER_LOCAL_SELECT:
        r.update(mode=Mode.INFER_LOCAL_RECORD, x=s['context'][r['lookup_index']][0])
    elif r['mode'] == Mode.INFER_LOCAL_RECORD:
        if not 0 < a < r['free'] or not 0 < b < r['free']: stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(mode=Mode.INFER_LOCAL_EXPR, x=a, lookup_type=b)
    elif r['mode'] == Mode.INFER_LOCAL_EXPR:
        if tag != Tag.LOCAL: stop(Outcome.INVALID, Reason.SYNTAX)
        elif a == r['lookup_uid']: ret(r['lookup_type'])
        elif r['lookup_index'] <= r['local_base']: stop(Outcome.INVALID, Reason.SCOPE)
        else: r.update(mode=Mode.INFER_LOCAL_SELECT, lookup_index=r['lookup_index']-1)
    else:
        if not r['sp'] and r['mode'] not in (Mode.INFER_LAM_RESULT,):
            stop(Outcome.INVALID, Reason.SYNTAX); return True
        phase, original, depth, task, first, second = s['stack'][r['sp']-1] if r['sp'] else (0,)*6
        if r['mode'] == Mode.INFER_DOMAIN_SORT:
            if tag != Tag.SORT: ensure(tag)
            else:
                replace(CALL_INFER_OPEN, original, depth, first=a, second=second)
                r.update(mode=Mode.TELESCOPE, task=Task.OPEN_TELESCOPE, x=original,
                    open_tag=second, bounded=1, limit=r['ctx']+1)
        elif r['mode'] == Mode.INFER_BINDER_RESULT:
            if tag == Tag.PI: r.update(mode=Mode.INFER_PI_BODY_SORT, x=r['r'])
            elif tag == Tag.LAM:
                replace(CALL_INFER_ABSTRACT, original, depth)
                r.update(mode=Mode.WALK, task=Task.ABSTRACT_ONE, x=r['r'], abstract_uid=second, depth=0)
            else: stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['mode'] == Mode.INFER_PI_BODY_SORT:
            if tag != Tag.SORT: ensure(tag)
            else:
                replace(CALL_INFER_PI_LEVEL, original, depth)
                r.update(mode=Mode.WALK, task=Task.LEVEL_IMAX, x=first, peer=a, ctx=depth)
        elif r['mode'] == Mode.INFER_LAM_RESULT:
            if tag != Tag.LAM: stop(Outcome.INVALID, Reason.SYNTAX)
            else: alloc((Tag.PI, a, r['r'], c))
        elif r['mode'] == Mode.INFER_FUNCTION_PI:
            if tag != Tag.PI:
                if tag in (Tag.SORT, Tag.LAM): stop(Outcome.INVALID, Reason.EXPECT_PI)
                else: stop(Outcome.GAP, Reason.GAP_CONVERSION)
            else:
                replace(CALL_INFER_ARGUMENT, r['x'], original)
                r.update(mode=Mode.WALK, task=Task.INFER, x=original)
        elif r['mode'] == Mode.INFER_ARGUMENT_TYPE:
            if tag != Tag.PI: stop(Outcome.INVALID, Reason.SYNTAX)
            else:
                replace(CALL_INFER_ARGUMENT_CONVERT, original, depth)
                r.update(mode=Mode.WALK, task=Task.CONVERT_POSITIVE, x=r['r'], peer=a)
        elif r['mode'] == Mode.INFER_APP_RESULT:
            if tag != Tag.PI: stop(Outcome.INVALID, Reason.SYNTAX)
            else: r.update(sp=r['sp']-1, mode=Mode.WALK, task=Task.INSTANTIATE_ONE, x=b, substitution=depth, depth=0)
        elif r['mode'] == Mode.INFER_LET_ANNOTATION:
            if tag != Tag.SORT: ensure(tag)
            else: r.update(mode=Mode.INFER_LET_SOURCE, x=original)
        elif r['mode'] == Mode.INFER_LET_SOURCE:
            if tag != Tag.LET: stop(Outcome.INVALID, Reason.SYNTAX)
            else:
                replace(CALL_INFER_LET_VALUE, original)
                r.update(mode=Mode.WALK, task=Task.INFER, x=b)
        elif r['mode'] == Mode.INFER_LET_VALUE_TYPE:
            if tag != Tag.LET: stop(Outcome.INVALID, Reason.SYNTAX)
            else:
                replace(CALL_INFER_LET_CONVERT, original)
                r.update(mode=Mode.WALK, task=Task.CONVERT_POSITIVE, x=r['r'], peer=a)
        elif r['mode'] == Mode.INFER_LET_INSTANTIATE:
            if tag != Tag.LET: stop(Outcome.INVALID, Reason.SYNTAX)
            else:
                replace(CALL_INFER_LET_BODY, 0)
                r.update(mode=Mode.WALK, task=Task.INSTANTIATE_ONE, x=c, substitution=b, depth=0)
        else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
