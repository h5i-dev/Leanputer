"""Generic closed recursor-type pass, DEVELOPMENT reference only."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_REC_TYPE_BODY,
    CALL_REC_TYPE_FOLD,CALL_REC_TYPE_SCOPE,CALL_REC_TYPE_VECTOR,CALL_REC_TYPE_RESTORE)
from .recursor_type_rules import NO_NODE,TAGS

PRIVATE_PHASES=tuple(range(CALL_REC_TYPE_BODY,CALL_REC_TYPE_VECTOR+1))+(CALL_REC_TYPE_RESTORE,)


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase=frame[0]
    def call(p,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.BUILD_RECURSOR_TYPES,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    if phase==CALL_REC_TYPE_RESTORE:r.update(task=Task.BUILD_RECURSOR_TYPES,mode=Mode.REC_TYPE_MAJOR,x=r['rec_type_major'])
    elif phase==CALL_REC_TYPE_BODY:
        call(CALL_REC_TYPE_FOLD,Task.FOLD_TELESCOPE,r['r'],Mode.FOLD_SELECT,
            fold_base=r['header_parameter_base'],fold_body=r['r'],fold_tag=Tag.PI)
    elif phase==CALL_REC_TYPE_FOLD:
        r['rec_type_closed']=r['r'];call(CALL_REC_TYPE_SCOPE,Task.EXPR_SCOPE,r['r'])
    elif phase==CALL_REC_TYPE_SCOPE:r.update(task=Task.BUILD_RECURSOR_TYPES,ctx=r['rec_type_mark'],mode=Mode.REC_TYPE_STORE)
    elif phase==CALL_REC_TYPE_VECTOR:
        r.update(task=Task.BUILD_RECURSOR_TYPES,core_rec_types=r['r'],sp=r['sp']-1);ret(r['r'])


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.BUILD_RECURSOR_TYPES:return False
    mode=r['mode']
    def call(p,task,x,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.BUILD_RECURSOR_TYPES,0,0]
        r.update(task=task,mode=Mode.WALK,x=x,depth=0,**updates)
    if mode==Mode.WALK:
        if not r['core_motives'] or not r['core_minors'] or r['ctx']!=r['header_parameter_end']+r['header_seen']+r['core_ctor_declared']:
            stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_REC_TYPE_VECTOR,0,0,Task.BUILD_RECURSOR_TYPES,0,0]
            r.update(sp=r['sp']+1,rec_type_mark=r['ctx'],rec_type_rev=0,mode=Mode.REC_TYPE_VECTOR,x=r['core_motives'])
    elif mode==Mode.REC_TYPE_VECTOR:
        if c!=VectorKind.REFERENCES or not a or not b or a!=r['header_seen']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(rec_type_remaining=a,mode=Mode.REC_TYPE_CELL,x=b)
    elif mode==Mode.REC_TYPE_CELL:
        if not r['rec_type_remaining'] or bool(b)!=(r['rec_type_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(rec_type_next=b,mode=Mode.REC_TYPE_INFO,x=a)
    elif mode==Mode.REC_TYPE_INFO:r.update(rec_type_family=a,rec_type_motive=b,mode=Mode.REC_TYPE_TELESCOPE,x=c)
    elif mode==Mode.REC_TYPE_TELESCOPE:
        r.update(rec_type_major=b,rec_type_symbol=c)
        call(CALL_REC_TYPE_RESTORE,Task.RESTORE_SCOPE,a)
    elif mode==Mode.REC_TYPE_MAJOR:
        if r['ctx']>=cfg.context:stop(Outcome.RESOURCE,Reason.CONTEXT)
        else:
            s['context'][r['ctx']]=[r['x']];r.update(ctx=r['ctx']+1,mode=Mode.REC_TYPE_MOTIVE_RECORD,x=r['rec_type_motive'])
    elif mode==Mode.REC_TYPE_MOTIVE_RECORD:
        call(CALL_REC_TYPE_BODY,Task.APPLY_SCOPE,a,apply_base=r['rec_type_mark'],apply_end=r['ctx'])
    elif mode==Mode.REC_TYPE_STORE:
        if r['free']+2>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.RECURSOR_TYPE,r['rec_type_family'],r['rec_type_closed'],r['rec_type_symbol']]
            r.update(free=ref+1,rec_type_info=ref,mode=Mode.REC_TYPE_LINK)
    elif mode==Mode.REC_TYPE_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['rec_type_info'],r['rec_type_rev'],0]
        more=r['rec_type_remaining']>1;r.update(free=ref+1,rec_type_rev=ref,rec_type_remaining=r['rec_type_remaining']-1)
        if more:r.update(mode=Mode.REC_TYPE_CELL,x=r['rec_type_next'])
        else:call(CALL_REC_TYPE_VECTOR,Task.REVERSE_LIST,ref,reverse_length=r['header_seen'])
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
