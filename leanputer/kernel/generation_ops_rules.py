"""Compile generic list application and checked family-to-motive lookup."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason

MOTIVE_TAGS={Mode.WALK:CellTag.VECTOR,Mode.MOTIVE_FIND_CELL:CellTag.VECTOR_CELL,
    Mode.MOTIVE_FIND_INFO:CellTag.MOTIVE_INFO,Mode.MOTIVE_FIND_RECORD:CellTag.LOCAL_DECL}


def emit_rules(c):
    r,n=c.r,c.read['node'];apply=c.task(Task.APPLY_LIST);at=lambda mode:c.AND(apply,c.mode(mode))
    init=at(Mode.WALK);empty=c.eq(r['list_head'],0);skip=c.NOT(c.eq(r['list_skip'],0))
    c.stop(c.AND(init,empty,skip),Outcome.INVALID,Reason.SYNTAX)
    c.ret(c.AND(init,empty,c.NOT(skip)),r['x'])
    c.emit(c.AND(init,c.NOT(empty)),list_body=r['x'],mode=Mode.LIST_CELL,x=r['list_head'])
    cell=at(Mode.LIST_CELL);tail=c.NOT(c.eq(n['b'],0));bad=c.AND(c.NOT(tail),c.lt(1,r['list_skip']))
    c.stop(c.AND(cell,skip,bad),Outcome.INVALID,Reason.SYNTAX)
    skipped=c.AND(cell,skip,c.NOT(bad))
    c.emit(skipped,list_skip=c.sub(r['list_skip'],1),x=n['b'])
    c.ret(c.AND(skipped,c.NOT(tail)),r['list_body'])
    c.emit(c.AND(cell,c.NOT(skip)),list_next=n['b'],mode=Mode.LIST_ARGUMENT,x=n['a'])
    argument=at(Mode.LIST_ARGUMENT);room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(argument,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    argument=c.AND(argument,room);more=c.NOT(c.eq(r['list_next'],0))
    c.write('heap',argument,r['free'],(Tag.APP,r['list_body'],r['x'],0))
    c.emit(argument,free=c.add(r['free'],1),list_body=r['free'])
    c.emit(c.AND(argument,more),mode=Mode.LIST_CELL,x=r['list_next'])
    c.ret(c.AND(argument,c.NOT(more)),r['free'])
    lookup=c.task(Task.FIND_MOTIVE);at=lambda mode:c.AND(lookup,c.mode(mode))
    init=at(Mode.WALK);valid=c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.NOT(c.eq(n['a'],0)),c.NOT(c.eq(n['b'],0)),c.NOT(c.eq(r['motive_query'],0)))
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(init,valid),motive_lookup_remaining=n['a'],mode=Mode.MOTIVE_FIND_CELL,x=n['b'])
    cell=at(Mode.MOTIVE_FIND_CELL);more=c.lt(1,r['motive_lookup_remaining'])
    valid=c.AND(c.NOT(c.eq(r['motive_lookup_remaining'],0)),c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(more,1,0)))
    c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(cell,valid),motive_lookup_next=n['b'],mode=Mode.MOTIVE_FIND_INFO,x=n['a'])
    info=at(Mode.MOTIVE_FIND_INFO);found=c.eq(n['a'],r['motive_query'])
    c.emit(c.AND(info,found),motive_lookup_info=r['x'],mode=Mode.MOTIVE_FIND_RECORD,x=n['b'])
    c.emit(c.AND(info,c.NOT(found),more),motive_lookup_remaining=c.sub(r['motive_lookup_remaining'],1),mode=Mode.MOTIVE_FIND_CELL,x=r['motive_lookup_next'])
    c.stop(c.AND(info,c.NOT(found),c.NOT(more)),Outcome.INVALID,Reason.SYNTAX)
    record=at(Mode.MOTIVE_FIND_RECORD);valid=c.AND(c.NOT(c.eq(n['a'],0)),c.lt(n['a'],r['free']))
    c.stop(c.AND(record,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);c.ret(c.AND(record,valid),n['a'])
