"""Untrusted core claim checking after generated signatures, DEVELOPMENT only."""
from .arena import Tag
from .native_cells import VectorKind,CellTag
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_CLAIM_SEEN,CALL_CLAIM_LOOKUP,
    CALL_CLAIM_PARAMETERS,CALL_CLAIM_SCOPE,CALL_CLAIM_INFER,CALL_CLAIM_WHNF,
    CALL_CLAIM_RENAME,CALL_CLAIM_CONVERT,CALL_CLAIM_RESTORE)
from .recursor_claim_rules import NO_NODE,TAGS

PRIVATE_PHASES=tuple(range(CALL_CLAIM_SEEN,CALL_CLAIM_RESTORE+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase=frame[0]
    def call(p,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.CHECK_RECURSOR_CLAIMS,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    if phase==CALL_CLAIM_SEEN:
        if r['r']:stop(Outcome.INVALID,Reason.DUPLICATE_DECLARATION)
        else:call(CALL_CLAIM_LOOKUP,Task.SIGNATURE_VECTOR_LOOKUP,r['core_rec_signatures'],query_symbol=r['claim_symbol'])
    elif phase==CALL_CLAIM_LOOKUP:
        if not r['r']:stop(Outcome.INVALID,Reason.UNKNOWN_CONSTANT)
        else:r.update(task=Task.CHECK_RECURSOR_CLAIMS,mode=Mode.CLAIM_SIGNATURE,x=r['r'])
    elif phase==CALL_CLAIM_PARAMETERS:call(CALL_CLAIM_SCOPE,Task.EXPR_SCOPE,r['claim_type'])
    elif phase==CALL_CLAIM_SCOPE:call(CALL_CLAIM_INFER,Task.INFER,r['claim_type'],local_base=r['ctx'])
    elif phase==CALL_CLAIM_INFER:call(CALL_CLAIM_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    elif phase==CALL_CLAIM_WHNF:r.update(task=Task.CHECK_RECURSOR_CLAIMS,mode=Mode.CLAIM_SORT,x=r['r'])
    elif phase==CALL_CLAIM_RENAME:call(CALL_CLAIM_CONVERT,Task.CONVERT_POSITIVE,r['claim_expected_type'],peer=r['r'])
    elif phase==CALL_CLAIM_CONVERT:
        if not r['r']:stop(Outcome.INVALID,Reason.TYPE_MISMATCH)
        else:r.update(task=Task.CHECK_RECURSOR_CLAIMS,mode=Mode.CLAIM_STORE)
    elif phase==CALL_CLAIM_RESTORE:
        r.update(task=Task.CHECK_RECURSOR_CLAIMS,local_base=r['ctx'],sp=r['sp']-1);ret(1)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.CHECK_RECURSOR_CLAIMS:return False
    def call(p,task,x,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.CHECK_RECURSOR_CLAIMS,0,0]
        r.update(task=task,mode=Mode.WALK,x=x,depth=0,**updates)
    mode=r['mode']
    if mode==Mode.WALK:
        if not r['core_rec_signatures'] or not r['core_rec_parameters'] or not r['core_rec_levels']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_CLAIM_SEEN,0,0,Task.CHECK_RECURSOR_CLAIMS,0,0]
            r.update(sp=r['sp']+1,claim_expected_uparams=r['count'],claim_seen=0,claim_checked=0,mode=Mode.CLAIM_VECTOR,x=c)
    elif mode==Mode.CLAIM_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif a and a!=r['header_seen']:stop(Outcome.INVALID,Reason.INVALID_DECLARATION)
        elif not a:call(CALL_CLAIM_RESTORE,Task.LOAD_PARAMETERS,r['core_rec_parameters'])
        else:r.update(claim_remaining=a,mode=Mode.CLAIM_CELL,x=b)
    elif mode==Mode.CLAIM_CELL:
        if not r['claim_remaining'] or bool(b)!=(r['claim_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(claim_next=b,mode=Mode.CLAIM_RECORD,x=a)
    elif mode==Mode.CLAIM_RECORD:
        r.update(claim_symbol=a,claim_type=b,claim_parameters=c)
        call(CALL_CLAIM_SEEN,Task.SYMBOL_MEMBER,r['claim_seen'],query_symbol=a)
    elif mode==Mode.CLAIM_SIGNATURE:
        if a!=r['claim_symbol']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(claim_expected_type=b,mode=Mode.CLAIM_SCHEME,x=c)
    elif mode==Mode.CLAIM_SCHEME:
        if b!=10 or a!=r['core_rec_parameters']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.CLAIM_PARAMETER_VECTOR,x=r['claim_parameters'])
    elif mode==Mode.CLAIM_PARAMETER_VECTOR:
        if c!=VectorKind.SYMBOLS or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif a!=r['claim_expected_uparams']:stop(Outcome.INVALID,Reason.UNIVERSE_ARITY)
        else:call(CALL_CLAIM_PARAMETERS,Task.LOAD_PARAMETERS,r['claim_parameters'])
    elif mode==Mode.CLAIM_SORT:
        if tag!=Tag.SORT:
            stable=tag in (Tag.PI,Tag.LAM,Tag.BVAR,Tag.LOCAL,Tag.NAT,Tag.STRING)
            stop(Outcome.INVALID if stable else Outcome.GAP,Reason.EXPECT_SORT if stable else Reason.GAP_CONVERSION)
        else:call(CALL_CLAIM_RENAME,Task.INSTANTIATE_SCHEME,r['claim_type'],parameter_vector=r['claim_parameters'],level_vector=r['core_rec_levels'])
    elif mode==Mode.CLAIM_STORE:
        if r['free']>=cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP)
        else:
            ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['claim_symbol'],r['claim_seen'],0]
            more=r['claim_remaining']>1
            r.update(free=ref+1,claim_seen=ref,claim_checked=r['claim_checked']+1,claim_remaining=r['claim_remaining']-1)
            if more:r.update(mode=Mode.CLAIM_CELL,x=r['claim_next'])
            else:call(CALL_CLAIM_RESTORE,Task.LOAD_PARAMETERS,r['core_rec_parameters'])
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
