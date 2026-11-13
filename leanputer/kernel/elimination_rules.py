"""Compile the complete pinned elimination universe/K decision and fresh binder.

Input is private weighted metadata, output172 is generated inside the model.
No field/type/large-elimination/K answer is accepted from the syntax boundary.
"""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_ELIM_NONZERO, CALL_ELIM_FIELD_INFER, CALL_ELIM_FIELD_WHNF)

PRIVATE_PHASES = (CALL_ELIM_NONZERO, CALL_ELIM_FIELD_INFER, CALL_ELIM_FIELD_WHNF)
NO_NODE = (Mode.WALK, Mode.ELIM_PREPARE, Mode.ELIM_FRESH,
    Mode.ELIM_SHIFT, Mode.ELIM_STORE_LEVEL, Mode.ELIM_STORE_CELL,
    Mode.ELIM_STORE_VECTOR, Mode.ELIM_STORE_METADATA, Mode.ELIM_APPEND)
TAGS = {Mode.ELIM_PENDING_CELL: CellTag.VECTOR_CELL,
    Mode.ELIM_PENDING: CellTag.PENDING_CONSTRUCTOR,
    Mode.ELIM_ANALYSIS: CellTag.CONSTRUCTOR_ANALYSIS,
    Mode.ELIM_FIELDS: CellTag.VECTOR,
    Mode.ELIM_FIELD_CELL: CellTag.VECTOR_CELL,
    Mode.ELIM_FIELD: CellTag.CONSTRUCTOR_FIELD,
    Mode.ELIM_LOCAL: CellTag.LOCAL_DECL,
    Mode.ELIM_ARGUMENT: CellTag.VECTOR_CELL,
    Mode.ELIM_PARAMETERS: CellTag.VECTOR}
