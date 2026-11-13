"""Declare fully checked constructors PRIVATELY, DEVELOPMENT transition reference.

Source declare_constructors. Walk original vector order; ordinal is data.
Pending metadata cannot be declared until all core typing/name checks pass.
Nothing is published into committed Γ by this operation.
"""
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_DECLARE_CTOR_LOOKUP

PRIVATE_PHASES=(CALL_DECLARE_CTOR_LOOKUP,)


def resume(machine,frame,stop,ret,alloc):
    r=machine.state['regs']
    if not r['r']:stop(Outcome.INVALID,Reason.SYNTAX)
    else:r.update(task=Task.DECLARE_CONSTRUCTORS,mode=Mode.DECL_CTOR_PENDING,x=r['r'])


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.DECLARE_CONSTRUCTORS:return False
    def family_done():
        more=r['decl_ctor_families']>1
        r['decl_ctor_families']-=1
        if more:r.update(mode=Mode.DECL_CTOR_NAME,x=r['decl_ctor_name_next'])
        else:r['sp']-=1;ret(r['typing_head'])
    mode=r['mode']
    if mode==Mode.WALK:
        if not r['typing_active'] or not r['core_rec_names'] or not r['header_seen']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_DECLARE_CTOR_LOOKUP,0,0,Task.DECLARE_CONSTRUCTORS,0,0]
            r.update(sp=r['sp']+1,mode=Mode.DECL_CTOR_NAME,x=r['core_rec_names'],decl_ctor_families=r['header_seen'],core_ctor_declared=0)
    elif mode==Mode.DECL_CTOR_NAME:
        if bool(c)!=(r['decl_ctor_families']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(decl_ctor_family=a,decl_ctor_name_next=c,mode=Mode.DECL_CTOR_FAMILY_SIGNATURE,x=a)
    elif mode==Mode.DECL_CTOR_FAMILY_SIGNATURE:r.update(mode=Mode.DECL_CTOR_FAMILY_SCHEME,x=c)
    elif mode==Mode.DECL_CTOR_FAMILY_SCHEME:
        if b!=8:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.DECL_CTOR_FAMILY_METADATA,x=c)
    elif mode==Mode.DECL_CTOR_FAMILY_METADATA:r.update(mode=Mode.DECL_CTOR_RAW_FAMILY,x=c)
    elif mode==Mode.DECL_CTOR_RAW_FAMILY:r.update(mode=Mode.DECL_CTOR_AUX,x=c)
    elif mode==Mode.DECL_CTOR_AUX:r.update(mode=Mode.DECL_CTOR_VECTOR,x=a)
    elif mode==Mode.DECL_CTOR_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:family_done()
        else:r.update(mode=Mode.DECL_CTOR_CELL,x=b,decl_ctor_remaining=a,decl_ctor_ordinal=0)
    elif mode==Mode.DECL_CTOR_CELL:
        if not r['decl_ctor_remaining'] or bool(b)!=(r['decl_ctor_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.DECL_CTOR_RAW,x=a,decl_ctor_next=b)
    elif mode==Mode.DECL_CTOR_RAW:
        r.update(decl_ctor_symbol=a,decl_ctor_type=b,query_symbol=a,lookup_head=r['ctor_names'],task=Task.ENV_LOOKUP,mode=Mode.WALK,x=0)
    elif mode==Mode.DECL_CTOR_PENDING:
        if a!=r['decl_ctor_symbol'] or b!=r['decl_ctor_type']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.DECL_CTOR_ANALYSIS,x=c)
    elif mode==Mode.DECL_CTOR_ANALYSIS:
        if a!=r['decl_ctor_family']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(decl_ctor_fields=b,mode=Mode.DECL_CTOR_STORE_INFO)
    elif mode==Mode.DECL_CTOR_STORE_INFO:
        if r['free']+4>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_CONSTRUCTOR,r['decl_ctor_family'],r['decl_ctor_fields'],r['decl_ctor_ordinal']]
            r.update(free=ref+1,decl_ctor_info=ref,mode=Mode.DECL_CTOR_STORE_SCHEME)
    elif mode==Mode.DECL_CTOR_STORE_SCHEME:
        ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_SCHEME,r['header_parameters'],9,r['decl_ctor_info']]
        r.update(free=ref+1,decl_ctor_scheme=ref,mode=Mode.DECL_CTOR_STORE_SIGNATURE)
    elif mode==Mode.DECL_CTOR_STORE_SIGNATURE:
        ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_SIGNATURE,r['decl_ctor_symbol'],r['decl_ctor_type'],r['decl_ctor_scheme']]
        r.update(free=ref+1,decl_ctor_signature=ref,mode=Mode.DECL_CTOR_LINK)
    elif mode==Mode.DECL_CTOR_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['decl_ctor_signature'],r['typing_head'],0]
        more=r['decl_ctor_remaining']>1
        r.update(free=ref+1,typing_head=ref,core_ctor_declared=r['core_ctor_declared']+1,
            decl_ctor_remaining=r['decl_ctor_remaining']-1,decl_ctor_ordinal=r['decl_ctor_ordinal']+1)
        if more:r.update(mode=Mode.DECL_CTOR_CELL,x=r['decl_ctor_next'])
        else:family_done()
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
