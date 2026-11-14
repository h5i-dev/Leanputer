"""Nested callback: structural maps, universe/parameter specialization, mutual copy.

This is a fixed kernel state machine compiled into Boolean rules. Expressions,
names, parameter counts and prior mutual-block members are runtime data.
Authority: pinned inductive.cpp:replace_if_nested/instantiate_pi_params.
"""
from enum import IntEnum
from .arena import Tag
from .native_cells import CellTag as C, VectorKind as V
from .traversal_machine import Mode, Task, Outcome, Reason


class P(IntEnum):
    INIT=0; CONDITION=1; NESTED=2; ORIGIN=3; BLOCK=4; SPINE=5; FUNCTION=6; ARGUMENTS=7
    KEY_APPLIED=8; KEY_ABSTRACTED=9; LOOKUP=10; LOOKUP_COMPARE=11; NEW_VECTOR=12
    FAMILY_CELL=13; FAMILY=14; FAMILY_AUX=15; NAME_START=16; NAME_CANDIDATE=17
    NAME_REC=18; NAME_CHECK=19; NAME_ENV=20; NAME_MEMBER=21; NAME_RESERVE=22; NAME_RESERVE_REC=23
    TEMPLATE_CONST=24; TEMPLATE_APPLIED=25; TEMPLATE_ABSTRACTED=26; TEMPLATE_STORE=27
    TYPE_UNIVERSES=28; TYPE_PARAMETERS=29; TYPE_FOLDED=30; CTOR_VECTOR=31
    CTOR_CELL=32; CTOR=33; CTOR_RENAMED=34; CTOR_UNIVERSES=35; CTOR_PARAMETERS=36
    CTOR_FOLDED=37; CTOR_RECORD=38; CTOR_LINK=39; CTOR_MAP=40; CTOR_MAP_LINK=41
    CTOR_RESERVED=42; CTOR_NEXT=43; CTOR_ORDERED=44; AUX_RECORD=45; FAMILY_RECORD=46
    ENQUEUE=47; ALL_LINK=48; ALL_VECTOR=49; NEXT_FAMILY=50
    RESULT_CONST=51; RESULT_PARAMETERS=52; RESULT_ARGUMENTS=53; FINISH=54
    FAMILY_VECTOR=55; FOUND=56; CTOR_BEGIN=57


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame']; top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.REPLACE_NESTED),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['copy_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
        return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,copy_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
        c.write('stack',g,r['sp'],(0,pc,0,Task.REPLACE_NESTED,0,0))
        c.emit(g,sp=c.add(r['sp'],1),task=task,mode=mode,x=x,depth=0,**kw)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
    def shape(g,kind):
        valid=c.AND(c.eq(n['c'],kind),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    ret=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.REPLACE_NESTED))
    c.emit(ret,sp=top,task=Task.REPLACE_NESTED,mode=Mode.WALK,copy_pc=f['original'],x=r['r'])
    g=at(P.INIT);c.emit(g,copy_application=r['x'])
    call(g,P.CONDITION,Task.IS_NESTED_APPLICATION,r['x'])
    g=at(P.CONDITION);empty=c.eq(r['r'],0)
    c.ret(c.AND(g,empty),0);go(c.AND(g,c.NOT(empty)),P.NESTED,x=r['r'])
    g=at(P.NESTED,C.NESTED_APPLICATION);go(g,P.ORIGIN,copy_origin=n['a'],copy_spine=n['b'],x=n['a'])
    g=at(P.ORIGIN,C.BLOCK_ORIGIN);go(g,P.BLOCK,copy_uparams=n['b'],x=n['a'])
    g=at(P.BLOCK,C.RAW_BLOCK);go(g,P.SPINE,copy_parameter_count=n['a'],copy_original_vector=n['b'],x=r['copy_spine'])
    g=at(P.SPINE,C.APPLICATION_SPINE);go(g,P.FUNCTION,copy_function=n['a'],copy_arguments=n['b'],x=n['a'])
    g=at(P.FUNCTION,Tag.CONST);go(g,P.ARGUMENTS,copy_owner=n['a'],copy_levels=n['b'],x=r['copy_arguments'])
    g=shape(at(P.ARGUMENTS,C.VECTOR),V.REFERENCES)
    c.emit(g,copy_argument_count=n['a'])
    call(g,P.KEY_APPLIED,Task.APPLY_VECTOR_SLICE,r['copy_arguments'],slice_body=r['copy_function'],slice_start=0,slice_take=r['copy_parameter_count'])
    call(at(P.KEY_APPLIED),P.KEY_ABSTRACTED,Task.ABSTRACT_SCOPE,r['r'],abstract_base=r['stage_parameters_base'],abstract_end=r['stage_parameters_end'])
    g=at(P.KEY_ABSTRACTED);go(g,P.LOOKUP,copy_key=r['r'],copy_lookup=r['stage_maps'],copy_selected=0,x=r['stage_maps'])
    g=at(P.LOOKUP);empty=c.eq(r['copy_lookup'],0)
    go(c.AND(g,empty),P.FAMILY_VECTOR,x=r['copy_original_vector'])
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.NESTED_SPECIALIZATION))
    c.stop(c.AND(g,c.NOT(empty),c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    g=c.AND(g,c.NOT(empty),valid)
    c.emit(g,copy_lookup_next=n['c'],copy_lookup_aux=n['b'])
    call(g,P.LOOKUP_COMPARE,Task.EXPR_EQUAL,r['copy_key'],peer=n['a'])
    g=at(P.LOOKUP_COMPARE);same=c.NOT(c.eq(r['r'],0))
    go(c.AND(g,same),P.RESULT_CONST,copy_selected=r['copy_lookup_aux'])
    go(c.AND(g,c.NOT(same)),P.LOOKUP,copy_lookup=r['copy_lookup_next'],x=r['copy_lookup_next'])
    g=shape(at(P.FAMILY_VECTOR,C.VECTOR),V.REFERENCES);empty=c.eq(n['a'],0)
    c.stop(c.AND(g,empty),Outcome.INVALID,Reason.INVALID_DECLARATION)
    go(c.AND(g,c.NOT(empty)),P.FAMILY_CELL,copy_family_remaining=n['a'],x=n['b'])
    g=at(P.FAMILY_CELL,C.VECTOR_CELL)
    valid=c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r['copy_family_remaining']),1,0))
    c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,valid)
    go(g,P.FAMILY,copy_family_next=n['b'],x=n['a'])
    g=at(P.FAMILY,C.RAW_FAMILY);go(g,P.FAMILY_AUX,copy_original_symbol=n['a'],copy_family_type=n['b'],copy_family_aux=n['c'],x=n['c'])
    g=at(P.FAMILY_AUX,C.RAW_FAMILY_AUX);go(g,P.NAME_START,copy_original_ctor_vector=n['a'])
    # Private names may alpha-rename. The shared name builder uses arbitrary
    # original paths plus a counted suffix, with actual Γ/reserved freshness.
    g,next_index=c.checked_add(at(P.NAME_START),r['stage_fresh_counter'],1)
    c.emit(g,stage_fresh_counter=next_index)
    call(g,P.NAME_CANDIDATE,Task.MAKE_RECURSOR_NAME,0,query_symbol=r['copy_original_symbol'],generated_rec_indexed=1,generated_rec_index=next_index)
    g=at(P.NAME_CANDIDATE);c.emit(g,copy_name_candidate=r['r'])
    call(g,P.NAME_REC,Task.MAKE_RECURSOR_NAME,0,query_symbol=r['r'],generated_rec_indexed=0,generated_rec_index=0)
    go(at(P.NAME_REC),P.NAME_CHECK,copy_name_rec=r['r'],copy_name_pass=0,copy_name_query=r['copy_name_candidate'])
    call(at(P.NAME_CHECK),P.NAME_ENV,Task.ENV_LOOKUP,0,query_symbol=r['copy_name_query'],lookup_head=r['env_head'])
    g=at(P.NAME_ENV);found=c.NOT(c.eq(r['r'],0))
    go(c.AND(g,found),P.NAME_START)
    call(c.AND(g,c.NOT(found)),P.NAME_MEMBER,Task.SYMBOL_MEMBER,r['stage_reserved'],query_symbol=r['copy_name_query'])
    g=at(P.NAME_MEMBER);found=c.NOT(c.eq(r['r'],0));second=c.NOT(c.eq(r['copy_name_pass'],0))
    go(c.AND(g,found),P.NAME_START)
    go(c.AND(g,c.NOT(found),c.NOT(second)),P.NAME_CHECK,copy_name_pass=1,copy_name_query=r['copy_name_rec'])
    go(c.AND(g,c.NOT(found),second),P.NAME_RESERVE,copy_aux_symbol=r['copy_name_candidate'],copy_rec_symbol=r['copy_name_rec'])
    store(at(P.NAME_RESERVE),(C.VECTOR_CELL,r['copy_aux_symbol'],r['stage_reserved'],0),P.NAME_RESERVE_REC,stage_reserved=r['free'])
    store(at(P.NAME_RESERVE_REC),(C.VECTOR_CELL,r['copy_rec_symbol'],r['stage_reserved'],0),P.TEMPLATE_CONST,stage_reserved=r['free'])
    # Register each mutual member's structural template BEFORE its copied
    # constructors are enqueued. No type/conversion result supplies map identity.
    store(at(P.TEMPLATE_CONST),(Tag.CONST,r['copy_original_symbol'],r['copy_levels'],0),P.NEW_VECTOR,copy_template_head=r['free'])
    call(at(P.NEW_VECTOR),P.TEMPLATE_APPLIED,Task.APPLY_VECTOR_SLICE,r['copy_arguments'],slice_body=r['copy_template_head'],slice_start=0,slice_take=r['copy_parameter_count'])
    call(at(P.TEMPLATE_APPLIED),P.TEMPLATE_ABSTRACTED,Task.ABSTRACT_SCOPE,r['r'],abstract_base=r['stage_parameters_base'],abstract_end=r['stage_parameters_end'])
    go(at(P.TEMPLATE_ABSTRACTED),P.TEMPLATE_STORE,copy_template=r['r'])
    store(at(P.TEMPLATE_STORE),(C.NESTED_SPECIALIZATION,r['copy_template'],r['copy_aux_symbol'],r['stage_maps']),P.TYPE_UNIVERSES,
        stage_maps=r['free'],copy_template_record=r['free'],copy_selected=c.mux(c.eq(r['copy_original_symbol'],r['copy_owner']),r['copy_aux_symbol'],r['copy_selected']))
    call(at(P.TYPE_UNIVERSES),P.TYPE_PARAMETERS,Task.INSTANTIATE_SCHEME,r['copy_family_type'],parameter_vector=r['copy_uparams'],level_vector=r['copy_levels'])
    call(at(P.TYPE_PARAMETERS),P.TYPE_FOLDED,Task.INSTANTIATE_PI_PARAMETERS,r['r'],pi_parameter_vector=r['copy_arguments'],pi_parameter_limit=r['copy_parameter_count'])
    call(at(P.TYPE_FOLDED),P.CTOR_BEGIN,Task.FOLD_TELESCOPE,r['r'],Mode.FOLD_SELECT,fold_body=r['r'],fold_base=r['stage_parameters_base'],fold_tag=Tag.PI)
    go(at(P.CTOR_BEGIN),P.CTOR_VECTOR,copy_fold_type=r['r'],ctx=r['stage_parameters_end'],copy_ctors=0,copy_ctor_count=0,x=r['copy_original_ctor_vector'])
    g=shape(at(P.CTOR_VECTOR,C.VECTOR),V.REFERENCES);empty=c.eq(n['a'],0)
    go(c.AND(g,c.NOT(empty)),P.CTOR_CELL,copy_ctor_remaining=n['a'],x=n['b'])
    call(c.AND(g,empty),P.CTOR_ORDERED,Task.REVERSE_LIST,0,reverse_length=0)
    g=at(P.CTOR_CELL,C.VECTOR_CELL)
    valid=c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r['copy_ctor_remaining']),1,0))
    c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,valid)
    go(g,P.CTOR,copy_ctor_next=n['b'],x=n['a'])
    g=at(P.CTOR,C.RAW_CONSTRUCTOR);c.emit(g,copy_ctor_symbol=n['a'],copy_ctor_type=n['b'])
    call(g,P.CTOR_RENAMED,Task.REPLACE_NAME_PREFIX,0,query_symbol=n['a'],name_parent_symbol=r['copy_original_symbol'],name_candidate_symbol=r['copy_aux_symbol'])
    g=at(P.CTOR_RENAMED);c.emit(g,copy_ctor_new_symbol=r['r'])
    call(g,P.CTOR_UNIVERSES,Task.INSTANTIATE_SCHEME,r['copy_ctor_type'],parameter_vector=r['copy_uparams'],level_vector=r['copy_levels'])
    call(at(P.CTOR_UNIVERSES),P.CTOR_PARAMETERS,Task.INSTANTIATE_PI_PARAMETERS,r['r'],pi_parameter_vector=r['copy_arguments'],pi_parameter_limit=r['copy_parameter_count'])
    call(at(P.CTOR_PARAMETERS),P.CTOR_FOLDED,Task.FOLD_TELESCOPE,r['r'],Mode.FOLD_SELECT,fold_body=r['r'],fold_base=r['stage_parameters_base'],fold_tag=Tag.PI)
    go(at(P.CTOR_FOLDED),P.CTOR_RECORD,copy_ctor_type=r['r'],ctx=r['stage_parameters_end'])
    store(at(P.CTOR_RECORD),(C.RAW_CONSTRUCTOR,r['copy_ctor_new_symbol'],r['copy_ctor_type'],0),P.CTOR_LINK,copy_ctor_record=r['free'])
    store(at(P.CTOR_LINK),(C.VECTOR_CELL,r['copy_ctor_record'],r['copy_ctors'],0),P.CTOR_MAP,copy_ctors=r['free'],copy_ctor_count=c.add(r['copy_ctor_count'],1))
    store(at(P.CTOR_MAP),(C.NESTED_CONSTRUCTOR_MAP,r['copy_ctor_new_symbol'],r['copy_ctor_symbol'],r['copy_template_record']),P.CTOR_MAP_LINK,copy_ctor_map_record=r['free'])
    store(at(P.CTOR_MAP_LINK),(C.VECTOR_CELL,r['copy_ctor_map_record'],r['stage_ctor_maps'],0),P.CTOR_RESERVED,stage_ctor_maps=r['free'])
    store(at(P.CTOR_RESERVED),(C.VECTOR_CELL,r['copy_ctor_new_symbol'],r['stage_reserved'],0),P.CTOR_NEXT,stage_reserved=r['free'])
    g=at(P.CTOR_NEXT);more=c.lt(1,r['copy_ctor_remaining'])
    go(c.AND(g,more),P.CTOR_CELL,copy_ctor_remaining=c.sub(r['copy_ctor_remaining'],1),x=r['copy_ctor_next'])
    call(c.AND(g,c.NOT(more)),P.CTOR_ORDERED,Task.REVERSE_LIST,r['copy_ctors'],reverse_length=r['copy_ctor_count'])
    go(at(P.CTOR_ORDERED),P.AUX_RECORD,copy_ctor_vector=r['r'])
    store(at(P.AUX_RECORD),(C.RAW_FAMILY_AUX,r['copy_ctor_vector'],r['copy_rec_symbol'],0),P.FAMILY_RECORD,copy_new_aux=r['free'])
    store(at(P.FAMILY_RECORD),(C.RAW_FAMILY,r['copy_aux_symbol'],r['copy_fold_type'],r['copy_new_aux']),P.ENQUEUE,copy_new_family=r['free'])
    store(at(P.ENQUEUE),(C.VECTOR_CELL,r['copy_new_family'],r['stage_back'],0),P.ALL_LINK,
        stage_back=r['free'],stage_back_count=c.add(r['stage_back_count'],1))
    store(at(P.ALL_LINK),(C.VECTOR_CELL,r['copy_new_family'],r['stage_all'],0),P.ALL_VECTOR,
        stage_all=r['free'],stage_all_count=c.add(r['stage_all_count'],1))
    store(at(P.ALL_VECTOR),(C.VECTOR,r['stage_all_count'],r['stage_all'],V.REFERENCES),P.NEXT_FAMILY,raw_family_vector=r['free'])
    g=at(P.NEXT_FAMILY);more=c.lt(1,r['copy_family_remaining'])
    go(c.AND(g,more),P.FAMILY_CELL,copy_family_remaining=c.sub(r['copy_family_remaining'],1),x=r['copy_family_next'])
    go(c.AND(g,c.NOT(more)),P.RESULT_CONST)
    g=at(P.RESULT_CONST);missing=c.eq(r['copy_selected'],0)
    c.stop(c.AND(g,missing),Outcome.INVALID,Reason.SYNTAX)
    store(c.AND(g,c.NOT(missing)),(Tag.CONST,r['copy_selected'],r['stage_levels'],0),P.FOUND,copy_result=r['free'])
    call(at(P.FOUND),P.RESULT_PARAMETERS,Task.APPLY_SCOPE,r['copy_result'],apply_base=r['stage_parameters_base'],apply_end=r['stage_parameters_end'])
    call(at(P.RESULT_PARAMETERS),P.RESULT_ARGUMENTS,Task.APPLY_VECTOR_SLICE,r['copy_arguments'],slice_body=r['r'],slice_start=r['copy_parameter_count'],slice_take=c.sub(r['copy_argument_count'],r['copy_parameter_count']))
    c.ret(at(P.RESULT_ARGUMENTS),r['r'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