LEVEL_MODES = (Mode.ELIM_RESULT_LEVEL, Mode.ELIM_FIELD_LEVEL)


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];a,b=n['a'],n['b'];top=c.sub(r['sp'],1)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)))
    phase=lambda p:c.AND(returning,c.eq(f['phase'],p))
    def call(guard,p,task,x,mode=Mode.WALK,**updates):
        c.write('stack',guard,top,(p,0,0,Task.INIT_ELIMINATION,0,0))
        c.emit(guard,task=task,mode=mode,x=x,depth=0,**updates)
    def prepare(guard,large): c.emit(guard,elim_large=large,mode=Mode.ELIM_PREPARE)
    nonzero=phase(CALL_ELIM_NONZERO)
    large=c.OR(c.NOT(c.eq(r['r'],0)),c.AND(c.eq(r['header_seen'],1),c.eq(r['core_ctor_declared'],0)))
    small=c.AND(c.NOT(large),c.OR(c.lt(1,r['header_seen']),c.lt(1,r['core_ctor_declared'])))
    c.emit(nonzero,task=Task.INIT_ELIMINATION,core_K=0)
    prepare(c.AND(nonzero,large),1);prepare(c.AND(nonzero,small),0)
    c.emit(c.AND(nonzero,c.NOT(large),c.NOT(small)),mode=Mode.ELIM_PENDING_CELL,x=r['ctor_names'])
    call(phase(CALL_ELIM_FIELD_INFER),CALL_ELIM_FIELD_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    c.emit(phase(CALL_ELIM_FIELD_WHNF),task=Task.INIT_ELIMINATION,mode=Mode.ELIM_FIELD_SORT,x=r['r'])
    active=c.task(Task.INIT_ELIMINATION);at=lambda m:c.AND(active,c.mode(m))
    init=at(Mode.WALK);valid=c.AND(c.NOT(c.eq(r['typing_active'],0)),c.NOT(c.eq(r['header_seen'],0)))
    room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.stop(c.AND(init,valid,c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    init=c.AND(init,valid,room)
    c.write('stack',init,r['sp'],(CALL_ELIM_NONZERO,0,0,Task.INIT_ELIMINATION,0,0))
    c.emit(init,sp=c.add(r['sp'],1),task=Task.LEVEL_NOT_ZERO,mode=Mode.WALK,x=r['header_result_level'])
    c.emit(at(Mode.ELIM_PENDING_CELL),mode=Mode.ELIM_PENDING,x=a)
    c.emit(at(Mode.ELIM_PENDING),mode=Mode.ELIM_ANALYSIS,x=n['c'])
    c.emit(at(Mode.ELIM_ANALYSIS),elim_arguments=n['c'],mode=Mode.ELIM_FIELDS,x=b)
    word_bool=lambda w:c.mux(c.eq(w,0),0,1)
    fields=at(Mode.ELIM_FIELDS)
    valid=c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.eq(word_bool(a),word_bool(b)))
    c.stop(c.AND(fields,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(fields,valid),elim_remaining=a,elim_head=b,mode=Mode.ELIM_RESULT_LEVEL,x=r['header_result_level'])
    result=at(Mode.ELIM_RESULT_LEVEL);empty=c.eq(r['elim_remaining'],0)
    c.emit(result,core_K=c.mux(c.AND(c.tag(CellTag.LEVEL_ZERO),empty),1,0),ctx=r['header_parameter_end'])
    prepare(c.AND(result,empty),1)
    c.emit(c.AND(result,c.NOT(empty)),mode=Mode.ELIM_FIELD_CELL,x=r['elim_head'])
    cell=at(Mode.ELIM_FIELD_CELL);more=c.lt(1,r['elim_remaining'])
    valid=c.AND(c.NOT(c.eq(r['elim_remaining'],0)),c.eq(word_bool(b),c.mux(more,1,0)))
    c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(cell,valid),elim_next=b,mode=Mode.ELIM_FIELD,x=a)
    c.emit(at(Mode.ELIM_FIELD),mode=Mode.ELIM_LOCAL,x=a)
    local=at(Mode.ELIM_LOCAL)
    c.emit(local,elim_record=r['x'],elim_local=a)
    call(local,CALL_ELIM_FIELD_INFER,Task.INFER,b,local_base=r['header_parameter_base'])
    sort=at(Mode.ELIM_FIELD_SORT);stable=c.tag(Tag.PI,Tag.LAM,Tag.BVAR,Tag.LOCAL,Tag.NAT,Tag.STRING)
    c.stop(c.AND(sort,c.NOT(c.tag(Tag.SORT)),stable),Outcome.INVALID,Reason.EXPECT_SORT)
    c.stop(c.AND(sort,c.NOT(c.tag(Tag.SORT)),c.NOT(stable)),Outcome.GAP,Reason.GAP_CONVERSION)
    c.emit(c.AND(sort,c.tag(Tag.SORT)),mode=Mode.ELIM_FIELD_LEVEL,x=a)
    level=at(Mode.ELIM_FIELD_LEVEL);prop=c.tag(CellTag.LEVEL_ZERO);args=c.NOT(c.eq(r['elim_arguments'],0))
    c.emit(c.AND(level,prop),mode=Mode.ELIM_APPEND)
    prepare(c.AND(level,c.NOT(prop),c.NOT(args)),0)
    c.emit(c.AND(level,c.NOT(prop),args),mode=Mode.ELIM_ARGUMENT,x=r['elim_arguments'])
    arg=at(Mode.ELIM_ARGUMENT);match=c.eq(a,r['elim_local']);tail=c.NOT(c.eq(b,0))
    c.emit(c.AND(arg,match),mode=Mode.ELIM_APPEND)
    c.emit(c.AND(arg,c.NOT(match),tail),x=b)
    prepare(c.AND(arg,c.NOT(match),c.NOT(tail)),0)
    append=at(Mode.ELIM_APPEND);room=c.lt(r['ctx'],c.cfg.context)
    c.stop(c.AND(append,c.NOT(room)),Outcome.RESOURCE,Reason.CONTEXT)
    append=c.AND(append,room);more=c.lt(1,r['elim_remaining'])
    c.write('context',append,r['ctx'],(r['elim_record'],))
    c.emit(append,ctx=c.add(r['ctx'],1),elim_remaining=c.sub(r['elim_remaining'],1))
    c.emit(c.AND(append,more),mode=Mode.ELIM_FIELD_CELL,x=r['elim_next'])
    prepare(c.AND(append,c.NOT(more)),1)
    prep=at(Mode.ELIM_PREPARE);large=c.NOT(c.eq(r['elim_large'],0))
    c.emit(prep,ctx=r['header_parameter_end'],count=r['header_parameter_base'],arg_base=0,local_base=r['header_parameter_base'])
    need=c.mux(large,4,1)
    wide=c.g.add(c.g.fit(r['free'],c.width+1),c.g.fit(need,c.width+1))
    room=c.NOT(c.g.lt(c.g.const(c.cfg.heap,c.width+1),wide));ctxroom=c.lt(r['header_parameter_end'],c.cfg.context)
    c.stop(c.AND(prep,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP)
    c.stop(c.AND(prep,room,large,c.NOT(ctxroom)),Outcome.RESOURCE,Reason.CONTEXT)
    c.emit(c.AND(prep,room,c.NOT(large)),core_elim_level=r['kernel_zero'],core_rec_parameters=r['header_parameters'],mode=Mode.ELIM_STORE_METADATA)
    c.emit(c.AND(prep,room,large,ctxroom),mode=Mode.ELIM_PARAMETERS,x=r['header_parameters'])
    params=at(Mode.ELIM_PARAMETERS)
    valid=c.AND(c.eq(n['c'],VectorKind.SYMBOLS),c.eq(a,r['header_parameter_base']),c.eq(word_bool(a),word_bool(b)))
    c.stop(c.AND(params,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(params,valid),elim_old_head=b,elim_fresh=1,elim_cursor=0,mode=Mode.ELIM_FRESH)
    fresh=at(Mode.ELIM_FRESH);within=c.lt(r['elim_cursor'],r['count'])
    match=c.eq(c.read['operand']['value'],r['elim_fresh']);full=c.eq(r['elim_fresh'],(1<<c.width)-1)
    c.emit(c.AND(fresh,c.NOT(within)),mode=Mode.ELIM_SHIFT,elim_cursor=r['ctx'])
    c.stop(c.AND(fresh,within,match,full),Outcome.RESOURCE,Reason.INDEX)
    c.emit(c.AND(fresh,within,match,c.NOT(full)),elim_fresh=c.add(r['elim_fresh'],1),elim_cursor=0)
    c.emit(c.AND(fresh,within,c.NOT(match)),elim_cursor=c.add(r['elim_cursor'],1))
    shift=at(Mode.ELIM_SHIFT);nonzero=c.NOT(c.eq(r['elim_cursor'],0))
    c.write('context',c.AND(shift,nonzero),r['elim_cursor'],(c.read['operand']['value'],))
    c.emit(c.AND(shift,nonzero),elim_cursor=c.sub(r['elim_cursor'],1))
    shift0=c.AND(shift,c.NOT(nonzero));c.write('context',shift0,0,(r['elim_fresh'],))
    c.emit(shift0,ctx=c.add(r['ctx'],1),count=c.add(r['count'],1),header_parameter_base=c.add(r['header_parameter_base'],1),
        header_parameter_end=c.add(r['header_parameter_end'],1),local_base=c.add(r['local_base'],1),mode=Mode.ELIM_STORE_LEVEL)
    level=at(Mode.ELIM_STORE_LEVEL)
    c.write('heap',level,r['free'],(CellTag.LEVEL_PARAM,r['elim_fresh'],0,0))
    c.emit(level,free=c.add(r['free'],1),core_elim_level=r['free'],mode=Mode.ELIM_STORE_CELL)
    cell=at(Mode.ELIM_STORE_CELL)
    c.write('heap',cell,r['free'],(CellTag.VECTOR_CELL,r['elim_fresh'],r['elim_old_head'],0))
    c.emit(cell,free=c.add(r['free'],1),elim_symbol_head=r['free'],mode=Mode.ELIM_STORE_VECTOR)
    vec=at(Mode.ELIM_STORE_VECTOR)
    c.write('heap',vec,r['free'],(CellTag.VECTOR,r['count'],r['elim_symbol_head'],VectorKind.SYMBOLS))
    c.emit(vec,free=c.add(r['free'],1),core_rec_parameters=r['free'],mode=Mode.ELIM_STORE_METADATA)
    meta=at(Mode.ELIM_STORE_METADATA)
    c.write('heap',meta,r['free'],(CellTag.ELIMINATION_INFO,r['core_elim_level'],r['core_rec_parameters'],r['core_K']))
    c.emit(meta,free=c.add(r['free'],1),core_elim_info=r['free'],sp=top);c.ret(meta,r['free'])
