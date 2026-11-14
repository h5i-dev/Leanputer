"""Pinned quot.h reduction, with immutable reentrant call frames.

Used only behind the checked Quot initialization flag and canonical bindings.
"""
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.QUOT_REDUCE),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['quot_reduce_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,quot_reduce_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        c.write('stack',g,top,(pc,f['original'],f['depth'],Task.QUOT_REDUCE,f['first'],f['second']))
        c.emit(g,task=task,mode=mode,x=x,depth=0,**kw)
    def finish(g,value=0):c.emit(g,sp=top);c.ret(g,value)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.QUOT_REDUCE))
    c.emit(returning,task=Task.QUOT_REDUCE,mode=Mode.WALK,quot_reduce_pc=f['phase'],x=r['r'])
    g=at(0);ready=c.AND(c.NOT(c.eq(r['quot_initialized'],0)),c.NOT(c.eq(r['env_ready'],0)))
    c.ret(c.AND(g,c.NOT(ready)),0);room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(g,ready,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,ready,room)
    c.write('stack',g,r['sp'],(1,r['x'],0,Task.QUOT_REDUCE,0,0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.APPLICATION_SPINE)
    g=at(1);c.write('stack',g,top,(2,f['original'],0,Task.QUOT_REDUCE,r['r'],0));go(g,2,x=r['r'])
    g=at(2,C.APPLICATION_SPINE);c.write('stack',g,top,(3,f['original'],0,Task.QUOT_REDUCE,f['first'],n['b']));go(g,3,x=n['a'])
    g=at(3);lift=c.AND(c.tag(Tag.CONST),c.eq(n['a'],r['quot_symbol_lift']));ind=c.AND(c.tag(Tag.CONST),c.eq(n['a'],r['quot_symbol_ind']))
    finish(c.AND(g,c.NOT(c.OR(lift,ind))));g=c.AND(g,c.OR(lift,ind))
    c.write('stack',g,top,(4,f['original'],c.mux(lift,5,4),Task.QUOT_REDUCE,f['first'],f['second']));go(g,4,x=f['second'])
    g=at(4,C.VECTOR);enough=c.AND(c.eq(n['c'],V.REFERENCES),c.lt(f['depth'],n['a']))
    finish(c.AND(g,c.NOT(enough)));call(c.AND(g,enough),5,Task.VECTOR_REFERENCE,f['second'],vector_index=f['depth'])
    call(at(5),6,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    call(at(6),7,Task.APPLICATION_SPINE,r['r'])
    go(at(7),8,x=r['r'])
    g=at(8,C.APPLICATION_SPINE);go(g,9,x=n['a'],quot_reduce_args=n['b'])
    g=at(9);mk=c.AND(c.tag(Tag.CONST),c.eq(n['a'],r['quot_symbol_mk']))
    finish(c.AND(g,c.NOT(mk)));go(c.AND(g,mk),10,x=r['quot_reduce_args'])
    g=at(10,C.VECTOR);exact=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(n['a'],3))
    finish(c.AND(g,c.NOT(exact)));call(c.AND(g,exact),11,Task.VECTOR_REFERENCE,r['quot_reduce_args'],vector_index=2)
    g=at(11);c.emit(g,quot_reduce_element=r['r']);call(g,12,Task.VECTOR_REFERENCE,f['second'],vector_index=3)
    g=at(12);room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
    c.write('heap',g,r['free'],(Tag.APP,r['r'],r['quot_reduce_element'],0));go(g,13,free=c.add(r['free'],1),quot_reduce_result=r['free'],x=f['second'])
    g=at(13,C.VECTOR);start=c.add(f['depth'],1)
    call(g,14,Task.APPLY_VECTOR_SLICE,f['second'],slice_body=r['quot_reduce_result'],slice_start=start,slice_take=c.sub(n['a'],start))
    finish(at(14),r['r'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
