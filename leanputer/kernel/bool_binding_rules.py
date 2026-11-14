"""Checked finite Bool bindings used by pinned reduce_bin_nat_pred.

This validates only the genuine primitive output interface. Ordinary Boolean
formation remains the general source transaction, including differently shaped
families that cannot authorize this primitive hook.
"""
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason
from .quotient_templates import Ref,name_syntax


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.BOOL_BINDINGS),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['bool_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.GAP,Reason.GAP_PRIMITIVE);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,bool_pc=pc,**kw)
    def call(g,pc,task,x,**kw):
        room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
        c.write('stack',g,r['sp'],(0,pc,0,Task.BOOL_BINDINGS,0,0))
        c.emit(g,sp=c.add(r['sp'],1),task=task,mode=Mode.WALK,x=x,depth=0,**kw)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
    def check(g,valid):
        c.stop(c.AND(g,c.NOT(valid)),Outcome.GAP,Reason.GAP_PRIMITIVE);return c.AND(g,valid)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.BOOL_BINDINGS))
    c.emit(returning,sp=top,task=Task.BOOL_BINDINGS,mode=Mode.WALK,bool_pc=f['original'],x=r['r'])
    g=at(0);ready=c.NOT(c.eq(r['bool_validated'],0));c.ret(c.AND(g,ready),1);go(c.AND(g,c.NOT(ready)),100)
    for index,(key,parts) in enumerate([('type',('Bool',)),('true',('Bool','true')),('false',('Bool','false'))]):
        start=100+index*24;s,path=name_syntax(parts)
        go(at(start),start+1,bool_name_base=r['free'])
        def ptr(x):return c.add(r['bool_name_base'],x.index) if isinstance(x,Ref) else x
        for i,row in enumerate(s.rows):store(at(start+1+i),tuple(ptr(x) for x in row),start+2+i)
        call(at(start+1+len(s.rows)),start+2+len(s.rows),Task.INTERN_NAME_PATH,ptr(path))
        go(at(start+2+len(s.rows)),start+24 if index<2 else 1,**{'bool_symbol_'+key:r['r']})
    store(at(1),(Tag.CONST,r['bool_symbol_type'],r['nat_empty_levels'],0),2,bool_type=r['free'])
    store(at(2),(Tag.CONST,r['bool_symbol_true'],r['nat_empty_levels'],0),3,bool_true_expression=r['free'])
    store(at(3),(Tag.CONST,r['bool_symbol_false'],r['nat_empty_levels'],0),10,bool_false_expression=r['free'])
    for index,(key,kind,expected) in enumerate([('type',8,'nat_expected_type'),('true',9,'bool_type'),('false',9,'bool_type')]):
        pc=10+index*8
        call(at(pc),pc+1,Task.ENV_LOOKUP,0,query_symbol=r['bool_symbol_'+key],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
        go(at(pc+1),pc+2,x=r['r'])
        g=at(pc+2,C.CHECKED_SIGNATURE);go(g,pc+3,bool_check_type=n['b'],x=n['c'])
        if index==0:c.emit(g,bool_family_signature=r['x'])
        g=check(at(pc+3,C.CHECKED_SCHEME),c.eq(n['b'],kind));go(g,pc+4,x=n['a'])
        g=check(at(pc+4,C.VECTOR),c.AND(c.eq(n['a'],0),c.eq(n['b'],0),c.eq(n['c'],V.SYMBOLS)))
        call(g,pc+5,Task.CONVERT_POSITIVE,r['bool_check_type'],peer=r[expected])
        g=check(at(pc+5),c.NOT(c.eq(r['r'],0)));go(g,pc+8 if index<2 else 40)
    call(at(40),41,Task.FAMILY_INFO,r['bool_family_signature'],family_info_pc=0)
    go(at(41),42,x=r['r'])
    g=check(at(42,C.PROJECTION_FAMILY_INFO),c.AND(c.eq(n['a'],0),c.eq(n['b'],0)));go(g,43,x=n['c'])
    g=at(43,C.RAW_FAMILY);go(g,44,x=n['c'])
    g=at(44,C.RAW_FAMILY_AUX);go(g,45,x=n['a'])
    g=check(at(45,C.VECTOR),c.AND(c.eq(n['a'],2),c.eq(n['c'],V.REFERENCES)))
    go(g,46,x=n['b'],bool_remaining=2,bool_seen=0)
    g=at(46,C.VECTOR_CELL);go(g,47,x=n['a'],bool_next=n['b'])
    g=at(47,C.RAW_CONSTRUCTOR);yes=c.eq(n['a'],r['bool_symbol_true']);no=c.eq(n['a'],r['bool_symbol_false'])
    valid=c.AND(c.OR(yes,no),c.OR(c.eq(r['bool_seen'],0),c.AND(yes,c.eq(r['bool_seen'],2)),c.AND(no,c.eq(r['bool_seen'],1))))
    g=check(g,valid);more=c.lt(1,r['bool_remaining'])
    go(c.AND(g,more),46,x=r['bool_next'],bool_remaining=1,bool_seen=c.mux(yes,1,2))
    c.emit(c.AND(g,c.NOT(more)),bool_validated=1);c.ret(c.AND(g,c.NOT(more)),1)


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
