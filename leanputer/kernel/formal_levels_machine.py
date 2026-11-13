"""Derive a formal universe-level vector from a checked symbol window.

DEVELOPMENT reference only. This generic loop is shared by family-constant
comparison and recursor generation. No host-built formal-level answer is packed.
"""
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.FORMAL_LEVELS:return False
    if r['mode']==Mode.WALK:
        r.update(formal_count=r['count'],formal_remaining=r['count'],formal_head=0,
            formal_i=r['count']-1 if r['count'] else 0,mode=Mode.FORMAL_SELECT if r['count'] else Mode.FORMAL_FINISH)
    elif r['mode']==Mode.FORMAL_SELECT:
        symbol=s['context'][r['arg_base']+r['formal_i']][0]
        if not symbol:stop(Outcome.INVALID,Reason.UNIVERSE)
        elif r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.LEVEL_PARAM,symbol,0,0]
            r.update(free=ref+1,formal_value=ref,mode=Mode.FORMAL_CELL)
    elif r['mode']==Mode.FORMAL_CELL:
        if r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['formal_value'],r['formal_head'],0]
            more=r['formal_remaining']>1
            r.update(free=ref+1,formal_head=ref,formal_remaining=r['formal_remaining']-1)
            if more:r.update(formal_i=r['formal_i']-1,mode=Mode.FORMAL_SELECT)
            else:r['mode']=Mode.FORMAL_FINISH
    elif r['mode']==Mode.FORMAL_FINISH:alloc((CellTag.VECTOR,r['formal_count'],r['formal_head'],VectorKind.LEVELS))
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
