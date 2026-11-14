"""Fixed source-defined FIFO staging rules for original inductive blocks.

Pinned inductive.cpp:elim_nested_inductive_fn::operator(). Every source block
uses this growing queue, including blocks that eventually generate no auxiliary.
No checked declaration or publication is produced by staging.
"""
from enum import IntEnum
from .arena import Tag
from .native_cells import CellTag as C, VectorKind as V
from .traversal_machine import Mode, Task, Outcome, Reason


class P(IntEnum):
    INIT=0; PARAMETERS=1; LEVELS=2; VECTOR=3; FIRST_CELL=4; FIRST_FAMILY=5
    OPENED=6; SNAPSHOT=7; RESERVE_CELL=8; RESERVE_FAMILY=9; RESERVE_AUX=10
    RESERVE_FAMILY_NAME=11; RESERVE_REC_NAME=12; RESERVE_CTOR_VECTOR=13
    RESERVE_CTOR_CELL=14; RESERVE_CTOR=15; RESERVE_CTOR_NAME=16
    POP=17; REFILL=18; REFILL_VECTOR=19; FAMILY_CELL=20; FAMILY=21; AUX=22
    CTOR_VECTOR=23; CTOR_CELL=24; CTOR=25; OPEN_CTOR=26; REWRITTEN=27; FOLDED=28
    CTOR_RECORD=29; CTOR_LINK=30; CTOR_ORDERED=31; STORE_AUX=32; STORE_FAMILY=33
    DONE_LINK=34; FINAL_VECTOR=35; FINAL_BLOCK=36; FINISH=37; ALL_VECTOR=38; READ_VECTOR=39; REFILL_START=40; CTOR_DONE=41


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame']; top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.NESTED_STAGE),c.mode(Mode.WALK))
    def at(pc, tag=None):
        g=c.AND(active,c.eq(r['stage_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
        return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,stage_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
        c.write('stack',g,r['sp'],(0,pc,0,Task.NESTED_STAGE,0,0))
        c.emit(g,sp=c.add(r['sp'],1),task=task,mode=mode,x=x,depth=0,**kw)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
    def vector(g,valid):
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
        return c.AND(g,valid)
    shape=lambda:c.AND(c.eq(n['c'],V.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    ret=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.NESTED_STAGE))
    c.emit(ret,sp=top,task=Task.NESTED_STAGE,mode=Mode.WALK,stage_pc=f['original'],x=r['r'])
    g=at(P.INIT,C.RAW_BLOCK)
    go(g,P.PARAMETERS,stage_original=r['x'],stage_parameter_count=n['a'],stage_original_claims=n['c'],stage_original_vector=n['b'],
        stage_saved_ctx=r['ctx'],stage_saved_count=r['count'],stage_saved_arg_base=r['arg_base'],
        stage_front=0,stage_back=0,stage_back_count=0,stage_all=0,stage_all_count=0,stage_done=0,stage_done_count=0,
        stage_reserved=0,stage_fresh_counter=0,stage_maps=0,stage_ctor_maps=0,x=n['b'])
    # Validate universe scheme and derive its formal levels with existing services.
    call(at(P.PARAMETERS),P.LEVELS,Task.LOAD_PARAMETERS,r['stage_uparams'])
    call(at(P.LEVELS),P.VECTOR,Task.FORMAL_LEVELS,0)
    go(at(P.VECTOR),P.READ_VECTOR,stage_levels=r['r'],x=r['stage_original_vector'])
    g=at(P.READ_VECTOR,C.VECTOR);g=vector(g,c.AND(shape(),c.NOT(c.eq(n['a'],0))))
    go(g,P.FIRST_CELL,stage_original_count=n['a'],stage_front_count=n['a'],stage_front=n['b'],
        stage_reserve_cursor=n['b'],stage_reserve_remaining=n['a'],stage_original_vector=r['x'],x=n['b'])
    g=at(P.FIRST_CELL,C.VECTOR_CELL);go(g,P.FIRST_FAMILY,x=n['a'])
    g=at(P.FIRST_FAMILY,C.RAW_FAMILY)
    call(g,P.OPENED,Task.OPEN_RAW_PREFIX,n['b'],raw_prefix_count=r['stage_parameter_count'],open_tag=Tag.PI)
    c.emit(g,stage_parameters_base=r['ctx'],local_base=r['ctx'])
    call(at(P.OPENED),P.SNAPSHOT,Task.SNAPSHOT_SCOPE,0,abstract_base=r['stage_parameters_base'],abstract_end=r['ctx'])
    g=at(P.SNAPSHOT);go(g,P.RESERVE_CELL,stage_param_snapshot=r['r'],ctx=r['stage_parameters_base'],x=r['stage_reserve_cursor'])
    g=at(P.RESERVE_CELL,C.VECTOR_CELL)
    g=vector(g,c.AND(c.NOT(c.eq(r['stage_reserve_remaining'],0)),c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r['stage_reserve_remaining']),1,0))))
    go(g,P.RESERVE_FAMILY,stage_reserve_next=n['b'],x=n['a'])
    g=at(P.RESERVE_FAMILY,C.RAW_FAMILY);go(g,P.RESERVE_FAMILY_NAME,stage_reserve_symbol=n['a'],stage_reserve_aux=n['c'])
    store(at(P.RESERVE_FAMILY_NAME),(C.VECTOR_CELL,r['stage_reserve_symbol'],r['stage_reserved'],0),P.RESERVE_AUX,stage_reserved=r['free'],x=r['stage_reserve_aux'])
    g=at(P.RESERVE_AUX,C.RAW_FAMILY_AUX);go(g,P.RESERVE_REC_NAME,stage_reserve_symbol=n['b'],stage_reserve_ctor_vector=n['a'])
    store(at(P.RESERVE_REC_NAME),(C.VECTOR_CELL,r['stage_reserve_symbol'],r['stage_reserved'],0),P.RESERVE_CTOR_VECTOR,stage_reserved=r['free'],x=r['stage_reserve_ctor_vector'])
    g=at(P.RESERVE_CTOR_VECTOR,C.VECTOR);g=vector(g,shape())
    go(c.AND(g,c.NOT(c.eq(n['a'],0))),P.RESERVE_CTOR_CELL,stage_reserve_ctor_remaining=n['a'],x=n['b'])
    def next_reserved(g):
        more=c.lt(1,r['stage_reserve_remaining'])
        go(c.AND(g,more),P.RESERVE_CELL,stage_reserve_remaining=c.sub(r['stage_reserve_remaining'],1),x=r['stage_reserve_next'])
        go(c.AND(g,c.NOT(more)),P.ALL_VECTOR,x=r['stage_original_vector'])
    next_reserved(c.AND(g,c.eq(n['a'],0)))
    g=at(P.RESERVE_CTOR_CELL,C.VECTOR_CELL)
    g=vector(g,c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r['stage_reserve_ctor_remaining']),1,0)))
    go(g,P.RESERVE_CTOR,stage_reserve_ctor_next=n['b'],x=n['a'])
    g=at(P.RESERVE_CTOR,C.RAW_CONSTRUCTOR);go(g,P.RESERVE_CTOR_NAME,stage_reserve_symbol=n['a'])
    g=at(P.RESERVE_CTOR_NAME);room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
    c.write('heap',g,r['free'],(C.VECTOR_CELL,r['stage_reserve_symbol'],r['stage_reserved'],0))
    c.emit(g,stage_reserved=r['free'],free=c.add(r['free'],1))
    more=c.lt(1,r['stage_reserve_ctor_remaining'])
    go(c.AND(g,more),P.RESERVE_CTOR_CELL,stage_reserve_ctor_remaining=c.sub(r['stage_reserve_ctor_remaining'],1),x=r['stage_reserve_ctor_next'])
    next_reserved(c.AND(g,c.NOT(more)))
    # The immutable initial vector is shared by FIFO and all-family occurrence data.
    g=at(P.ALL_VECTOR,C.VECTOR)
    go(g,P.POP,stage_all=n['b'],stage_all_count=n['a'],raw_family_vector=r['x'])
    g=at(P.POP);empty=c.eq(r['stage_front_count'],0);back=c.eq(r['stage_back_count'],0)
    go(c.AND(g,c.NOT(empty)),P.FAMILY_CELL,x=r['stage_front'])
    go(c.AND(g,empty,c.NOT(back)),P.REFILL_START)
    call(c.AND(g,empty,back),P.FINAL_VECTOR,Task.REVERSE_LIST,r['stage_done'],reverse_length=r['stage_done_count'])
    call(at(P.REFILL_START),P.REFILL_VECTOR,Task.REVERSE_LIST,r['stage_back'],reverse_length=r['stage_back_count'])
    g=at(P.REFILL_VECTOR,C.VECTOR)
    go(g,P.FAMILY_CELL,stage_front=n['b'],stage_front_count=n['a'],stage_back=0,stage_back_count=0,x=n['b'])
    g=at(P.FAMILY_CELL,C.VECTOR_CELL)
    g=vector(g,c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r['stage_front_count']),1,0)))
    go(g,P.FAMILY,stage_front=n['b'],stage_front_count=c.sub(r['stage_front_count'],1),stage_family=n['a'],x=n['a'])
    g=at(P.FAMILY,C.RAW_FAMILY);go(g,P.AUX,stage_symbol=n['a'],stage_type=n['b'],stage_aux=n['c'],x=n['c'])
    g=at(P.AUX,C.RAW_FAMILY_AUX);go(g,P.CTOR_VECTOR,stage_rec=n['b'],stage_ctors=0,stage_ctor_count=0,x=n['a'])
    g=at(P.CTOR_VECTOR,C.VECTOR);g=vector(g,shape())
    go(c.AND(g,c.NOT(c.eq(n['a'],0))),P.CTOR_CELL,stage_ctor_remaining=n['a'],x=n['b'])
    call(c.AND(g,c.eq(n['a'],0)),P.CTOR_ORDERED,Task.REVERSE_LIST,0,reverse_length=0)
    g=at(P.CTOR_CELL,C.VECTOR_CELL)
    g=vector(g,c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r['stage_ctor_remaining']),1,0)))
    go(g,P.CTOR,stage_ctor_next=n['b'],x=n['a'])
    g=at(P.CTOR,C.RAW_CONSTRUCTOR)
    c.emit(g,stage_ctor_symbol=n['a'],stage_ctor_type=n['b'],stage_parameters_base=r['ctx'])
    call(g,P.OPEN_CTOR,Task.OPEN_RAW_PREFIX,n['b'],raw_prefix_count=r['stage_parameter_count'],open_tag=Tag.PI)
    g=at(P.OPEN_CTOR)
    c.emit(g,stage_parameters_end=r['ctx'])
    call(g,P.REWRITTEN,Task.REWRITE_NESTED,r['r'],rewrite_pc=0)
    call(at(P.REWRITTEN),P.FOLDED,Task.FOLD_TELESCOPE,r['r'],Mode.FOLD_SELECT,
        fold_body=r['r'],fold_base=r['stage_parameters_base'],fold_tag=Tag.PI)
    go(at(P.FOLDED),P.CTOR_RECORD,stage_ctor_type=r['r'])
    store(at(P.CTOR_RECORD),(C.RAW_CONSTRUCTOR,r['stage_ctor_symbol'],r['stage_ctor_type'],0),P.CTOR_LINK,stage_ctor_record=r['free'])
    store(at(P.CTOR_LINK),(C.VECTOR_CELL,r['stage_ctor_record'],r['stage_ctors'],0),P.CTOR_DONE,
        stage_ctors=r['free'],stage_ctor_count=c.add(r['stage_ctor_count'],1))
    g=at(P.CTOR_DONE);more=c.lt(1,r['stage_ctor_remaining'])
    go(c.AND(g,more),P.CTOR_CELL,stage_ctor_remaining=c.sub(r['stage_ctor_remaining'],1),x=r['stage_ctor_next'])
    call(c.AND(g,c.NOT(more)),P.CTOR_ORDERED,Task.REVERSE_LIST,r['stage_ctors'],reverse_length=r['stage_ctor_count'])
    go(at(P.CTOR_ORDERED),P.STORE_AUX,stage_ctor_vector=r['r'])
    store(at(P.STORE_AUX),(C.RAW_FAMILY_AUX,r['stage_ctor_vector'],r['stage_rec'],0),P.STORE_FAMILY,stage_new_aux=r['free'])
    store(at(P.STORE_FAMILY),(C.RAW_FAMILY,r['stage_symbol'],r['stage_type'],r['stage_new_aux']),P.DONE_LINK,stage_new_family=r['free'])
    store(at(P.DONE_LINK),(C.VECTOR_CELL,r['stage_new_family'],r['stage_done'],0),P.POP,
        stage_done=r['free'],stage_done_count=c.add(r['stage_done_count'],1))
    go(at(P.FINAL_VECTOR),P.FINAL_BLOCK,stage_final_vector=r['r'])
    store(at(P.FINAL_BLOCK),(C.RAW_BLOCK,r['stage_parameter_count'],r['stage_final_vector'],r['stage_original_claims']),P.FINISH,stage_expanded=r['free'])
    g=at(P.FINISH)
    c.emit(g,ctx=r['stage_saved_ctx'],count=r['stage_saved_count'],arg_base=r['stage_saved_arg_base'],local_base=r['stage_saved_ctx'])
    c.ret(g,r['stage_expanded'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
