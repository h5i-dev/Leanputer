"""Compile generic closed computation rules using shared prefix/scope services."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_RULE_LEVELS,CALL_RULE_RESTORE,
    CALL_RULE_MINOR_APPLY,CALL_RULE_PREFIX,CALL_RULE_FAMILY,CALL_RULE_PARAMETERS,
    CALL_RULE_MOTIVES,CALL_RULE_MINORS,CALL_RULE_INDICES,CALL_RULE_FUNCTION,
    CALL_RULE_IH_FOLD,CALL_RULE_FINAL_FOLD,CALL_RULE_SCOPE,CALL_RULE_VECTOR)

PRIVATE_PHASES=tuple(range(CALL_RULE_LEVELS,CALL_RULE_VECTOR+1))
NO_NODE=(Mode.WALK,Mode.RULE_CONSTANT,Mode.RULE_IH_BODY,Mode.RULE_APPEND_IH,
    Mode.RULE_STORE,Mode.RULE_STORE_FAMILY,Mode.RULE_LINK)
TAGS={Mode.RULE_VECTOR:CellTag.VECTOR,Mode.RULE_CELL:CellTag.VECTOR_CELL,
    Mode.RULE_INFO:CellTag.MINOR_INFO,Mode.RULE_PENDING:CellTag.PENDING_CONSTRUCTOR,
    Mode.RULE_ANALYSIS:CellTag.CONSTRUCTOR_ANALYSIS,Mode.RULE_MINOR_RECORD:CellTag.LOCAL_DECL,
    Mode.RULE_FIELD_VECTOR:CellTag.VECTOR,Mode.RULE_FIELD_CELL:CellTag.VECTOR_CELL,
    Mode.RULE_FIELD:CellTag.CONSTRUCTOR_FIELD,Mode.RULE_LOCAL:CellTag.LOCAL_DECL,
    Mode.RULE_OPENED:CellTag.OPENED_RECURSIVE_PREFIX,Mode.RULE_FAMILY_INFO:CellTag.MOTIVE_INFO,
    Mode.RULE_TELESCOPE:CellTag.MOTIVE_TELESCOPE,Mode.RULE_INDEX_VECTOR:CellTag.VECTOR}


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)))
    phase=lambda p:c.AND(returning,c.eq(f['phase'],p))
    def call(guard,p,task,x,mode=Mode.WALK,**updates):
        c.write('stack',guard,top,(p,0,0,Task.BUILD_RECURSOR_RULES,0,0))
        c.emit(guard,task=task,mode=mode,x=x,depth=0,**updates)
    def fold(guard,body):call(guard,CALL_RULE_FINAL_FOLD,Task.FOLD_TELESCOPE,body,Mode.FOLD_SELECT,
        fold_base=r['header_parameter_base'],fold_body=body,fold_tag=Tag.LAM)
    def next_field(guard,body):
        more=c.lt(1,r['rule_field_remaining']);c.emit(guard,rule_field_remaining=c.sub(r['rule_field_remaining'],1))
        c.emit(c.AND(guard,more),mode=Mode.RULE_FIELD_CELL,x=r['rule_field_next'])
        fold(c.AND(guard,c.NOT(more)),body)
    c.emit(phase(CALL_RULE_LEVELS),task=Task.BUILD_RECURSOR_RULES,core_rec_levels=r['r'],mode=Mode.RULE_VECTOR,x=r['core_minors'])
    restored=phase(CALL_RULE_RESTORE);valid=c.eq(r['restore_length'],r['rule_field_count'])
    c.stop(c.AND(restored,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(restored,valid),task=Task.BUILD_RECURSOR_RULES,rule_fields_end=r['ctx'],mode=Mode.RULE_MINOR_RECORD,x=r['rule_minor_record'])
    c.emit(phase(CALL_RULE_MINOR_APPLY),task=Task.BUILD_RECURSOR_RULES,rule_result=r['r'],mode=Mode.RULE_FIELD_VECTOR,x=r['rule_fields'])
    c.emit(phase(CALL_RULE_PREFIX),task=Task.BUILD_RECURSOR_RULES,mode=Mode.RULE_OPENED,x=r['r'])
    c.emit(phase(CALL_RULE_FAMILY),task=Task.BUILD_RECURSOR_RULES,mode=Mode.RULE_FAMILY_INFO,x=r['motive_lookup_info'])
    call(phase(CALL_RULE_PARAMETERS),CALL_RULE_MOTIVES,Task.APPLY_SCOPE,r['r'],apply_base=r['header_parameter_end'],apply_end=c.add(r['header_parameter_end'],r['header_seen']))
    call(phase(CALL_RULE_MOTIVES),CALL_RULE_MINORS,Task.APPLY_SCOPE,r['r'],apply_base=c.add(r['header_parameter_end'],r['header_seen']),apply_end=r['rule_mark'])
    c.emit(phase(CALL_RULE_MINORS),task=Task.BUILD_RECURSOR_RULES,rule_recursive_fn=r['r'],mode=Mode.RULE_INDEX_VECTOR,x=r['rule_index_vector'])
    indices=phase(CALL_RULE_INDICES);c.emit(indices,rule_ih_target=r['r'])
    call(indices,CALL_RULE_FUNCTION,Task.APPLY_SCOPE,r['rule_recursive_local'],apply_base=r['rule_ih_mark'],apply_end=r['ctx'])
    c.emit(phase(CALL_RULE_FUNCTION),task=Task.BUILD_RECURSOR_RULES,mode=Mode.RULE_IH_BODY)
    c.emit(phase(CALL_RULE_IH_FOLD),task=Task.BUILD_RECURSOR_RULES,mode=Mode.RULE_APPEND_IH)
    final=phase(CALL_RULE_FINAL_FOLD);c.emit(final,rule_closed=r['r']);call(final,CALL_RULE_SCOPE,Task.EXPR_SCOPE,r['r'])
    c.emit(phase(CALL_RULE_SCOPE),task=Task.BUILD_RECURSOR_RULES,ctx=r['rule_mark'],mode=Mode.RULE_STORE)
    done=phase(CALL_RULE_VECTOR);c.emit(done,task=Task.BUILD_RECURSOR_RULES,core_rules=r['r'],sp=top);c.ret(done,r['r'])
    active=c.task(Task.BUILD_RECURSOR_RULES);at=lambda m:c.AND(active,c.mode(m))
    def room(guard,size=1):
        wide=c.g.add(c.g.fit(r['free'],c.width+1),c.g.const(size,c.width+1));fits=c.NOT(c.g.lt(c.g.const(c.cfg.heap,c.width+1),wide))
        c.stop(c.AND(guard,c.NOT(fits)),Outcome.RESOURCE,Reason.HEAP)
        return c.AND(guard,fits)
    init=at(Mode.WALK)
    wide=c.g.add(c.g.fit(r['header_parameter_end'],c.width+2),c.g.fit(r['header_seen'],c.width+2));wide=c.g.add(wide,c.g.fit(r['core_ctor_declared'],c.width+2))
    valid=c.AND(c.NOT(c.eq(r['core_rec_types'],0)),c.NOT(c.eq(r['core_minors'],0)),c.g.eq(c.g.fit(r['ctx'],c.width+2),wide));stackroom=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.stop(c.AND(init,valid,c.NOT(stackroom)),Outcome.RESOURCE,Reason.STACK);init=c.AND(init,valid,stackroom)
    c.write('stack',init,r['sp'],(CALL_RULE_LEVELS,0,0,Task.BUILD_RECURSOR_RULES,0,0))
    c.emit(init,sp=c.add(r['sp'],1),rule_mark=r['ctx'],rule_rev=0,task=Task.FORMAL_LEVELS,mode=Mode.WALK,x=0)
    shape=lambda:c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    vector=at(Mode.RULE_VECTOR);valid=c.AND(shape(),c.eq(n['a'],r['core_ctor_declared']))
    c.stop(c.AND(vector,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    call(c.AND(vector,valid,c.eq(n['a'],0)),CALL_RULE_VECTOR,Task.REVERSE_LIST,0,reverse_length=0)
    c.emit(c.AND(vector,valid,c.NOT(c.eq(n['a'],0))),rule_remaining=n['a'],mode=Mode.RULE_CELL,x=n['b'])
    def cell_guard(mode,remaining):
        cell=at(mode);valid=c.AND(c.NOT(c.eq(r[remaining],0)),c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r[remaining]),1,0)))
        c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
        return c.AND(cell,valid)
    c.emit(cell_guard(Mode.RULE_CELL,'rule_remaining'),rule_next=n['b'],mode=Mode.RULE_INFO,x=n['a'])
    c.emit(at(Mode.RULE_INFO),rule_minor_record=n['b'],rule_field_count=n['c'],mode=Mode.RULE_PENDING,x=n['a'])
    c.emit(at(Mode.RULE_PENDING),rule_symbol=n['a'],mode=Mode.RULE_ANALYSIS,x=n['c'])
    analysis=at(Mode.RULE_ANALYSIS);c.emit(analysis,rule_family=n['a'],rule_fields=n['b'])
    call(analysis,CALL_RULE_RESTORE,Task.RESTORE_SCOPE,n['b'])
    call(at(Mode.RULE_MINOR_RECORD),CALL_RULE_MINOR_APPLY,Task.APPLY_SCOPE,n['a'],apply_base=r['rule_mark'],apply_end=r['rule_fields_end'])
    vector=at(Mode.RULE_FIELD_VECTOR);valid=c.AND(shape(),c.eq(n['a'],r['rule_field_count']))
    c.stop(c.AND(vector,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    fold(c.AND(vector,valid,c.eq(n['a'],0)),r['rule_result'])
    c.emit(c.AND(vector,valid,c.NOT(c.eq(n['a'],0))),rule_field_remaining=n['a'],mode=Mode.RULE_FIELD_CELL,x=n['b'])
    c.emit(cell_guard(Mode.RULE_FIELD_CELL,'rule_field_remaining'),rule_field_next=n['b'],mode=Mode.RULE_FIELD,x=n['a'])
    field=at(Mode.RULE_FIELD);recursive=c.NOT(c.eq(n['b'],0));next_field(c.AND(field,c.NOT(recursive)),r['rule_result'])
    c.emit(c.AND(field,recursive),rule_descriptor=n['b'],mode=Mode.RULE_LOCAL,x=n['a'])
    local=at(Mode.RULE_LOCAL);c.emit(local,rule_recursive_local=n['a'],rule_ih_mark=r['ctx'])
    call(local,CALL_RULE_PREFIX,Task.OPEN_RECURSIVE_PREFIX,r['rule_descriptor'])
    opened=at(Mode.RULE_OPENED);c.emit(opened,rule_index_vector=n['c'])
    call(opened,CALL_RULE_FAMILY,Task.FIND_MOTIVE,r['core_motives'],motive_query=n['a'])
    c.emit(at(Mode.RULE_FAMILY_INFO),mode=Mode.RULE_TELESCOPE,x=n['c'])
    c.emit(at(Mode.RULE_TELESCOPE),rule_recursive_symbol=n['c'],mode=Mode.RULE_CONSTANT)
    const=room(at(Mode.RULE_CONSTANT));c.write('heap',const,r['free'],(Tag.CONST,r['rule_recursive_symbol'],r['core_rec_levels'],0));c.emit(const,free=c.add(r['free'],1))
    call(const,CALL_RULE_PARAMETERS,Task.APPLY_SCOPE,r['free'],apply_base=r['header_parameter_base'],apply_end=r['header_parameter_end'])
    vector=at(Mode.RULE_INDEX_VECTOR);valid=shape();c.stop(c.AND(vector,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    call(c.AND(vector,valid),CALL_RULE_INDICES,Task.APPLY_LIST,r['rule_recursive_fn'],list_head=n['b'],list_skip=0)
    body=room(at(Mode.RULE_IH_BODY));c.write('heap',body,r['free'],(Tag.APP,r['rule_ih_target'],r['r'],0));c.emit(body,free=c.add(r['free'],1))
    call(body,CALL_RULE_IH_FOLD,Task.FOLD_TELESCOPE,r['free'],Mode.FOLD_SELECT,fold_base=r['rule_ih_mark'],fold_body=r['free'],fold_tag=Tag.LAM)
    append=room(at(Mode.RULE_APPEND_IH));c.write('heap',append,r['free'],(Tag.APP,r['rule_result'],r['r'],0));c.emit(append,free=c.add(r['free'],1),rule_result=r['free']);next_field(append,r['free'])
    store=room(at(Mode.RULE_STORE),3);c.write('heap',store,r['free'],(CellTag.CHECKED_RULE,r['rule_symbol'],r['rule_field_count'],r['rule_closed']))
    c.emit(store,free=c.add(r['free'],1),rule_info=r['free'],mode=Mode.RULE_STORE_FAMILY)
    family=at(Mode.RULE_STORE_FAMILY);c.write('heap',family,r['free'],(CellTag.FAMILY_RULE,r['rule_family'],r['rule_info'],0))
    c.emit(family,free=c.add(r['free'],1),rule_family_info=r['free'],mode=Mode.RULE_LINK)
    link=at(Mode.RULE_LINK);more=c.lt(1,r['rule_remaining']);c.write('heap',link,r['free'],(CellTag.VECTOR_CELL,r['rule_family_info'],r['rule_rev'],0))
    c.emit(link,free=c.add(r['free'],1),rule_rev=r['free'],rule_remaining=c.sub(r['rule_remaining'],1))
    c.emit(c.AND(link,more),mode=Mode.RULE_CELL,x=r['rule_next'])
    call(c.AND(link,c.NOT(more)),CALL_RULE_VECTOR,Task.REVERSE_LIST,r['free'],reverse_length=r['core_ctor_declared'])
