"""Weighted pinned quot.cpp initialization and quot.h reduction controllers.

Raw interface names/types are claims. Only atomic initialization from checked
Eq authorizes the four genuine quotient primitives. Fixed syntax is constructed
inside the weighted machine; no loader supplies signatures or init flags.
"""
from enum import IntEnum
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason
from .quotient_templates import Ref,name_syntax,interface_syntax


class P(IntEnum):
    INIT=0; EQ_LOOKUP=1; EQ_SIG=2; EQ_SCHEME=3; EQ_PARAMS=4; EQ_PARAM=5
    FAMILY=6; FAMILY_INFO=7; FAMILY_RAW=8; FAMILY_AUX=9; CTORS=10; CTOR_CELL=11; CTOR_RAW=12
    REFL_FOUND=13; REFL_SIG=14; REFL_SCHEME=15; REFL_PARAMS=16; REFL_PARAM=17
    BUILD=18; EQ_COMPARE=19; EQ_COMPARED=20; REFL_COMPARED=21
    OVERLAY=22; CLAIM=23; PARAMETERS=24; SCOPE=25; FORMALS=26; SPECIALIZED=27
    INFERRED=28; SORT=29; CONVERTED=30; COMMIT=31


NAMES=[('eq',('Eq',)),('quot',('Quot',)),('mk',('Quot','mk')),('lift',('Quot','lift')),
       ('ind',('Quot','ind')),('u',('u',)),('v',('v',))]


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.QUOT_INITIALIZE),c.mode(Mode.WALK))
    if c.width < 10:
        # This controller's fixed program counter must fit the physical word.
        # Never truncate distinct control states into overlapping instructions.
        c.stop(active,Outcome.RESOURCE,Reason.INDEX)
        return
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['quot_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.INVALID_DECLARATION);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,quot_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
        c.write('stack',g,r['sp'],(0,pc,0,Task.QUOT_INITIALIZE,0,0))
        c.emit(g,sp=c.add(r['sp'],1),task=task,mode=mode,x=x,depth=0,**kw)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.QUOT_INITIALIZE))
    c.emit(returning,sp=top,task=Task.QUOT_INITIALIZE,mode=Mode.WALK,quot_pc=f['original'],x=r['r'])
    def check(g,valid,reason=Reason.INVALID_DECLARATION):
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,reason);return c.AND(g,valid)
    def pointer(ref,base):return c.add(r[base],ref.index) if isinstance(ref,Ref) else r[ref] if isinstance(ref,str) else ref
    # The finite primitive names are built byte by byte and content-interned.
    g=at(P.INIT);initialized=c.NOT(c.eq(r['quot_initialized'],0))
    go(c.AND(g,initialized),P.CLAIM,quot_head=r['env_head'],quot_new=0)
    go(c.AND(g,c.NOT(initialized)),100,quot_new=0)
    for index,(key,parts) in enumerate(NAMES):
        start=100+index*40;s,path=name_syntax(parts)
        go(at(start),start+1,quot_build_base=r['free'])
        for i,row in enumerate(s.rows):
            store(at(start+1+i),tuple(pointer(x,'quot_build_base') for x in row),start+2+i)
        call(at(start+1+len(s.rows)),start+2+len(s.rows),Task.INTERN_NAME_PATH,pointer(path,'quot_build_base'))
        go(at(start+2+len(s.rows)),start+40 if index+1<len(NAMES) else P.EQ_LOOKUP,**{'quot_symbol_'+key:r['r']})
    call(at(P.EQ_LOOKUP),P.EQ_SIG,Task.ENV_LOOKUP,0,query_symbol=r['quot_symbol_eq'],lookup_head=r['env_head'])
    g=at(P.EQ_SIG,C.CHECKED_SIGNATURE);go(g,P.EQ_SCHEME,quot_eq_signature=r['x'],quot_eq_type=n['b'],x=n['c'])
    g=check(at(P.EQ_SCHEME,C.CHECKED_SCHEME),c.eq(n['b'],8));go(g,P.EQ_PARAMS,x=n['a'])
    g=check(at(P.EQ_PARAMS,C.VECTOR),c.AND(c.eq(n['a'],1),c.eq(n['c'],V.SYMBOLS)));go(g,P.EQ_PARAM,x=n['b'])
    g=check(at(P.EQ_PARAM,C.VECTOR_CELL),c.eq(n['b'],0));c.emit(g,quot_eq_u=n['a'])
    call(g,P.FAMILY,Task.FAMILY_INFO,r['quot_eq_signature'],family_info_pc=0)
    go(at(P.FAMILY),P.FAMILY_INFO,x=r['r'])
    g=at(P.FAMILY_INFO,C.PROJECTION_FAMILY_INFO);go(g,P.FAMILY_RAW,x=n['c'])
    g=at(P.FAMILY_RAW,C.RAW_FAMILY);go(g,P.FAMILY_AUX,x=n['c'])
    g=at(P.FAMILY_AUX,C.RAW_FAMILY_AUX);go(g,P.CTORS,x=n['a'])
    g=check(at(P.CTORS,C.VECTOR),c.AND(c.eq(n['a'],1),c.eq(n['c'],V.REFERENCES)));go(g,P.CTOR_CELL,x=n['b'])
    g=at(P.CTOR_CELL,C.VECTOR_CELL);go(g,P.CTOR_RAW,x=n['a'])
    g=at(P.CTOR_RAW,C.RAW_CONSTRUCTOR);call(g,P.REFL_FOUND,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=r['env_head'])
    go(at(P.REFL_FOUND),P.REFL_SIG,x=r['r'])
    g=at(P.REFL_SIG,C.CHECKED_SIGNATURE);go(g,P.REFL_SCHEME,quot_refl_type=n['b'],x=n['c'])
    g=check(at(P.REFL_SCHEME,C.CHECKED_SCHEME),c.eq(n['b'],9));go(g,P.REFL_PARAMS,x=n['a'])
    g=check(at(P.REFL_PARAMS,C.VECTOR),c.AND(c.eq(n['a'],1),c.eq(n['c'],V.SYMBOLS)));go(g,P.REFL_PARAM,x=n['b'])
    g=check(at(P.REFL_PARAM,C.VECTOR_CELL),c.eq(n['b'],0));go(g,P.BUILD,quot_refl_u=n['a'])
    s,types,params,lift_params=interface_syntax()
    go(at(P.BUILD),400,quot_data_base=r['free'])
    for i,row in enumerate(s.rows):store(at(400+i),tuple(pointer(x,'quot_data_base') for x in row),401+i)
    g=at(400+len(s.rows))
    go(g,P.EQ_COMPARE,quot_parameters=pointer(params,'quot_data_base'),quot_lift_parameters=pointer(lift_params,'quot_data_base'),
       **{'quot_'+key:pointer(ref,'quot_data_base') for key,ref in types.items()})
    call(at(P.EQ_COMPARE),P.EQ_COMPARED,Task.EXPR_EQUAL,r['quot_eq'],peer=r['quot_eq_type'])
    g=check(at(P.EQ_COMPARED),c.NOT(c.eq(r['r'],0)))
    call(g,P.REFL_COMPARED,Task.EXPR_EQUAL,r['quot_refl'],peer=r['quot_refl_type'])
    g=check(at(P.REFL_COMPARED),c.NOT(c.eq(r['r'],0)));go(g,P.OVERLAY,quot_head=r['env_head'])
    go(at(P.OVERLAY),600,nat_validated=0,nat_type_validated=0,bool_validated=0,string_validated=0,string_type_validated=0)
    for index,(key,name) in enumerate([('type','quot'),('ctor','mk'),('lift','lift'),('ind','ind')]):
        pc=600+index*6
        call(at(pc),pc+1,Task.ENV_LOOKUP,0,query_symbol=r['quot_symbol_'+name],lookup_head=r['env_head'])
        existing=at(pc+1);fresh=c.eq(r['r'],0)
        # add_core replaces only these map entries. The current checked
        # signature determines its kind; original-block records are historical
        # provenance, never permission to reuse a shadowed family/constructor.
        go(existing,pc+2,quot_new=c.add(r['quot_new'],c.mux(fresh,1,0)))
        store(at(pc+2),(C.CHECKED_SCHEME,r['quot_lift_parameters'] if key=='lift' else r['quot_parameters'],11,index+1),pc+3,quot_scheme=r['free'])
        store(at(pc+3),(C.CHECKED_SIGNATURE,r['quot_symbol_'+name],r['quot_'+key],r['quot_scheme']),pc+4,quot_signature=r['free'])
        store(at(pc+4),(C.VECTOR_CELL,r['quot_signature'],r['quot_head'],0),pc+5,quot_head=r['free'])
        go(at(pc+5),pc+6 if index<3 else P.CLAIM)
    g=at(P.CLAIM)
    valid=c.OR(*(c.AND(c.eq(r['quot_claim_kind'],i+1),c.eq(r['quot_claim_symbol'],r['quot_symbol_'+name])) for i,name in enumerate(('quot','mk','lift','ind'))))
    g=check(g,valid)
    ty=r['quot_ind']
    for i,key in reversed(list(enumerate(('type','ctor','lift')))):ty=c.mux(c.eq(r['quot_claim_kind'],i+1),r['quot_'+key],ty)
    c.emit(g,quot_expected=ty,typing_active=1,typing_head=r['quot_head'])
    call(g,P.PARAMETERS,Task.LOAD_PARAMETERS,r['quot_claim_parameters'])
    g=check(at(P.PARAMETERS),c.eq(r['count'],c.mux(c.eq(r['quot_claim_kind'],3),2,1)),Reason.UNIVERSE_ARITY)
    call(g,P.SCOPE,Task.EXPR_SCOPE,r['quot_claim_type'])
    call(at(P.SCOPE),P.FORMALS,Task.FORMAL_LEVELS,0)
    call(at(P.FORMALS),P.SPECIALIZED,Task.INSTANTIATE_SCHEME,r['quot_expected'],
        parameter_vector=c.mux(c.eq(r['quot_claim_kind'],3),r['quot_lift_parameters'],r['quot_parameters']),level_vector=r['r'])
    g=at(P.SPECIALIZED);c.emit(g,quot_expected=r['r'])
    call(g,P.INFERRED,Task.INFER,r['quot_claim_type'],local_base=r['ctx'])
    call(at(P.INFERRED),P.SORT,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    g=check(at(P.SORT),c.tag(Tag.SORT),Reason.EXPECT_SORT)
    call(g,P.CONVERTED,Task.CONVERT_POSITIVE,r['quot_claim_type'],peer=r['quot_expected'])
    g=check(at(P.CONVERTED),c.NOT(c.eq(r['r'],0)),Reason.TYPE_MISMATCH);go(g,P.COMMIT)
    g=at(P.COMMIT)
    c.emit(g,env_head=r['quot_head'],typing_active=0,typing_head=0,quot_initialized=1,
        published_declarations=c.add(r['published_declarations'],r['quot_new']),raw_index=c.add(r['raw_index'],1),decl=c.add(r['decl'],1),ctx=0,count=0,arg_base=0,local_base=0)
    c.ret(g,1)


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
