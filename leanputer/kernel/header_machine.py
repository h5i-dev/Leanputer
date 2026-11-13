"""General inductive header algorithm, DEVELOPMENT transition reference.

Pinned inductive.cpp:check_inductive_types. Checks all headers in PREVIOUS Γ;
opens shared parameters, reuses their dependent domains for every family, opens
indices and derives common result-level data. Private outputs do not publish an
inductive block. The outer source controller still GAPs unfinished later stages.
"""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_HEADER_PARAMETERS,
    CALL_HEADER_NAME,CALL_HEADER_DUPLICATE_GLOBAL,CALL_HEADER_DUPLICATE_PRIVATE,
    CALL_HEADER_SCOPE,CALL_HEADER_INFER,CALL_HEADER_TYPE_WHNF,
    CALL_HEADER_OPEN_PARAMETERS,CALL_HEADER_CONSUME,CALL_HEADER_INDICES,CALL_HEADER_LEVEL,CALL_HEADER_FORMAL_LEVELS)

PRIVATE_PHASES=tuple(range(CALL_HEADER_PARAMETERS,CALL_HEADER_LEVEL+1))+(CALL_HEADER_FORMAL_LEVELS,)


def resume(machine,frame,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    def call(phase,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[phase,0,0,Task.ANALYZE_HEADERS,0,0]
        r.update(task=task,x=x,mode=mode,depth=0,**updates)
    phase=frame[0]
    if phase==CALL_HEADER_PARAMETERS:
        call(CALL_HEADER_FORMAL_LEVELS,Task.FORMAL_LEVELS,0)
    elif phase==CALL_HEADER_FORMAL_LEVELS:
        r['header_levels']=r['r']
        end=r['ctx']+r['header_parameter_count']
        if end>cfg.context:stop(Outcome.RESOURCE,Reason.CONTEXT)
        else:r.update(task=Task.ANALYZE_HEADERS,mode=Mode.HEADER_VECTOR,x=r['header_vector'],
            header_parameter_base=r['ctx'],header_parameter_end=end,local_base=r['ctx'])
    elif phase==CALL_HEADER_NAME:
        call(CALL_HEADER_DUPLICATE_GLOBAL,Task.ENV_LOOKUP,0,query_symbol=r['header_symbol'],lookup_head=r['typing_head'] if r['typing_active'] else r['env_head'])
    elif phase in (CALL_HEADER_DUPLICATE_GLOBAL,CALL_HEADER_DUPLICATE_PRIVATE):
        if r['r']:stop(Outcome.INVALID,Reason.DUPLICATE_DECLARATION)
        elif phase==CALL_HEADER_DUPLICATE_GLOBAL:
            call(CALL_HEADER_DUPLICATE_PRIVATE,Task.ENV_LOOKUP,0,query_symbol=r['header_symbol'],lookup_head=r['header_head'])
        else:call(CALL_HEADER_SCOPE,Task.EXPR_SCOPE,r['header_type'])
    elif phase==CALL_HEADER_SCOPE:
        call(CALL_HEADER_INFER,Task.INFER,r['header_type'],local_base=r['header_parameter_base'])
    elif phase==CALL_HEADER_INFER:call(CALL_HEADER_TYPE_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    elif phase==CALL_HEADER_TYPE_WHNF:r.update(task=Task.ANALYZE_HEADERS,mode=Mode.HEADER_TYPE_SORT,x=r['r'])
    elif phase in (CALL_HEADER_OPEN_PARAMETERS,CALL_HEADER_CONSUME):
        call(CALL_HEADER_INDICES,Task.OPEN_TELESCOPE,r['r'],Mode.TELESCOPE,open_tag=Tag.PI,bounded=0,limit=0)
    elif phase==CALL_HEADER_INDICES:r.update(task=Task.ANALYZE_HEADERS,mode=Mode.HEADER_SORT,x=r['r'])
    elif phase==CALL_HEADER_LEVEL:
        if not r['r']:stop(Outcome.INVALID,Reason.UNIVERSE)
        else:r.update(task=Task.ANALYZE_HEADERS,mode=Mode.HEADER_STORE_FAMILY)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.ANALYZE_HEADERS:return False
    def call(phase,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[phase,0,0,Task.ANALYZE_HEADERS,0,0]
        r.update(task=task,x=x,mode=mode,depth=0,**updates)
    def ensure_sort():
        if tag==Tag.SORT:return True
        stable=tag in (Tag.PI,Tag.LAM,Tag.BVAR,Tag.LOCAL,Tag.NAT,Tag.STRING)
        stop(Outcome.INVALID if stable else Outcome.GAP,Reason.EXPECT_SORT if stable else Reason.GAP_CONVERSION)
        return False
    if r['mode']==Mode.WALK:
        if r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_HEADER_PARAMETERS,0,0,Task.ANALYZE_HEADERS,0,0]
            r.update(sp=r['sp']+1,task=Task.LOAD_PARAMETERS,x=r['header_parameters'],
                header_block=r['x'],header_parameter_count=a,header_vector=b,header_head=r['typing_head'] if r['typing_active'] else r['env_head'],header_seen=0)
    elif r['mode']==Mode.HEADER_VECTOR:
        if c!=VectorKind.REFERENCES or not a or not b:stop(Outcome.INVALID,Reason.INVALID_DECLARATION)
        else:r.update(mode=Mode.HEADER_CELL,x=b,header_remaining=a)
    elif r['mode']==Mode.HEADER_CELL:
        if not r['header_remaining'] or bool(b)!=(r['header_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.HEADER_FAMILY,x=a,header_next=b)
    elif r['mode']==Mode.HEADER_FAMILY:
        if not a or not 0<b<r['free'] or not 0<c<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:
            r.update(header_symbol=a,header_type=b,header_raw=r['x'])
            call(CALL_HEADER_NAME,Task.CHECK_NAME,r['symbols_root'],query_symbol=a)
    elif r['mode']==Mode.HEADER_TYPE_SORT:
        if ensure_sort():
            if not r['header_seen']:
                call(CALL_HEADER_OPEN_PARAMETERS,Task.OPEN_TELESCOPE,r['header_type'],Mode.TELESCOPE,
                    open_tag=Tag.PI,bounded=1,limit=r['header_parameter_end'])
            else:call(CALL_HEADER_CONSUME,Task.CONSUME_PARAMETERS,r['header_type'],
                reuse_base=r['header_parameter_base'],reuse_end=r['header_parameter_end'],reuse_whnf=1)
    elif r['mode']==Mode.HEADER_SORT:
        if ensure_sort():
            r.update(header_indices=r['ctx']-r['header_parameter_end'],header_current_level=a)
            if not r['header_seen']:r.update(header_result_level=a,mode=Mode.HEADER_STORE_FAMILY)
            else:call(CALL_HEADER_LEVEL,Task.LEVEL_EQUIVALENT,a,peer=r['header_result_level'])
    elif r['mode']==Mode.HEADER_STORE_FAMILY:
        if r['free']+4>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_FAMILY,r['header_indices'],r['header_current_level'],r['header_raw']]
            r.update(free=ref+1,header_meta=ref,mode=Mode.HEADER_STORE_SCHEME)
    elif r['mode']==Mode.HEADER_STORE_SCHEME:
        ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_SCHEME,r['header_parameters'],8,r['header_meta']]
        r.update(free=ref+1,header_scheme=ref,mode=Mode.HEADER_STORE_SIGNATURE)
    elif r['mode']==Mode.HEADER_STORE_SIGNATURE:
        ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_SIGNATURE,r['header_symbol'],r['header_type'],r['header_scheme']]
        r.update(free=ref+1,header_signature=ref,mode=Mode.HEADER_LINK)
    elif r['mode']==Mode.HEADER_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['header_signature'],r['header_head'],0]
        more=r['header_remaining']>1
        r.update(free=ref+1,header_head=ref,header_remaining=r['header_remaining']-1,
            header_seen=r['header_seen']+1,ctx=r['header_parameter_end'])
        if more:r.update(mode=Mode.HEADER_CELL,x=r['header_next'])
        else:r['sp']-=1;ret(ref)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
