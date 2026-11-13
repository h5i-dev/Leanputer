"""Shared weighted fresh Local and application over a derived context window."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def emit_rules(c):
    r,n=c.r,c.read['node'];fresh=c.task(Task.FRESH_LOCAL);apply=c.task(Task.APPLY_SCOPE)
    snapshot=c.task(Task.SNAPSHOT_SCOPE);init=c.AND(snapshot,c.mode(Mode.WALK))
    valid=c.AND(c.NOT(c.lt(r['abstract_base'],r['local_base'])),c.NOT(c.lt(r['abstract_end'],r['abstract_base'])),
        c.NOT(c.lt(r['ctx'],r['abstract_end'])))
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    size=c.sub(r['abstract_end'],r['abstract_base']);empty=c.eq(size,0)
    c.emit(c.AND(init,valid),snapshot_count=size,snapshot_remaining=size,snapshot_head=0,
        scope_cursor=c.mux(empty,0,c.sub(r['abstract_end'],1)),mode=c.mux(empty,Mode.SNAPSHOT_VECTOR,Mode.SNAPSHOT_SCOPE))
    store=c.AND(snapshot,c.mode(Mode.SNAPSHOT_SCOPE));room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(store,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    store=c.AND(store,room);more=c.lt(1,r['snapshot_remaining'])
    c.write('heap',store,r['free'],(CellTag.VECTOR_CELL,c.read['operand']['value'],r['snapshot_head'],0))
    c.emit(store,free=c.add(r['free'],1),snapshot_head=r['free'],snapshot_remaining=c.sub(r['snapshot_remaining'],1),
        mode=c.mux(more,Mode.SNAPSHOT_SCOPE,Mode.SNAPSHOT_VECTOR))
    c.emit(c.AND(store,more),scope_cursor=c.sub(r['scope_cursor'],1))
    c.alloc(c.AND(snapshot,c.mode(Mode.SNAPSHOT_VECTOR)),(CellTag.VECTOR,r['snapshot_count'],r['snapshot_head'],VectorKind.REFERENCES))
    init=c.AND(fresh,c.mode(Mode.WALK));ctxroom=c.lt(r['ctx'],c.cfg.context)
    wide=c.g.add(c.g.fit(r['free'],c.width+1),c.g.const(2,c.width+1))
    room=c.NOT(c.g.lt(c.g.const(c.cfg.heap,c.width+1),wide))
    c.stop(c.AND(init,c.NOT(ctxroom)),Outcome.RESOURCE,Reason.CONTEXT)
    c.stop(c.AND(init,ctxroom,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    init=c.AND(init,ctxroom,room)
    c.write('heap',init,r['free'],(Tag.LOCAL,r['free'],0,0))
    c.emit(init,free=c.add(r['free'],1),fresh_local=r['free'],fresh_domain=r['x'],mode=Mode.FRESH_LOCAL_RECORD)
    record=c.AND(fresh,c.mode(Mode.FRESH_LOCAL_RECORD))
    c.write('heap',record,r['free'],(CellTag.LOCAL_DECL,r['fresh_local'],r['fresh_domain'],r['binder_info']))
    c.write('context',record,r['ctx'],(r['free'],))
    c.emit(record,free=c.add(r['free'],1),fresh_record=r['free'],ctx=c.add(r['ctx'],1));c.ret(record,r['fresh_local'])
    init=c.AND(apply,c.mode(Mode.WALK));valid=c.AND(c.NOT(c.lt(r['apply_base'],r['local_base'])),
        c.NOT(c.lt(r['apply_end'],r['apply_base'])),c.NOT(c.lt(r['ctx'],r['apply_end'])))
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    empty=c.eq(r['apply_base'],r['apply_end']);c.ret(c.AND(init,valid,empty),r['x'])
    c.emit(c.AND(init,valid,c.NOT(empty)),apply_cursor=r['apply_base'],apply_body=r['x'],mode=Mode.APPLY_SCOPE_SELECT)
    c.emit(c.AND(apply,c.mode(Mode.APPLY_SCOPE_SELECT)),mode=Mode.APPLY_SCOPE_RECORD,x=c.read['operand']['value'])
    record=c.AND(apply,c.mode(Mode.APPLY_SCOPE_RECORD));valid=c.AND(c.NOT(c.eq(n['a'],0)),c.lt(n['a'],r['free']))
    c.stop(c.AND(record,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(record,valid),mode=Mode.APPLY_SCOPE_LOCAL,x=n['a'])
    local=c.AND(apply,c.mode(Mode.APPLY_SCOPE_LOCAL));valid=c.tag(Tag.LOCAL);room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(local,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.stop(c.AND(local,valid,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    local=c.AND(local,valid,room);more=c.lt(c.add(r['apply_cursor'],1),r['apply_end'])
    c.write('heap',local,r['free'],(Tag.APP,r['apply_body'],r['x'],0))
    c.emit(local,free=c.add(r['free'],1),apply_body=r['free'],apply_cursor=c.add(r['apply_cursor'],1))
    c.emit(c.AND(local,more),mode=Mode.APPLY_SCOPE_SELECT);c.ret(c.AND(local,c.NOT(more)),r['free'])
