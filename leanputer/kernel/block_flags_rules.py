"""Compile raw-domain recursion/reflexivity scans over all checked fields."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_FLAGS_OCCURRENCE

PRIVATE_PHASES=(CALL_FLAGS_OCCURRENCE,)
NO_NODE=(Mode.WALK,Mode.FLAGS_NEXT,Mode.FLAGS_STORE)
TAGS={Mode.FLAGS_CTOR_CELL:CellTag.VECTOR_CELL,Mode.FLAGS_PENDING:CellTag.PENDING_CONSTRUCTOR,
    Mode.FLAGS_ANALYSIS:CellTag.CONSTRUCTOR_ANALYSIS,Mode.FLAGS_FIELDS:CellTag.VECTOR,
    Mode.FLAGS_FIELD_CELL:CellTag.VECTOR_CELL,Mode.FLAGS_FIELD:CellTag.CONSTRUCTOR_FIELD,
    Mode.FLAGS_LOCAL:CellTag.LOCAL_DECL}


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    returned=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['phase'],CALL_FLAGS_OCCURRENCE))
    c.emit(returned,task=Task.BLOCK_FLAGS,core_recursive=c.mux(c.OR(c.NOT(c.eq(r['core_recursive'],0)),c.NOT(c.eq(r['r'],0))),1,0),
        core_reflexive=c.mux(c.OR(c.NOT(c.eq(r['core_reflexive'],0)),c.AND(c.NOT(c.eq(r['r'],0)),c.NOT(c.eq(r['flags_pi'],0)))),1,0),mode=Mode.FLAGS_NEXT)
    active=c.task(Task.BLOCK_FLAGS);at=lambda m:c.AND(active,c.mode(m))
    def next_constructor(guard):
        more=c.NOT(c.eq(r['flags_ctor_next'],0))
        c.emit(guard,mode=c.mux(more,Mode.FLAGS_CTOR_CELL,Mode.FLAGS_STORE),x=r['flags_ctor_next'])
    init=at(Mode.WALK);valid=c.AND(c.NOT(c.eq(r['typing_active'],0)),c.NOT(c.eq(r['header_seen'],0)));room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.stop(c.AND(init,valid,c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    init=c.AND(init,valid,room);ctors=c.NOT(c.eq(r['ctor_names'],0))
    c.write('stack',init,r['sp'],(CALL_FLAGS_OCCURRENCE,0,0,Task.BLOCK_FLAGS,0,0))
    c.emit(init,sp=c.add(r['sp'],1),core_recursive=0,core_reflexive=0,
        mode=c.mux(ctors,Mode.FLAGS_CTOR_CELL,Mode.FLAGS_STORE),x=r['ctor_names'])
    c.emit(at(Mode.FLAGS_CTOR_CELL),flags_ctor_next=n['b'],mode=Mode.FLAGS_PENDING,x=n['a'])
    c.emit(at(Mode.FLAGS_PENDING),mode=Mode.FLAGS_ANALYSIS,x=n['c'])
    c.emit(at(Mode.FLAGS_ANALYSIS),mode=Mode.FLAGS_FIELDS,x=n['b'])
    fields=at(Mode.FLAGS_FIELDS);valid=c.AND(c.eq(n['c'],VectorKind.REFERENCES),
        c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    c.stop(c.AND(fields,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    next_constructor(c.AND(fields,valid,c.eq(n['a'],0)))
    c.emit(c.AND(fields,valid,c.NOT(c.eq(n['a'],0))),flags_remaining=n['a'],mode=Mode.FLAGS_FIELD_CELL,x=n['b'])
    cell=at(Mode.FLAGS_FIELD_CELL);more=c.lt(1,r['flags_remaining'])
    valid=c.AND(c.NOT(c.eq(r['flags_remaining'],0)),c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(more,1,0)))
    c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(cell,valid),flags_field_next=n['b'],mode=Mode.FLAGS_FIELD,x=n['a'])
    c.emit(at(Mode.FLAGS_FIELD),mode=Mode.FLAGS_LOCAL,x=n['a'])
    c.emit(at(Mode.FLAGS_LOCAL),mode=Mode.FLAGS_DOMAIN,x=n['b'])
    domain=at(Mode.FLAGS_DOMAIN)
    c.write('stack',domain,top,(CALL_FLAGS_OCCURRENCE,0,0,Task.BLOCK_FLAGS,0,0))
    c.emit(domain,flags_pi=c.mux(c.tag(Tag.PI),1,0),task=Task.HAS_FAMILIES,mode=Mode.WALK,depth=0)
    next_=at(Mode.FLAGS_NEXT);more=c.lt(1,r['flags_remaining'])
    c.emit(next_,flags_remaining=c.sub(r['flags_remaining'],1))
    c.emit(c.AND(next_,more),mode=Mode.FLAGS_FIELD_CELL,x=r['flags_field_next'])
    next_constructor(c.AND(next_,c.NOT(more)))
    store=at(Mode.FLAGS_STORE);room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(store,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    store=c.AND(store,room)
    c.write('heap',store,r['free'],(CellTag.BLOCK_FLAGS,r['core_recursive'],r['core_reflexive'],0))
    c.emit(store,free=c.add(r['free'],1),core_flags=r['free'],sp=top);c.ret(store,r['free'])
