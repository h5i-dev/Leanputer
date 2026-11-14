"""Nat primitive/ordinary delta bridge.

Canonical name classification supplies no type/reduction answer. Neutral genuine
primitive applications must retain ordinary delta fallback, unlike an inductive
or Quot iota attempt. All fallback syntax is private checked lookup provenance.
"""
from .native_cells import CellTag as C
from .traversal_machine import Mode,Task,Outcome,Reason


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.NAT_BRIDGE),c.mode(Mode.WALK))
    def at(pc,tag):
        g=c.AND(active,c.eq(r['nat_bridge_pc'],pc))
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.NAT_BRIDGE))
    c.emit(returning,sp=top,task=Task.NAT_BRIDGE,mode=Mode.WALK,nat_bridge_pc=1,x=f['original'],nat_operation=r['r'],nat_signature=f['original'])
    g=at(0,C.CHECKED_SIGNATURE);room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
    c.write('stack',g,r['sp'],(1,r['x'],0,Task.NAT_BRIDGE,0,0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.NAT_CLASSIFY,mode=Mode.WALK,nat_name_pc=0,x=f['original'])
    g=at(1,C.CHECKED_SIGNATURE);primitive=c.AND(c.lt(0,r['nat_operation']),c.NOT(c.lt(15,r['nat_operation'])))
    c.emit(c.AND(g,c.NOT(primitive)),task=Task.BETA_ZETA,mode=Mode.CONST_SCHEME,x=n['c'],signature_type=n['b'])
    room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,primitive,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,primitive,room)
    c.write('heap',g,r['free'],(C.NAT_FALLBACK,n['c'],n['b'],f['original']))
    c.emit(g,free=c.add(r['free'],1),nat_bridge_pc=2,x=r['free'])
    g=at(2,C.NAT_FALLBACK)
    c.emit(g,task=Task.GATHER_RECURSOR_ARGUMENTS,mode=Mode.WALK,x=f['original'],gather_service=Task.NAT_REDUCE,gather_fallback=r['x'])
    # The gather bridge restores the original checked-lookup frame before this
    # continuation, leaving all pending application arguments in place.
    g=at(20,C.NAT_FALLBACK)
    c.emit(g,task=Task.BETA_ZETA,mode=Mode.CONST_SCHEME,x=n['a'],signature_type=n['b'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
