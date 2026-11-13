"""Compile closed recursor schemes with the SAME scope/application/Pi fold."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_REC_TYPE_BODY,
    CALL_REC_TYPE_FOLD,CALL_REC_TYPE_SCOPE,CALL_REC_TYPE_VECTOR)

PRIVATE_PHASES=tuple(range(CALL_REC_TYPE_BODY,CALL_REC_TYPE_VECTOR+1))
NO_NODE=(Mode.WALK,Mode.REC_TYPE_STORE,Mode.REC_TYPE_LINK)
TAGS={Mode.REC_TYPE_VECTOR:CellTag.VECTOR,Mode.REC_TYPE_CELL:CellTag.VECTOR_CELL,
    Mode.REC_TYPE_INFO:CellTag.MOTIVE_INFO,Mode.REC_TYPE_TELESCOPE:CellTag.MOTIVE_TELESCOPE,
    Mode.REC_TYPE_INDICES:CellTag.VECTOR,Mode.REC_TYPE_INDEX_CELL:CellTag.VECTOR_CELL,
    Mode.REC_TYPE_INDEX_RECORD:CellTag.LOCAL_DECL,Mode.REC_TYPE_MAJOR:CellTag.LOCAL_DECL,
    Mode.REC_TYPE_MOTIVE_RECORD:CellTag.LOCAL_DECL}


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)))
    phase=lambda p:c.AND(returning,c.eq(f['phase'],p))
    def call(guard,p,task,x,mode=Mode.WALK,**updates):
        c.write('stack',guard,top,(p,0,0,Task.BUILD_RECURSOR_TYPES,0,0))
        c.emit(guard,task=task,mode=mode,x=x,depth=0,**updates)
    call(phase(CALL_REC_TYPE_BODY),CALL_REC_TYPE_FOLD,Task.FOLD_TELESCOPE,r['r'],Mode.FOLD_SELECT,
        fold_base=r['header_parameter_base'],fold_body=r['r'],fold_tag=Tag.PI)
    folded=phase(CALL_REC_TYPE_FOLD);c.emit(folded,rec_type_closed=r['r'])
    call(folded,CALL_REC_TYPE_SCOPE,Task.EXPR_SCOPE,r['r'])
    c.emit(phase(CALL_REC_TYPE_SCOPE),task=Task.BUILD_RECURSOR_TYPES,ctx=r['rec_type_mark'],mode=Mode.REC_TYPE_STORE)
    done=phase(CALL_REC_TYPE_VECTOR);c.emit(done,task=Task.BUILD_RECURSOR_TYPES,core_rec_types=r['r'],sp=top);c.ret(done,r['r'])
    active=c.task(Task.BUILD_RECURSOR_TYPES);at=lambda m:c.AND(active,c.mode(m))
    init=at(Mode.WALK)
    wide=c.g.add(c.g.fit(r['header_parameter_end'],c.width+2),c.g.fit(r['header_seen'],c.width+2))
    wide=c.g.add(wide,c.g.fit(r['core_ctor_declared'],c.width+2))
    valid=c.AND(c.NOT(c.eq(r['core_motives'],0)),c.NOT(c.eq(r['core_minors'],0)),c.g.eq(c.g.fit(r['ctx'],c.width+2),wide))
    room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.stop(c.AND(init,valid,c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    init=c.AND(init,valid,room)
    c.write('stack',init,r['sp'],(CALL_REC_TYPE_VECTOR,0,0,Task.BUILD_RECURSOR_TYPES,0,0))
    c.emit(init,sp=c.add(r['sp'],1),rec_type_mark=r['ctx'],rec_type_rev=0,mode=Mode.REC_TYPE_VECTOR,x=r['core_motives'])
    vector=at(Mode.REC_TYPE_VECTOR);valid=c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.NOT(c.eq(n['a'],0)),c.NOT(c.eq(n['b'],0)),c.eq(n['a'],r['header_seen']))
    c.stop(c.AND(vector,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(vector,valid),rec_type_remaining=n['a'],mode=Mode.REC_TYPE_CELL,x=n['b'])
    def cell_guard(mode,remaining):
        cell=at(mode);valid=c.AND(c.NOT(c.eq(r[remaining],0)),
            c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r[remaining]),1,0)))
        c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
        return c.AND(cell,valid)
    c.emit(cell_guard(Mode.REC_TYPE_CELL,'rec_type_remaining'),rec_type_next=n['b'],mode=Mode.REC_TYPE_INFO,x=n['a'])
    c.emit(at(Mode.REC_TYPE_INFO),rec_type_family=n['a'],rec_type_motive=n['b'],mode=Mode.REC_TYPE_TELESCOPE,x=n['c'])
    c.emit(at(Mode.REC_TYPE_TELESCOPE),rec_type_major=n['b'],rec_type_symbol=n['c'],mode=Mode.REC_TYPE_INDICES,x=n['a'])
    indices=at(Mode.REC_TYPE_INDICES);valid=c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    wide=c.g.add(c.g.fit(r['ctx'],c.width+2),c.g.fit(n['a'],c.width+2));wide=c.g.add(wide,c.g.const(1,c.width+2))
    room=c.NOT(c.g.lt(c.g.const(c.cfg.context,c.width+2),wide))
    c.stop(c.AND(indices,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.stop(c.AND(indices,valid,c.NOT(room)),Outcome.RESOURCE,Reason.CONTEXT)
    indices=c.AND(indices,valid,room);empty=c.eq(n['a'],0)
    c.emit(c.AND(indices,empty),mode=Mode.REC_TYPE_MAJOR,x=r['rec_type_major'])
    c.emit(c.AND(indices,c.NOT(empty)),rec_type_index_remaining=n['a'],mode=Mode.REC_TYPE_INDEX_CELL,x=n['b'])
    c.emit(cell_guard(Mode.REC_TYPE_INDEX_CELL,'rec_type_index_remaining'),rec_type_index_next=n['b'],mode=Mode.REC_TYPE_INDEX_RECORD,x=n['a'])
    record=at(Mode.REC_TYPE_INDEX_RECORD);more=c.lt(1,r['rec_type_index_remaining'])
    c.write('context',record,r['ctx'],(r['x'],));c.emit(record,ctx=c.add(r['ctx'],1),rec_type_index_remaining=c.sub(r['rec_type_index_remaining'],1))
    c.emit(c.AND(record,more),mode=Mode.REC_TYPE_INDEX_CELL,x=r['rec_type_index_next'])
    c.emit(c.AND(record,c.NOT(more)),mode=Mode.REC_TYPE_MAJOR,x=r['rec_type_major'])
    major=at(Mode.REC_TYPE_MAJOR);c.write('context',major,r['ctx'],(r['x'],))
    c.emit(major,ctx=c.add(r['ctx'],1),mode=Mode.REC_TYPE_MOTIVE_RECORD,x=r['rec_type_motive'])
    call(at(Mode.REC_TYPE_MOTIVE_RECORD),CALL_REC_TYPE_BODY,Task.APPLY_SCOPE,n['a'],apply_base=r['rec_type_mark'],apply_end=r['ctx'])
    store=at(Mode.REC_TYPE_STORE);wide=c.g.add(c.g.fit(r['free'],c.width+1),c.g.const(2,c.width+1))
    room=c.NOT(c.g.lt(c.g.const(c.cfg.heap,c.width+1),wide))
    c.stop(c.AND(store,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);store=c.AND(store,room)
    c.write('heap',store,r['free'],(CellTag.RECURSOR_TYPE,r['rec_type_family'],r['rec_type_closed'],r['rec_type_symbol']))
    c.emit(store,free=c.add(r['free'],1),rec_type_info=r['free'],mode=Mode.REC_TYPE_LINK)
    link=at(Mode.REC_TYPE_LINK);more=c.lt(1,r['rec_type_remaining'])
    c.write('heap',link,r['free'],(CellTag.VECTOR_CELL,r['rec_type_info'],r['rec_type_rev'],0))
    c.emit(link,free=c.add(r['free'],1),rec_type_rev=r['free'],rec_type_remaining=c.sub(r['rec_type_remaining'],1))
    c.emit(c.AND(link,more),mode=Mode.REC_TYPE_CELL,x=r['rec_type_next'])
    call(c.AND(link,c.NOT(more)),CALL_REC_TYPE_VECTOR,Task.REVERSE_LIST,r['free'],reverse_length=r['header_seen'])
