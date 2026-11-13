"""Lower generic symbol-window -> formal Param-level vector generation."""
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason


def emit_rules(c):
    r=c.r;active=c.task(Task.FORMAL_LEVELS)
    at=lambda mode:c.AND(active,c.mode(mode))
    empty=c.eq(r['count'],0)
    c.emit(at(Mode.WALK),formal_count=r['count'],formal_remaining=r['count'],formal_head=0,
        formal_i=c.mux(empty,0,c.sub(r['count'],1)),mode=c.mux(empty,Mode.FORMAL_FINISH,Mode.FORMAL_SELECT))
    symbol=c.read['operand']['value'];select=at(Mode.FORMAL_SELECT);room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(select,c.eq(symbol,0)),Outcome.INVALID,Reason.UNIVERSE)
    c.stop(c.AND(select,c.NOT(c.eq(symbol,0)),c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    store=c.AND(select,c.NOT(c.eq(symbol,0)),room)
    c.write('heap',store,r['free'],(CellTag.LEVEL_PARAM,symbol,0,0))
    c.emit(store,free=c.add(r['free'],1),formal_value=r['free'],mode=Mode.FORMAL_CELL)
    cell=at(Mode.FORMAL_CELL)
    c.stop(c.AND(cell,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    cell=c.AND(cell,room);more=c.lt(1,r['formal_remaining'])
    c.write('heap',cell,r['free'],(CellTag.VECTOR_CELL,r['formal_value'],r['formal_head'],0))
    c.emit(cell,free=c.add(r['free'],1),formal_head=r['free'],formal_remaining=c.sub(r['formal_remaining'],1),
        mode=c.mux(more,Mode.FORMAL_SELECT,Mode.FORMAL_FINISH))
    c.emit(c.AND(cell,more),formal_i=c.sub(r['formal_i'],1))
    c.alloc(at(Mode.FORMAL_FINISH),(CellTag.VECTOR,r['formal_count'],r['formal_head'],VectorKind.LEVELS))
