"""Fixed multiplication, binary division, Euclid and bounded-exponent power.

Parent loop records are immutable across recursive child arithmetic; raw input
cannot supply these records or an arithmetic operation stream. Source integration
and selected Boolean evidence are tracked separately from STOCK evidence.
"""
from enum import IntEnum
from .native_cells import CellTag as C
from .traversal_machine import Mode,Task,Outcome,Reason
from .nat_bits_rules import Op


class HighOp(IntEnum):
    MUL=8; DIVMOD=9; GCD=10; POW=11


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.NAT_HIGH),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['high_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,high_pc=pc,**kw)
    def call(g,pc,task,x,**kw):
        c.write('stack',g,top,(pc,f['original'],f['depth'],Task.NAT_HIGH,f['first'],f['second']))
        c.emit(g,task=task,mode=Mode.WALK,x=x,bits_pc=0,high_pc=0,depth=0,**kw)
    def low(g,pc,op,x,peer=0,**kw):call(g,pc,Task.NAT_BITS,x,bits_operation=op,bits_peer=peer,**kw)
    def high(g,pc,op,x,peer):call(g,pc,Task.NAT_HIGH,x,bits_operation=op,bits_peer=peer)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
    def state(g,row,pc):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row)
        c.write('stack',g,top,(pc,f['original'],f['depth'],Task.NAT_HIGH,f['first'],r['free']))
        go(g,pc,free=c.add(r['free'],1),x=r['free'])
    def finish(g,value):c.emit(g,sp=top);c.ret(g,value)
    def output(g,row):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);c.emit(g,free=c.add(r['free'],1));finish(g,r['free'])
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.NAT_HIGH))
    c.emit(returning,task=Task.NAT_HIGH,mode=Mode.WALK,high_pc=f['phase'],x=r['r'])
    op=lambda value:c.eq(f['first'],value)
    g=at(0);valid=c.OR(*(c.eq(r['bits_operation'],v) for v in HighOp));c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,valid,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,valid,room)
    c.write('stack',g,r['sp'],(1,r['x'],r['bits_peer'],Task.NAT_HIGH,r['bits_operation'],0))
    go(g,1,sp=c.add(r['sp'],1))
    g=at(1);go(c.AND(g,op(HighOp.MUL)),10)
    go(c.AND(g,op(HighOp.DIVMOD)),40,x=f['depth'])
    state(c.AND(g,op(HighOp.GCD)),(C.NAT_ARITHMETIC,f['original'],f['depth'],0),80)
    go(c.AND(g,op(HighOp.POW)),100,x=f['depth'])

    # Shift/add multiplication. All low-level calls preserve high scratch; the
    # owning immutable record also makes this safe when called from power.
    store(at(10),(C.NAT_BITS,0,0,0),11,high_zero=r['free'])
    state(at(11),(C.NAT_ARITHMETIC,r['high_zero'],f['original'],f['depth']),12)
    g=at(12,C.NAT_ARITHMETIC);go(g,13,high_acc=n['a'],high_base=n['b'],x=n['c'])
    g=at(13,C.NAT_BITS);empty=c.eq(n['a'],0);finish(c.AND(g,empty),r['high_acc'])
    go(c.AND(g,c.NOT(empty)),14,high_remaining=n['a'],x=n['b'])
    g=at(14,C.VECTOR_CELL);go(g,15,high_bit=n['a'],high_next=n['b'])
    g=at(15);one=c.NOT(c.eq(r['high_bit'],0))
    low(c.AND(g,one),16,Op.ADD,r['high_acc'],r['high_base'])
    go(c.AND(g,c.NOT(one)),16,x=r['high_acc'])
    g=at(16);store(g,(C.NAT_BITS,c.sub(r['high_remaining'],1),r['high_next'],0),17,high_acc=r['x'],high_tail=r['free'])
    state(at(17),(C.NAT_ARITHMETIC,r['high_acc'],r['high_base'],r['high_tail']),18)
    g=at(18,C.NAT_ARITHMETIC);last=c.eq(r['high_remaining'],1)
    finish(c.AND(g,last),n['a']);low(c.AND(g,c.NOT(last)),19,Op.SHIFT,n['b'],1,bits_direction=0)
    go(at(19),20,high_result=r['x'],x=f['second'])
    g=at(20,C.NAT_ARITHMETIC);state(g,(C.NAT_ARITHMETIC,n['a'],r['high_result'],n['c']),12)

    # MSB-first long division. Quotient and remainder are canonical private
    # vectors. A zero divisor returns(0,numerator), matching pinned Nat semantics.
    g=at(40,C.NAT_BITS);go(g,41,high_divisor_zero=c.mux(c.eq(n['a'],0),1,0),x=f['original'])
    store(at(41),(C.NAT_BITS,0,0,0),42,high_zero=r['free'])
    g=at(42);zero=c.NOT(c.eq(r['high_divisor_zero'],0))
    output(c.AND(g,zero),(C.NAT_DIV_RESULT,r['high_zero'],f['original'],0))
    go(c.AND(g,c.NOT(zero)),43,x=f['original'])
    g=at(43,C.NAT_BITS);call(g,44,Task.REVERSE_LIST,n['b'],reverse_length=n['a'])
    state(at(44),(C.NAT_ARITHMETIC,r['high_zero'],r['high_zero'],r['x']),45)
    g=at(45,C.NAT_ARITHMETIC);go(g,46,high_quotient=n['a'],high_remainder=n['b'],x=n['c'])
    g=at(46,C.VECTOR);empty=c.eq(n['a'],0)
    output(c.AND(g,empty),(C.NAT_DIV_RESULT,r['high_quotient'],r['high_remainder'],0))
    go(c.AND(g,c.NOT(empty)),47,high_remaining=n['a'],x=n['b'])
    g=at(47,C.VECTOR_CELL);store(g,(C.VECTOR,c.sub(r['high_remaining'],1),n['b'],1),48,high_bit=n['a'],high_tail=r['free'])
    state(at(48),(C.NAT_ARITHMETIC,r['high_quotient'],r['high_remainder'],r['high_tail']),49)
    low(at(49),50,Op.PUSH,r['high_remainder'],r['high_bit'])
    go(at(50),51,high_result=r['x'],x=f['second'])
    g=at(51,C.NAT_ARITHMETIC);state(g,(C.NAT_ARITHMETIC,n['a'],r['high_result'],n['c']),52)
    low(at(52),53,Op.COMPARE,r['high_result'],f['depth'])
    g=at(53);enough=c.NOT(c.eq(r['x'],0));c.emit(g,high_decision=c.mux(enough,1,0))
    low(c.AND(g,enough),54,Op.SUB,r['high_result'],f['depth'])
    go(c.AND(g,c.NOT(enough)),54,x=r['high_result'])
    go(at(54),55,high_result=r['x'],x=f['second'])
    g=at(55,C.NAT_ARITHMETIC);state(g,(C.NAT_ARITHMETIC,n['a'],r['high_result'],n['c']),56)
    g=at(56,C.NAT_ARITHMETIC);low(g,57,Op.PUSH,n['a'],r['high_decision'])
    go(at(57),58,high_result=r['x'],x=f['second'])
    g=at(58,C.NAT_ARITHMETIC);state(g,(C.NAT_ARITHMETIC,r['high_result'],n['b'],n['c']),45)

    # Euclid: a,b -> b, a%b. Child division may overwrite every high scratch.
    g=at(80,C.NAT_ARITHMETIC);go(g,81,high_base=n['a'],high_divisor=n['b'],x=n['b'])
    g=at(81,C.NAT_BITS);zero=c.eq(n['a'],0)
    finish(c.AND(g,zero),r['high_base']);high(c.AND(g,c.NOT(zero)),82,HighOp.DIVMOD,r['high_base'],r['high_divisor'])
    g=at(82,C.NAT_DIV_RESULT);go(g,83,high_result=n['b'],x=f['second'])
    g=at(83,C.NAT_ARITHMETIC);state(g,(C.NAT_ARITHMETIC,n['b'],r['high_result'],0),80)

    # Repeated-squaring exponentiation. Cap is the pinned1<<24, including its
    # boundary; cap overflow is neutral(result0), not physical RESOURCE.
    g=at(100,C.NAT_BITS);too_large=c.lt(25,n['a']);finish(c.AND(g,too_large),0)
    cap=c.eq(n['a'],25);go(c.AND(g,cap),101,high_remaining=24,x=n['b'])
    go(c.AND(g,c.NOT(too_large),c.NOT(cap)),104)
    g=at(101,C.VECTOR_CELL);nonzero=c.NOT(c.eq(n['a'],0));finish(c.AND(g,nonzero),0)
    more=c.lt(1,r['high_remaining'])
    go(c.AND(g,c.NOT(nonzero),more),101,x=n['b'],high_remaining=c.sub(r['high_remaining'],1))
    go(c.AND(g,c.NOT(nonzero),c.NOT(more)),104)
    store(at(104),(C.VECTOR_CELL,1,0,0),105,high_one_head=r['free'])
    store(at(105),(C.NAT_BITS,1,r['high_one_head'],0),106,high_one=r['free'])
    state(at(106),(C.NAT_ARITHMETIC,r['high_one'],f['original'],f['depth']),107)
    g=at(107,C.NAT_ARITHMETIC);go(g,108,high_acc=n['a'],high_base=n['b'],x=n['c'])
    g=at(108,C.NAT_BITS);zero=c.eq(n['a'],0);finish(c.AND(g,zero),r['high_acc'])
    go(c.AND(g,c.NOT(zero)),109,high_remaining=n['a'],x=n['b'])
    g=at(109,C.VECTOR_CELL);store(g,(C.NAT_BITS,c.sub(r['high_remaining'],1),n['b'],0),110,high_bit=n['a'],high_tail=r['free'])
    state(at(110),(C.NAT_ARITHMETIC,r['high_acc'],r['high_base'],r['high_tail']),111)
    g=at(111);one=c.NOT(c.eq(r['high_bit'],0))
    high(c.AND(g,one),112,HighOp.MUL,r['high_acc'],r['high_base'])
    go(c.AND(g,c.NOT(one)),112,x=r['high_acc'])
    go(at(112),113,high_result=r['x'],x=f['second'])
    g=at(113,C.NAT_ARITHMETIC);state(g,(C.NAT_ARITHMETIC,r['high_result'],n['b'],n['c']),114)
    g=at(114,C.NAT_ARITHMETIC);go(g,115,high_acc=n['a'],high_base=n['b'],x=n['c'])
    g=at(115,C.NAT_BITS);zero=c.eq(n['a'],0);finish(c.AND(g,zero),r['high_acc'])
    high(c.AND(g,c.NOT(zero)),116,HighOp.MUL,r['high_base'],r['high_base'])
    go(at(116),117,high_result=r['x'],x=f['second'])
    g=at(117,C.NAT_ARITHMETIC);state(g,(C.NAT_ARITHMETIC,n['a'],r['high_result'],n['c']),107)


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
