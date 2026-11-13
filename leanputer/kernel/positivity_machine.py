"""General strict positivity CORE operation, DEVELOPMENT transition reference.

Pinned inductive.cpp:check_positivity. Its full-source caller must first perform
nested specialization, header staging and constructor typing. This core does
not admit raw original blocks. Shared WHNF, family occurrence, telescope and
application operations run as private calls; no inferred/positivity answers.
"""
from .arena import Tag
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_POS_WHNF,
    CALL_POS_OCCURRENCE,CALL_POS_DOMAIN,CALL_POS_OPEN,CALL_POS_APPLICATION)

PRIVATE_PHASES=tuple(range(CALL_POS_WHNF,CALL_POS_APPLICATION+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs']
    phase,original,mark,task,first,second=frame
    def call(phase,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[phase,original,mark,Task.CHECK_POSITIVITY,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    def done():r.update(sp=r['sp']-1,ctx=mark,task=Task.CHECK_POSITIVITY);ret(1)
    def invalid(reason):r.update(ctx=mark,task=Task.CHECK_POSITIVITY);stop(Outcome.INVALID,reason)
    if phase==CALL_POS_WHNF:
        original=r['r'];call(CALL_POS_OCCURRENCE,Task.HAS_FAMILIES,original)
    elif phase==CALL_POS_OCCURRENCE:
        if not r['r']:done()
        else:r.update(task=Task.CHECK_POSITIVITY,mode=Mode.POSITIVITY_NODE,x=original)
    elif phase==CALL_POS_DOMAIN:
        if r['r']:invalid(Reason.NEGATIVE_OCCURRENCE)
        else:call(CALL_POS_OPEN,Task.OPEN_TELESCOPE,original,Mode.TELESCOPE,
            open_tag=Tag.PI,bounded=1,limit=r['ctx']+1)
    elif phase==CALL_POS_OPEN:call(CALL_POS_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    elif phase==CALL_POS_APPLICATION:
        if not r['r']:invalid(Reason.INVALID_INDUCTIVE_APPLICATION)
        else:done()


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.CHECK_POSITIVITY:return False
    if r['mode']==Mode.WALK:
        if r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_POS_WHNF,0,r['ctx'],Task.CHECK_POSITIVITY,0,0]
            r.update(sp=r['sp']+1,task=Task.BETA_ZETA,mode=Mode.BETA_ZETA)
    elif r['mode']==Mode.POSITIVITY_NODE:
        frame=s['stack'][r['sp']-1]
        s['stack'][r['sp']-1]=[CALL_POS_DOMAIN if tag==Tag.PI else CALL_POS_APPLICATION,r['x'],frame[2],Task.CHECK_POSITIVITY,0,0]
        r.update(task=Task.HAS_FAMILIES if tag==Tag.PI else Task.FAMILY_APPLICATION,mode=Mode.WALK,
            x=a if tag==Tag.PI else r['x'],depth=0)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
