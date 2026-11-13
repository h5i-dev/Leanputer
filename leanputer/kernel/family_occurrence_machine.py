"""Shared temporary family-symbol window, DEVELOPMENT transition reference.

The header list is weighted derived metadata, not supplied admission answers.
Copy its symbols past live context, leave ctx unchanged, call the SAME internal
occurrence walk, restore the caller's universe/window state on return. Fresh
Local allocation may later overwrite the dead scratch cells. No source loader
can enter this internal ABI with supplied checked headers.
"""
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_FAMILY_OCCURRENCE

PRIVATE_PHASES=(CALL_FAMILY_OCCURRENCE,)


def resume(machine,frame,stop,ret,alloc):
    r=machine.state['regs']
    _,original,ctx,task,count,base=frame
    r.update(sp=r['sp']-1,ctx=ctx,count=count,arg_base=base,task=Task.HAS_FAMILIES,mode=Mode.RETURN)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.HAS_FAMILIES:return False
    if r['mode']==Mode.WALK:
        if not r['header_seen']:ret(0)
        elif r['ctx']+r['header_seen']>cfg.context:stop(Outcome.RESOURCE,Reason.CONTEXT)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_FAMILY_OCCURRENCE,r['x'],r['ctx'],Task.HAS_FAMILIES,r['count'],r['arg_base']]
            r.update(sp=r['sp']+1,mode=Mode.FAMILY_SET_CELL,x=r['header_head'],
                family_set_cursor=r['ctx'],family_set_remaining=r['header_seen'])
    elif r['mode']==Mode.FAMILY_SET_CELL:
        if not 0<a<r['free'] or not r['family_set_remaining'] or (r['family_set_remaining']>1 and not 0<b<r['free']):
            stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.FAMILY_SET_SIGNATURE,x=a,family_set_next=b)
    elif r['mode']==Mode.FAMILY_SET_SIGNATURE:
        if not a or not 0<b<r['free'] or not 0<c<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:
            s['context'][r['family_set_cursor']]=[a]
            more=r['family_set_remaining']>1
            r.update(family_set_cursor=r['family_set_cursor']+1,family_set_remaining=r['family_set_remaining']-1)
            if more:r.update(mode=Mode.FAMILY_SET_CELL,x=r['family_set_next'])
            else:
                frame=s['stack'][r['sp']-1]
                r.update(mode=Mode.WALK,task=Task.HAS_CONSTANTS,x=frame[1],arg_base=frame[2],count=r['header_seen'])
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
