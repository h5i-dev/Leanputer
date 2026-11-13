"""Lower general recursor name/namespace verification before generation."""
from .native_cells import CellTag
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_CORE_NAME_PROFILE,
    CALL_CORE_NAME_RELATION,CALL_CORE_NAME_DECLARATION,CALL_CORE_NAME_PENDING)

PRIVATE_PHASES=tuple(range(CALL_CORE_NAME_PROFILE,CALL_CORE_NAME_PENDING+1))


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)))
    at=lambda phase:c.AND(returning,c.eq(f['phase'],phase))
    def call(guard,phase,task,x,**updates):
        c.write('stack',guard,top,(phase,0,0,Task.CHECK_CORE_NAMES,0,0))
        c.emit(guard,task=task,mode=Mode.WALK,x=x,depth=0,**updates)
    call(at(CALL_CORE_NAME_PROFILE),CALL_CORE_NAME_RELATION,Task.CHECK_RECURSOR_NAME,0,
        name_parent_symbol=r['core_name_family_symbol'],name_candidate_symbol=r['core_name_symbol'])
    relation=at(CALL_CORE_NAME_RELATION)
    c.stop(c.AND(relation,c.eq(r['r'],0)),Outcome.INVALID,Reason.INVALID_RECURSOR_NAME)
    call(c.AND(relation,c.NOT(c.eq(r['r'],0))),CALL_CORE_NAME_DECLARATION,Task.ENV_LOOKUP,0,
        query_symbol=r['core_name_symbol'],lookup_head=r['typing_head'])
    for phase in (CALL_CORE_NAME_DECLARATION,CALL_CORE_NAME_PENDING):
        c.stop(c.AND(at(phase),c.NOT(c.eq(r['r'],0))),Outcome.INVALID,Reason.DUPLICATE_DECLARATION)
    call(c.AND(at(CALL_CORE_NAME_DECLARATION),c.eq(r['r'],0)),CALL_CORE_NAME_PENDING,Task.ENV_LOOKUP,0,
        query_symbol=r['core_name_symbol'],lookup_head=r['ctor_names'])
    c.emit(c.AND(at(CALL_CORE_NAME_PENDING),c.eq(r['r'],0)),task=Task.CHECK_CORE_NAMES,mode=Mode.CORE_NAME_STORE)
    active=c.task(Task.CHECK_CORE_NAMES);at_mode=lambda mode:c.AND(active,c.mode(mode))
    init=at_mode(Mode.WALK);nonempty=c.NOT(c.eq(r['header_seen'],0));room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(nonempty)),Outcome.INVALID,Reason.INVALID_DECLARATION)
    c.stop(c.AND(init,nonempty,c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    init=c.AND(init,nonempty,room)
    c.write('stack',init,r['sp'],(CALL_CORE_NAME_PROFILE,0,0,Task.CHECK_CORE_NAMES,0,0))
    c.emit(init,sp=c.add(r['sp'],1),mode=Mode.CORE_NAME_CELL,x=r['header_head'],core_names_remaining=r['header_seen'],core_rec_names=0)
    c.emit(at_mode(Mode.CORE_NAME_CELL),mode=Mode.CORE_NAME_SIGNATURE,x=n['a'],core_name_next=n['b'])
    c.emit(at_mode(Mode.CORE_NAME_SIGNATURE),mode=Mode.CORE_NAME_SCHEME,x=n['c'],core_name_family=r['x'],core_name_family_symbol=n['a'])
    scheme=at_mode(Mode.CORE_NAME_SCHEME)
    c.stop(c.AND(scheme,c.NOT(c.eq(n['b'],8))),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(scheme,c.eq(n['b'],8)),mode=Mode.CORE_NAME_METADATA,x=n['c'])
    c.emit(at_mode(Mode.CORE_NAME_METADATA),mode=Mode.CORE_NAME_RAW_FAMILY,x=n['c'])
    c.emit(at_mode(Mode.CORE_NAME_RAW_FAMILY),mode=Mode.CORE_NAME_AUX,x=n['c'])
    aux=at_mode(Mode.CORE_NAME_AUX)
    c.emit(aux,core_name_symbol=n['b'])
    call(aux,CALL_CORE_NAME_PROFILE,Task.CHECK_NAME,r['symbols_root'],query_symbol=n['b'])
    store=at_mode(Mode.CORE_NAME_STORE);room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(store,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    store=c.AND(store,room);more=c.lt(1,r['core_names_remaining'])
    c.write('heap',store,r['free'],(CellTag.VALIDATED_RECURSOR_NAME,r['core_name_family'],r['core_name_symbol'],r['core_rec_names']))
    c.emit(store,free=c.add(r['free'],1),core_rec_names=r['free'],core_names_remaining=c.sub(r['core_names_remaining'],1))
    c.emit(c.AND(store,more),mode=Mode.CORE_NAME_CELL,x=r['core_name_next'])
    c.emit(c.AND(store,c.NOT(more)),sp=top)
    c.ret(c.AND(store,c.NOT(more)),r['free'])
