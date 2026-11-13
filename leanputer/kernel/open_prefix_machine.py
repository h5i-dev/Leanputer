"""Open generated dependent recursive templates, DEVELOPMENT reference only."""
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_PREFIX_DOMAIN,
    CALL_PREFIX_LOCAL,CALL_PREFIX_INDEX,CALL_PREFIX_INDEX_VECTOR,CALL_PREFIX_LOCAL_VECTOR)
from .open_prefix_rules import NO_NODE,TAGS

PRIVATE_PHASES=tuple(range(CALL_PREFIX_DOMAIN,CALL_PREFIX_LOCAL_VECTOR+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase=frame[0]
    def call(p,task,x,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.OPEN_RECURSIVE_PREFIX,0,0]
        r.update(task=task,mode=Mode.WALK,x=x,depth=0,**updates)
    if phase==CALL_PREFIX_DOMAIN:call(CALL_PREFIX_LOCAL,Task.FRESH_LOCAL,r['r'],binder_info=r['prefix_binder_info'])
    elif phase==CALL_PREFIX_LOCAL:
        more=r['prefix_remaining']>1;r['prefix_remaining']-=1
        if more:r.update(task=Task.OPEN_RECURSIVE_PREFIX,mode=Mode.PREFIX_CELL,x=r['prefix_next'])
        else:call(CALL_PREFIX_LOCAL_VECTOR,Task.SNAPSHOT_SCOPE,0,abstract_base=r['prefix_mark'],abstract_end=r['ctx'])
    elif phase==CALL_PREFIX_LOCAL_VECTOR:
        r.update(task=Task.OPEN_RECURSIVE_PREFIX,prefix_locals=r['r'],prefix_index_rev=0,mode=Mode.PREFIX_INDICES,x=r['prefix_indices'])
    elif phase==CALL_PREFIX_INDEX:r.update(task=Task.OPEN_RECURSIVE_PREFIX,mode=Mode.PREFIX_INDEX_STORE)
    elif phase==CALL_PREFIX_INDEX_VECTOR:
        r.update(task=Task.OPEN_RECURSIVE_PREFIX,prefix_index_vector=r['r'],mode=Mode.PREFIX_STORE)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.OPEN_RECURSIVE_PREFIX:return False
    def call(p,task,x,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.OPEN_RECURSIVE_PREFIX,0,0]
        r.update(task=task,mode=Mode.WALK,x=x,depth=0,**updates)
    mode=r['mode']
    if mode==Mode.WALK:
        if r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_PREFIX_DOMAIN,0,0,Task.OPEN_RECURSIVE_PREFIX,0,0]
            r.update(sp=r['sp']+1,prefix_family=a,prefix_indices=c,prefix_mark=r['ctx'],mode=Mode.PREFIX_VECTOR,x=b)
    elif mode==Mode.PREFIX_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:call(CALL_PREFIX_LOCAL_VECTOR,Task.SNAPSHOT_SCOPE,0,abstract_base=r['prefix_mark'],abstract_end=r['ctx'])
        else:r.update(prefix_remaining=a,mode=Mode.PREFIX_CELL,x=b)
    elif mode==Mode.PREFIX_CELL:
        if not r['prefix_remaining'] or bool(b)!=(r['prefix_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(prefix_next=b,mode=Mode.PREFIX_BINDER,x=a)
    elif mode==Mode.PREFIX_BINDER:
        r['prefix_binder_info']=b
        call(CALL_PREFIX_DOMAIN,Task.INSTANTIATE_SCOPE,a,abstract_base=r['prefix_mark'],abstract_end=r['ctx'])
    elif mode==Mode.PREFIX_INDICES:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        else:
            r.update(prefix_index_count=a,prefix_index_remaining=a)
            if a:r.update(mode=Mode.PREFIX_INDEX_CELL,x=b)
            else:call(CALL_PREFIX_INDEX_VECTOR,Task.REVERSE_LIST,0,reverse_length=0)
    elif mode==Mode.PREFIX_INDEX_CELL:
        if not r['prefix_index_remaining'] or bool(b)!=(r['prefix_index_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:
            r['prefix_index_next']=b
            call(CALL_PREFIX_INDEX,Task.INSTANTIATE_SCOPE,a,abstract_base=r['prefix_mark'],abstract_end=r['ctx'])
    elif mode==Mode.PREFIX_INDEX_STORE:
        if r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['r'],r['prefix_index_rev'],0]
            more=r['prefix_index_remaining']>1
            r.update(free=ref+1,prefix_index_rev=ref,prefix_index_remaining=r['prefix_index_remaining']-1)
            if more:r.update(mode=Mode.PREFIX_INDEX_CELL,x=r['prefix_index_next'])
            else:call(CALL_PREFIX_INDEX_VECTOR,Task.REVERSE_LIST,ref,reverse_length=r['prefix_index_count'])
    elif mode==Mode.PREFIX_STORE:
        if r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.OPENED_RECURSIVE_PREFIX,r['prefix_family'],r['prefix_locals'],r['prefix_index_vector']]
            r.update(free=ref+1,opened_prefix=ref,sp=r['sp']-1);ret(ref)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
