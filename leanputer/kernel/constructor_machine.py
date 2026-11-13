"""General typed constructor CORE controller, DEVELOPMENT transition reference.

Pinned check_constructors; later constructor declaration/generation separate.
All raw types are checked under a provisional HEADER overlay. Pending ctor
metadata never supplies a type to a later ctor. Original-source nested staging
must precede this core; the original-source entry cannot bypass that stage.
"""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_CTOR_NAME,CALL_CTOR_DUPLICATE_DECLARATION,
    CALL_CTOR_DUPLICATE_PENDING,CALL_CTOR_SCOPE,CALL_CTOR_INFER,CALL_CTOR_TYPE_WHNF,CALL_CTOR_CONSUME,
    CALL_CTOR_FIELD_INFER,CALL_CTOR_FIELD_WHNF,CALL_CTOR_RESULT_PROP,CALL_CTOR_FIELD_LEVEL,
    CALL_CTOR_POSITIVITY,CALL_CTOR_RECURSIVE,CALL_CTOR_OPEN_FIELD,CALL_CTOR_RESULT_APPLICATION,CALL_CTOR_FIELD_VECTOR)

PRIVATE_PHASES=tuple(range(CALL_CTOR_NAME,CALL_CTOR_FIELD_VECTOR+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase=frame[0]
    def call(phase,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[phase,0,0,Task.CHECK_CONSTRUCTORS,0,0]
        r.update(task=task,x=x,mode=mode,depth=0,**updates)
    def positivity():call(CALL_CTOR_POSITIVITY,Task.CHECK_POSITIVITY,r['ctor_field_domain'])
    if phase==CALL_CTOR_NAME:
        call(CALL_CTOR_DUPLICATE_DECLARATION,Task.ENV_LOOKUP,0,query_symbol=r['ctor_symbol'],lookup_head=r['typing_head'])
    elif phase in (CALL_CTOR_DUPLICATE_DECLARATION,CALL_CTOR_DUPLICATE_PENDING):
        if r['r']:stop(Outcome.INVALID,Reason.DUPLICATE_DECLARATION)
        elif phase==CALL_CTOR_DUPLICATE_DECLARATION:
            call(CALL_CTOR_DUPLICATE_PENDING,Task.ENV_LOOKUP,0,query_symbol=r['ctor_symbol'],lookup_head=r['ctor_names'])
        else:call(CALL_CTOR_SCOPE,Task.EXPR_SCOPE,r['ctor_type'])
    elif phase==CALL_CTOR_SCOPE:call(CALL_CTOR_INFER,Task.INFER,r['ctor_type'],local_base=r['header_parameter_base'])
    elif phase==CALL_CTOR_INFER:call(CALL_CTOR_TYPE_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    elif phase==CALL_CTOR_TYPE_WHNF:r.update(task=Task.CHECK_CONSTRUCTORS,mode=Mode.CTOR_TYPE_SORT,x=r['r'])
    elif phase==CALL_CTOR_CONSUME:r.update(task=Task.CHECK_CONSTRUCTORS,mode=Mode.CTOR_FIELDS,x=r['r'])
    elif phase==CALL_CTOR_FIELD_INFER:call(CALL_CTOR_FIELD_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    elif phase==CALL_CTOR_FIELD_WHNF:r.update(task=Task.CHECK_CONSTRUCTORS,mode=Mode.CTOR_FIELD_SORT,x=r['r'])
    elif phase==CALL_CTOR_RESULT_PROP:
        if r['r']:positivity()
        else:call(CALL_CTOR_FIELD_LEVEL,Task.LEVEL_GEQ,r['header_result_level'],peer=r['ctor_field_level'])
    elif phase==CALL_CTOR_FIELD_LEVEL:
        if not r['r']:stop(Outcome.INVALID,Reason.UNIVERSE)
        else:positivity()
    elif phase==CALL_CTOR_POSITIVITY:
        if not r['r']:stop(Outcome.INVALID,Reason.INVALID_INDUCTIVE_APPLICATION)
        else:call(CALL_CTOR_RECURSIVE,Task.RECURSIVE_ARGUMENT,r['ctor_field_domain'])
    elif phase==CALL_CTOR_RECURSIVE:
        r['ctor_recursive']=r['r']
        call(CALL_CTOR_OPEN_FIELD,Task.OPEN_TELESCOPE,r['ctor_active_pi'],Mode.TELESCOPE,
            open_tag=Tag.PI,bounded=1,limit=r['ctx']+1)
    elif phase==CALL_CTOR_OPEN_FIELD:r.update(task=Task.CHECK_CONSTRUCTORS,mode=Mode.CTOR_FIELD_SELECT,x=r['r'],ctor_field_tail=r['r'])
    elif phase==CALL_CTOR_RESULT_APPLICATION:
        if not r['r'] or r['r']!=r['ctor_family_signature']:stop(Outcome.INVALID,Reason.INVALID_INDUCTIVE_APPLICATION)
        else:
            r['ctor_result_args']=r['app_args']
            call(CALL_CTOR_FIELD_VECTOR,Task.REVERSE_LIST,r['ctor_field_rev'],reverse_length=r['ctor_field_count'])
    elif phase==CALL_CTOR_FIELD_VECTOR:r.update(task=Task.CHECK_CONSTRUCTORS,mode=Mode.CTOR_STORE_META,ctor_field_vector=r['r'])


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.CHECK_CONSTRUCTORS:return False
    def call(phase,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[phase,0,0,Task.CHECK_CONSTRUCTORS,0,0]
        r.update(task=task,x=x,mode=mode,depth=0,**updates)
    def family_done():
        more=r['ctor_families_remaining']>1
        r.update(ctor_families_remaining=r['ctor_families_remaining']-1,ctx=r['header_parameter_end'])
        if more:r.update(mode=Mode.CTOR_FAMILY_CELL,x=r['ctor_family_next'])
        else:r['sp']-=1;ret(r['ctor_names'])
    def ensure_sort():
        if tag==Tag.SORT:return True
        stable=tag in (Tag.PI,Tag.LAM,Tag.BVAR,Tag.LOCAL,Tag.NAT,Tag.STRING)
        stop(Outcome.INVALID if stable else Outcome.GAP,Reason.EXPECT_SORT if stable else Reason.GAP_CONVERSION);return False
    mode=r['mode']
    if mode==Mode.WALK:
        if not r['header_seen']:stop(Outcome.INVALID,Reason.INVALID_DECLARATION)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_CTOR_NAME,0,0,Task.CHECK_CONSTRUCTORS,0,0]
            r.update(sp=r['sp']+1,typing_active=1,typing_head=r['header_head'],ctor_names=0,
                ctor_families_remaining=r['header_seen'],mode=Mode.CTOR_FAMILY_CELL,x=r['header_head'])
    elif mode==Mode.CTOR_FAMILY_CELL:
        r.update(ctor_family_next=b,mode=Mode.CTOR_FAMILY_SIGNATURE,x=a)
    elif mode==Mode.CTOR_FAMILY_SIGNATURE:r.update(ctor_family_signature=r['x'],mode=Mode.CTOR_FAMILY_SCHEME,x=c)
    elif mode==Mode.CTOR_FAMILY_SCHEME:
        if b!=8:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.CTOR_FAMILY_METADATA,x=c)
    elif mode==Mode.CTOR_FAMILY_METADATA:r.update(mode=Mode.CTOR_RAW_FAMILY,x=c)
    elif mode==Mode.CTOR_RAW_FAMILY:r.update(mode=Mode.CTOR_FAMILY_AUX,x=c)
    elif mode==Mode.CTOR_FAMILY_AUX:r.update(mode=Mode.CTOR_VECTOR,x=a)
    elif mode==Mode.CTOR_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:family_done()
        else:r.update(ctor_remaining=a,mode=Mode.CTOR_CELL,x=b)
    elif mode==Mode.CTOR_CELL:
        if not r['ctor_remaining'] or bool(b)!=(r['ctor_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(ctor_next=b,mode=Mode.CTOR_RECORD,x=a)
    elif mode==Mode.CTOR_RECORD:
        if not a or not 0<b<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:
            r.update(ctor_symbol=a,ctor_type=b,ctor_field_count=0,ctor_field_rev=0,ctx=r['header_parameter_end'])
            call(CALL_CTOR_NAME,Task.CHECK_NAME,r['symbols_root'],query_symbol=a)
    elif mode==Mode.CTOR_TYPE_SORT:
        if ensure_sort():call(CALL_CTOR_CONSUME,Task.CONSUME_PARAMETERS,r['ctor_type'],
            reuse_base=r['header_parameter_base'],reuse_end=r['header_parameter_end'],reuse_whnf=0)
    elif mode==Mode.CTOR_FIELDS:
        if tag==Tag.PI:
            r.update(ctor_active_pi=r['x'],ctor_field_domain=a)
            call(CALL_CTOR_FIELD_INFER,Task.INFER,a,local_base=r['header_parameter_base'])
        else:call(CALL_CTOR_RESULT_APPLICATION,Task.FAMILY_APPLICATION,r['x'])
    elif mode==Mode.CTOR_FIELD_SORT:
        if ensure_sort():
            r['ctor_field_level']=a
            call(CALL_CTOR_RESULT_PROP,Task.LEVEL_EQUIVALENT,r['header_result_level'],peer=r['kernel_zero'])
    elif mode==Mode.CTOR_FIELD_SELECT:r.update(mode=Mode.CTOR_FIELD_RECORD,x=s['context'][r['ctx']-1][0])
    elif mode==Mode.CTOR_FIELD_RECORD:
        if not 0<a<r['free'] or not 0<b<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['free']+2>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.CONSTRUCTOR_FIELD,r['x'],r['ctor_recursive'],r['ctor_field_count']]
            r.update(free=ref+1,ctor_field_info=ref,mode=Mode.CTOR_FIELD_LINK,x=r['ctor_field_tail'])
    elif mode==Mode.CTOR_FIELD_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['ctor_field_info'],r['ctor_field_rev'],0]
        r.update(free=ref+1,ctor_field_rev=ref,ctor_field_count=r['ctor_field_count']+1,mode=Mode.CTOR_FIELDS)
    elif mode==Mode.CTOR_STORE_META:
        if r['free']+3>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.CONSTRUCTOR_ANALYSIS,r['ctor_family_signature'],r['ctor_field_vector'],r['ctor_result_args']]
            r.update(free=ref+1,ctor_meta=ref,mode=Mode.CTOR_STORE_PENDING)
    elif mode==Mode.CTOR_STORE_PENDING:
        ref=r['free'];s['heap'][ref]=[CellTag.PENDING_CONSTRUCTOR,r['ctor_symbol'],r['ctor_type'],r['ctor_meta']]
        r.update(free=ref+1,ctor_pending=ref,mode=Mode.CTOR_LINK)
    elif mode==Mode.CTOR_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['ctor_pending'],r['ctor_names'],0]
        more=r['ctor_remaining']>1
        r.update(free=ref+1,ctor_names=ref,ctor_remaining=r['ctor_remaining']-1)
        if more:r.update(mode=Mode.CTOR_CELL,x=r['ctor_next'])
        else:family_done()
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
