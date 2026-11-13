"""Compile a shared counted restore loop for derived Local metadata variants."""
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason

TAGS={Mode.WALK:(CellTag.VECTOR,),Mode.RESTORE_SCOPE_CELL:(CellTag.VECTOR_CELL,),
    Mode.RESTORE_SCOPE_ITEM:(CellTag.LOCAL_DECL,CellTag.CONSTRUCTOR_FIELD),Mode.RESTORE_SCOPE_RECORD:(CellTag.LOCAL_DECL,)}


def emit_rules(c):
    r,n=c.r,c.read['node'];active=c.task(Task.RESTORE_SCOPE);at=lambda m:c.AND(active,c.mode(m))
    init=at(Mode.WALK);valid=c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    wide=c.g.add(c.g.fit(r['ctx'],c.width+1),c.g.fit(n['a'],c.width+1));room=c.NOT(c.g.lt(c.g.const(c.cfg.context,c.width+1),wide))
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.stop(c.AND(init,valid,c.NOT(room)),Outcome.RESOURCE,Reason.CONTEXT)
    init=c.AND(init,valid,room);empty=c.eq(n['a'],0)
    c.emit(init,restore_length=n['a']);c.ret(c.AND(init,empty),r['ctx'])
    c.emit(c.AND(init,c.NOT(empty)),restore_remaining=n['a'],mode=Mode.RESTORE_SCOPE_CELL,x=n['b'])
    cell=at(Mode.RESTORE_SCOPE_CELL);more=c.lt(1,r['restore_remaining'])
    valid=c.AND(c.NOT(c.eq(r['restore_remaining'],0)),c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(more,1,0)))
    c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(cell,valid),restore_next=n['b'],mode=Mode.RESTORE_SCOPE_ITEM,x=n['a'])
    item=at(Mode.RESTORE_SCOPE_ITEM);wrapped=c.tag(CellTag.CONSTRUCTOR_FIELD)
    c.emit(c.AND(item,wrapped),mode=Mode.RESTORE_SCOPE_RECORD,x=n['a'])
    append=c.OR(c.AND(item,c.NOT(wrapped)),at(Mode.RESTORE_SCOPE_RECORD))
    c.write('context',append,r['ctx'],(r['x'],));more=c.lt(1,r['restore_remaining'])
    c.emit(append,ctx=c.add(r['ctx'],1),restore_remaining=c.sub(r['restore_remaining'],1))
    c.emit(c.AND(append,more),mode=Mode.RESTORE_SCOPE_CELL,x=r['restore_next'])
    c.ret(c.AND(append,c.NOT(more)),c.add(r['ctx'],1))
