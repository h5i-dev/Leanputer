"""Restored private environment, full rechecks and atomic original publication.

Fixed weighted controller from pinned environment::add_inductive plus explicit
conservative scope/type/RHS/claim rechecks, as in environment.py. Public Γ and
committed origin registry change together only at COMMIT. No CORE ABI admission.
"""
from enum import IntEnum
from .arena import Tag
from .native_cells import CellTag as C, VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


class P(IntEnum):
    INIT=0; RAW_BLOCK=1; FAMILIES=2; FAMILY_CELL=3; FAMILY=4; FAMILY_FOUND=5; FAMILY_SIG=6
    FAMILY_SCHEME=7; FAMILY_META=8; FAMILY_STORE=9; FAMILY_SAVED=10; FAMILY_LIST=11
    CTOR_VECTOR=12; CTOR_CELL=13; CTOR=14; CTOR_FOUND=15; CTOR_SIG=16; CTOR_SCHEME=17
    CTOR_META=18; CTOR_RESTORED=19; CTOR_STORE=20; CTOR_SAVED=21; CTOR_MAP=22; CTOR_NEXT=23
    FAMILY_NEXT=24; FAMILY_ORDERED=25; REC_NAMES_VECTOR=26; REC_NAMES_CELL=27; REC_NAMES_SIG=28
    REC_NAME_BUILT=29; REC_NAME_STORE=30; REC_NAME_NEXT=31; RECS_VECTOR=32; REC_CELL=33
    REC_SIG=34; REC_SCHEME=35; REC_META=36; REC_COUNTS=37; REC_SHARED=38; REC_BLOCK=39
    REC_RENAME=40; REC_TYPE=41; REC_TYPE_DONE=42; OWNER_SIG=43; OWNER_MAP=44
    OWNER_TEMPLATE=45; OWNER_SPINE=46; OWNER_HEAD=47; OWNER_FOUND=48; OWNER_READY=49
    RULE_VECTOR=50; RULE_CELL=51; RULE=52; RULE_DONE=53; RULE_MAP_CELL=54; RULE_MAP=55
    RULE_STORE=56; RULE_LINK=57; RULE_NEXT=58; RULE_ORDERED=59; BLOCK_STORE=60
    SHARED_STORE=61; COUNTS_STORE=62; REC_STORE=63; REC_SAVED=64; REC_LINK=65
    REC_NEXT=66; RECS_ORDERED=67; CHECK_BEGIN=68; CHECK_CELL=69; CHECK_SIG=70
    CHECK_SCHEME=71; CHECK_PARAMS=72; CHECK_SCOPE=73; CHECK_INFER=74; CHECK_SORT=75
    CHECK_RULE_META=76; CHECK_RULE_VECTOR=77; CHECK_RULE_CELL=78; CHECK_RULE=79
    CHECK_RULE_SCOPE=80; CHECK_RULE_INFER=81; CHECK_RULE_NEXT=82; CHECK_NEXT=83
    COMPAT_BEGIN=84; COMPAT=85; COMPAT_SIG=86; COMPAT_PARAMS=87; COMPAT_DONE=88
    CLAIM_PARAMS=89; CLAIMS=90; CHECKED=91; ORIGIN=92; ORIGIN_LINK=93; COMMIT=94
    ENTRY_NAME=95; ENTRY_DUPLICATE=96; ENTRY_UNIQUE=97; ENTRY_SCHEME=98; ENTRY_SIG=99
    ENTRY_LINK=100; ENTRY_FINISH=101; RESULT_VECTOR=102; MAIN_CELL=103; MAIN_FAMILY=104
    CTOR_VECTOR_START=105; REC_NAME_SCAN=106; REC_OWNER_SELECT=107; CHECK_SELECT=108


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.RESTORE_NESTED_BLOCK),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['publish_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,publish_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
        c.write('stack',g,r['sp'],(0,pc,0,Task.RESTORE_NESTED_BLOCK,0,0))
        c.emit(g,sp=c.add(r['sp'],1),task=task,mode=mode,x=x,depth=0,**kw)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
    def shape(g):
        valid=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def entry(g,kind,parameters,type_ref,symbol,payload,nextpc):
        go(g,P.ENTRY_NAME,publish_entry_kind=kind,publish_entry_parameters=parameters,publish_entry_type=type_ref,
            publish_entry_symbol=symbol,publish_entry_payload=payload,publish_entry_return=nextpc)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.RESTORE_NESTED_BLOCK))
    c.emit(returning,sp=top,task=Task.RESTORE_NESTED_BLOCK,mode=Mode.WALK,publish_pc=f['original'],x=r['r'])
    go(at(P.INIT),P.RAW_BLOCK,publish_head=r['env_head'],publish_old_head=r['env_head'],publish_expanded_head=r['typing_head'],
        publish_rec_source=r['core_rec_signatures'],publish_families=0,publish_recs=0,publish_compat=0,
        ctx=0,count=0,arg_base=0,local_base=0,restore_rec_map=0,x=r['stage_original'])
    g=at(P.RAW_BLOCK,C.RAW_BLOCK);go(g,P.FAMILIES,x=n['b'])
    g=shape(at(P.FAMILIES,C.VECTOR));go(g,P.MAIN_CELL,publish_family_remaining=n['a'],publish_family_cursor=n['b'],x=n['b'])
    g=at(P.MAIN_CELL,C.VECTOR_CELL);go(g,P.MAIN_FAMILY,x=n['a'])
    g=at(P.MAIN_FAMILY,C.RAW_FAMILY);go(g,P.FAMILY_CELL,publish_main=n['a'],x=r['publish_family_cursor'])
    g=at(P.FAMILY_CELL,C.VECTOR_CELL);go(g,P.FAMILY,publish_family_next=n['b'],publish_raw_family=n['a'],x=n['a'])
    g=at(P.FAMILY,C.RAW_FAMILY);c.emit(g,publish_family_symbol=n['a'],publish_family_type=n['b'],publish_raw_aux=n['c'])
    call(g,P.FAMILY_FOUND,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=r['publish_expanded_head'])
    go(at(P.FAMILY_FOUND),P.FAMILY_SIG,x=r['r'])
    g=at(P.FAMILY_SIG,C.CHECKED_SIGNATURE);go(g,P.FAMILY_SCHEME,x=n['c'])
    g=at(P.FAMILY_SCHEME,C.CHECKED_SCHEME);go(g,P.FAMILY_META,x=n['c'])
    g=at(P.FAMILY_META,C.CHECKED_FAMILY)
    store(g,(C.CHECKED_FAMILY,n['a'],n['b'],r['publish_raw_family']),P.FAMILY_STORE,publish_payload=r['free'])
    entry(at(P.FAMILY_STORE),8,r['stage_uparams'],r['publish_family_type'],r['publish_family_symbol'],r['publish_payload'],P.FAMILY_SAVED)
    go(at(P.FAMILY_SAVED),P.FAMILY_LIST,publish_current_family=r['publish_entry_signature'])
    store(at(P.FAMILY_LIST),(C.VECTOR_CELL,r['publish_current_family'],r['publish_families'],0),P.CTOR_VECTOR_START,publish_families=r['free'],x=r['publish_raw_aux'])
    g=at(P.CTOR_VECTOR_START,C.RAW_FAMILY_AUX);go(g,P.CTOR_VECTOR,x=n['a'])
    g=shape(at(P.CTOR_VECTOR,C.VECTOR));empty=c.eq(n['a'],0)
    go(c.AND(g,c.NOT(empty)),P.CTOR_CELL,publish_ctor_remaining=n['a'],x=n['b'])
    go(c.AND(g,empty),P.FAMILY_NEXT)
    g=at(P.CTOR_CELL,C.VECTOR_CELL);go(g,P.CTOR,publish_ctor_next=n['b'],x=n['a'])
    g=at(P.CTOR,C.RAW_CONSTRUCTOR);c.emit(g,publish_ctor_symbol=n['a'],publish_original_type=n['b'])
    call(g,P.CTOR_FOUND,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=r['publish_expanded_head'])
    go(at(P.CTOR_FOUND),P.CTOR_SIG,x=r['r'])
    g=at(P.CTOR_SIG,C.CHECKED_SIGNATURE);go(g,P.CTOR_SCHEME,publish_ctor_type=n['b'],x=n['c'])
    g=at(P.CTOR_SCHEME,C.CHECKED_SCHEME);go(g,P.CTOR_META,x=n['c'])
    g=at(P.CTOR_META,C.CHECKED_CONSTRUCTOR);c.emit(g,publish_ctor_fields=n['b'],publish_ctor_ordinal=n['c'])
    call(g,P.CTOR_RESTORED,Task.RESTORE_NESTED_EXPR,r['publish_ctor_type'],restore_expr_pc=0)
    go(at(P.CTOR_RESTORED),P.CTOR_STORE,publish_ctor_type=r['r'])
    store(at(P.CTOR_STORE),(C.CHECKED_CONSTRUCTOR,r['publish_current_family'],r['publish_ctor_fields'],r['publish_ctor_ordinal']),P.CTOR_SAVED,publish_payload=r['free'])
    entry(at(P.CTOR_SAVED),9,r['stage_uparams'],r['publish_ctor_type'],r['publish_ctor_symbol'],r['publish_payload'],P.CTOR_MAP)
    store(at(P.CTOR_MAP),(C.NESTED_TYPE_COMPAT,r['publish_entry_signature'],r['publish_original_type'],r['publish_compat']),P.CTOR_NEXT,publish_compat=r['free'])
    g=at(P.CTOR_NEXT);more=c.lt(1,r['publish_ctor_remaining'])
    go(c.AND(g,more),P.CTOR_CELL,publish_ctor_remaining=c.sub(r['publish_ctor_remaining'],1),x=r['publish_ctor_next'])
    go(c.AND(g,c.NOT(more)),P.FAMILY_NEXT)
    g=at(P.FAMILY_NEXT);more=c.lt(1,r['publish_family_remaining'])
    go(c.AND(g,more),P.FAMILY_CELL,publish_family_remaining=c.sub(r['publish_family_remaining'],1),x=r['publish_family_next'])
    call(c.AND(g,c.NOT(more)),P.FAMILY_ORDERED,Task.REVERSE_LIST,r['publish_families'],reverse_length=r['stage_original_count'])
    go(at(P.FAMILY_ORDERED),P.REC_NAMES_VECTOR,publish_family_vector=r['r'],publish_rec_index=0,x=r['publish_rec_source'])
    g=shape(at(P.REC_NAMES_VECTOR,C.VECTOR));go(g,P.REC_NAMES_CELL,publish_rec_remaining=n['a'],x=n['b'])
    g=at(P.REC_NAMES_CELL,C.VECTOR_CELL);go(g,P.REC_NAMES_SIG,publish_rec_next=n['b'],x=n['a'])
    g=at(P.REC_NAMES_SIG,C.CHECKED_SIGNATURE);aux=c.NOT(c.lt(r['publish_rec_index'],r['stage_original_count']))
    c.emit(g,publish_rec_old_symbol=n['a'])
    go(c.AND(g,c.NOT(aux)),P.REC_NAME_NEXT)
    call(c.AND(g,aux),P.REC_NAME_BUILT,Task.MAKE_RECURSOR_NAME,0,query_symbol=r['publish_main'],generated_rec_indexed=1,generated_rec_index=c.add(c.sub(r['publish_rec_index'],r['stage_original_count']),1))
    go(at(P.REC_NAME_BUILT),P.REC_NAME_STORE,publish_rec_new_symbol=r['r'])
    store(at(P.REC_NAME_STORE),(C.NESTED_REC_MAP,r['publish_rec_old_symbol'],r['publish_rec_new_symbol'],r['restore_rec_map']),P.REC_NAME_NEXT,restore_rec_map=r['free'])
    g=at(P.REC_NAME_NEXT);more=c.lt(1,r['publish_rec_remaining'])
    go(c.AND(g,more),P.REC_NAMES_CELL,publish_rec_remaining=c.sub(r['publish_rec_remaining'],1),publish_rec_index=c.add(r['publish_rec_index'],1),x=r['publish_rec_next'])
    go(c.AND(g,c.NOT(more)),P.RECS_VECTOR,x=r['publish_rec_source'])
    g=shape(at(P.RECS_VECTOR,C.VECTOR));go(g,P.REC_CELL,publish_rec_remaining=n['a'],x=n['b'])
    g=at(P.REC_CELL,C.VECTOR_CELL);go(g,P.REC_SIG,publish_rec_next=n['b'],x=n['a'])
    g=at(P.REC_SIG,C.CHECKED_SIGNATURE);go(g,P.REC_SCHEME,publish_rec_old_symbol=n['a'],publish_rec_new_symbol=n['a'],publish_rec_type=n['b'],x=n['c'])
    g=at(P.REC_SCHEME,C.CHECKED_SCHEME);go(g,P.REC_META,publish_rec_parameters=n['a'],x=n['c'])
    g=at(P.REC_META,C.CHECKED_RECURSOR);go(g,P.REC_COUNTS,publish_rec_owner=n['a'],publish_rec_rules=n['c'],x=n['b'])
    g=at(P.REC_COUNTS,C.RECURSOR_COUNTS);go(g,P.REC_SHARED,publish_nparams=n['a'],publish_nindices=n['b'],x=n['c'])
    g=at(P.REC_SHARED,C.RECURSOR_SHARED_COUNTS);go(g,P.REC_BLOCK,publish_nmotives=n['a'],publish_nminors=n['b'],x=n['c'])
    g=at(P.REC_BLOCK,C.RECURSOR_BLOCK);go(g,P.REC_RENAME,publish_K=n['a'],publish_flags=n['b'],publish_map_cursor=r['restore_rec_map'],x=r['restore_rec_map'])
    g=at(P.REC_RENAME);empty=c.eq(r['publish_map_cursor'],0)
    go(c.AND(g,empty),P.REC_TYPE)
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.NESTED_REC_MAP))
    c.stop(c.AND(g,c.NOT(empty),c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,c.NOT(empty),valid)
    same=c.eq(n['a'],r['publish_rec_old_symbol'])
    go(c.AND(g,same),P.REC_TYPE,publish_rec_new_symbol=n['b'])
    go(c.AND(g,c.NOT(same)),P.REC_RENAME,publish_map_cursor=n['c'],x=n['c'])
    call(at(P.REC_TYPE),P.REC_TYPE_DONE,Task.RESTORE_NESTED_EXPR,r['publish_rec_type'],restore_expr_pc=0)
    go(at(P.REC_TYPE_DONE),P.OWNER_SIG,publish_rec_type=r['r'],x=r['publish_rec_owner'])
    g=at(P.OWNER_SIG,C.CHECKED_SIGNATURE);go(g,P.OWNER_MAP,publish_owner_symbol=n['a'],publish_map_cursor=r['stage_maps'],x=r['stage_maps'])
    g=at(P.OWNER_MAP);empty=c.eq(r['publish_map_cursor'],0)
    call(c.AND(g,empty),P.OWNER_FOUND,Task.ENV_LOOKUP,0,query_symbol=r['publish_owner_symbol'],lookup_head=r['publish_head'])
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.NESTED_SPECIALIZATION))
    c.stop(c.AND(g,c.NOT(empty),c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,c.NOT(empty),valid)
    same=c.eq(n['b'],r['publish_owner_symbol'])
    call(c.AND(g,same),P.OWNER_SPINE,Task.APPLICATION_SPINE,n['a'])
    go(c.AND(g,c.NOT(same)),P.OWNER_MAP,publish_map_cursor=n['c'],x=n['c'])
    go(at(P.OWNER_SPINE),P.OWNER_TEMPLATE,x=r['r'])
    g=at(P.OWNER_TEMPLATE,C.APPLICATION_SPINE);go(g,P.OWNER_HEAD,x=n['a'])
    g=at(P.OWNER_HEAD,Tag.CONST)
    call(g,P.OWNER_FOUND,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=r['publish_old_head'])
    g=at(P.OWNER_FOUND);found=c.NOT(c.eq(r['r'],0));c.stop(c.AND(g,c.NOT(found)),Outcome.INVALID,Reason.SYNTAX)
    go(c.AND(g,found),P.RULE_VECTOR,publish_rec_owner=r['r'],publish_rules=0,publish_rule_count=0,x=r['publish_rec_rules'])
    g=shape(at(P.RULE_VECTOR,C.VECTOR));empty=c.eq(n['a'],0)
    go(c.AND(g,c.NOT(empty)),P.RULE_CELL,publish_rule_remaining=n['a'],x=n['b'])
    call(c.AND(g,empty),P.RULE_ORDERED,Task.REVERSE_LIST,0,reverse_length=0)
    g=at(P.RULE_CELL,C.VECTOR_CELL);go(g,P.RULE,publish_rule_next=n['b'],x=n['a'])
    g=at(P.RULE,C.CHECKED_RULE);c.emit(g,publish_rule_constructor=n['a'],publish_rule_fields=n['b'])
    call(g,P.RULE_DONE,Task.RESTORE_NESTED_EXPR,n['c'],restore_expr_pc=0)
    g=at(P.RULE_DONE);c.emit(g,publish_rule_rhs=r['r'])
    aux=c.NOT(c.eq(r['publish_rec_old_symbol'],r['publish_rec_new_symbol']))
    go(c.AND(g,c.NOT(aux)),P.RULE_STORE)
    go(c.AND(g,aux),P.RULE_MAP_CELL,publish_map_cursor=r['stage_ctor_maps'],x=r['stage_ctor_maps'])
    g=at(P.RULE_MAP_CELL);empty=c.eq(r['publish_map_cursor'],0)
    c.stop(c.AND(g,empty),Outcome.INVALID,Reason.SYNTAX)
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.VECTOR_CELL))
    c.stop(c.AND(g,c.NOT(empty),c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,c.NOT(empty),valid)
    go(g,P.RULE_MAP,publish_map_next=n['b'],x=n['a'])
    g=at(P.RULE_MAP,C.NESTED_CONSTRUCTOR_MAP);same=c.eq(n['a'],r['publish_rule_constructor'])
    go(c.AND(g,same),P.RULE_STORE,publish_rule_constructor=n['b'])
    go(c.AND(g,c.NOT(same)),P.RULE_MAP_CELL,publish_map_cursor=r['publish_map_next'],x=r['publish_map_next'])
    store(at(P.RULE_STORE),(C.CHECKED_RULE,r['publish_rule_constructor'],r['publish_rule_fields'],r['publish_rule_rhs']),P.RULE_LINK,publish_rule=r['free'])
    store(at(P.RULE_LINK),(C.VECTOR_CELL,r['publish_rule'],r['publish_rules'],0),P.RULE_NEXT,publish_rules=r['free'],publish_rule_count=c.add(r['publish_rule_count'],1))
    g=at(P.RULE_NEXT);more=c.lt(1,r['publish_rule_remaining'])
    go(c.AND(g,more),P.RULE_CELL,publish_rule_remaining=c.sub(r['publish_rule_remaining'],1),x=r['publish_rule_next'])
    call(c.AND(g,c.NOT(more)),P.RULE_ORDERED,Task.REVERSE_LIST,r['publish_rules'],reverse_length=r['publish_rule_count'])
    go(at(P.RULE_ORDERED),P.BLOCK_STORE,publish_rule_vector=r['r'])
    store(at(P.BLOCK_STORE),(C.RECURSOR_BLOCK,r['publish_K'],r['publish_flags'],r['publish_family_vector']),P.SHARED_STORE,publish_block=r['free'])
    store(at(P.SHARED_STORE),(C.RECURSOR_SHARED_COUNTS,r['publish_nmotives'],r['publish_nminors'],r['publish_block']),P.COUNTS_STORE,publish_shared=r['free'])
    store(at(P.COUNTS_STORE),(C.RECURSOR_COUNTS,r['publish_nparams'],r['publish_nindices'],r['publish_shared']),P.REC_STORE,publish_counts=r['free'])
    store(at(P.REC_STORE),(C.CHECKED_RECURSOR,r['publish_rec_owner'],r['publish_counts'],r['publish_rule_vector']),P.REC_SAVED,publish_payload=r['free'])
    entry(at(P.REC_SAVED),10,r['publish_rec_parameters'],r['publish_rec_type'],r['publish_rec_new_symbol'],r['publish_payload'],P.REC_LINK)
    store(at(P.REC_LINK),(C.VECTOR_CELL,r['publish_entry_signature'],r['publish_recs'],0),P.REC_NEXT,publish_recs=r['free'])
    g=at(P.REC_NEXT);more=c.lt(1,r['publish_rec_remaining'])
    go(c.AND(g,more),P.REC_CELL,publish_rec_remaining=c.sub(r['publish_rec_remaining'],1),x=r['publish_rec_next'])
    call(c.AND(g,c.NOT(more)),P.RECS_ORDERED,Task.REVERSE_LIST,r['publish_recs'],reverse_length=r['header_seen'])
    go(at(P.RECS_ORDERED),P.CHECK_BEGIN,core_rec_signatures=r['r'],typing_active=1,typing_head=r['publish_head'],publish_check_cursor=r['publish_head'])
    # Every restored signature is scoped and inferred in the complete private overlay.
    g=at(P.CHECK_BEGIN);end=c.eq(r['publish_check_cursor'],r['publish_old_head'])
    go(c.AND(g,end),P.COMPAT_BEGIN,publish_map_cursor=r['publish_compat'])
    go(c.AND(g,c.NOT(end)),P.CHECK_CELL,x=r['publish_check_cursor'])
    g=at(P.CHECK_CELL,C.VECTOR_CELL);go(g,P.CHECK_SIG,publish_check_next=n['b'],x=n['a'])
    g=at(P.CHECK_SIG,C.CHECKED_SIGNATURE);go(g,P.CHECK_SCHEME,publish_check_type=n['b'],x=n['c'])
    g=at(P.CHECK_SCHEME,C.CHECKED_SCHEME);c.emit(g,publish_check_kind=n['b'],publish_check_payload=n['c'])
    call(g,P.CHECK_PARAMS,Task.LOAD_PARAMETERS,n['a'])
    call(at(P.CHECK_PARAMS),P.CHECK_SCOPE,Task.EXPR_SCOPE,r['publish_check_type'])
    call(at(P.CHECK_SCOPE),P.CHECK_INFER,Task.INFER,r['publish_check_type'],local_base=r['ctx'])
    call(at(P.CHECK_INFER),P.CHECK_SORT,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    g=at(P.CHECK_SORT);sort=c.tag(Tag.SORT);valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']))
    c.stop(c.AND(g,c.NOT(c.AND(valid,sort))),Outcome.GAP,Reason.GAP_CONVERSION);g=c.AND(g,valid,sort)
    rec=c.eq(r['publish_check_kind'],10)
    go(c.AND(g,rec),P.CHECK_RULE_META,x=r['publish_check_payload'])
    go(c.AND(g,c.NOT(rec)),P.CHECK_NEXT)
    g=at(P.CHECK_RULE_META,C.CHECKED_RECURSOR);go(g,P.CHECK_RULE_VECTOR,x=n['c'])
    g=shape(at(P.CHECK_RULE_VECTOR,C.VECTOR));empty=c.eq(n['a'],0)
    go(c.AND(g,empty),P.CHECK_NEXT)
    go(c.AND(g,c.NOT(empty)),P.CHECK_RULE_CELL,publish_check_rules=n['a'],x=n['b'])
    g=at(P.CHECK_RULE_CELL,C.VECTOR_CELL);go(g,P.CHECK_RULE,publish_check_rule_next=n['b'],x=n['a'])
    g=at(P.CHECK_RULE,C.CHECKED_RULE);c.emit(g,publish_check_rhs=n['c'])
    call(g,P.CHECK_RULE_SCOPE,Task.EXPR_SCOPE,n['c'])
    call(at(P.CHECK_RULE_SCOPE),P.CHECK_RULE_INFER,Task.INFER,r['publish_check_rhs'],local_base=r['ctx'])
    go(at(P.CHECK_RULE_INFER),P.CHECK_RULE_NEXT)
    g=at(P.CHECK_RULE_NEXT);more=c.lt(1,r['publish_check_rules'])
    go(c.AND(g,more),P.CHECK_RULE_CELL,publish_check_rules=c.sub(r['publish_check_rules'],1),x=r['publish_check_rule_next'])
    go(c.AND(g,c.NOT(more)),P.CHECK_NEXT)
    go(at(P.CHECK_NEXT),P.CHECK_BEGIN,publish_check_cursor=r['publish_check_next'])
    # Compare every restored original constructor type with original input.
    g=at(P.COMPAT_BEGIN);empty=c.eq(r['publish_map_cursor'],0)
    go(c.AND(g,c.NOT(empty)),P.COMPAT,x=r['publish_map_cursor'])
    call(c.AND(g,empty),P.CLAIM_PARAMS,Task.LOAD_PARAMETERS,r['core_rec_parameters'])
    g=at(P.COMPAT,C.NESTED_TYPE_COMPAT);go(g,P.COMPAT_SIG,publish_map_next=n['c'],publish_original_type=n['b'],x=n['a'])
    g=at(P.COMPAT_SIG,C.CHECKED_SIGNATURE);c.emit(g,publish_check_type=n['b'])
    call(g,P.COMPAT_PARAMS,Task.LOAD_PARAMETERS,r['stage_uparams'])
    call(at(P.COMPAT_PARAMS),P.COMPAT_DONE,Task.CONVERT_POSITIVE,r['publish_check_type'],peer=r['publish_original_type'])
    g=at(P.COMPAT_DONE);same=c.NOT(c.eq(r['r'],0));c.stop(c.AND(g,c.NOT(same)),Outcome.INVALID,Reason.TYPE_MISMATCH)
    go(c.AND(g,same),P.COMPAT_BEGIN,publish_map_cursor=r['publish_map_next'])
    call(at(P.CLAIM_PARAMS),P.CLAIMS,Task.CHECK_RECURSOR_CLAIMS,r['stage_original'])
    go(at(P.CLAIMS),P.ORIGIN)
    store(at(P.ORIGIN),(C.BLOCK_ORIGIN,r['stage_original'],r['stage_uparams'],r['publish_family_vector']),P.ORIGIN_LINK,publish_origin=r['free'])
    store(at(P.ORIGIN_LINK),(C.VECTOR_CELL,r['publish_origin'],r['nested_registry_head'],0),P.COMMIT,publish_registry=r['free'])
    g=at(P.COMMIT)
    c.emit(g,env_head=r['publish_head'],nested_registry_head=r['publish_registry'],raw_index=c.add(r['raw_index'],1),decl=c.add(r['decl'],1),
        typing_active=0,typing_head=0,ctx=0,count=0,arg_base=0,local_base=0)
    c.ret(g,1)
    # All new public names are checked against prior Γ and this private overlay.
    call(at(P.ENTRY_NAME),P.ENTRY_DUPLICATE,Task.CHECK_NAME,r['symbols_root'],query_symbol=r['publish_entry_symbol'])
    call(at(P.ENTRY_DUPLICATE),P.ENTRY_UNIQUE,Task.ENV_LOOKUP,0,query_symbol=r['publish_entry_symbol'],lookup_head=r['publish_head'])
    g=at(P.ENTRY_UNIQUE);empty=c.eq(r['r'],0);c.stop(c.AND(g,c.NOT(empty)),Outcome.INVALID,Reason.DUPLICATE_DECLARATION)
    go(c.AND(g,empty),P.ENTRY_SCHEME)
    store(at(P.ENTRY_SCHEME),(C.CHECKED_SCHEME,r['publish_entry_parameters'],r['publish_entry_kind'],r['publish_entry_payload']),P.ENTRY_SIG,publish_entry_scheme=r['free'])
    store(at(P.ENTRY_SIG),(C.CHECKED_SIGNATURE,r['publish_entry_symbol'],r['publish_entry_type'],r['publish_entry_scheme']),P.ENTRY_LINK,publish_entry_signature=r['free'])
    store(at(P.ENTRY_LINK),(C.VECTOR_CELL,r['publish_entry_signature'],r['publish_head'],0),P.ENTRY_FINISH,publish_head=r['free'])
    g=at(P.ENTRY_FINISH);c.emit(g,publish_pc=r['publish_entry_return'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
