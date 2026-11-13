"""Counted private list -> reversed reference vector, DEVELOPMENT reference."""
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.REVERSE_LIST:return False
    if r['mode']==Mode.WALK:
        r.update(reverse_remaining=r['reverse_length'],reverse_head=0,
            mode=Mode.REVERSE_LIST if r['reverse_length'] else Mode.REVERSE_FINISH)
    elif r['mode']==Mode.REVERSE_LIST:
        if not r['reverse_remaining'] or bool(b)!=(r['reverse_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,a,r['reverse_head'],0]
            more=r['reverse_remaining']>1
            r.update(free=ref+1,reverse_head=ref,reverse_remaining=r['reverse_remaining']-1,x=b,
                mode=Mode.REVERSE_LIST if more else Mode.REVERSE_FINISH)
    elif r['mode']==Mode.REVERSE_FINISH:alloc((CellTag.VECTOR,r['reverse_length'],r['reverse_head'],VectorKind.REFERENCES))
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
