"""Generic functional recursive-argument descriptors, DEVELOPMENT reference.

Source is_rec_argument and shared template construction. Only CORE after nested
specialization/header staging; positivity and typing are separate requirements.
Domains abstract preceding functional Locals; indices abstract the entire prefix.
Private output records are not admitted declarations or supplied input answers.
"""
from .arena import Tag
from .native_cells import CellTag
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_REC_WHNF,CALL_REC_DOMAIN,
    CALL_REC_OPEN,CALL_REC_APPLICATION,CALL_REC_INDEX,CALL_REC_REVERSE_INDICES,CALL_REC_REVERSE_PREFIX)

PRIVATE_PHASES=tuple(range(CALL_REC_WHNF,CALL_REC_REVERSE_PREFIX+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase,original,mark,task,first,second=frame
    def call(phase,task,x,mode=Mode.WALK,original=0,**updates):
        s['stack'][r['sp']-1]=[phase,original,mark,Task.RECURSIVE_ARGUMENT,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    if phase==CALL_REC_WHNF:r.update(task=Task.RECURSIVE_ARGUMENT,mode=Mode.RECURSIVE_NODE,x=r['r'])
    elif phase==CALL_REC_DOMAIN:r.update(task=Task.RECURSIVE_ARGUMENT,mode=Mode.RECURSIVE_CAPTURE,x=original)
    elif phase==CALL_REC_OPEN:call(CALL_REC_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    elif phase==CALL_REC_APPLICATION:
        if not r['r']:
            r.update(sp=r['sp']-1,task=Task.RECURSIVE_ARGUMENT,ctx=mark);ret(0)
        else:
            r.update(recursive_family=r['r'],recursive_skip=r['header_parameter_end']-r['header_parameter_base'],
                recursive_indices=r['app_arity']-(r['header_parameter_end']-r['header_parameter_base']),
                recursive_index_remaining=r['app_arity']-(r['header_parameter_end']-r['header_parameter_base']),recursive_index_rev=0)
            if r['recursive_skip']:r.update(task=Task.RECURSIVE_ARGUMENT,mode=Mode.RECURSIVE_SKIP,x=r['app_args'])
            elif r['recursive_indices']:r.update(task=Task.RECURSIVE_ARGUMENT,mode=Mode.RECURSIVE_INDEX,x=r['app_args'])
            else:call(CALL_REC_REVERSE_INDICES,Task.REVERSE_LIST,0,reverse_length=0)
    elif phase==CALL_REC_INDEX:r.update(task=Task.RECURSIVE_ARGUMENT,mode=Mode.RECURSIVE_INDEX_STORE)
    elif phase==CALL_REC_REVERSE_INDICES:
        r['recursive_index_vector']=r['r']
        call(CALL_REC_REVERSE_PREFIX,Task.REVERSE_LIST,r['recursive_prefix_rev'],reverse_length=r['recursive_prefix_count'])
    elif phase==CALL_REC_REVERSE_PREFIX:
        r.update(sp=r['sp']-1,task=Task.RECURSIVE_ARGUMENT,ctx=mark)
        alloc((CellTag.RECURSIVE_ARGUMENT,r['recursive_family'],r['r'],r['recursive_index_vector']))


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.RECURSIVE_ARGUMENT:return False
    def call(phase,task,x,mode=Mode.WALK,original=0,**updates):
        mark=s['stack'][r['sp']-1][2]
        s['stack'][r['sp']-1]=[phase,original,mark,Task.RECURSIVE_ARGUMENT,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    if r['mode']==Mode.WALK:
        if r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_REC_WHNF,0,r['ctx'],Task.RECURSIVE_ARGUMENT,0,0]
            r.update(sp=r['sp']+1,task=Task.BETA_ZETA,mode=Mode.BETA_ZETA,recursive_mark=r['ctx'],
                recursive_prefix_rev=0,recursive_prefix_count=0)
    elif r['mode']==Mode.RECURSIVE_NODE:
        if tag==Tag.PI:call(CALL_REC_DOMAIN,Task.ABSTRACT_SCOPE,a,original=r['x'],abstract_base=r['recursive_mark'],abstract_end=r['ctx'])
        else:call(CALL_REC_APPLICATION,Task.FAMILY_APPLICATION,r['x'])
    elif r['mode']==Mode.RECURSIVE_CAPTURE:
        if tag!=Tag.PI:stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['free']+2>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.PREFIX_BINDER,r['r'],c,0]
            r.update(free=ref+1,recursive_prefix_value=ref,mode=Mode.RECURSIVE_PREFIX_LINK)
    elif r['mode']==Mode.RECURSIVE_PREFIX_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['recursive_prefix_value'],r['recursive_prefix_rev'],0]
        r.update(free=ref+1,recursive_prefix_rev=ref,recursive_prefix_count=r['recursive_prefix_count']+1)
        call(CALL_REC_OPEN,Task.OPEN_TELESCOPE,r['x'],Mode.TELESCOPE,open_tag=Tag.PI,bounded=1,limit=r['ctx']+1)
    elif r['mode']==Mode.RECURSIVE_SKIP:
        if not r['recursive_skip']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['recursive_skip']>1:r.update(recursive_skip=r['recursive_skip']-1,x=b)
        elif r['recursive_indices']:r.update(recursive_skip=0,mode=Mode.RECURSIVE_INDEX,x=b)
        else:call(CALL_REC_REVERSE_INDICES,Task.REVERSE_LIST,0,reverse_length=0)
    elif r['mode']==Mode.RECURSIVE_INDEX:
        if not r['recursive_index_remaining'] or bool(b)!=(r['recursive_index_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:
            r['recursive_index_next']=b
            call(CALL_REC_INDEX,Task.ABSTRACT_SCOPE,a,abstract_base=r['recursive_mark'],abstract_end=r['ctx'])
    elif r['mode']==Mode.RECURSIVE_INDEX_STORE:
        if r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['r'],r['recursive_index_rev'],0]
            more=r['recursive_index_remaining']>1
            r.update(free=ref+1,recursive_index_rev=ref,recursive_index_remaining=r['recursive_index_remaining']-1)
            if more:r.update(mode=Mode.RECURSIVE_INDEX,x=r['recursive_index_next'])
            else:call(CALL_REC_REVERSE_INDICES,Task.REVERSE_LIST,ref,reverse_length=r['recursive_indices'])
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
