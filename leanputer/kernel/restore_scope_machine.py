"""Restore any bounded derived Local vector, DEVELOPMENT reference only.

Elements are Local records or checked constructor-field records wrapping one.
Both output-only metadata variants use the same counted context traversal.
"""
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.RESTORE_SCOPE:return False
    def append():
        s['context'][r['ctx']]=[r['x']];more=r['restore_remaining']>1
        r.update(ctx=r['ctx']+1,restore_remaining=r['restore_remaining']-1)
        if more:r.update(mode=Mode.RESTORE_SCOPE_CELL,x=r['restore_next'])
        else:ret(r['ctx'])
    mode=r['mode']
    if mode==Mode.WALK:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['ctx']+a>cfg.context:stop(Outcome.RESOURCE,Reason.CONTEXT)
        else:
            r['restore_length']=a
            if not a:ret(r['ctx'])
            else:r.update(restore_remaining=a,mode=Mode.RESTORE_SCOPE_CELL,x=b)
    elif mode==Mode.RESTORE_SCOPE_CELL:
        if not r['restore_remaining'] or bool(b)!=(r['restore_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(restore_next=b,mode=Mode.RESTORE_SCOPE_ITEM,x=a)
    elif mode==Mode.RESTORE_SCOPE_ITEM:
        if tag==CellTag.CONSTRUCTOR_FIELD:r.update(mode=Mode.RESTORE_SCOPE_RECORD,x=a)
        else:append()
    elif mode==Mode.RESTORE_SCOPE_RECORD:append()
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
