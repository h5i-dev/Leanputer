"""General mk_rec_infos minor/functional IH pass, DEVELOPMENT reference only."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_MINOR_OWN_MOTIVE,
    CALL_MINOR_RESULT_INDICES,CALL_MINOR_PARAMETERS,CALL_MINOR_FIELDS,CALL_MINOR_PREFIX,
    CALL_MINOR_IH_MOTIVE,CALL_MINOR_IH_INDICES,CALL_MINOR_FUNCTION,CALL_MINOR_IH_FOLD,
    CALL_MINOR_IH_LOCAL,CALL_MINOR_FOLD,CALL_MINOR_LOCAL,CALL_MINOR_VECTOR)
from .minor_rules import NO_NODE,TAGS

PRIVATE_PHASES=tuple(range(CALL_MINOR_OWN_MOTIVE,CALL_MINOR_VECTOR+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase=frame[0]
    def call(p,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.BUILD_MINORS,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    if phase==CALL_MINOR_OWN_MOTIVE:
        call(CALL_MINOR_RESULT_INDICES,Task.APPLY_LIST,r['r'],list_head=r['minor_result_args'],list_skip=r['header_parameter_count'])
    elif phase==CALL_MINOR_RESULT_INDICES:
        r.update(task=Task.BUILD_MINORS,minor_result_fn=r['r'],mode=Mode.MINOR_CONSTANT)
    elif phase==CALL_MINOR_PARAMETERS:
        call(CALL_MINOR_FIELDS,Task.APPLY_SCOPE,r['r'],apply_base=r['minor_mark'],apply_end=r['minor_fields_end'])
    elif phase==CALL_MINOR_FIELDS:r.update(task=Task.BUILD_MINORS,mode=Mode.MINOR_RESULT)
    elif phase==CALL_MINOR_PREFIX:r.update(task=Task.BUILD_MINORS,mode=Mode.MINOR_OPENED,x=r['r'])
    elif phase==CALL_MINOR_IH_MOTIVE:
        r.update(task=Task.BUILD_MINORS,minor_ih_motive=r['r'],mode=Mode.MINOR_IH_INDICES,x=r['minor_index_vector'])
    elif phase==CALL_MINOR_IH_INDICES:
        r['minor_ih_target']=r['r']
        call(CALL_MINOR_FUNCTION,Task.APPLY_SCOPE,r['minor_recursive_local'],apply_base=r['minor_ih_mark'],apply_end=r['ctx'])
    elif phase==CALL_MINOR_FUNCTION:r.update(task=Task.BUILD_MINORS,mode=Mode.MINOR_IH_RESULT)
    elif phase==CALL_MINOR_IH_FOLD:call(CALL_MINOR_IH_LOCAL,Task.FRESH_LOCAL,r['r'],binder_info=0)
    elif phase==CALL_MINOR_IH_LOCAL:
        more=r['minor_ih_remaining']>1;r['minor_ih_remaining']-=1
        if more:r.update(task=Task.BUILD_MINORS,mode=Mode.MINOR_IH_CELL,x=r['minor_ih_next'])
        else:call(CALL_MINOR_FOLD,Task.FOLD_TELESCOPE,r['minor_result_type'],Mode.FOLD_SELECT,
            fold_base=r['minor_mark'],fold_body=r['minor_result_type'],fold_tag=Tag.PI)
    elif phase==CALL_MINOR_FOLD:call(CALL_MINOR_LOCAL,Task.FRESH_LOCAL,r['r'],binder_info=0)
    elif phase==CALL_MINOR_LOCAL:r.update(task=Task.BUILD_MINORS,minor_local=r['fresh_record'],mode=Mode.MINOR_STORE)
    elif phase==CALL_MINOR_VECTOR:
        r.update(task=Task.BUILD_MINORS,core_minors=r['r'],sp=r['sp']-1);ret(r['r'])


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.BUILD_MINORS:return False
    def call(p,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.BUILD_MINORS,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    def fold():call(CALL_MINOR_FOLD,Task.FOLD_TELESCOPE,r['minor_result_type'],Mode.FOLD_SELECT,
        fold_base=r['minor_mark'],fold_body=r['minor_result_type'],fold_tag=Tag.PI)
    def own_motive():call(CALL_MINOR_OWN_MOTIVE,Task.FIND_MOTIVE,r['core_motives'],motive_query=r['minor_family'])
    def next_ih():
        more=r['minor_ih_remaining']>1;r['minor_ih_remaining']-=1
        if more:r.update(mode=Mode.MINOR_IH_CELL,x=r['minor_ih_next'])
        else:fold()
    def room(n=1):
        if r['free']+n>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP);return False
        return True
    mode=r['mode']
    if mode==Mode.WALK:
        if not r['core_motives'] or not r['core_constructors'] or r['ctx']!=r['header_parameter_end']+r['header_seen']:
            stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_MINOR_VECTOR,0,0,Task.BUILD_MINORS,0,0]
            r.update(sp=r['sp']+1,minor_rev=0,mode=Mode.MINOR_VECTOR,x=r['core_constructors'])
    elif mode==Mode.MINOR_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b) or a!=r['core_ctor_declared']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:call(CALL_MINOR_VECTOR,Task.REVERSE_LIST,0,reverse_length=0)
        else:r.update(minor_remaining=a,mode=Mode.MINOR_CELL,x=b)
    elif mode==Mode.MINOR_CELL:
        if not r['minor_remaining'] or bool(b)!=(r['minor_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(minor_next=b,minor_pending=a,mode=Mode.MINOR_PENDING,x=a,minor_mark=r['ctx'])
    elif mode==Mode.MINOR_PENDING:r.update(minor_symbol=a,mode=Mode.MINOR_ANALYSIS,x=c)
    elif mode==Mode.MINOR_ANALYSIS:r.update(minor_family=a,minor_fields=b,minor_result_args=c,mode=Mode.MINOR_FIELD_VECTOR,x=b)
    elif mode==Mode.MINOR_FIELD_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['ctx']+a>cfg.context:stop(Outcome.RESOURCE,Reason.CONTEXT)
        else:
            r.update(minor_field_count=a,minor_restore_remaining=a,minor_fields_end=r['ctx']+a)
            if a:r.update(mode=Mode.MINOR_FIELD_CELL,x=b)
            else:own_motive()
    elif mode==Mode.MINOR_FIELD_CELL:
        if not r['minor_restore_remaining'] or bool(b)!=(r['minor_restore_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(minor_restore_next=b,mode=Mode.MINOR_FIELD,x=a)
    elif mode==Mode.MINOR_FIELD:r.update(mode=Mode.MINOR_RESTORE_RECORD,x=a)
    elif mode==Mode.MINOR_RESTORE_RECORD:
        s['context'][r['ctx']]=[r['x']];more=r['minor_restore_remaining']>1
        r.update(ctx=r['ctx']+1,minor_restore_remaining=r['minor_restore_remaining']-1)
        if more:r.update(mode=Mode.MINOR_FIELD_CELL,x=r['minor_restore_next'])
        else:own_motive()
    elif mode==Mode.MINOR_CONSTANT:
        if room():
            ref=r['free'];s['heap'][ref]=[Tag.CONST,r['minor_symbol'],r['header_levels'],0];r['free']=ref+1
            call(CALL_MINOR_PARAMETERS,Task.APPLY_SCOPE,ref,apply_base=r['header_parameter_base'],apply_end=r['header_parameter_end'])
    elif mode==Mode.MINOR_RESULT:
        if room():
            ref=r['free'];s['heap'][ref]=[Tag.APP,r['minor_result_fn'],r['r'],0]
            r.update(free=ref+1,minor_result_type=ref,mode=Mode.MINOR_IH_VECTOR,x=r['minor_fields'])
    elif mode==Mode.MINOR_IH_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b) or a!=r['minor_field_count']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:fold()
        else:r.update(minor_ih_remaining=a,mode=Mode.MINOR_IH_CELL,x=b)
    elif mode==Mode.MINOR_IH_CELL:
        if not r['minor_ih_remaining'] or bool(b)!=(r['minor_ih_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(minor_ih_next=b,mode=Mode.MINOR_IH_FIELD,x=a)
    elif mode==Mode.MINOR_IH_FIELD:
        if not b:next_ih()
        else:r.update(minor_descriptor=b,mode=Mode.MINOR_IH_LOCAL,x=a)
    elif mode==Mode.MINOR_IH_LOCAL:
        r.update(minor_recursive_local=a,minor_ih_mark=r['ctx'])
        call(CALL_MINOR_PREFIX,Task.OPEN_RECURSIVE_PREFIX,r['minor_descriptor'])
    elif mode==Mode.MINOR_OPENED:
        r['minor_index_vector']=c
        call(CALL_MINOR_IH_MOTIVE,Task.FIND_MOTIVE,r['core_motives'],motive_query=a)
    elif mode==Mode.MINOR_IH_INDICES:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        else:call(CALL_MINOR_IH_INDICES,Task.APPLY_LIST,r['minor_ih_motive'],list_head=b,list_skip=0)
    elif mode==Mode.MINOR_IH_RESULT:
        if room():
            ref=r['free'];s['heap'][ref]=[Tag.APP,r['minor_ih_target'],r['r'],0];r['free']=ref+1
            call(CALL_MINOR_IH_FOLD,Task.FOLD_TELESCOPE,ref,Mode.FOLD_SELECT,fold_base=r['minor_ih_mark'],fold_body=ref,fold_tag=Tag.PI)
    elif mode==Mode.MINOR_STORE:
        if room(2):
            ref=r['free'];s['heap'][ref]=[CellTag.MINOR_INFO,r['minor_pending'],r['minor_local'],r['minor_field_count']]
            r.update(free=ref+1,minor_info=ref,mode=Mode.MINOR_LINK)
    elif mode==Mode.MINOR_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['minor_info'],r['minor_rev'],0]
        more=r['minor_remaining']>1;r.update(free=ref+1,minor_rev=ref,minor_remaining=r['minor_remaining']-1)
        if more:r.update(mode=Mode.MINOR_CELL,x=r['minor_next'])
        else:call(CALL_MINOR_VECTOR,Task.REVERSE_LIST,ref,reverse_length=r['core_ctor_declared'])
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
