"""Compile all constructors/fields/functional IHs into generated minor types."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_MINOR_OWN_MOTIVE,
    CALL_MINOR_RESULT_INDICES,CALL_MINOR_PARAMETERS,CALL_MINOR_FIELDS,CALL_MINOR_PREFIX,
    CALL_MINOR_IH_MOTIVE,CALL_MINOR_IH_INDICES,CALL_MINOR_FUNCTION,CALL_MINOR_IH_FOLD,
    CALL_MINOR_IH_LOCAL,CALL_MINOR_FOLD,CALL_MINOR_LOCAL,CALL_MINOR_VECTOR,CALL_MINOR_RESTORE)

PRIVATE_PHASES=tuple(range(CALL_MINOR_OWN_MOTIVE,CALL_MINOR_VECTOR+1))+(CALL_MINOR_RESTORE,)
NO_NODE=(Mode.WALK,Mode.MINOR_CONSTANT,Mode.MINOR_RESULT,Mode.MINOR_IH_RESULT,Mode.MINOR_STORE,Mode.MINOR_LINK)
TAGS={Mode.MINOR_VECTOR:CellTag.VECTOR,Mode.MINOR_CELL:CellTag.VECTOR_CELL,
    Mode.MINOR_PENDING:CellTag.PENDING_CONSTRUCTOR,Mode.MINOR_ANALYSIS:CellTag.CONSTRUCTOR_ANALYSIS,
    Mode.MINOR_IH_VECTOR:CellTag.VECTOR,Mode.MINOR_IH_CELL:CellTag.VECTOR_CELL,
    Mode.MINOR_IH_FIELD:CellTag.CONSTRUCTOR_FIELD,Mode.MINOR_IH_LOCAL:CellTag.LOCAL_DECL,
    Mode.MINOR_OPENED:CellTag.OPENED_RECURSIVE_PREFIX,Mode.MINOR_IH_INDICES:CellTag.VECTOR}


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)))
    phase=lambda p:c.AND(returning,c.eq(f['phase'],p))
    def call(guard,p,task,x,mode=Mode.WALK,**updates):
        c.write('stack',guard,top,(p,0,0,Task.BUILD_MINORS,0,0))
        c.emit(guard,task=task,mode=mode,x=x,depth=0,**updates)
    def fold(guard):call(guard,CALL_MINOR_FOLD,Task.FOLD_TELESCOPE,r['minor_result_type'],Mode.FOLD_SELECT,
        fold_base=r['minor_mark'],fold_body=r['minor_result_type'],fold_tag=Tag.PI)
    def own_motive(guard):call(guard,CALL_MINOR_OWN_MOTIVE,Task.FIND_MOTIVE,r['core_motives'],motive_query=r['minor_family'])
    def next_ih(guard):
        more=c.lt(1,r['minor_ih_remaining'])
        c.emit(guard,minor_ih_remaining=c.sub(r['minor_ih_remaining'],1))
        c.emit(c.AND(guard,more),task=Task.BUILD_MINORS,mode=Mode.MINOR_IH_CELL,x=r['minor_ih_next'])
        fold(c.AND(guard,c.NOT(more)))
    restored=phase(CALL_MINOR_RESTORE);c.emit(restored,minor_field_count=r['restore_length'],minor_fields_end=r['ctx'])
    own_motive(restored)
    call(phase(CALL_MINOR_OWN_MOTIVE),CALL_MINOR_RESULT_INDICES,Task.APPLY_LIST,r['r'],list_head=r['minor_result_args'],list_skip=r['header_parameter_count'])
    c.emit(phase(CALL_MINOR_RESULT_INDICES),task=Task.BUILD_MINORS,minor_result_fn=r['r'],mode=Mode.MINOR_CONSTANT)
    call(phase(CALL_MINOR_PARAMETERS),CALL_MINOR_FIELDS,Task.APPLY_SCOPE,r['r'],apply_base=r['minor_mark'],apply_end=r['minor_fields_end'])
    c.emit(phase(CALL_MINOR_FIELDS),task=Task.BUILD_MINORS,mode=Mode.MINOR_RESULT)
    c.emit(phase(CALL_MINOR_PREFIX),task=Task.BUILD_MINORS,mode=Mode.MINOR_OPENED,x=r['r'])
    c.emit(phase(CALL_MINOR_IH_MOTIVE),task=Task.BUILD_MINORS,minor_ih_motive=r['r'],mode=Mode.MINOR_IH_INDICES,x=r['minor_index_vector'])
    ih_indices=phase(CALL_MINOR_IH_INDICES);c.emit(ih_indices,minor_ih_target=r['r'])
    call(ih_indices,CALL_MINOR_FUNCTION,Task.APPLY_SCOPE,r['minor_recursive_local'],apply_base=r['minor_ih_mark'],apply_end=r['ctx'])
    c.emit(phase(CALL_MINOR_FUNCTION),task=Task.BUILD_MINORS,mode=Mode.MINOR_IH_RESULT)
    call(phase(CALL_MINOR_IH_FOLD),CALL_MINOR_IH_LOCAL,Task.FRESH_LOCAL,r['r'],binder_info=0)
    next_ih(phase(CALL_MINOR_IH_LOCAL))
    call(phase(CALL_MINOR_FOLD),CALL_MINOR_LOCAL,Task.FRESH_LOCAL,r['r'],binder_info=0)
    c.emit(phase(CALL_MINOR_LOCAL),task=Task.BUILD_MINORS,minor_local=r['fresh_record'],mode=Mode.MINOR_STORE)
    vector=phase(CALL_MINOR_VECTOR);c.emit(vector,task=Task.BUILD_MINORS,core_minors=r['r'],sp=top);c.ret(vector,r['r'])
    active=c.task(Task.BUILD_MINORS);at=lambda m:c.AND(active,c.mode(m))
    def room(guard,size=1):
        wide=c.g.add(c.g.fit(r['free'],c.width+1),c.g.const(size,c.width+1))
        fits=c.NOT(c.g.lt(c.g.const(c.cfg.heap,c.width+1),wide))
        c.stop(c.AND(guard,c.NOT(fits)),Outcome.RESOURCE,Reason.HEAP)
        return c.AND(guard,fits)
    init=at(Mode.WALK)
    wide=c.g.add(c.g.fit(r['header_parameter_end'],c.width+1),c.g.fit(r['header_seen'],c.width+1))
    valid=c.AND(c.NOT(c.eq(r['core_motives'],0)),c.NOT(c.eq(r['core_constructors'],0)),c.g.eq(c.g.fit(r['ctx'],c.width+1),wide))
    stackroom=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.stop(c.AND(init,valid,c.NOT(stackroom)),Outcome.RESOURCE,Reason.STACK)
    init=c.AND(init,valid,stackroom)
    c.write('stack',init,r['sp'],(CALL_MINOR_VECTOR,0,0,Task.BUILD_MINORS,0,0))
    c.emit(init,sp=c.add(r['sp'],1),minor_rev=0,mode=Mode.MINOR_VECTOR,x=r['core_constructors'])
    vector_shape=lambda:c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    vector=at(Mode.MINOR_VECTOR);valid=c.AND(vector_shape(),c.eq(n['a'],r['core_ctor_declared']))
    c.stop(c.AND(vector,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    call(c.AND(vector,valid,c.eq(n['a'],0)),CALL_MINOR_VECTOR,Task.REVERSE_LIST,0,reverse_length=0)
    c.emit(c.AND(vector,valid,c.NOT(c.eq(n['a'],0))),minor_remaining=n['a'],mode=Mode.MINOR_CELL,x=n['b'])
    def cell_guard(mode,remaining):
        cell=at(mode);valid=c.AND(c.NOT(c.eq(r[remaining],0)),
            c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r[remaining]),1,0)))
        c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
        return c.AND(cell,valid)
    c.emit(cell_guard(Mode.MINOR_CELL,'minor_remaining'),minor_next=n['b'],minor_pending=n['a'],mode=Mode.MINOR_PENDING,x=n['a'],minor_mark=r['ctx'])
    c.emit(at(Mode.MINOR_PENDING),minor_symbol=n['a'],mode=Mode.MINOR_ANALYSIS,x=n['c'])
    analysis=at(Mode.MINOR_ANALYSIS);c.emit(analysis,minor_family=n['a'],minor_fields=n['b'],minor_result_args=n['c'])
    call(analysis,CALL_MINOR_RESTORE,Task.RESTORE_SCOPE,n['b'])
    const=room(at(Mode.MINOR_CONSTANT));c.write('heap',const,r['free'],(Tag.CONST,r['minor_symbol'],r['header_levels'],0));c.emit(const,free=c.add(r['free'],1))
    call(const,CALL_MINOR_PARAMETERS,Task.APPLY_SCOPE,r['free'],apply_base=r['header_parameter_base'],apply_end=r['header_parameter_end'])
    result=room(at(Mode.MINOR_RESULT));c.write('heap',result,r['free'],(Tag.APP,r['minor_result_fn'],r['r'],0))
    c.emit(result,free=c.add(r['free'],1),minor_result_type=r['free'],mode=Mode.MINOR_IH_VECTOR,x=r['minor_fields'])
    vector=at(Mode.MINOR_IH_VECTOR);valid=c.AND(vector_shape(),c.eq(n['a'],r['minor_field_count']))
    c.stop(c.AND(vector,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    fold(c.AND(vector,valid,c.eq(n['a'],0)))
    c.emit(c.AND(vector,valid,c.NOT(c.eq(n['a'],0))),minor_ih_remaining=n['a'],mode=Mode.MINOR_IH_CELL,x=n['b'])
    c.emit(cell_guard(Mode.MINOR_IH_CELL,'minor_ih_remaining'),minor_ih_next=n['b'],mode=Mode.MINOR_IH_FIELD,x=n['a'])
    field=at(Mode.MINOR_IH_FIELD);recursive=c.NOT(c.eq(n['b'],0))
    next_ih(c.AND(field,c.NOT(recursive)))
    c.emit(c.AND(field,recursive),minor_descriptor=n['b'],mode=Mode.MINOR_IH_LOCAL,x=n['a'])
    local=at(Mode.MINOR_IH_LOCAL);c.emit(local,minor_recursive_local=n['a'],minor_ih_mark=r['ctx'])
    call(local,CALL_MINOR_PREFIX,Task.OPEN_RECURSIVE_PREFIX,r['minor_descriptor'])
    opened=at(Mode.MINOR_OPENED);c.emit(opened,minor_index_vector=n['c'])
    call(opened,CALL_MINOR_IH_MOTIVE,Task.FIND_MOTIVE,r['core_motives'],motive_query=n['a'])
    indices=at(Mode.MINOR_IH_INDICES);valid=vector_shape()
    c.stop(c.AND(indices,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    call(c.AND(indices,valid),CALL_MINOR_IH_INDICES,Task.APPLY_LIST,r['minor_ih_motive'],list_head=n['b'],list_skip=0)
    result=room(at(Mode.MINOR_IH_RESULT));c.write('heap',result,r['free'],(Tag.APP,r['minor_ih_target'],r['r'],0));c.emit(result,free=c.add(r['free'],1))
    call(result,CALL_MINOR_IH_FOLD,Task.FOLD_TELESCOPE,r['free'],Mode.FOLD_SELECT,fold_base=r['minor_ih_mark'],fold_body=r['free'],fold_tag=Tag.PI)
    store=room(at(Mode.MINOR_STORE),2)
    c.write('heap',store,r['free'],(CellTag.MINOR_INFO,r['minor_pending'],r['minor_local'],r['minor_field_count']))
    c.emit(store,free=c.add(r['free'],1),minor_info=r['free'],mode=Mode.MINOR_LINK)
    link=at(Mode.MINOR_LINK);more=c.lt(1,r['minor_remaining'])
    c.write('heap',link,r['free'],(CellTag.VECTOR_CELL,r['minor_info'],r['minor_rev'],0))
    c.emit(link,free=c.add(r['free'],1),minor_rev=r['free'],minor_remaining=c.sub(r['minor_remaining'],1))
    c.emit(c.AND(link,more),mode=Mode.MINOR_CELL,x=r['minor_next'])
    call(c.AND(link,c.NOT(more)),CALL_MINOR_VECTOR,Task.REVERSE_LIST,r['free'],reverse_length=r['core_ctor_declared'])
