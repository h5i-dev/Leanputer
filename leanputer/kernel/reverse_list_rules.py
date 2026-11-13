"""Lower generic counted private-list reversal, immutable output vector."""
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason


def emit_rules(c):
    r,n=c.r,c.read['node'];active=c.task(Task.REVERSE_LIST);at=lambda mode:c.AND(active,c.mode(mode))
    empty=c.eq(r['reverse_length'],0)
    c.emit(at(Mode.WALK),reverse_remaining=r['reverse_length'],reverse_head=0,mode=c.mux(empty,Mode.REVERSE_FINISH,Mode.REVERSE_LIST))
    cell=at(Mode.REVERSE_LIST);more=c.lt(1,r['reverse_remaining'])
    valid=c.AND(c.NOT(c.eq(r['reverse_remaining'],0)),c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(more,1,0)))
    c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(cell,valid,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    store=c.AND(cell,valid,room)
    c.write('heap',store,r['free'],(CellTag.VECTOR_CELL,n['a'],r['reverse_head'],0))
    c.emit(store,free=c.add(r['free'],1),reverse_head=r['free'],reverse_remaining=c.sub(r['reverse_remaining'],1),x=n['b'],
        mode=c.mux(more,Mode.REVERSE_LIST,Mode.REVERSE_FINISH))
    c.alloc(at(Mode.REVERSE_FINISH),(CellTag.VECTOR,r['reverse_length'],r['reverse_head'],VectorKind.REFERENCES))
