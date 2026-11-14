"""Pinned Nat zero/successor offset conversion (type_checker.cpp:943–970).

The finite checked Nat interface authorizes literal predecessor comparison.
The caller's typed conversion still handles all other expressions generically.
Return0unknown,1equal,2unequal; input supplies no equality decision.
"""
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.NAT_OFFSET),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['offset_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,offset_pc=pc,**kw)
    def call(g,pc,task,x,**kw):
        c.write('stack',g,top,(pc,f['original'],f['depth'],Task.NAT_OFFSET,f['first'],f['second']))
        c.emit(g,task=task,mode=Mode.WALK,x=x,depth=0,**kw)
    def finish(g,value):c.emit(g,sp=top);c.ret(g,value)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.NAT_OFFSET))
    c.emit(returning,task=Task.NAT_OFFSET,mode=Mode.WALK,offset_pc=f['phase'],x=r['r'])
    g=at(0);literal=c.tag(Tag.NAT)
    go(c.AND(g,literal),2,offset_literal=r['x'],offset_other=r['peer'])
    go(c.AND(g,c.NOT(literal)),1,x=r['peer'],offset_other=r['x'])
    g=at(1);literal=c.tag(Tag.NAT)
    c.ret(c.AND(g,c.NOT(literal)),0);go(c.AND(g,literal),2,offset_literal=r['x'])
    g=at(2);room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
    c.write('stack',g,r['sp'],(3,r['offset_literal'],r['offset_other'],Task.NAT_OFFSET,0,0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.NAT_BINDINGS,mode=Mode.WALK,x=0,nat_binding_pc=0)
    call(at(3),4,Task.APPLICATION_SPINE,f['depth'])
    g=at(4,C.APPLICATION_SPINE)
    c.write('stack',g,top,(5,f['original'],f['depth'],Task.NAT_OFFSET,r['x'],0))
    go(g,5,x=n['a'],offset_arguments=n['b'])
    g=at(5);zero=c.AND(c.tag(Tag.CONST),c.eq(n['a'],r['nat_symbol_zero']));succ=c.AND(c.tag(Tag.CONST),c.eq(n['a'],r['nat_symbol_succ']))
    finish(c.AND(g,c.NOT(c.OR(zero,succ))),0)
    go(c.AND(g,c.OR(zero,succ)),6,x=n['b'],offset_is_zero=c.mux(zero,1,0))
    g=at(6,C.VECTOR);empty=c.AND(c.eq(n['c'],V.LEVELS),c.eq(n['a'],0),c.eq(n['b'],0))
    finish(c.AND(g,c.NOT(empty)),0);go(c.AND(g,empty),7,x=r['offset_arguments'])
    g=at(7,C.VECTOR);arity=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(n['a'],c.mux(c.eq(r['offset_is_zero'],1),0,1)))
    finish(c.AND(g,c.NOT(arity)),0);go(c.AND(g,arity),8,x=f['original'])
    g=at(8,Tag.NAT);go(g,9,x=n['a'])
    g=at(9,C.VECTOR);empty=c.eq(n['a'],0);zero=c.eq(r['offset_is_zero'],1)
    finish(c.AND(g,empty,zero),1)
    # Checked Nat zero and successor are disjoint; after offset comparison these
    # are precisely the corresponding typed canonical-constructor clash cases.
    finish(c.AND(g,c.NOT(c.eq(c.mux(empty,1,0),r['offset_is_zero']))),2)
    call(c.AND(g,c.NOT(empty),c.NOT(zero)),10,Task.NAT_LITERAL,f['original'],nat_literal_pc=0,nat_literal_operation=1)
    g=at(10,Tag.APP)
    c.write('stack',g,top,(11,f['original'],f['depth'],Task.NAT_OFFSET,f['first'],n['b']))
    go(g,11,x=f['first'])
    g=at(11,C.APPLICATION_SPINE);call(g,12,Task.VECTOR_REFERENCE,n['b'],vector_index=0)
    call(at(12),13,Task.CONVERT_POSITIVE,f['second'],peer=r['x'])
    finish(at(13),c.mux(c.eq(r['x'],0),2,1))


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
