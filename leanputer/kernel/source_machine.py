"""General source declaration controller, DEVELOPMENT TRANSITION REFERENCE.

This is not a native inference callback. It checks raw names, unique parameters,
scopes, type Sort and body conversion BEFORE private publication. Missing general
inductive/recursor/primitive/full-conversion services report GAP, never axioms.
Ordinary source algorithms are generic; no name/field-count feature catalog.
"""
from .arena import Tag
from .native_cells import CellTag, DeclarationKind
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_SOURCE_NAME, CALL_SOURCE_DUPLICATE, CALL_SOURCE_PARAMETERS,
    CALL_SOURCE_TYPE_SCOPE, CALL_SOURCE_TYPE_INFER, CALL_SOURCE_TYPE_WHNF,
    CALL_SOURCE_PROPOSITION, CALL_SOURCE_VALUE_SCOPE, CALL_SOURCE_VALUE_INFER,
    CALL_SOURCE_VALUE_CONVERT, CALL_SOURCE_BLOCK_HEADERS, CALL_SOURCE_CORE_CONSTRUCTORS, CALL_SOURCE_CORE_NAMES, CALL_SOURCE_DECLARE_CONSTRUCTORS, CALL_SOURCE_ELIMINATION, CALL_SOURCE_MOTIVES, CALL_SOURCE_FLAGS, CALL_SOURCE_MINORS)

