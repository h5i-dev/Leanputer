"""Lower derived Local-window -> UID-window -> shared abstraction calls."""
from .arena import Tag
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_ABSTRACT_SCOPE

PRIVATE_PHASES=(CALL_ABSTRACT_SCOPE,)


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame']
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['phase'],CALL_ABSTRACT_SCOPE))
    c.emit(returning,sp=c.sub(r['sp'],1),task=f['task'],count=f['depth'],arg_base=f['first'],ctx=f['second'],mode=Mode.RETURN)
    instantiating=c.task(Task.INSTANTIATE_SCOPE)
    active=c.OR(c.task(Task.ABSTRACT_SCOPE),instantiating);at=lambda mode:c.AND(active,c.mode(mode))
    init=at(Mode.WALK)
    valid=c.AND(c.NOT(c.lt(r['abstract_base'],r['local_base'])),c.NOT(c.lt(r['abstract_end'],r['abstract_base'])),c.NOT(c.lt(r['ctx'],r['abstract_end'])))
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    init=c.AND(init,valid);size=c.sub(r['abstract_end'],r['abstract_base']);empty=c.eq(size,0)
    c.ret(c.AND(init,empty),r['x'])
    wide=c.g.add(c.g.fit(r['ctx'],c.width+1),c.g.fit(size,c.width+1))
    enough=c.NOT(c.g.lt(c.g.const(c.cfg.context,c.width+1),wide));room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(empty),c.NOT(enough)),Outcome.RESOURCE,Reason.CONTEXT)
    c.stop(c.AND(init,c.NOT(empty),enough,c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    begin=c.AND(init,c.NOT(empty),enough,room)
    c.write('stack',begin,r['sp'],(CALL_ABSTRACT_SCOPE,r['x'],r['count'],r['task'],r['arg_base'],r['ctx']))
    c.emit(begin,sp=c.add(r['sp'],1),mode=Mode.ABSTRACT_SCOPE_SELECT,
        scope_cursor=c.mux(instantiating,c.sub(r['abstract_end'],1),r['abstract_base']),scope_dest=r['ctx'])
    c.emit(at(Mode.ABSTRACT_SCOPE_SELECT),mode=Mode.ABSTRACT_SCOPE_RECORD,x=c.read['operand']['value'])
    record=at(Mode.ABSTRACT_SCOPE_RECORD);ptr=c.AND(c.NOT(c.eq(n['a'],0)),c.lt(n['a'],r['free']))
    c.stop(c.AND(record,c.NOT(ptr)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(record,ptr),mode=Mode.ABSTRACT_SCOPE_LOCAL,x=n['a'])
    local=at(Mode.ABSTRACT_SCOPE_LOCAL);valid=c.AND(c.tag(Tag.LOCAL),c.NOT(c.eq(n['a'],0)))
    c.stop(c.AND(local,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    local=c.AND(local,valid);more=c.OR(c.AND(instantiating,c.lt(r['abstract_base'],r['scope_cursor'])),
        c.AND(c.NOT(instantiating),c.lt(c.add(r['scope_cursor'],1),r['abstract_end'])))
    c.write('context',local,r['scope_dest'],(c.mux(instantiating,r['x'],n['a']),))
    c.emit(local,scope_dest=c.add(r['scope_dest'],1),scope_cursor=c.mux(instantiating,
        c.mux(c.eq(r['scope_cursor'],0),0,c.sub(r['scope_cursor'],1)),c.add(r['scope_cursor'],1)))
    c.emit(c.AND(local,more),mode=Mode.ABSTRACT_SCOPE_SELECT)
    c.emit(c.AND(local,c.NOT(more)),task=c.mux(instantiating,Task.INSTANTIATE,Task.ABSTRACT),start=0,
        mode=Mode.WALK,x=f['original'],arg_base=f['second'],count=size,depth=0)
