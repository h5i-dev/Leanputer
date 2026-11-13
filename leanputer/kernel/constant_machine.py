"""Development reference for checked-signature constant inference.

The public typed-service entry has env_ready=0 and still GAPs raw signatures.
Only the weighted source driver may set up/publish a checked environment.
This operation searches that PRIVATE list, checks arity and zips raw universe
arguments into a temporary caller window, invoking the SAME source-instantiation
walker. No host inferred type, specialization or admission answer is loaded.
The same lookup/zip/source-instantiation serves weighted inference AND delta.
Source definitions/theorems unfold; axioms/opaque declarations remain neutral.
"""
from .arena import Tag
from .native_cells import CellTag, VectorKind, DeclarationKind
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_INFER_CONSTANT_LOOKUP, CALL_INFER_CONSTANT_SUBSTITUTE)

PRIVATE_PHASES = (CALL_INFER_CONSTANT_LOOKUP, CALL_INFER_CONSTANT_SUBSTITUTE)


def resume(machine, frame, stop, ret, alloc):
    r = machine.state['regs']
    phase, original, depth, task, first, second = frame
    if phase == CALL_INFER_CONSTANT_LOOKUP:
        if not r['r']: stop(Outcome.INVALID, Reason.UNKNOWN_CONSTANT)
        else: r.update(mode=Mode.CONST_SIGNATURE, task=task, x=r['r'])
    else:
        r.update(sp=r['sp']-1, mode=Mode.BETA_ZETA if task == Task.BETA_ZETA else Mode.RETURN,
            task=task, ctx=depth, arg_base=first, count=second)
        if task == Task.BETA_ZETA: r.update(x=r['r'], depth=0)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] not in (Task.INFER, Task.BETA_ZETA): return False
    if r['mode'] == (Mode.BETA_ZETA if r['task'] == Task.BETA_ZETA else Mode.WALK):
        if tag != Tag.CONST or not r['env_ready']: return False
        if r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [CALL_INFER_CONSTANT_LOOKUP, r['x'], r['ctx'], r['task'], r['arg_base'], r['count']]
            r.update(sp=r['sp']+1, mode=Mode.WALK, task=Task.ENV_LOOKUP, query_symbol=a)
        return True
    if r['mode'] not in (Mode.CONST_SIGNATURE, Mode.CONST_SCHEME, Mode.CONST_EXPRESSION,
        Mode.CONST_PARAMETER_HEADER, Mode.CONST_LEVEL_HEADER, Mode.CONST_PARAMETER_CELL, Mode.CONST_LEVEL_CELL): return False
    if not r['sp']:
        stop(Outcome.INVALID, Reason.SYNTAX); return True
    if r['mode'] == Mode.CONST_SIGNATURE:
        r.update(signature_type=b, mode=Mode.CONST_SCHEME, x=c)
    elif r['mode'] == Mode.CONST_SCHEME:
        if r['task'] == Task.BETA_ZETA and b not in (DeclarationKind.DEFINITION, DeclarationKind.THEOREM):
            original = s['stack'][r['sp']-1][1]
            r['sp'] -= 1; ret(original)
        elif not 0 < a < r['free'] or (r['task'] == Task.BETA_ZETA and not 0 < c < r['free']): stop(Outcome.INVALID, Reason.SYNTAX)
        else:
            if r['task'] == Task.BETA_ZETA: r['signature_type'] = c
            r.update(parameter_vector=a, mode=Mode.CONST_EXPRESSION, x=s['stack'][r['sp']-1][1])
    elif r['mode'] == Mode.CONST_EXPRESSION:
        if tag != Tag.CONST: stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(level_vector=b, mode=Mode.CONST_PARAMETER_HEADER, x=r['parameter_vector'])
    elif r['mode'] == Mode.CONST_PARAMETER_HEADER:
        if c != VectorKind.SYMBOLS or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(zip_count=a, parameter_head=b, mode=Mode.CONST_LEVEL_HEADER, x=r['level_vector'])
    elif r['mode'] == Mode.CONST_LEVEL_HEADER:
        if c != VectorKind.LEVELS or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif a != r['zip_count']: stop(Outcome.INVALID, Reason.UNIVERSE_ARITY)
        elif not a:
            r['sp'] -= 1
            if r['task'] == Task.BETA_ZETA: r.update(mode=Mode.BETA_ZETA, x=r['signature_type'], depth=0)
            else: ret(r['signature_type'])
        elif r['ctx']+a > cfg.context: stop(Outcome.RESOURCE, Reason.CONTEXT)
        else: r.update(arg_base=r['ctx'], count=a, level_head=b, zip_remaining=a,
                       mode=Mode.CONST_PARAMETER_CELL, x=r['parameter_head'])
    elif r['mode'] == Mode.CONST_PARAMETER_CELL:
        if not a or not r['zip_remaining'] or bool(b) != (r['zip_remaining'] > 1):
            stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(zip_symbol=a, zip_parameter_next=b, mode=Mode.CONST_LEVEL_CELL, x=r['level_head'])
    elif r['mode'] == Mode.CONST_LEVEL_CELL:
        if not r['zip_remaining'] or bool(b) != (r['zip_remaining'] > 1) or not 0 < a < r['free']:
            stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            ref = r['free']
            s['heap'][ref] = [CellTag.LEVEL_BINDING, r['zip_symbol'], a, 0]
            s['context'][r['ctx']] = [ref]
            more = r['zip_remaining'] > 1
            r.update(free=ref+1, ctx=r['ctx']+1, zip_remaining=r['zip_remaining']-1,
                parameter_head=r['zip_parameter_next'], level_head=b)
            if more: r.update(mode=Mode.CONST_PARAMETER_CELL, x=r['zip_parameter_next'])
            else:
                s['stack'][r['sp']-1][0] = CALL_INFER_CONSTANT_SUBSTITUTE
                r.update(mode=Mode.WALK, task=Task.EXPR_LEVEL_INSTANTIATE, x=r['signature_type'], depth=0)
    return True
