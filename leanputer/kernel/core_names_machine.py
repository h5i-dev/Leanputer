"""Validate every generated recursor-name claim, DEVELOPMENT reference.

Names and counts are data. Source mk_rec_name relation and namespace checks must
pass before the raw symbol can label a generated recursor. No supplied type is
used. Output-only records retain the verified family/name association.
"""
from .native_cells import CellTag
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_CORE_NAME_PROFILE,
    CALL_CORE_NAME_RELATION,CALL_CORE_NAME_DECLARATION,CALL_CORE_NAME_PENDING)

PRIVATE_PHASES=tuple(range(CALL_CORE_NAME_PROFILE,CALL_CORE_NAME_PENDING+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase=frame[0]
    def call(phase,task,x,**updates):
        s['stack'][r['sp']-1]=[phase,0,0,Task.CHECK_CORE_NAMES,0,0]
        r.update(task=task,mode=Mode.WALK,x=x,depth=0,**updates)
    if phase==CALL_CORE_NAME_PROFILE:
        call(CALL_CORE_NAME_RELATION,Task.CHECK_RECURSOR_NAME,0,
            name_parent_symbol=r['core_name_family_symbol'],name_candidate_symbol=r['core_name_symbol'])
    elif phase==CALL_CORE_NAME_RELATION:
        if not r['r']:stop(Outcome.INVALID,Reason.INVALID_RECURSOR_NAME)
        else:call(CALL_CORE_NAME_DECLARATION,Task.ENV_LOOKUP,0,query_symbol=r['core_name_symbol'],lookup_head=r['typing_head'])
    elif phase in (CALL_CORE_NAME_DECLARATION,CALL_CORE_NAME_PENDING):
        if r['r']:stop(Outcome.INVALID,Reason.DUPLICATE_DECLARATION)
        elif phase==CALL_CORE_NAME_DECLARATION:
            call(CALL_CORE_NAME_PENDING,Task.ENV_LOOKUP,0,query_symbol=r['core_name_symbol'],lookup_head=r['ctor_names'])
        else:r.update(task=Task.CHECK_CORE_NAMES,mode=Mode.CORE_NAME_STORE)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.CHECK_CORE_NAMES:return False
    mode=r['mode']
    if mode==Mode.WALK:
        if not r['header_seen']:stop(Outcome.INVALID,Reason.INVALID_DECLARATION)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_CORE_NAME_PROFILE,0,0,Task.CHECK_CORE_NAMES,0,0]
            r.update(sp=r['sp']+1,mode=Mode.CORE_NAME_CELL,x=r['header_head'],core_names_remaining=r['header_seen'],core_rec_names=0)
    elif mode==Mode.CORE_NAME_CELL:r.update(mode=Mode.CORE_NAME_SIGNATURE,x=a,core_name_next=b)
    elif mode==Mode.CORE_NAME_SIGNATURE:r.update(mode=Mode.CORE_NAME_SCHEME,x=c,core_name_family=r['x'],core_name_family_symbol=a)
    elif mode==Mode.CORE_NAME_SCHEME:
        if b!=8:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.CORE_NAME_METADATA,x=c)
    elif mode==Mode.CORE_NAME_METADATA:r.update(mode=Mode.CORE_NAME_RAW_FAMILY,x=c)
    elif mode==Mode.CORE_NAME_RAW_FAMILY:r.update(mode=Mode.CORE_NAME_AUX,x=c)
    elif mode==Mode.CORE_NAME_AUX:
        r['core_name_symbol']=b
        s['stack'][r['sp']-1]=[CALL_CORE_NAME_PROFILE,0,0,Task.CHECK_CORE_NAMES,0,0]
        r.update(task=Task.CHECK_NAME,mode=Mode.WALK,x=r['symbols_root'],query_symbol=b)
    elif mode==Mode.CORE_NAME_STORE:
        if r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.VALIDATED_RECURSOR_NAME,r['core_name_family'],r['core_name_symbol'],r['core_rec_names']]
            more=r['core_names_remaining']>1
            r.update(free=ref+1,core_rec_names=ref,core_names_remaining=r['core_names_remaining']-1)
            if more:r.update(mode=Mode.CORE_NAME_CELL,x=r['core_name_next'])
            else:r['sp']-=1;ret(ref)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
