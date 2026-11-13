"""Exact current-family application predicate, DEVELOPMENT transition reference.

Source inductive.cpp:is_valid_ind_app. Counts/symbols/levels come from weighted
header analysis. Shared Expr/level equality and occurrence services check every
parameter/index. No field-count branches or host-derived validity answers.
"""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_APP_MEMBER,CALL_APP_LOOKUP,
    CALL_APP_LEVELS,CALL_APP_INDEX,CALL_APP_PARAMETER)

PRIVATE_PHASES=tuple(range(CALL_APP_MEMBER,CALL_APP_PARAMETER+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs']
    phase=frame[0]
    def no():r['sp']-=1;ret(0)
    def call(phase,task,x,**updates):
        s['stack'][r['sp']-1]=[phase,0,0,Task.FAMILY_APPLICATION,0,0]
        r.update(task=task,mode=Mode.WALK,x=x,depth=0,**updates)
    if phase==CALL_APP_MEMBER:
        if not r['r']:no()
        else:call(CALL_APP_LOOKUP,Task.ENV_LOOKUP,0,query_symbol=r['app_symbol'],lookup_head=r['header_head'])
    elif phase==CALL_APP_LOOKUP:
        if not r['r']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(task=Task.FAMILY_APPLICATION,mode=Mode.APP_SIGNATURE,x=r['r'],app_signature=r['r'])
    elif phase==CALL_APP_LEVELS:
        if not r['r']:no()
        elif not r['app_arity']:r['sp']-=1;ret(r['app_signature'])
        else:r.update(task=Task.FAMILY_APPLICATION,mode=Mode.APP_ARGUMENT,x=r['app_args'],
            app_remaining=r['app_arity'],app_context_index=r['header_parameter_base'])
    else:
        invalid=bool(r['r']) if phase==CALL_APP_INDEX else not r['r']
        if invalid:no()
        elif r['app_remaining']==1:r['sp']-=1;ret(r['app_signature'])
        else:
            r.update(task=Task.FAMILY_APPLICATION,mode=Mode.APP_ARGUMENT,x=r['app_next'],app_remaining=r['app_remaining']-1)
            if phase==CALL_APP_PARAMETER:r['app_context_index']+=1


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.FAMILY_APPLICATION:return False
    def no():r['sp']-=1;ret(0)
    def call(phase,task,x,**updates):
        s['stack'][r['sp']-1]=[phase,0,0,Task.FAMILY_APPLICATION,0,0]
        r.update(task=task,mode=Mode.WALK,x=x,depth=0,**updates)
    if r['mode']==Mode.WALK:r.update(mode=Mode.APP_SPINE,app_args=0,app_arity=0)
    elif r['mode']==Mode.APP_SPINE:
        if tag==Tag.APP:
            if r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
            else:
                ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,b,r['app_args'],0]
                r.update(free=ref+1,app_args=ref,app_arity=r['app_arity']+1,x=a)
        elif tag!=Tag.CONST:ret(0)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_APP_MEMBER,0,0,Task.FAMILY_APPLICATION,0,0]
            r.update(sp=r['sp']+1,app_symbol=a,app_levels=b,task=Task.HAS_FAMILIES,mode=Mode.WALK)
    elif r['mode']==Mode.APP_SIGNATURE:r.update(mode=Mode.APP_SCHEME,x=c)
    elif r['mode']==Mode.APP_SCHEME:
        if b!=8:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.APP_METADATA,x=c)
    elif r['mode']==Mode.APP_METADATA:
        if r['app_arity']!=r['header_parameter_end']-r['header_parameter_base']+a:no()
        else:call(CALL_APP_LEVELS,Task.VECTOR_EQUAL,r['app_levels'],peer=r['header_levels'],vector_expected_role=VectorKind.LEVELS)
    elif r['mode']==Mode.APP_ARGUMENT:
        if not r['app_remaining'] or bool(b)!=(r['app_remaining']>1) or not 0<a<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:
            r.update(app_argument=a,app_next=b)
            if r['app_context_index']<r['header_parameter_end']:r.update(mode=Mode.APP_PARAMETER_SELECT,x=a)
            else:call(CALL_APP_INDEX,Task.HAS_FAMILIES,a)
    elif r['mode']==Mode.APP_PARAMETER_SELECT:
        r.update(mode=Mode.APP_PARAMETER_RECORD,x=s['context'][r['app_context_index']][0])
    elif r['mode']==Mode.APP_PARAMETER_RECORD:
        if not 0<a<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:call(CALL_APP_PARAMETER,Task.EXPR_EQUAL,r['app_argument'],peer=a)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
