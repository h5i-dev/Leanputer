"""Generic signature-vector and immutable word-set lookup, DEVELOPMENT only."""
from .native_cells import VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason


def step(machine,tag,a,b,c,stop,ret,alloc):
    r=machine.state['regs']
    if r['task']==Task.SYMBOL_MEMBER:
        if r['mode']!=Mode.WALK:stop(Outcome.INVALID,Reason.SYNTAX)
        elif not r['x']:ret(0)
        elif a==r['query_symbol']:ret(1)
        elif b:r['x']=b
        else:ret(0)
        return True
    if r['task']!=Task.SIGNATURE_VECTOR_LOOKUP:return False
    if r['mode']==Mode.WALK:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:ret(0)
        else:r.update(signature_lookup_remaining=a,mode=Mode.SIGV_CELL,x=b)
    elif r['mode']==Mode.SIGV_CELL:
        if not r['signature_lookup_remaining'] or bool(b)!=(r['signature_lookup_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(signature_lookup_next=b,mode=Mode.SIGV_SIGNATURE,x=a)
    elif r['mode']==Mode.SIGV_SIGNATURE:
        if a==r['query_symbol']:ret(r['x'])
        elif r['signature_lookup_remaining']>1:
            r.update(signature_lookup_remaining=r['signature_lookup_remaining']-1,mode=Mode.SIGV_CELL,x=r['signature_lookup_next'])
        else:ret(0)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
