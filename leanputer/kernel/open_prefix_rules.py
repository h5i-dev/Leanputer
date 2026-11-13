"""Compile generic dependent recursive-prefix/index template reopening."""
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_PREFIX_DOMAIN,
    CALL_PREFIX_LOCAL,CALL_PREFIX_INDEX,CALL_PREFIX_INDEX_VECTOR,CALL_PREFIX_LOCAL_VECTOR)

PRIVATE_PHASES=tuple(range(CALL_PREFIX_DOMAIN,CALL_PREFIX_LOCAL_VECTOR+1))
NO_NODE=(Mode.PREFIX_INDEX_STORE,Mode.PREFIX_STORE)
TAGS={Mode.WALK:CellTag.RECURSIVE_ARGUMENT,Mode.PREFIX_VECTOR:CellTag.VECTOR,
    Mode.PREFIX_CELL:CellTag.VECTOR_CELL,Mode.PREFIX_BINDER:CellTag.PREFIX_BINDER,
    Mode.PREFIX_INDICES:CellTag.VECTOR,Mode.PREFIX_INDEX_CELL:CellTag.VECTOR_CELL}


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)))
    phase=lambda p:c.AND(returning,c.eq(f['phase'],p))
    def call(guard,p,task,x,**updates):
        c.write('stack',guard,top,(p,0,0,Task.OPEN_RECURSIVE_PREFIX,0,0))
        c.emit(guard,task=task,mode=Mode.WALK,x=x,depth=0,**updates)
    call(phase(CALL_PREFIX_DOMAIN),CALL_PREFIX_LOCAL,Task.FRESH_LOCAL,r['r'],binder_info=r['prefix_binder_info'])
    local=phase(CALL_PREFIX_LOCAL);more=c.lt(1,r['prefix_remaining'])
    c.emit(local,prefix_remaining=c.sub(r['prefix_remaining'],1))
    c.emit(c.AND(local,more),task=Task.OPEN_RECURSIVE_PREFIX,mode=Mode.PREFIX_CELL,x=r['prefix_next'])
    call(c.AND(local,c.NOT(more)),CALL_PREFIX_LOCAL_VECTOR,Task.SNAPSHOT_SCOPE,0,abstract_base=r['prefix_mark'],abstract_end=r['ctx'])
    c.emit(phase(CALL_PREFIX_LOCAL_VECTOR),task=Task.OPEN_RECURSIVE_PREFIX,prefix_locals=r['r'],prefix_index_rev=0,mode=Mode.PREFIX_INDICES,x=r['prefix_indices'])
    c.emit(phase(CALL_PREFIX_INDEX),task=Task.OPEN_RECURSIVE_PREFIX,mode=Mode.PREFIX_INDEX_STORE)
    c.emit(phase(CALL_PREFIX_INDEX_VECTOR),task=Task.OPEN_RECURSIVE_PREFIX,prefix_index_vector=r['r'],mode=Mode.PREFIX_STORE)
    active=c.task(Task.OPEN_RECURSIVE_PREFIX);at=lambda m:c.AND(active,c.mode(m))
    init=at(Mode.WALK);room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);init=c.AND(init,room)
    c.write('stack',init,r['sp'],(CALL_PREFIX_DOMAIN,0,0,Task.OPEN_RECURSIVE_PREFIX,0,0))
    c.emit(init,sp=c.add(r['sp'],1),prefix_family=n['a'],prefix_indices=n['c'],prefix_mark=r['ctx'],mode=Mode.PREFIX_VECTOR,x=n['b'])
    for mode,remaining in ((Mode.PREFIX_VECTOR,'prefix_remaining'),(Mode.PREFIX_INDICES,'prefix_index_remaining')):
        vector=at(mode);valid=c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
        c.stop(c.AND(vector,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
        nonempty=c.AND(vector,valid,c.NOT(c.eq(n['a'],0)));empty=c.AND(vector,valid,c.eq(n['a'],0))
        c.emit(nonempty,**{remaining:n['a']},mode=Mode.PREFIX_CELL if mode==Mode.PREFIX_VECTOR else Mode.PREFIX_INDEX_CELL,x=n['b'])
        if mode==Mode.PREFIX_VECTOR:call(empty,CALL_PREFIX_LOCAL_VECTOR,Task.SNAPSHOT_SCOPE,0,abstract_base=r['prefix_mark'],abstract_end=r['ctx'])
        else:
            c.emit(c.AND(vector,valid),prefix_index_count=n['a'],prefix_index_remaining=n['a'])
            call(empty,CALL_PREFIX_INDEX_VECTOR,Task.REVERSE_LIST,0,reverse_length=0)
    for mode,remaining in ((Mode.PREFIX_CELL,'prefix_remaining'),(Mode.PREFIX_INDEX_CELL,'prefix_index_remaining')):
        cell=at(mode);more=c.lt(1,r[remaining]);valid=c.AND(c.NOT(c.eq(r[remaining],0)),
            c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(more,1,0)))
        c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);cell=c.AND(cell,valid)
        if mode==Mode.PREFIX_CELL:c.emit(cell,prefix_next=n['b'],mode=Mode.PREFIX_BINDER,x=n['a'])
        else:
            c.emit(cell,prefix_index_next=n['b'])
            call(cell,CALL_PREFIX_INDEX,Task.INSTANTIATE_SCOPE,n['a'],abstract_base=r['prefix_mark'],abstract_end=r['ctx'])
    binder=at(Mode.PREFIX_BINDER);c.emit(binder,prefix_binder_info=n['b'])
    call(binder,CALL_PREFIX_DOMAIN,Task.INSTANTIATE_SCOPE,n['a'],abstract_base=r['prefix_mark'],abstract_end=r['ctx'])
    room=c.lt(r['free'],c.cfg.heap);store=at(Mode.PREFIX_INDEX_STORE)
    c.stop(c.AND(store,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);store=c.AND(store,room);more=c.lt(1,r['prefix_index_remaining'])
    c.write('heap',store,r['free'],(CellTag.VECTOR_CELL,r['r'],r['prefix_index_rev'],0))
    c.emit(store,free=c.add(r['free'],1),prefix_index_rev=r['free'],prefix_index_remaining=c.sub(r['prefix_index_remaining'],1))
    c.emit(c.AND(store,more),mode=Mode.PREFIX_INDEX_CELL,x=r['prefix_index_next'])
    call(c.AND(store,c.NOT(more)),CALL_PREFIX_INDEX_VECTOR,Task.REVERSE_LIST,r['free'],reverse_length=r['prefix_index_count'])
    store=at(Mode.PREFIX_STORE);c.stop(c.AND(store,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);store=c.AND(store,room)
    c.write('heap',store,r['free'],(CellTag.OPENED_RECURSIVE_PREFIX,r['prefix_family'],r['prefix_locals'],r['prefix_index_vector']))
    c.emit(store,free=c.add(r['free'],1),opened_prefix=r['free'],sp=top);c.ret(store,r['free'])
