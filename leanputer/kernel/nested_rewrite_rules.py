"""Fixed preorder replace with a nested-specialization callback.

A successful callback replaces the entire subtree without visiting its result,
as in pinned replace_fn. Local types and Const levels are not Expr children.
Task-owned frames preserve binder depth across arbitrary service continuations.
"""
from .arena import Tag
from .traversal_machine import Mode, Task, Outcome, Reason


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.REWRITE_NESTED),c.mode(Mode.WALK))
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.REWRITE_NESTED))
    callback=c.AND(returning,c.eq(f['phase'],0));replaced=c.NOT(c.eq(r['r'],0))
    c.emit(callback,sp=top,task=Task.REWRITE_NESTED,depth=f['depth'])
    c.ret(c.AND(callback,replaced),r['r'])
    c.emit(c.AND(callback,c.NOT(replaced)),mode=Mode.WALK,x=f['original'],rewrite_pc=1)
    child=c.AND(returning,c.NOT(c.eq(f['phase'],0)))
    c.emit(child,task=Task.REWRITE_NESTED,mode=Mode.WALK,x=f['original'],depth=f['depth'],rewrite_pc=2)
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),
        c.NOT(c.lt(n['tag'],Tag.BVAR)),c.NOT(c.lt(Tag.MDATA,n['tag'])))
    c.stop(c.AND(active,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);active=c.AND(active,valid)
    init=c.AND(active,c.eq(r['rewrite_pc'],0));room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(init,room)
    c.write('stack',g,r['sp'],(0,r['x'],r['depth'],Task.REWRITE_NESTED,0,0))
    c.emit(g,sp=c.add(r['sp'],1),task=c.mux(c.eq(r['rewrite_restoring'],0),Task.REPLACE_NESTED,Task.RESTORE_NESTED_CALLBACK),copy_pc=0,restore_cb_pc=0)
    unary=c.tag(Tag.PROJ,Tag.MDATA);binary=c.tag(Tag.PI,Tag.LAM,Tag.APP);let=c.tag(Tag.LET)
    branch=c.OR(unary,binary,let)
    descend=c.AND(active,c.eq(r['rewrite_pc'],1));g=c.AND(descend,branch)
    c.ret(c.AND(descend,c.NOT(branch)),r['x'])
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
    c.write('stack',g,r['sp'],(1,r['x'],r['depth'],Task.REWRITE_NESTED,0,0))
    c.emit(g,sp=c.add(r['sp'],1),rewrite_pc=0,x=c.mux(c.tag(Tag.PROJ),n['c'],n['a']))
    resume=c.AND(active,c.eq(r['rewrite_pc'],2))
    count=c.mux(let,3,c.mux(binary,2,c.mux(unary,1,0)))
    phaseok=c.AND(c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.REWRITE_NESTED),
        c.NOT(c.eq(f['phase'],0)),c.NOT(c.lt(count,f['phase'])))
    c.stop(c.AND(resume,c.NOT(phaseok)),Outcome.INVALID,Reason.SYNTAX);resume=c.AND(resume,phaseok)
    more=c.lt(f['phase'],count);second=c.eq(f['phase'],1)
    g=c.AND(resume,more)
    increment=c.mux(c.OR(c.AND(c.tag(Tag.PI,Tag.LAM),second),c.AND(let,c.NOT(second))),1,0)
    g,depth=c.checked_add(g,r['depth'],increment)
    c.write('stack',g,top,(c.add(f['phase'],1),f['original'],f['depth'],Task.REWRITE_NESTED,
        c.mux(second,r['r'],f['first']),c.mux(second,f['second'],r['r'])))
    c.emit(g,rewrite_pc=0,depth=depth,x=c.mux(second,n['b'],n['c']))
    g=c.AND(resume,c.NOT(more))
    a=c.mux(unary,c.mux(c.tag(Tag.PROJ),n['a'],r['r']),f['first'])
    b=c.mux(binary,r['r'],c.mux(let,f['second'],n['b']))
    last=c.mux(c.OR(let,c.tag(Tag.PROJ)),r['r'],n['c'])
    same=c.AND(c.eq(a,n['a']),c.eq(b,n['b']),c.eq(last,n['c']))
    c.emit(g,sp=top)
    c.ret(c.AND(g,same),f['original'])
    g=c.AND(g,c.NOT(same));heap=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(g,c.NOT(heap)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,heap)
    c.write('heap',g,r['free'],(n['tag'],a,b,last));c.emit(g,free=c.add(r['free'],1));c.ret(g,r['free'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
