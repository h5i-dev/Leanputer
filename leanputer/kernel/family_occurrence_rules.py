"""Lower weighted family-list collection and scoped occurrence callback."""
from .native_cells import VectorKind
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_FAMILY_OCCURRENCE

PRIVATE_PHASES=(CALL_FAMILY_OCCURRENCE,)


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame']
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['phase'],CALL_FAMILY_OCCURRENCE))
    c.emit(returning,sp=c.sub(r['sp'],1),ctx=f['depth'],count=f['first'],arg_base=f['second'],task=f['task'],mode=Mode.RETURN)
    raw=c.task(Task.HAS_RAW_FAMILIES)
    active=c.OR(c.task(Task.HAS_FAMILIES),raw)
    c.emit(c.AND(raw,c.mode(Mode.WALK)),family_occurrence_root=r['x'],mode=Mode.RAW_FAMILY_VECTOR,x=r['raw_family_vector'])
    vector=c.AND(raw,c.mode(Mode.RAW_FAMILY_VECTOR));wb=lambda v:c.mux(c.eq(v,0),0,1)
    shape=c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.eq(wb(n['a']),wb(n['b'])))
    c.stop(c.AND(vector,c.NOT(shape)),Outcome.INVALID,Reason.SYNTAX)
    nonempty=c.NOT(c.eq(n['a'],0));wide=c.g.add(c.g.fit(r['ctx'],c.width+1),c.g.fit(n['a'],c.width+1))
    enough=c.NOT(c.g.lt(c.g.const(c.cfg.context,c.width+1),wide));room=c.lt(r['sp'],c.cfg.stack)
    c.ret(c.AND(vector,shape,c.NOT(nonempty)),0)
    c.stop(c.AND(vector,shape,nonempty,c.NOT(enough)),Outcome.RESOURCE,Reason.CONTEXT)
    c.stop(c.AND(vector,shape,nonempty,enough,c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    begin_raw=c.AND(vector,shape,nonempty,enough,room)
    c.write('stack',begin_raw,r['sp'],(CALL_FAMILY_OCCURRENCE,r['family_occurrence_root'],r['ctx'],Task.HAS_RAW_FAMILIES,r['count'],r['arg_base']))
    c.emit(begin_raw,sp=c.add(r['sp'],1),mode=Mode.FAMILY_SET_CELL,x=n['b'],family_set_cursor=r['ctx'],family_set_remaining=n['a'])
    init=c.AND(c.task(Task.HAS_FAMILIES),c.mode(Mode.WALK));empty=c.eq(r['header_seen'],0)
    c.ret(c.AND(init,empty),0)
    wide=c.g.add(c.g.fit(r['ctx'],c.width+1),c.g.fit(r['header_seen'],c.width+1))
    enough=c.NOT(c.g.lt(c.g.const(c.cfg.context,c.width+1),wide))
    c.stop(c.AND(init,c.NOT(empty),c.NOT(enough)),Outcome.RESOURCE,Reason.CONTEXT)
    room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(empty),enough,c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    begin=c.AND(init,c.NOT(empty),enough,room)
    c.write('stack',begin,r['sp'],(CALL_FAMILY_OCCURRENCE,r['x'],r['ctx'],Task.HAS_FAMILIES,r['count'],r['arg_base']))
    c.emit(begin,sp=c.add(r['sp'],1),mode=Mode.FAMILY_SET_CELL,x=r['header_head'],family_set_cursor=r['ctx'],family_set_remaining=r['header_seen'])
    cell=c.AND(active,c.mode(Mode.FAMILY_SET_CELL));a,b=n['a'],n['b']
    ptr=lambda p:c.AND(c.NOT(c.eq(p,0)),c.lt(p,r['free']))
    more=c.lt(1,r['family_set_remaining'])
    valid=c.AND(ptr(a),c.NOT(c.eq(r['family_set_remaining'],0)),c.OR(c.NOT(more),ptr(b)))
    c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(cell,valid),mode=Mode.FAMILY_SET_SIGNATURE,x=a,family_set_next=b)
    sig=c.AND(active,c.mode(Mode.FAMILY_SET_SIGNATURE))
    valid=c.AND(c.NOT(c.eq(a,0)),ptr(b),ptr(n['c']))
    c.stop(c.AND(sig,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    sig=c.AND(sig,valid)
    c.write('context',sig,r['family_set_cursor'],(a,))
    c.emit(sig,family_set_cursor=c.add(r['family_set_cursor'],1),family_set_remaining=c.sub(r['family_set_remaining'],1))
    c.emit(c.AND(sig,more),mode=Mode.FAMILY_SET_CELL,x=r['family_set_next'])
    c.emit(c.AND(sig,c.NOT(more)),mode=Mode.WALK,task=Task.HAS_CONSTANTS,x=f['original'],arg_base=f['depth'],count=c.sub(c.add(r['family_set_cursor'],1),f['depth']))
