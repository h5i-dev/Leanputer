"""Genuine pinned Nat WHNF operations over arbitrary private bit vectors.

The source driver supplies no primitive answer. Checked canonical bindings,
fixed kernel-name classification, recursively normalized operands and immutable
owned call records authorize reductions. Neutral/capped results return0 so the
WHNF bridge can resume ordinary delta. Evidence is recorded separately from the algorithm.
"""
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason
from .nat_bits_rules import Op
from .nat_high_rules import HighOp


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.NAT_REDUCE),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['nat_reduce_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,nat_reduce_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        c.write('stack',g,top,(pc,f['original'],f['depth'],Task.NAT_REDUCE,f['first'],f['second']))
        c.emit(g,task=task,mode=mode,x=x,depth=0,**kw)
    def low(g,pc,op,x,peer=0,**kw):call(g,pc,Task.NAT_BITS,x,bits_pc=0,bits_operation=op,bits_peer=peer,**kw)
    def high(g,pc,op,x,peer):call(g,pc,Task.NAT_HIGH,x,high_pc=0,bits_operation=op,bits_peer=peer)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
    def state(g,row,pc):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row)
        c.write('stack',g,top,(pc,f['original'],f['depth'],Task.NAT_REDUCE,f['first'],r['free']))
        go(g,pc,free=c.add(r['free'],1),x=r['free'])
    def finish(g,value=0):c.emit(g,sp=top);c.ret(g,value)
    def binding(g,valid):
        c.stop(c.AND(g,c.NOT(valid)),Outcome.GAP,Reason.GAP_PRIMITIVE);return c.AND(g,valid)
    op=lambda value:c.eq(f['depth'],value)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.NAT_REDUCE))
    c.emit(returning,task=Task.NAT_REDUCE,mode=Mode.WALK,nat_reduce_pc=f['phase'],x=r['r'])
    g=at(0);known=c.AND(c.lt(0,r['nat_operation']),c.NOT(c.lt(15,r['nat_operation'])))
    c.stop(c.AND(g,c.NOT(known)),Outcome.INVALID,Reason.SYNTAX);room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(g,known,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,known,room)
    c.write('stack',g,r['sp'],(2,r['x'],r['nat_operation'],Task.NAT_REDUCE,r['nat_signature'],0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.APPLICATION_SPINE,mode=Mode.WALK)
    go(at(2),3,x=r['x'])
    g=at(3,C.APPLICATION_SPINE);state(g,(C.NAT_REDUCE_STATE,n['b'],0,0),4)
    g=at(4,C.NAT_REDUCE_STATE);go(g,5,x=n['a'])
    g=at(5,C.VECTOR);arity=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(n['a'],c.mux(op(1),1,2)))
    finish(c.AND(g,c.NOT(arity)));g=c.AND(g,arity)
    go(g,20,x=f['second'])
    g=at(7);predicate=c.OR(op(9),op(10))
    call(c.AND(g,predicate),6,Task.BOOL_BINDINGS,0,bool_pc=0)
    go(c.AND(g,c.NOT(predicate)),10,x=f['first'])
    go(at(6),10,x=f['first'])
    g=at(10,C.CHECKED_SIGNATURE);go(g,11,nat_reduce_type=n['b'],x=n['c'])
    g=at(11,C.CHECKED_SCHEME);go(g,12,x=n['a'])
    g=binding(at(12,C.VECTOR),c.AND(c.eq(n['a'],0),c.eq(n['b'],0),c.eq(n['c'],V.SYMBOLS)))
    result=c.mux(c.OR(op(9),op(10)),r['bool_type'],r['nat_type'])
    store(g,(Tag.PI,r['nat_type'],result,0),13,nat_reduce_expected=r['free'])
    g=at(13);go(c.AND(g,op(1)),15)
    store(c.AND(g,c.NOT(op(1))),(Tag.PI,r['nat_type'],r['nat_reduce_expected'],0),15,nat_reduce_expected=r['free'])
    call(at(15),16,Task.CONVERT_POSITIVE,r['nat_reduce_type'],peer=r['nat_reduce_expected'])
    g=binding(at(16),c.NOT(c.eq(r['x'],0)));go(g,100,x=f['second'])

    # First normalize and recognize BOTH numeric candidates. Primitive binding
    # requirements apply only when the genuine hook can reduce; ordinary data
    # with these names and neutral arguments must still reach delta normally.
    for side,base in enumerate((20,40)):
        g=at(base,C.NAT_REDUCE_STATE);call(g,base+1,Task.VECTOR_REFERENCE,n['a'],vector_index=side)
        call(at(base+1),base+2,Task.BETA_ZETA,r['x'],Mode.BETA_ZETA)
        g=at(base+2);literal=c.tag(Tag.NAT);constant=c.tag(Tag.CONST)
        go(c.AND(g,literal),base+4)
        c.emit(c.AND(g,constant),nat_reduce_candidate=r['x'])
        call(c.AND(g,constant),base+3,Task.NAT_CLASSIFY,r['x'],nat_name_pc=0)
        finish(c.AND(g,c.NOT(c.OR(literal,constant))))
        g=at(base+3);zero=c.eq(r['x'],16)
        go(c.AND(g,zero),base+4,x=r['nat_reduce_candidate']);finish(c.AND(g,c.NOT(zero)))
        go(at(base+4),base+5,nat_reduce_result=r['x'],x=f['second'])
        g=at(base+5,C.NAT_REDUCE_STATE)
        state(g,(C.NAT_REDUCE_STATE,n['a'],r['nat_reduce_result'] if side==0 else n['b'],r['nat_reduce_result'] if side==1 else n['c']),base+6)
        if side==0:
            g=at(base+6)
            call(c.AND(g,op(1)),7,Task.NAT_BINDINGS,0,nat_binding_pc=0)
            go(c.AND(g,c.NOT(op(1))),40,x=f['second'])
        else:call(at(base+6),7,Task.NAT_BINDINGS,0,nat_binding_pc=0)

    # Binding/type checks may reenter Nat reduction. Candidate expressions are
    # already in the immutable state; only now convert them to private bits.
    for side,base in enumerate((100,120)):
        g=at(base,C.NAT_REDUCE_STATE);go(g,base+1,x=n['b'] if side==0 else n['c'])
        g=at(base+1);literal=c.tag(Tag.NAT)
        low(c.AND(g,literal),base+2,Op.FROM_LIMBS,n['a'])
        store(c.AND(g,c.NOT(literal)),(C.NAT_BITS,0,0,0),base+2,x=r['free'])
        go(at(base+2),base+3,nat_reduce_result=r['x'],x=f['second'])
        g=at(base+3,C.NAT_REDUCE_STATE)
        state(g,(C.NAT_REDUCE_STATE,n['a'],r['nat_reduce_result'] if side==0 else n['b'],r['nat_reduce_result'] if side==1 else n['c']),base+4)
        if side==0:
            g=at(base+4);go(c.AND(g,op(1)),30);go(c.AND(g,c.NOT(op(1))),120,x=f['second'])
        else:go(at(base+4),60,x=f['second'])
    store(at(30),(C.VECTOR_CELL,1,0,0),31,nat_reduce_one_head=r['free'])
    store(at(31),(C.NAT_BITS,1,r['nat_reduce_one_head'],0),32,nat_reduce_one=r['free'],x=f['second'])
    g=at(32,C.NAT_REDUCE_STATE);state(g,(C.NAT_REDUCE_STATE,n['a'],n['b'],r['nat_reduce_one']),60)
    g=at(60,C.NAT_REDUCE_STATE);c.emit(g,nat_reduce_left=n['b'],nat_reduce_right=n['c'])
    low(c.AND(g,c.OR(op(1),op(2))),82,Op.ADD,n['b'],n['c'])
    low(c.AND(g,op(3)),82,Op.SUB,n['b'],n['c'])
    high(c.AND(g,op(4)),82,HighOp.MUL,n['b'],n['c'])
    high(c.AND(g,op(5)),82,HighOp.POW,n['b'],n['c'])
    high(c.AND(g,op(6)),82,HighOp.GCD,n['b'],n['c'])
    high(c.AND(g,c.OR(op(7),op(8))),80,HighOp.DIVMOD,n['b'],n['c'])
    low(c.AND(g,c.OR(op(9),op(10))),81,Op.COMPARE,n['b'],n['c'])
    low(c.AND(g,c.OR(op(11),op(12),op(13))),82,c.add(f['depth'],1),n['b'],n['c'])
    go(c.AND(g,c.OR(op(14),op(15))),90,x=n['c'])
    g=at(80,C.NAT_DIV_RESULT);go(g,82,x=c.mux(op(7),n['b'],n['a']))
    g=at(81);yes=c.OR(c.AND(op(9),c.eq(r['x'],1)),c.AND(op(10),c.NOT(c.eq(r['x'],2))))
    finish(g,c.mux(yes,r['bool_true_expression'],r['bool_false_expression']))
    g=at(82);neutral=c.eq(r['x'],0);finish(c.AND(g,neutral))
    low(c.AND(g,c.NOT(neutral)),84,Op.TO_LIMBS,r['x'])
    g=at(84,C.VECTOR);room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
    c.write('heap',g,r['free'],(Tag.NAT,r['x'],0,0));c.emit(g,free=c.add(r['free'],1));finish(g,r['free'])

    # Shift count is arbitrary Nat data. A count too large for the physical
    # word gives0for right shifts; nonzero left results cannot physically fit.
    g=at(90,C.NAT_BITS);large=c.lt(c.width,n['a'])
    go(c.AND(g,large),91,x=r['nat_reduce_left'])
    go(c.AND(g,c.NOT(large)),94,nat_reduce_count_remaining=n['a'],nat_reduce_count_cursor=n['b'],nat_reduce_count=0,nat_reduce_factor=1)
    g=at(91,C.NAT_BITS);zero=c.eq(n['a'],0);right=op(15)
    go(c.AND(g,zero),82,x=r['nat_reduce_left'])
    c.stop(c.AND(g,c.NOT(zero),c.NOT(right)),Outcome.RESOURCE,Reason.INDEX)
    store(c.AND(g,c.NOT(zero),right),(C.NAT_BITS,0,0,0),82,x=r['free'])
    g=at(94);done=c.eq(r['nat_reduce_count_remaining'],0)
    low(c.AND(g,done),82,Op.SHIFT,r['nat_reduce_left'],r['nat_reduce_count'],bits_direction=c.mux(op(15),1,0))
    go(c.AND(g,c.NOT(done)),95,x=r['nat_reduce_count_cursor'])
    g=at(95,C.VECTOR_CELL)
    go(g,94,nat_reduce_count=c.add(r['nat_reduce_count'],c.mux(c.eq(n['a'],0),0,r['nat_reduce_factor'])),
        nat_reduce_factor=c.word_shl1(r['nat_reduce_factor']),nat_reduce_count_cursor=n['b'],nat_reduce_count_remaining=c.sub(r['nat_reduce_count_remaining'],1))


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