PRIVATE_PHASES = tuple(range(CALL_SOURCE_NAME, CALL_SOURCE_VALUE_CONVERT+1))+(CALL_SOURCE_BLOCK_HEADERS,CALL_SOURCE_CORE_CONSTRUCTORS,CALL_SOURCE_CORE_NAMES,CALL_SOURCE_DECLARE_CONSTRUCTORS,CALL_SOURCE_ELIMINATION,CALL_SOURCE_MOTIVES,CALL_SOURCE_FLAGS,CALL_SOURCE_MINORS,)


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']
    phase = frame[0]
    def call(next_phase, task, x, mode=Mode.WALK, **updates):
        s['stack'][r['sp']-1] = [next_phase, 0, 0, Task.CHECK_SOURCE, 0, 0]
        r.update(mode=mode, task=task, x=x, depth=0, **updates)
    if phase == CALL_SOURCE_BLOCK_HEADERS:
        if r['core_operation'] and r['raw_index']==r['core_index']:
            call(CALL_SOURCE_CORE_CONSTRUCTORS,Task.CHECK_CONSTRUCTORS,0)
        else:stop(Outcome.GAP, Reason.GAP_INDUCTIVE) # Original-source nested staging remains missing.
    elif phase == CALL_SOURCE_CORE_CONSTRUCTORS:
        call(CALL_SOURCE_CORE_NAMES,Task.CHECK_CORE_NAMES,0)
    elif phase == CALL_SOURCE_CORE_NAMES:
        call(CALL_SOURCE_DECLARE_CONSTRUCTORS,Task.DECLARE_CONSTRUCTORS,0)
    elif phase == CALL_SOURCE_DECLARE_CONSTRUCTORS:
        call(CALL_SOURCE_FLAGS,Task.BLOCK_FLAGS,0)
    elif phase == CALL_SOURCE_FLAGS:
        call(CALL_SOURCE_ELIMINATION,Task.INIT_ELIMINATION,0)
    elif phase == CALL_SOURCE_ELIMINATION:
        call(CALL_SOURCE_MOTIVES,Task.BUILD_MOTIVES,0)
    elif phase == CALL_SOURCE_MOTIVES:
        call(CALL_SOURCE_MINORS,Task.BUILD_MINORS,0)
    elif phase == CALL_SOURCE_MINORS:
        stop(Outcome.GAP,Reason.GAP_RECURSOR_GENERATION)
    elif phase == CALL_SOURCE_NAME:
        call(CALL_SOURCE_DUPLICATE, Task.ENV_LOOKUP, r['active_type'], query_symbol=r['active_symbol'], lookup_head=r['env_head'])
    elif phase == CALL_SOURCE_DUPLICATE:
        if r['r']: stop(Outcome.INVALID, Reason.DUPLICATE_DECLARATION)
        else: call(CALL_SOURCE_PARAMETERS, Task.LOAD_PARAMETERS, r['active_parameters'])
    elif phase == CALL_SOURCE_PARAMETERS:
        call(CALL_SOURCE_TYPE_SCOPE, Task.EXPR_SCOPE, r['active_type'])
    elif phase == CALL_SOURCE_TYPE_SCOPE:
        call(CALL_SOURCE_TYPE_INFER, Task.INFER, r['active_type'], local_base=r['ctx'])
    elif phase == CALL_SOURCE_TYPE_INFER:
        call(CALL_SOURCE_TYPE_WHNF, Task.BETA_ZETA, r['r'], Mode.BETA_ZETA)
    elif phase == CALL_SOURCE_TYPE_WHNF:
        r.update(task=Task.CHECK_SOURCE, mode=Mode.SOURCE_TYPE_SORT, x=r['r'])
    elif phase == CALL_SOURCE_PROPOSITION:
        if not r['r']: stop(Outcome.INVALID, Reason.INVALID_DECLARATION)
        else: r.update(task=Task.CHECK_SOURCE, mode=Mode.SOURCE_REQUIRE_VALUE, x=r['active_type'])
    elif phase == CALL_SOURCE_VALUE_SCOPE:
        call(CALL_SOURCE_VALUE_INFER, Task.INFER, r['active_value'], local_base=r['ctx'])
    elif phase == CALL_SOURCE_VALUE_INFER:
        call(CALL_SOURCE_VALUE_CONVERT, Task.CONVERT_POSITIVE, r['r'], peer=r['active_type'])
    elif phase == CALL_SOURCE_VALUE_CONVERT:
        if not r['r']: stop(Outcome.INVALID, Reason.TYPE_MISMATCH)
        else: r.update(task=Task.CHECK_SOURCE, mode=Mode.SOURCE_COMMIT, x=r['active_type'])


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.CHECK_SOURCE: return False
    if r['mode'] == Mode.WALK:
        if not 0 < r['decl_count'] <= cfg.constants or r['target_index'] != r['decl_count']-1 or (r['core_operation'] and r['core_index']>=r['target_index']):
            stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            zero = r['free']
            s['heap'][zero] = [CellTag.LEVEL_ZERO, 0, 0, 0]
            r.update(free=zero+1, kernel_zero=zero, env_ready=1, env_head=0, typing_active=0, typing_head=0, decl=0, raw_index=0,
                ctx=0, count=0, arg_base=0, local_base=0, sp=0, pending_scope=0, pending_infer=0,
                pending_open=0, pending_fold=0, pending_compare=0, mode=Mode.SOURCE_READ, x=0)
    elif r['mode'] == Mode.SOURCE_READ:
        if r['raw_index'] >= r['decl_count']: stop(Outcome.INVALID, Reason.SYNTAX)
        else:
            kind, symbol, parameters, type_ref, value, extra = s['constants'][r['raw_index']]
            if r['raw_index'] == r['target_index'] and kind == DeclarationKind.AXIOM:
                stop(Outcome.INVALID, Reason.INVALID_DECLARATION)
            elif kind == DeclarationKind.BLOCK:
                if r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [CALL_SOURCE_BLOCK_HEADERS,0,0,Task.CHECK_SOURCE,0,0]
                    r.update(sp=r['sp']+1,task=Task.ANALYZE_HEADERS,mode=Mode.WALK,x=extra,header_parameters=parameters)
            elif kind == DeclarationKind.RECURSOR_CLAIM: stop(Outcome.GAP, Reason.GAP_RECURSOR_CLAIM)
            elif kind == DeclarationKind.QUOT_PRIMITIVE: stop(Outcome.GAP, Reason.GAP_PRIMITIVE)
            elif kind not in (DeclarationKind.AXIOM, DeclarationKind.DEFINITION, DeclarationKind.THEOREM, DeclarationKind.OPAQUE):
                stop(Outcome.INVALID, Reason.INVALID_DECLARATION)
            elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
            else:
                r.update(active_kind=int(kind), active_symbol=symbol, active_parameters=parameters,
                    active_type=type_ref, active_value=value, active_extra=extra, query_symbol=symbol)
                s['stack'][r['sp']] = [CALL_SOURCE_NAME, 0, 0, Task.CHECK_SOURCE, 0, 0]
                r.update(sp=r['sp']+1, task=Task.CHECK_NAME, mode=Mode.WALK, x=r['symbols_root'])
    elif r['mode'] == Mode.SOURCE_TYPE_SORT:
        if tag != Tag.SORT:
            if tag in (Tag.PI, Tag.LAM, Tag.BVAR, Tag.LOCAL, Tag.NAT, Tag.STRING): stop(Outcome.INVALID, Reason.EXPECT_SORT)
            else: stop(Outcome.GAP, Reason.GAP_CONVERSION)
        elif r['active_kind'] == DeclarationKind.THEOREM:
            s['stack'][r['sp']-1] = [CALL_SOURCE_PROPOSITION, 0, 0, Task.CHECK_SOURCE, 0, 0]
            r.update(task=Task.LEVEL_EQUIVALENT, mode=Mode.WALK, x=a, peer=r['kernel_zero'])
        else: r.update(mode=Mode.SOURCE_REQUIRE_VALUE, x=r['active_type'])
    elif r['mode'] == Mode.SOURCE_REQUIRE_VALUE:
        if r['active_kind'] == DeclarationKind.AXIOM:
            if r['active_value']: stop(Outcome.INVALID, Reason.INVALID_DECLARATION)
            else: r['mode'] = Mode.SOURCE_COMMIT
        elif not r['active_value']: stop(Outcome.GAP, Reason.UNAVAILABLE_BODY)
        else:
            s['stack'][r['sp']-1] = [CALL_SOURCE_VALUE_SCOPE, 0, 0, Task.CHECK_SOURCE, 0, 0]
            r.update(mode=Mode.WALK, task=Task.EXPR_SCOPE, x=r['active_value'], depth=0)
    elif r['mode'] == Mode.SOURCE_COMMIT:
        if r['raw_index'] == r['target_index']:
            r.update(sp=r['sp']-1, r=1); stop(Outcome.DONE)
        elif r['free']+3 > cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            ref = r['free']
            s['heap'][ref] = [CellTag.CHECKED_SCHEME, r['active_parameters'], r['active_kind'], r['active_value']]
            r.update(free=ref+1, commit_scheme=ref, mode=Mode.SOURCE_SIGNATURE)
    elif r['mode'] == Mode.SOURCE_SIGNATURE:
        ref = r['free']
        s['heap'][ref] = [CellTag.CHECKED_SIGNATURE, r['active_symbol'], r['active_type'], r['commit_scheme']]
        r.update(free=ref+1, commit_signature=ref, mode=Mode.SOURCE_LINK)
    elif r['mode'] == Mode.SOURCE_LINK:
        ref = r['free']
        s['heap'][ref] = [CellTag.VECTOR_CELL, r['commit_signature'], r['env_head'], 0]
        r.update(free=ref+1, env_head=ref, decl=r['decl']+1, raw_index=r['raw_index']+1,
            sp=r['sp']-1, mode=Mode.SOURCE_READ, x=0)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
