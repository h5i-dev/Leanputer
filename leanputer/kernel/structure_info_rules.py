"""Checked is_non_rec_structure/count query for general conversion.

Pinned inductive.cpp:27. Counts/flags are derived from checked family,
constructor and recursor records, never loader-supplied structure annotations.
"""
from enum import IntEnum
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


class P(IntEnum):
    INIT=0; SCHEME=1; INFO=2; FAMILY_INFO=3; FAMILY=4; AUX=5; VECTOR=6
    CTOR_CELL=7; CTOR_RAW=8; CTOR_FOUND=9; CTOR_SIG=10; CTOR_SCHEME=11
    CTOR_META=12; FIELDS=13; REC_LOOKUP=14; REC_FOUND=15; REC_SIG=16; REC_SCHEME=17
    REC_META=18; REC_COUNTS=19; REC_SHARED=20; REC_BLOCK=21; FLAGS=22; DETAIL=23; RESULT=24


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.STRUCTURE_INFO),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['structure_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.GAP,Reason.GAP_CONVERSION);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,structure_pc=pc,**kw)
    def call(g,pc,task,x,**kw):
        room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
        c.write('stack',g,r['sp'],(0,pc,0,Task.STRUCTURE_INFO,0,0))
        c.emit(g,sp=c.add(r['sp'],1),task=task,mode=Mode.WALK,x=x,depth=0,**kw)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.STRUCTURE_INFO))
    c.emit(returning,sp=top,task=Task.STRUCTURE_INFO,mode=Mode.WALK,structure_pc=f['original'],x=r['r'])
    g=at(P.INIT,C.CHECKED_SIGNATURE);go(g,P.SCHEME,structure_signature=r['x'],structure_symbol=n['a'],x=n['c'])
    g=at(P.SCHEME,C.CHECKED_SCHEME);family=c.eq(n['b'],8);c.ret(c.AND(g,c.NOT(family)),0)
    call(c.AND(g,family),P.INFO,Task.FAMILY_INFO,r['structure_signature'],family_info_pc=0)
    go(at(P.INFO),P.FAMILY_INFO,x=r['r'])
    g=at(P.FAMILY_INFO,C.PROJECTION_FAMILY_INFO);indices=c.NOT(c.eq(n['b'],0));c.ret(c.AND(g,indices),0)
    go(c.AND(g,c.NOT(indices)),P.FAMILY,structure_parameters=n['a'],x=n['c'])
    g=at(P.FAMILY,C.RAW_FAMILY);go(g,P.AUX,x=n['c'])
    g=at(P.AUX,C.RAW_FAMILY_AUX);go(g,P.VECTOR,structure_rec_symbol=n['b'],x=n['a'])
    g=at(P.VECTOR,C.VECTOR);one=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(n['a'],1),c.NOT(c.eq(n['b'],0)))
    c.ret(c.AND(g,c.NOT(one)),0);go(c.AND(g,one),P.CTOR_CELL,x=n['b'])
    g=at(P.CTOR_CELL,C.VECTOR_CELL);go(g,P.CTOR_RAW,x=n['a'])
    g=at(P.CTOR_RAW,C.RAW_CONSTRUCTOR);c.emit(g,structure_ctor=n['a'])
    call(g,P.CTOR_FOUND,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
    go(at(P.CTOR_FOUND),P.CTOR_SIG,x=r['r'])
    g=at(P.CTOR_SIG,C.CHECKED_SIGNATURE);go(g,P.CTOR_SCHEME,x=n['c'])
    g=at(P.CTOR_SCHEME,C.CHECKED_SCHEME);ctor=c.eq(n['b'],9)
    c.stop(c.AND(g,c.NOT(ctor)),Outcome.GAP,Reason.GAP_CONVERSION);go(c.AND(g,ctor),P.CTOR_META,x=n['c'])
    g=at(P.CTOR_META,C.CHECKED_CONSTRUCTOR);go(g,P.FIELDS,x=n['b'])
    g=at(P.FIELDS,C.VECTOR);go(g,P.REC_LOOKUP,structure_fields=n['a'])
    call(at(P.REC_LOOKUP),P.REC_FOUND,Task.ENV_LOOKUP,0,query_symbol=r['structure_rec_symbol'],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
    go(at(P.REC_FOUND),P.REC_SIG,x=r['r'])
    g=at(P.REC_SIG,C.CHECKED_SIGNATURE);go(g,P.REC_SCHEME,x=n['c'])
    g=at(P.REC_SCHEME,C.CHECKED_SCHEME);rec=c.eq(n['b'],10)
    c.stop(c.AND(g,c.NOT(rec)),Outcome.GAP,Reason.GAP_CONVERSION);go(c.AND(g,rec),P.REC_META,x=n['c'])
    g=at(P.REC_META,C.CHECKED_RECURSOR);go(g,P.REC_COUNTS,x=n['b'])
    g=at(P.REC_COUNTS,C.RECURSOR_COUNTS);go(g,P.REC_SHARED,x=n['c'])
    g=at(P.REC_SHARED,C.RECURSOR_SHARED_COUNTS);go(g,P.REC_BLOCK,x=n['c'])
    g=at(P.REC_BLOCK,C.RECURSOR_BLOCK);go(g,P.FLAGS,x=n['b'])
    g=at(P.FLAGS,C.BLOCK_FLAGS);recursive=c.NOT(c.eq(n['a'],0));c.ret(c.AND(g,recursive),0)
    go(c.AND(g,c.NOT(recursive)),P.DETAIL)
    store(at(P.DETAIL),(C.STRUCTURE_DETAIL,r['structure_ctor'],r['structure_fields'],0),P.RESULT,structure_detail=r['free'])
    g=at(P.RESULT);room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
    c.write('heap',g,r['free'],(C.STRUCTURE_INFO,r['structure_symbol'],r['structure_parameters'],r['structure_detail']))
    c.emit(g,free=c.add(r['free'],1));c.ret(g,r['free'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
