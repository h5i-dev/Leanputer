"""Compile reusable ordered signature lookup and immutable word membership."""
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason

TAGS={Mode.WALK:CellTag.VECTOR,Mode.SIGV_CELL:CellTag.VECTOR_CELL,Mode.SIGV_SIGNATURE:CellTag.CHECKED_SIGNATURE}


def emit_rules(c):
    r,n=c.r,c.read['node'];member=c.task(Task.SYMBOL_MEMBER);at=c.AND(member,c.mode(Mode.WALK));empty=c.eq(r['x'],0)
    c.stop(c.AND(member,c.active,c.NOT(c.eq(r['mode'],Mode.WALK)),c.NOT(c.eq(r['mode'],Mode.RETURN))),Outcome.INVALID,Reason.SYNTAX)
    c.ret(c.AND(at,empty),0);found=c.eq(n['a'],r['query_symbol']);tail=c.NOT(c.eq(n['b'],0))
    c.ret(c.AND(at,c.NOT(empty),found),1)
    c.emit(c.AND(at,c.NOT(empty),c.NOT(found),tail),x=n['b'])
    c.ret(c.AND(at,c.NOT(empty),c.NOT(found),c.NOT(tail)),0)
    active=c.task(Task.SIGNATURE_VECTOR_LOOKUP);at=lambda m:c.AND(active,c.mode(m))
    init=at(Mode.WALK);valid=c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.ret(c.AND(init,valid,c.eq(n['a'],0)),0)
    c.emit(c.AND(init,valid,c.NOT(c.eq(n['a'],0))),signature_lookup_remaining=n['a'],mode=Mode.SIGV_CELL,x=n['b'])
    cell=at(Mode.SIGV_CELL);more=c.lt(1,r['signature_lookup_remaining'])
    valid=c.AND(c.NOT(c.eq(r['signature_lookup_remaining'],0)),c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(more,1,0)))
    c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(cell,valid),signature_lookup_next=n['b'],mode=Mode.SIGV_SIGNATURE,x=n['a'])
    sig=at(Mode.SIGV_SIGNATURE);found=c.eq(n['a'],r['query_symbol'])
    c.ret(c.AND(sig,found),r['x'])
    c.emit(c.AND(sig,c.NOT(found),more),signature_lookup_remaining=c.sub(r['signature_lookup_remaining'],1),mode=Mode.SIGV_CELL,x=r['signature_lookup_next'])
    c.ret(c.AND(sig,c.NOT(found),c.NOT(more)),0)
