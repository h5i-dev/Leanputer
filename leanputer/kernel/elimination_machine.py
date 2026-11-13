"""Pinned elimination universe/K algorithm, DEVELOPMENT transition reference.

Consumes internally checked constructor snapshots. The source's singleton,
empty and mutual conditions are semantic rules, not supported shape classes.
Every field uses the same inference/result-argument loop. Generated universe
binder identities are alpha-renamed fresh symbols, never supplied answers.
"""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_ELIM_NONZERO, CALL_ELIM_FIELD_INFER, CALL_ELIM_FIELD_WHNF)

PRIVATE_PHASES = (CALL_ELIM_NONZERO, CALL_ELIM_FIELD_INFER, CALL_ELIM_FIELD_WHNF)
from .elimination_rules import NO_NODE, TAGS, LEVEL_MODES


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    def call(phase, task, x, mode=Mode.WALK):
        s['stack'][r['sp']-1] = [phase, 0, 0, Task.INIT_ELIMINATION, 0, 0]
        r.update(task=task, mode=mode, x=x, depth=0)
    if frame[0] == CALL_ELIM_NONZERO:
        r.update(task=Task.INIT_ELIMINATION, core_K=0)
        if r['r'] or (r['header_seen']==1 and not r['core_ctor_declared']):
            r.update(elim_large=1, mode=Mode.ELIM_PREPARE)
        elif r['header_seen']>1 or r['core_ctor_declared']>1:
            r.update(elim_large=0, mode=Mode.ELIM_PREPARE)
        else: r.update(mode=Mode.ELIM_PENDING_CELL, x=r['ctor_names'])
    elif frame[0] == CALL_ELIM_FIELD_INFER:
        call(CALL_ELIM_FIELD_WHNF, Task.BETA_ZETA, r['r'], Mode.BETA_ZETA)
    elif frame[0] == CALL_ELIM_FIELD_WHNF:
        r.update(task=Task.INIT_ELIMINATION, mode=Mode.ELIM_FIELD_SORT, x=r['r'])


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.INIT_ELIMINATION: return False
    mode = r['mode']
    def prepare(large): r.update(elim_large=large, mode=Mode.ELIM_PREPARE)
    if mode == Mode.WALK:
        if not r['typing_active'] or not r['header_seen']:
            stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [CALL_ELIM_NONZERO, 0, 0, Task.INIT_ELIMINATION, 0, 0]
            r.update(sp=r['sp']+1, task=Task.LEVEL_NOT_ZERO, mode=Mode.WALK, x=r['header_result_level'])
    elif mode == Mode.ELIM_PENDING_CELL: r.update(mode=Mode.ELIM_PENDING, x=a)
    elif mode == Mode.ELIM_PENDING: r.update(mode=Mode.ELIM_ANALYSIS, x=c)
    elif mode == Mode.ELIM_ANALYSIS: r.update(elim_arguments=c, mode=Mode.ELIM_FIELDS, x=b)
    elif mode == Mode.ELIM_FIELDS:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(elim_remaining=a, elim_head=b, mode=Mode.ELIM_RESULT_LEVEL, x=r['header_result_level'])
    elif mode == Mode.ELIM_RESULT_LEVEL:
        # Source is_zero is a TAG test, not normalization/equivalence to zero.
        r.update(core_K=int(tag==CellTag.LEVEL_ZERO and not r['elim_remaining']), ctx=r['header_parameter_end'])
        if not r['elim_remaining']: prepare(1)
        else: r.update(mode=Mode.ELIM_FIELD_CELL, x=r['elim_head'])
    elif mode == Mode.ELIM_FIELD_CELL:
        if not r['elim_remaining'] or bool(b)!=(r['elim_remaining']>1): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(elim_next=b, mode=Mode.ELIM_FIELD, x=a)
    elif mode == Mode.ELIM_FIELD: r.update(mode=Mode.ELIM_LOCAL, x=a)
    elif mode == Mode.ELIM_LOCAL:
        r.update(elim_record=r['x'], elim_local=a, local_base=r['header_parameter_base'])
        s['stack'][r['sp']-1] = [CALL_ELIM_FIELD_INFER, 0, 0, Task.INIT_ELIMINATION, 0, 0]
        r.update(task=Task.INFER, mode=Mode.WALK, x=b, depth=0)
    elif mode == Mode.ELIM_FIELD_SORT:
        if tag != Tag.SORT:
            stable=tag in (Tag.PI,Tag.LAM,Tag.BVAR,Tag.LOCAL,Tag.NAT,Tag.STRING)
            stop(Outcome.INVALID if stable else Outcome.GAP, Reason.EXPECT_SORT if stable else Reason.GAP_CONVERSION)
        else: r.update(mode=Mode.ELIM_FIELD_LEVEL, x=a)
    elif mode == Mode.ELIM_FIELD_LEVEL:
        if tag==CellTag.LEVEL_ZERO: r['mode']=Mode.ELIM_APPEND
        elif not r['elim_arguments']: prepare(0)
        else: r.update(mode=Mode.ELIM_ARGUMENT, x=r['elim_arguments'])
    elif mode == Mode.ELIM_ARGUMENT:
        # All Locals here are canonical weighted allocations, UID=heap address.
        # Source std::find tests direct equality of result arguments, not occurs.
        if a==r['elim_local']: r['mode']=Mode.ELIM_APPEND
        elif b: r['x']=b
        else: prepare(0)
    elif mode == Mode.ELIM_APPEND:
        if r['ctx']>=cfg.context: stop(Outcome.RESOURCE, Reason.CONTEXT)
        else:
            s['context'][r['ctx']]=[r['elim_record']]
            more=r['elim_remaining']>1
            r.update(ctx=r['ctx']+1, elim_remaining=r['elim_remaining']-1)
            if more: r.update(mode=Mode.ELIM_FIELD_CELL, x=r['elim_next'])
            else: prepare(1)
    elif mode == Mode.ELIM_PREPARE:
        r.update(ctx=r['header_parameter_end'], count=r['header_parameter_base'], arg_base=0, local_base=r['header_parameter_base'])
        if r['free']+(4 if r['elim_large'] else 1)>cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        elif r['elim_large'] and r['header_parameter_end']>=cfg.context: stop(Outcome.RESOURCE, Reason.CONTEXT)
        elif not r['elim_large']:
            r.update(core_elim_level=r['kernel_zero'], core_rec_parameters=r['header_parameters'], mode=Mode.ELIM_STORE_METADATA)
        else: r.update(mode=Mode.ELIM_PARAMETERS, x=r['header_parameters'])
    elif mode == Mode.ELIM_PARAMETERS:
        if c!=VectorKind.SYMBOLS or a!=r['header_parameter_base'] or bool(a)!=bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(elim_old_head=b, elim_fresh=1, elim_cursor=0, mode=Mode.ELIM_FRESH)
    elif mode == Mode.ELIM_FRESH:
        if r['elim_cursor']>=r['count']:
            r.update(mode=Mode.ELIM_SHIFT, elim_cursor=r['ctx'])
        elif s['context'][r['elim_cursor']][0]==r['elim_fresh']:
            if r['elim_fresh']==(1<<cfg.word_bits)-1: stop(Outcome.RESOURCE, Reason.INDEX)
            else: r.update(elim_fresh=r['elim_fresh']+1, elim_cursor=0)
        else: r['elim_cursor']+=1
    elif mode == Mode.ELIM_SHIFT:
        if r['elim_cursor']:
            s['context'][r['elim_cursor']]=list(s['context'][r['elim_cursor']-1]);r['elim_cursor']-=1
        else:
            s['context'][0]=[r['elim_fresh']]
            r.update(ctx=r['ctx']+1, count=r['count']+1, header_parameter_base=r['header_parameter_base']+1,
                header_parameter_end=r['header_parameter_end']+1, local_base=r['local_base']+1, mode=Mode.ELIM_STORE_LEVEL)
    elif mode == Mode.ELIM_STORE_LEVEL:
        ref=r['free'];s['heap'][ref]=[CellTag.LEVEL_PARAM,r['elim_fresh'],0,0]
        r.update(free=ref+1, core_elim_level=ref, mode=Mode.ELIM_STORE_CELL)
    elif mode == Mode.ELIM_STORE_CELL:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['elim_fresh'],r['elim_old_head'],0]
        r.update(free=ref+1, elim_symbol_head=ref, mode=Mode.ELIM_STORE_VECTOR)
    elif mode == Mode.ELIM_STORE_VECTOR:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR,r['count'],r['elim_symbol_head'],VectorKind.SYMBOLS]
        r.update(free=ref+1, core_rec_parameters=ref, mode=Mode.ELIM_STORE_METADATA)
    elif mode == Mode.ELIM_STORE_METADATA:
        ref=r['free'];s['heap'][ref]=[CellTag.ELIMINATION_INFO,r['core_elim_level'],r['core_rec_parameters'],r['core_K']]
        r.update(free=ref+1, core_elim_info=ref, sp=r['sp']-1);ret(ref)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
