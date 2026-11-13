"""Pinned is_rec/is_reflexive from raw domains, DEVELOPMENT reference only."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_FLAGS_OCCURRENCE
from .block_flags_rules import NO_NODE,TAGS

PRIVATE_PHASES=(CALL_FLAGS_OCCURRENCE,)


def resume(machine,frame,stop,ret,alloc):
    r=machine.state['regs']
    r.update(task=Task.BLOCK_FLAGS,core_recursive=int(bool(r['core_recursive'] or r['r'])),
        core_reflexive=int(bool(r['core_reflexive'] or (r['r'] and r['flags_pi']))),mode=Mode.FLAGS_NEXT)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.BLOCK_FLAGS:return False
    def next_constructor():
        r.update(mode=Mode.FLAGS_CTOR_CELL if r['flags_ctor_next'] else Mode.FLAGS_STORE,x=r['flags_ctor_next'])
    mode=r['mode']
    if mode==Mode.WALK:
        if not r['typing_active'] or not r['header_seen']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_FLAGS_OCCURRENCE,0,0,Task.BLOCK_FLAGS,0,0]
            r.update(sp=r['sp']+1,core_recursive=0,core_reflexive=0,
                mode=Mode.FLAGS_CTOR_CELL if r['ctor_names'] else Mode.FLAGS_STORE,x=r['ctor_names'])
    elif mode==Mode.FLAGS_CTOR_CELL:r.update(flags_ctor_next=b,mode=Mode.FLAGS_PENDING,x=a)
    elif mode==Mode.FLAGS_PENDING:r.update(mode=Mode.FLAGS_ANALYSIS,x=c)
    elif mode==Mode.FLAGS_ANALYSIS:r.update(mode=Mode.FLAGS_FIELDS,x=b)
    elif mode==Mode.FLAGS_FIELDS:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:next_constructor()
        else:r.update(flags_remaining=a,mode=Mode.FLAGS_FIELD_CELL,x=b)
    elif mode==Mode.FLAGS_FIELD_CELL:
        if not r['flags_remaining'] or bool(b)!=(r['flags_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(flags_field_next=b,mode=Mode.FLAGS_FIELD,x=a)
    elif mode==Mode.FLAGS_FIELD:r.update(mode=Mode.FLAGS_LOCAL,x=a)
    elif mode==Mode.FLAGS_LOCAL:r.update(mode=Mode.FLAGS_DOMAIN,x=b)
    elif mode==Mode.FLAGS_DOMAIN:
        s['stack'][r['sp']-1]=[CALL_FLAGS_OCCURRENCE,0,0,Task.BLOCK_FLAGS,0,0]
        r.update(flags_pi=int(tag==Tag.PI),task=Task.HAS_FAMILIES,mode=Mode.WALK,depth=0)
    elif mode==Mode.FLAGS_NEXT:
        more=r['flags_remaining']>1;r['flags_remaining']-=1
        if more:r.update(mode=Mode.FLAGS_FIELD_CELL,x=r['flags_field_next'])
        else:next_constructor()
    elif mode==Mode.FLAGS_STORE:
        if r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.BLOCK_FLAGS,r['core_recursive'],r['core_reflexive'],0]
            r.update(free=ref+1,core_flags=ref,sp=r['sp']-1);ret(ref)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
