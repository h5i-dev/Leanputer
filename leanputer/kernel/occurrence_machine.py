"""Composable current-family occurrence, DEVELOPMENT transition reference.

Source inductive.cpp:has_ind_occ via complete Expr find. Matches are by symbol
DATA regardless of universe arguments. The same all-Expr walker returns through
its private stack delimiter instead of halting the source checker. No host scan.
"""
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_OCCURRENCE_FINISH

PRIVATE_PHASES=(CALL_OCCURRENCE_FINISH,)


def resume(machine,frame,stop,ret,alloc):
    r=machine.state['regs']
    r.update(sp=r['sp']-1,task=frame[3],occurrence_internal=0)
    ret(r['occurrence_found'])


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task'] not in (Task.HAS_CONSTANTS,Task.HAS_LOOSE_BVARS):return False
    loose = r['task']==Task.HAS_LOOSE_BVARS
    if r['mode']!=Mode.WALK:stop(Outcome.INVALID,Reason.SYNTAX)
    elif not loose and not r['count']:ret(0)
    elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
    else:
        s['stack'][r['sp']]=[CALL_OCCURRENCE_FINISH,0,0,r['task'],0,0]
        r.update(occurrence_mark=r['sp'],sp=r['sp']+1,task=Task.LOOSE_BVAR_WALK if loose else Task.OCCURS,
            occurrence_found=0,occurrence_internal=1,depth=0)
    return True
