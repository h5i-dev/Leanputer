"""Pinned inductive_reduce_rec rule-selection/application segment, DEVELOPMENT.

The surrounding reducer owns checked lookup and K/WHNF/literal/structure major
preparation. This pure segment never treats an arbitrary supplied major as WHNF.
"""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_IOTA_ZIP, CALL_IOTA_PREFIX, CALL_IOTA_FIELDS, CALL_IOTA_EXTRA)
from .recursor_apply_rules import TAGS

PRIVATE_PHASES = (CALL_IOTA_ZIP, CALL_IOTA_PREFIX, CALL_IOTA_FIELDS, CALL_IOTA_EXTRA)


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    def apply(phase, vector, start, take):
        s['stack'][r['sp']-1] = [phase, 0, 0, Task.APPLY_RECURSOR_RULE, 0, 0]
        r.update(task=Task.APPLY_VECTOR_SLICE, mode=Mode.WALK, x=vector,
            slice_body=r['r'], slice_start=start, slice_take=take, depth=0)
    if frame[0] == CALL_IOTA_ZIP:
        apply(CALL_IOTA_PREFIX, r['iota_rec_args'], 0, r['iota_prefix'])
    elif frame[0] == CALL_IOTA_PREFIX:
        apply(CALL_IOTA_FIELDS, r['iota_major_args'], r['iota_major_count']-r['iota_fields'], r['iota_fields'])
    elif frame[0] == CALL_IOTA_FIELDS:
        apply(CALL_IOTA_EXTRA, r['iota_rec_args'], r['iota_major_index']+1, r['iota_arg_count']-r['iota_major_index']-1)
    else:
        r.update(task=Task.APPLY_RECURSOR_RULE, sp=r['sp']-1); ret(r['r'])


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.APPLY_RECURSOR_RULE: return False
    def finish(value=0):
        r['sp'] -= 1; ret(value)
    mode = r['mode']
    if mode == Mode.WALK:
        if r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [CALL_IOTA_ZIP, 0, 0, Task.APPLY_RECURSOR_RULE, 0, 0]
            r.update(sp=r['sp']+1, iota_symbol=a, mode=Mode.IOTA_SCHEME, x=c)
    elif mode == Mode.IOTA_SCHEME:
        if b != 10: finish()
        else: r.update(iota_parameters=a, mode=Mode.IOTA_METADATA, x=c)
    elif mode == Mode.IOTA_METADATA:
        r.update(iota_rules=c, mode=Mode.IOTA_COUNTS, x=b)
    elif mode == Mode.IOTA_COUNTS:
        r.update(iota_parameters_count=a, iota_indices=b, mode=Mode.IOTA_SHARED_COUNTS, x=c)
    elif mode == Mode.IOTA_SHARED_COUNTS:
        prefix = r['iota_parameters_count']+a+b
        major = prefix+r['iota_indices']
        if major >= 1 << cfg.word_bits: stop(Outcome.RESOURCE, Reason.INDEX)
        else: r.update(iota_prefix=prefix, iota_major_index=major, mode=Mode.IOTA_REC_SPINE, x=r['reduction_rec_spine'])
    elif mode == Mode.IOTA_REC_SPINE:
        r.update(iota_rec_args=b, mode=Mode.IOTA_REC_HEAD, x=a)
    elif mode == Mode.IOTA_REC_HEAD:
        if tag != Tag.CONST or a != r['iota_symbol']: finish()
        else: r.update(iota_levels=b, mode=Mode.IOTA_REC_ARGUMENTS, x=r['iota_rec_args'])
    elif mode == Mode.IOTA_REC_ARGUMENTS:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif a <= r['iota_major_index']: finish()
        else: r.update(iota_arg_count=a, mode=Mode.IOTA_MAJOR_SPINE, x=r['reduction_major_spine'])
    elif mode == Mode.IOTA_MAJOR_SPINE:
        r.update(iota_major_args=b, mode=Mode.IOTA_MAJOR_HEAD, x=a)
    elif mode == Mode.IOTA_MAJOR_HEAD:
        if tag != Tag.CONST: finish()
        else: r.update(iota_constructor=a, mode=Mode.IOTA_MAJOR_ARGUMENTS, x=r['iota_major_args'])
    elif mode == Mode.IOTA_MAJOR_ARGUMENTS:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(iota_major_count=a, mode=Mode.IOTA_RULE_VECTOR, x=r['iota_rules'])
    elif mode == Mode.IOTA_RULE_VECTOR:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif not a: finish()
        else: r.update(iota_remaining=a, mode=Mode.IOTA_RULE_CELL, x=b)
    elif mode == Mode.IOTA_RULE_CELL:
        if not r['iota_remaining'] or bool(b) != (r['iota_remaining'] > 1): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(iota_next=b, mode=Mode.IOTA_RULE, x=a)
    elif mode == Mode.IOTA_RULE:
        if a != r['iota_constructor']:
            if r['iota_remaining'] > 1: r.update(iota_remaining=r['iota_remaining']-1, mode=Mode.IOTA_RULE_CELL, x=r['iota_next'])
            else: finish()
        elif b > r['iota_major_count']: finish()
        else: r.update(iota_fields=b, iota_rhs=c, mode=Mode.IOTA_PARAMETER_VECTOR, x=r['iota_parameters'])
    elif mode == Mode.IOTA_PARAMETER_VECTOR:
        if c != VectorKind.SYMBOLS or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(iota_uparams=a, mode=Mode.IOTA_LEVEL_VECTOR, x=r['iota_levels'])
    elif mode == Mode.IOTA_LEVEL_VECTOR:
        if c != VectorKind.LEVELS or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif a != r['iota_uparams']: finish()
        else:
            r.update(task=Task.INSTANTIATE_SCHEME, mode=Mode.WALK, x=r['iota_rhs'],
                parameter_vector=r['iota_parameters'], level_vector=r['iota_levels'], depth=0)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
