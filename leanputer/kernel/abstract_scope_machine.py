"""Multi-Local context-window abstraction, DEVELOPMENT transition reference.

Only derived Local records in live context are consumed. UIDs (abstraction) or
Local Expr refs (reverse instantiation) borrow a scratch window after ctx. The
same all-Expr walkers handle binding depths; caller count/window is restored.
"""
from .arena import Tag
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_ABSTRACT_SCOPE

PRIVATE_PHASES=(CALL_ABSTRACT_SCOPE,)


def resume(machine,frame,stop,ret,alloc):
    r=machine.state['regs'];_,original,count,task,base,ctx=frame
    r.update(sp=r['sp']-1,task=task,count=count,arg_base=base,ctx=ctx,mode=Mode.RETURN)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task'] not in (Task.ABSTRACT_SCOPE,Task.INSTANTIATE_SCOPE):return False
    if r['mode']==Mode.WALK:
        size=r['abstract_end']-r['abstract_base']
        if not r['local_base']<=r['abstract_base']<=r['abstract_end']<=r['ctx']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif not size:ret(r['x'])
        elif r['ctx']+size>cfg.context:stop(Outcome.RESOURCE,Reason.CONTEXT)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            instantiating=r['task']==Task.INSTANTIATE_SCOPE
            s['stack'][r['sp']]=[CALL_ABSTRACT_SCOPE,r['x'],r['count'],r['task'],r['arg_base'],r['ctx']]
            r.update(sp=r['sp']+1,mode=Mode.ABSTRACT_SCOPE_SELECT,
                scope_cursor=r['abstract_end']-1 if instantiating else r['abstract_base'],scope_dest=r['ctx'])
    elif r['mode']==Mode.ABSTRACT_SCOPE_SELECT:r.update(mode=Mode.ABSTRACT_SCOPE_RECORD,x=s['context'][r['scope_cursor']][0])
    elif r['mode']==Mode.ABSTRACT_SCOPE_RECORD:
        if not 0<a<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.ABSTRACT_SCOPE_LOCAL,x=a)
    elif r['mode']==Mode.ABSTRACT_SCOPE_LOCAL:
        if tag!=Tag.LOCAL or not a:stop(Outcome.INVALID,Reason.SYNTAX)
        else:
            instantiating=r['task']==Task.INSTANTIATE_SCOPE
            s['context'][r['scope_dest']]=[r['x'] if instantiating else a]
            more=r['abstract_base']<r['scope_cursor'] if instantiating else r['scope_cursor']+1<r['abstract_end']
            r.update(scope_dest=r['scope_dest']+1,scope_cursor=max(0,r['scope_cursor']-1) if instantiating else r['scope_cursor']+1)
            if more:r['mode']=Mode.ABSTRACT_SCOPE_SELECT
            else:
                frame=s['stack'][r['sp']-1]
                r.update(task=Task.INSTANTIATE if instantiating else Task.ABSTRACT,start=0,
                    mode=Mode.WALK,x=frame[1],arg_base=frame[5],
                    count=r['abstract_end']-r['abstract_base'],depth=0)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
