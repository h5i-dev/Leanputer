"""Multi-Local context-window abstraction, DEVELOPMENT transition reference.

Only derived Local records in live context are consumed. UIDs borrow a scratch
window after ctx; no host binding/abstraction answers. The SAME abstract walker
handles all Expr tags and binder depths. Caller count/window state is restored.
"""
from .arena import Tag
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_ABSTRACT_SCOPE

PRIVATE_PHASES=(CALL_ABSTRACT_SCOPE,)


def resume(machine,frame,stop,ret,alloc):
    r=machine.state['regs'];_,original,count,task,base,ctx=frame
    r.update(sp=r['sp']-1,task=Task.ABSTRACT_SCOPE,count=count,arg_base=base,ctx=ctx,mode=Mode.RETURN)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.ABSTRACT_SCOPE:return False
    if r['mode']==Mode.WALK:
        size=r['abstract_end']-r['abstract_base']
        if not r['local_base']<=r['abstract_base']<=r['abstract_end']<=r['ctx']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif not size:ret(r['x'])
        elif r['ctx']+size>cfg.context:stop(Outcome.RESOURCE,Reason.CONTEXT)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_ABSTRACT_SCOPE,r['x'],r['count'],Task.ABSTRACT_SCOPE,r['arg_base'],r['ctx']]
            r.update(sp=r['sp']+1,mode=Mode.ABSTRACT_SCOPE_SELECT,scope_cursor=r['abstract_base'],scope_dest=r['ctx'])
    elif r['mode']==Mode.ABSTRACT_SCOPE_SELECT:r.update(mode=Mode.ABSTRACT_SCOPE_RECORD,x=s['context'][r['scope_cursor']][0])
    elif r['mode']==Mode.ABSTRACT_SCOPE_RECORD:
        if not 0<a<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.ABSTRACT_SCOPE_LOCAL,x=a)
    elif r['mode']==Mode.ABSTRACT_SCOPE_LOCAL:
        if tag!=Tag.LOCAL or not a:stop(Outcome.INVALID,Reason.SYNTAX)
        else:
            s['context'][r['scope_dest']]=[a]
            more=r['scope_cursor']+1<r['abstract_end']
            r.update(scope_dest=r['scope_dest']+1,scope_cursor=r['scope_cursor']+1)
            if more:r['mode']=Mode.ABSTRACT_SCOPE_SELECT
            else:
                frame=s['stack'][r['sp']-1]
                r.update(task=Task.ABSTRACT,mode=Mode.WALK,x=frame[1],arg_base=frame[5],
                    count=r['abstract_end']-r['abstract_base'],depth=0)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
