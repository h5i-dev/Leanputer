"""General telescope WHNF/parameter reuse, DEVELOPMENT transition reference.

Source inductive.cpp:check_inductive_types/check_constructors and telescope.py.
No type, uniformity or fresh-Local answers may enter the public wrapper. All
nested calls use weighted services in the native lowering; this file is offline.
"""
from .arena import Tag
from .traversal_machine import (Mode, Task, Outcome, Reason, CALL_TELESCOPE_WHNF,
    CALL_REUSE_WHNF, CALL_REUSE_CONVERT, CALL_REUSE_SUBSTITUTE,
    CALL_REUSE_SCOPE_TYPE, CALL_REUSE_SCOPE_CANDIDATE, CALL_REUSE_OPEN, CALL_REUSE_FINISH)

PRIVATE_PHASES=tuple(range(CALL_TELESCOPE_WHNF,CALL_REUSE_FINISH+1))


def resume(machine, frame, stop, ret, alloc):
    s,r=machine.state,machine.state['regs']
    phase,original,index,task,end,policy=frame
    top=r['sp']-1
    if phase==CALL_TELESCOPE_WHNF:
        r.update(sp=top,task=Task.OPEN_TELESCOPE,mode=Mode.TELESCOPE_READY,x=r['r'],
            limit=original,bounded=index,open_tag=end)
    elif phase in (CALL_REUSE_WHNF,CALL_REUSE_CONVERT,CALL_REUSE_SUBSTITUTE):
        r.update(reuse_index=index,reuse_end=end,reuse_whnf=policy,task=Task.CONSUME_PARAMETERS)
        if phase==CALL_REUSE_WHNF:r.update(sp=top,mode=Mode.REUSE_BINDER,x=r['r'])
        elif phase==CALL_REUSE_CONVERT:
            if not r['r']:stop(Outcome.INVALID,Reason.TYPE_MISMATCH)
            else:r.update(sp=top,mode=Mode.REUSE_INSTANTIATE,x=original)
        else:r.update(sp=top,mode=Mode.REUSE_LOOP,x=r['r'],reuse_index=index+1)
    else:
        def call(next_phase,task,x,mode=Mode.WALK,**updates):
            s['stack'][top]=[next_phase,0,0,Task.PREPARE_REUSE,0,0]
            r.update(task=task,x=x,mode=mode,depth=0,**updates)
        if phase==CALL_REUSE_SCOPE_TYPE:call(CALL_REUSE_SCOPE_CANDIDATE,Task.EXPR_SCOPE,r['reuse_root'])
        elif phase==CALL_REUSE_SCOPE_CANDIDATE:
            call(CALL_REUSE_OPEN,Task.OPEN_TELESCOPE,r['root'],Mode.TELESCOPE,
                bounded=1,limit=r['reuse_end'],open_tag=Tag.PI)
        elif phase==CALL_REUSE_OPEN:
            call(CALL_REUSE_FINISH,Task.CONSUME_PARAMETERS,r['reuse_root'])
        elif phase==CALL_REUSE_FINISH:
            r.update(sp=top,task=Task.PREPARE_REUSE,mode=Mode.RETURN)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    def push(phase,original=0,index=0,end=0,policy=0):
        if r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK);return False
        s['stack'][r['sp']]=[phase,original,index,r['task'],end,policy]
        r['sp']+=1
        return True
    if r['mode']==Mode.TELESCOPE:
        if r['bounded'] and r['ctx']==r['limit']:ret(r['x'])
        elif push(CALL_TELESCOPE_WHNF,r['limit'],r['bounded'],r['open_tag']):r.update(mode=Mode.BETA_ZETA,task=Task.BETA_ZETA)
        return True
    if r['task']==Task.PREPARE_REUSE and r['mode']==Mode.WALK:
        end=r['ctx']+r['reuse_end']
        if end>cfg.context:stop(Outcome.RESOURCE,Reason.CONTEXT)
        elif push(CALL_REUSE_SCOPE_TYPE):
            r.update(task=Task.EXPR_SCOPE,mode=Mode.WALK,x=r['root'],depth=0,
                local_base=r['ctx'],reuse_base=r['ctx'],reuse_end=end)
        return True
    if r['task']!=Task.CONSUME_PARAMETERS:return False
    if r['mode']==Mode.WALK:
        if not r['local_base']<=r['reuse_base']<=r['reuse_end']<=r['ctx']:
            stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.REUSE_LOOP,reuse_index=r['reuse_base'])
    elif r['mode']==Mode.REUSE_LOOP:
        if r['reuse_index']==r['reuse_end']:ret(r['x'])
        elif r['reuse_whnf']:
            if push(CALL_REUSE_WHNF,0,r['reuse_index'],r['reuse_end'],r['reuse_whnf']):
                r.update(task=Task.BETA_ZETA,mode=Mode.BETA_ZETA)
        else:r['mode']=Mode.REUSE_BINDER
    elif r['mode']==Mode.REUSE_BINDER:
        if tag!=Tag.PI:
            stop(Outcome.INVALID if tag in (Tag.SORT,Tag.LAM) else Outcome.GAP,
                 Reason.EXPECT_PI if tag in (Tag.SORT,Tag.LAM) else Reason.GAP_CONVERSION)
        else:r.update(mode=Mode.REUSE_SELECT,reuse_body=r['x'],reuse_domain=a)
    elif r['mode'] in (Mode.REUSE_SELECT,Mode.REUSE_SUBST_SELECT):
        mode=Mode.REUSE_RECORD if r['mode']==Mode.REUSE_SELECT else Mode.REUSE_SUBST_RECORD
        r.update(mode=mode,x=s['context'][r['reuse_index']][0])
    elif r['mode']==Mode.REUSE_RECORD:
        if not 0<a<r['free'] or not 0<b<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif push(CALL_REUSE_CONVERT,r['reuse_body'],r['reuse_index'],r['reuse_end'],r['reuse_whnf']):
            r.update(mode=Mode.WALK,task=Task.CONVERT_POSITIVE,x=r['reuse_domain'],peer=b)
    elif r['mode']==Mode.REUSE_INSTANTIATE:
        if tag!=Tag.PI:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.REUSE_SUBST_SELECT,reuse_body=b)
    elif r['mode']==Mode.REUSE_SUBST_RECORD:
        if not 0<a<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif push(CALL_REUSE_SUBSTITUTE,0,r['reuse_index'],r['reuse_end'],r['reuse_whnf']):
            r.update(mode=Mode.WALK,task=Task.INSTANTIATE_ONE,x=r['reuse_body'],substitution=a,depth=0)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
