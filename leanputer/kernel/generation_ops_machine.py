"""Shared recursor construction data operations, DEVELOPMENT reference only."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    mode=r['mode']
    if r['task']==Task.APPLY_LIST:
        if mode==Mode.WALK:
            if not r['list_head']:
                if r['list_skip']:stop(Outcome.INVALID,Reason.SYNTAX)
                else:ret(r['x'])
            else:r.update(list_body=r['x'],mode=Mode.LIST_CELL,x=r['list_head'])
        elif mode==Mode.LIST_CELL:
            if r['list_skip']:
                if not b and r['list_skip']>1:stop(Outcome.INVALID,Reason.SYNTAX)
                else:
                    r.update(list_skip=r['list_skip']-1,x=b)
                    if not b:ret(r['list_body'])
            else:r.update(list_next=b,mode=Mode.LIST_ARGUMENT,x=a)
        elif mode==Mode.LIST_ARGUMENT:
            if r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
            else:
                ref=r['free'];s['heap'][ref]=[Tag.APP,r['list_body'],r['x'],0]
                r.update(free=ref+1,list_body=ref)
                if r['list_next']:r.update(mode=Mode.LIST_CELL,x=r['list_next'])
                else:ret(ref)
        else:stop(Outcome.INVALID,Reason.SYNTAX)
        return True
    if r['task']!=Task.FIND_MOTIVE:return False
    if mode==Mode.WALK:
        if c!=VectorKind.REFERENCES or not a or not b or not r['motive_query']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(motive_lookup_remaining=a,mode=Mode.MOTIVE_FIND_CELL,x=b)
    elif mode==Mode.MOTIVE_FIND_CELL:
        if not r['motive_lookup_remaining'] or bool(b)!=(r['motive_lookup_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(motive_lookup_next=b,mode=Mode.MOTIVE_FIND_INFO,x=a)
    elif mode==Mode.MOTIVE_FIND_INFO:
        if a==r['motive_query']:r.update(motive_lookup_info=r['x'],mode=Mode.MOTIVE_FIND_RECORD,x=b)
        elif r['motive_lookup_remaining']>1:r.update(motive_lookup_remaining=r['motive_lookup_remaining']-1,mode=Mode.MOTIVE_FIND_CELL,x=r['motive_lookup_next'])
        else:stop(Outcome.INVALID,Reason.SYNTAX)
    elif mode==Mode.MOTIVE_FIND_RECORD:
        if not 0<a<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:ret(a)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
