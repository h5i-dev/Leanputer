"""Contextual String literal WHNF and conversion, pinned kernel composition.

Literal WHNF itself stays inert. Only projection/recursor preparation and the
String.ofList conversion extension construct its checked helper image.
"""
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.STRING_WHNF),c.mode(Mode.WALK))
    at=lambda pc:c.AND(active,c.eq(r['string_whnf_pc'],pc))
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.STRING_WHNF))
    c.emit(returning,task=Task.STRING_WHNF,mode=Mode.WALK,string_whnf_pc=f['phase'],x=r['r'])
    g=at(0);room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
    c.write('stack',g,r['sp'],(1,r['x'],r['string_tail_major'],Task.STRING_WHNF,0,0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.STRING_LITERAL,mode=Mode.WALK,string_pc=0,string_operation=1)
    g=at(1);c.write('stack',g,top,(2,f['original'],f['depth'],Task.STRING_WHNF,0,0))
    c.emit(g,task=Task.BETA_ZETA,mode=Mode.BETA_ZETA,x=r['r'],depth=0)
    g=at(2);tail=c.NOT(c.eq(f['depth'],0))
    c.emit(g,sp=top)
    c.ret(c.AND(g,c.NOT(tail)),r['r'])
    c.emit(c.AND(g,tail),string_whnf_pc=3,x=r['r'])
    # This literal branch must skip structure eta, just as the else-if in
    # inductive.h:92–97. Consume the caller major frame and return its value.
    g=at(3);valid=c.AND(c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.PREPARE_RECURSOR_MAJOR))
    c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,valid)
    c.emit(g,sp=top);c.ret(g,r['x'])

    active=c.AND(c.task(Task.STRING_COMPARE),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['string_compare_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,string_compare_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        c.write('stack',g,top,(pc,f['original'],f['depth'],Task.STRING_COMPARE,0,0))
        c.emit(g,task=task,mode=mode,x=x,depth=0,**kw)
    def finish(g,value):c.emit(g,sp=top);c.ret(g,value)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.STRING_COMPARE))
    c.emit(returning,task=Task.STRING_COMPARE,mode=Mode.WALK,string_compare_pc=f['phase'],x=r['r'])
    g=at(0);literal=c.tag(Tag.STRING)
    go(c.AND(g,literal),2,string_compare_literal=r['x'],string_compare_other=r['peer'])
    go(c.AND(g,c.NOT(literal)),1,x=r['peer'],string_compare_other=r['x'])
    g=at(1);literal=c.tag(Tag.STRING);c.ret(c.AND(g,c.NOT(literal)),0)
    go(c.AND(g,literal),2,string_compare_literal=r['x'])
    g=at(2);room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
    c.write('stack',g,r['sp'],(3,r['string_compare_literal'],r['string_compare_other'],Task.STRING_COMPARE,0,0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.STRING_BINDINGS,mode=Mode.WALK,x=0,string_binding_pc=0)
    go(at(3),4,x=f['depth'])
    g=at(4);app=c.tag(Tag.APP);finish(c.AND(g,c.NOT(app)),0)
    go(c.AND(g,app),5,x=n['a'])
    g=at(5);head=c.AND(c.tag(Tag.CONST),c.eq(n['a'],r['string_symbol_oflist']))
    finish(c.AND(g,c.NOT(head)),0);go(c.AND(g,head),6,x=n['b'])
    g=at(6,C.VECTOR);empty=c.AND(c.eq(n['c'],V.LEVELS),c.eq(n['a'],0),c.eq(n['b'],0))
    finish(c.AND(g,c.NOT(empty)),0)
    call(c.AND(g,empty),7,Task.STRING_LITERAL,f['original'],string_pc=0,string_operation=1)
    call(at(7),8,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    call(at(8),9,Task.CONVERT_POSITIVE,r['r'],peer=f['depth'])
    finish(at(9),c.mux(c.eq(r['r'],0),2,1))


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
