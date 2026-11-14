"""Classify exactly the genuine pinned reduce_nat constant namespace.

A fixed byte trie of C++ kernel primitive interface names, not an ordinary
library declaration catalog. Arbitrary name shapes/numerals fall through to
ordinary delta; raw names cannot authorize signatures or successful reduction.
"""
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


# Source type_checker.cpp:reduce_nat/initialize_type_checker only.
NAMES=('succ','add','sub','mul','pow','gcd','mod','div','beq','ble',
       'land','lor','xor','shiftLeft','shiftRight','zero')


def trie():
    edges={};terminal={};next_state=1
    for code,name in enumerate(NAMES,1):
        state=0
        for byte in name.encode('ascii'):
            key=(state,byte)
            if key not in edges:edges[key]=next_state;next_state+=1
            state=edges[key]
        terminal[state]=code
    return edges,terminal


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.NAT_CLASSIFY),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['nat_name_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,nat_name_pc=pc,**kw)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.NAT_CLASSIFY))
    c.emit(returning,sp=top,task=Task.NAT_CLASSIFY,mode=Mode.WALK,nat_name_pc=f['original'],x=r['r'])
    g=at(0,Tag.CONST);go(g,1,nat_name_symbol=n['a'],x=n['b'])
    g=at(1,C.VECTOR);empty=c.AND(c.eq(n['c'],V.LEVELS),c.eq(n['a'],0),c.eq(n['b'],0))
    c.ret(c.AND(g,c.NOT(empty)),0);g=c.AND(g,empty)
    room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
    c.write('stack',g,r['sp'],(0,2,0,Task.NAT_CLASSIFY,0,0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.GET_NAME_PATH,mode=Mode.WALK,x=r['symbols_root'],query_symbol=r['nat_name_symbol'])
    g=at(2,C.VECTOR);shape=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(n['a'],2))
    c.ret(c.AND(g,c.NOT(shape)),0);go(c.AND(g,shape),3,x=n['b'])
    g=at(3,C.VECTOR_CELL);go(g,4,x=n['a'],nat_name_tail=n['b'])
    g=at(4);string=c.tag(C.NAME_STRING)
    c.ret(c.AND(g,c.NOT(string)),0);go(c.AND(g,string),5,x=n['a'])
    g=at(5,C.VECTOR);shape=c.AND(c.eq(n['c'],V.BYTES),c.eq(n['a'],3))
    c.ret(c.AND(g,c.NOT(shape)),0);go(c.AND(g,shape),6,x=n['b'],nat_name_position=0)
    g=at(6,C.VECTOR_CELL)
    expected=c.mux(c.eq(r['nat_name_position'],0),78,c.mux(c.eq(r['nat_name_position'],1),97,116))
    same=c.eq(n['a'],expected);more=c.lt(r['nat_name_position'],2)
    c.ret(c.AND(g,c.NOT(same)),0)
    go(c.AND(g,same,more),6,x=n['b'],nat_name_position=c.add(r['nat_name_position'],1))
    go(c.AND(g,same,c.NOT(more)),7,x=r['nat_name_tail'])
    g=at(7,C.VECTOR_CELL);go(g,8,x=n['a'])
    g=at(8);string=c.tag(C.NAME_STRING)
    c.ret(c.AND(g,c.NOT(string)),0);go(c.AND(g,string),9,x=n['a'])
    g=at(9,C.VECTOR);valid=c.AND(c.eq(n['c'],V.BYTES),c.NOT(c.eq(n['a'],0)))
    c.ret(c.AND(g,c.NOT(valid)),0);go(c.AND(g,valid),10,x=n['b'],nat_name_remaining=n['a'],nat_name_state=0)
    g=at(10,C.VECTOR_CELL);edges,terminal=trie();matched=[];last=c.eq(r['nat_name_remaining'],1)
    for (state,byte),target in edges.items():
        found=c.AND(c.eq(r['nat_name_state'],state),c.eq(n['a'],byte));matched.append(found);guard=c.AND(g,found)
        go(c.AND(guard,c.NOT(last)),10,x=n['b'],nat_name_remaining=c.sub(r['nat_name_remaining'],1),nat_name_state=target)
        c.ret(c.AND(guard,last),terminal.get(target,0))
    c.ret(c.AND(g,c.NOT(c.OR(*matched))),0)


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
