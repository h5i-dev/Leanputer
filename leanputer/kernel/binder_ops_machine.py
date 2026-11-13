"""Reusable internal Local allocation/context application, DEVELOPMENT ONLY.

Generated binder types come from the caller's kernel algorithm. This operation
is not a public type/admission boundary; it cannot be entered by raw proof data.
"""
from .arena import Tag
from .native_cells import CellTag
from .traversal_machine import Mode, Task, Outcome, Reason


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']==Task.FRESH_LOCAL:
        if r['mode']==Mode.WALK:
            if r['ctx']>=cfg.context:stop(Outcome.RESOURCE,Reason.CONTEXT)
            elif r['free']+2>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
            else:
                ref=r['free'];s['heap'][ref]=[Tag.LOCAL,ref,0,0]
                r.update(free=ref+1,fresh_local=ref,fresh_domain=r['x'],mode=Mode.FRESH_LOCAL_RECORD)
        elif r['mode']==Mode.FRESH_LOCAL_RECORD:
            ref=r['free'];s['heap'][ref]=[CellTag.LOCAL_DECL,r['fresh_local'],r['fresh_domain'],r['binder_info']]
            s['context'][r['ctx']]=[ref]
            r.update(free=ref+1,fresh_record=ref,ctx=r['ctx']+1);ret(r['fresh_local'])
        else:stop(Outcome.INVALID,Reason.SYNTAX)
        return True
    if r['task']!=Task.APPLY_SCOPE:return False
    if r['mode']==Mode.WALK:
        if not r['local_base']<=r['apply_base']<=r['apply_end']<=r['ctx']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['apply_base']==r['apply_end']:ret(r['x'])
        else:r.update(apply_cursor=r['apply_base'],apply_body=r['x'],mode=Mode.APPLY_SCOPE_SELECT)
    elif r['mode']==Mode.APPLY_SCOPE_SELECT:r.update(mode=Mode.APPLY_SCOPE_RECORD,x=s['context'][r['apply_cursor']][0])
    elif r['mode']==Mode.APPLY_SCOPE_RECORD:
        if not 0<a<r['free']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.APPLY_SCOPE_LOCAL,x=a)
    elif r['mode']==Mode.APPLY_SCOPE_LOCAL:
        if tag!=Tag.LOCAL:stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[Tag.APP,r['apply_body'],r['x'],0]
            r.update(free=ref+1,apply_body=ref,apply_cursor=r['apply_cursor']+1)
            if r['apply_cursor']<r['apply_end']:r['mode']=Mode.APPLY_SCOPE_SELECT
            else:ret(ref)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
