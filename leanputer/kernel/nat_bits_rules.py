"""Fixed arbitrary bit/limb arithmetic services for genuine Nat primitives.

Private canonical vectors, not a proof-supplied instruction tape. Source Nat arithmetic composes these with checked bindings, recursive operand
normalization and ordinary delta fallback. Evidence is recorded separately.
"""
from enum import IntEnum
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


class Op(IntEnum):
    FROM_LIMBS=1; TO_LIMBS=2; ADD=3; SUB=4; COMPARE=5; PUSH=6; SHIFT=7
    AND=12; OR=13; XOR=14


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.NAT_BITS),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['bits_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,bits_pc=pc,**kw)
    def check(g,valid):
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
    def reverse(g,pc,head,length):
        room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
        c.write('stack',g,r['sp'],(0,pc,0,Task.NAT_BITS,0,0))
        c.emit(g,sp=c.add(r['sp'],1),task=Task.REVERSE_LIST,mode=Mode.WALK,x=head,reverse_length=length)
    def finish(g,row):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);c.emit(g,free=c.add(r['free'],1));c.ret(g,r['free'])
    def valid_head(g,role):
        return check(g,c.AND(c.eq(n['c'],role),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1))))
    def valid_cell(g,remaining,bit=False):
        valid=c.AND(c.NOT(c.eq(remaining,0)),c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,remaining),1,0)))
        if bit:valid=c.AND(valid,c.NOT(c.lt(1,n['a'])),c.OR(c.lt(1,remaining),c.eq(n['a'],1)))
        return check(g,valid)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.NAT_BITS))
    c.emit(returning,sp=top,task=Task.NAT_BITS,mode=Mode.WALK,bits_pc=f['original'],x=r['r'])
    op=lambda value:c.eq(r['bits_operation'],value)
    g=at(0);known=c.OR(*(op(value)for value in Op))
    g=check(g,known);c.emit(g,bits_input=r['x'])
    go(c.AND(g,op(Op.FROM_LIMBS)),10)
    go(c.AND(g,op(Op.TO_LIMBS)),20)
    go(c.AND(g,c.OR(op(Op.ADD),op(Op.SUB),op(Op.COMPARE),op(Op.AND),op(Op.OR),op(Op.XOR))),40)
    go(c.AND(g,op(Op.PUSH)),70)
    go(c.AND(g,op(Op.SHIFT)),80)

    # Little-endian16bit limbs -> canonical little-endian bits.
    g=valid_head(at(10,C.VECTOR),V.LIMBS)
    go(g,11,bits_remaining=n['a'],bits_head=0,bits_length=0,x=n['b'])
    g=at(11);empty=c.eq(r['bits_remaining'],0);go(c.AND(g,empty),16)
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.VECTOR_CELL))
    g=check(c.AND(g,c.NOT(empty)),valid);g=valid_cell(g,r['bits_remaining'])
    g=check(g,c.OR(c.lt(1,r['bits_remaining']),c.NOT(c.eq(n['a'],0))))
    if c.width>16:g=check(g,c.lt(n['a'],65536))
    go(g,12,bits_word=n['a'],bits_next=n['b'],bits_position=0)
    g=at(12);last=c.eq(r['bits_remaining'],1)
    done=c.OR(c.eq(r['bits_position'],16),c.AND(last,c.eq(r['bits_word'],0)))
    go(c.AND(g,done,last),16)
    go(c.AND(g,done,c.NOT(last)),11,bits_remaining=c.sub(r['bits_remaining'],1),x=r['bits_next'])
    g,length=c.checked_add(c.AND(g,c.NOT(done)),r['bits_length'],1)
    store(g,(C.VECTOR_CELL,c.mux(c.word_lsb(r['bits_word']),1,0),r['bits_head'],0),12,
        bits_head=r['free'],bits_length=length,bits_position=c.add(r['bits_position'],1),bits_word=c.word_shr1(r['bits_word']))
    reverse(at(16),17,r['bits_head'],r['bits_length'])
    g=at(17,C.VECTOR);finish(g,(C.NAT_BITS,n['a'],n['b'],0))

    # Canonical little-endian bits ->16bit limbs.
    g=valid_head(at(20,C.NAT_BITS),0)
    go(g,21,bits_remaining=n['a'],bits_head=0,bits_length=0,bits_position=0,bits_word=0,bits_factor=1,x=n['b'])
    g=at(21);empty=c.eq(r['bits_remaining'],0);go(c.AND(g,empty),26)
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.VECTOR_CELL))
    g=check(c.AND(g,c.NOT(empty)),valid);g=valid_cell(g,r['bits_remaining'],True)
    representable=c.OR(c.lt(r['bits_position'],c.width),c.eq(n['a'],0))
    c.stop(c.AND(g,c.NOT(representable)),Outcome.RESOURCE,Reason.INDEX);g=c.AND(g,representable)
    value=c.add(r['bits_word'],c.mux(c.eq(n['a'],0),0,r['bits_factor']))
    last=c.eq(r['bits_remaining'],1);full=c.eq(r['bits_position'],15)
    go(c.AND(g,c.NOT(last),c.NOT(full)),21,x=n['b'],bits_remaining=c.sub(r['bits_remaining'],1),bits_position=c.add(r['bits_position'],1),bits_factor=c.word_shl1(r['bits_factor']),bits_word=value)
    g,length=c.checked_add(c.AND(g,c.OR(last,full)),r['bits_length'],1)
    store(g,(C.VECTOR_CELL,value,r['bits_head'],0),21,bits_head=r['free'],bits_length=length,
        bits_word=0,bits_factor=1,bits_position=0,x=n['b'],bits_remaining=c.sub(r['bits_remaining'],1))
    reverse(at(26),27,r['bits_head'],r['bits_length'])
    g=at(27,C.VECTOR);finish(g,(C.VECTOR,n['a'],n['b'],V.LIMBS))

    # Pairwise low-to-high scans. Later differences dominate for comparison.
    g=valid_head(at(40,C.NAT_BITS),0)
    go(g,41,bits_left_count=n['a'],bits_left_cursor=n['b'],x=r['bits_peer'])
    g=valid_head(at(41,C.NAT_BITS),0);compare=op(Op.COMPARE)
    less=c.lt(r['bits_left_count'],n['a']);greater=c.lt(n['a'],r['bits_left_count'])
    c.ret(c.AND(g,compare,c.OR(less,greater)),c.mux(less,0,2))
    go(c.AND(g,c.NOT(c.AND(compare,c.OR(less,greater)))),42,bits_right_count=n['a'],bits_right_cursor=n['b'],bits_head=0,bits_length=0,bits_carry=0,bits_comparison=1)
    g=at(42);aempty=c.eq(r['bits_left_count'],0);bempty=c.eq(r['bits_right_count'],0);empty=c.AND(aempty,bempty)
    c.ret(c.AND(g,empty,op(Op.COMPARE)),r['bits_comparison'])
    gfinal=c.AND(g,empty,c.NOT(op(Op.COMPARE)));add_carry=c.AND(op(Op.ADD),c.NOT(c.eq(r['bits_carry'],0)))
    store(c.AND(gfinal,add_carry),(C.VECTOR_CELL,1,r['bits_head'],0),58,bits_head=r['free'],bits_length=c.add(r['bits_length'],1))
    go(c.AND(gfinal,c.NOT(add_carry)),58)
    go(c.AND(g,c.NOT(empty),aempty),44,bits_left_value=0)
    go(c.AND(g,c.NOT(empty),c.NOT(aempty)),43,x=r['bits_left_cursor'])
    g=valid_cell(at(43,C.VECTOR_CELL),r['bits_left_count'],True)
    go(g,44,bits_left_value=n['a'],bits_left_cursor=n['b'],bits_left_count=c.sub(r['bits_left_count'],1))
    g=at(44);bempty=c.eq(r['bits_right_count'],0)
    go(c.AND(g,bempty),46,bits_right_value=0)
    go(c.AND(g,c.NOT(bempty)),45,x=r['bits_right_cursor'])
    g=valid_cell(at(45,C.VECTOR_CELL),r['bits_right_count'],True)
    go(g,46,bits_right_value=n['a'],bits_right_cursor=n['b'],bits_right_count=c.sub(r['bits_right_count'],1))
    g=at(46);a,b=r['bits_left_value'],r['bits_right_value'];compare=op(Op.COMPARE)
    same=c.eq(a,b);relation=c.mux(same,r['bits_comparison'],c.mux(c.lt(a,b),0,2))
    go(c.AND(g,compare),42,bits_comparison=relation)
    add=c.add(c.add(a,b),r['bits_carry']);sub=c.sub(c.sub(a,b),r['bits_carry'])
    total=c.mux(op(Op.SUB),sub,add)
    abit=c.NOT(c.eq(a,0));bbit=c.NOT(c.eq(b,0));xor=c.NOT(c.eq(a,b))
    bit=c.mux(op(Op.AND),c.mux(c.AND(abit,bbit),1,0),c.mux(op(Op.OR),c.mux(c.OR(abit,bbit),1,0),c.mux(op(Op.XOR),c.mux(xor,1,0),c.mux(c.word_lsb(total),1,0))))
    carry=c.mux(op(Op.SUB),c.mux(c.lt(a,c.add(b,r['bits_carry'])),1,0),c.word_shr1(add))
    g,length=c.checked_add(c.AND(g,c.NOT(compare)),r['bits_length'],1)
    store(g,(C.VECTOR_CELL,bit,r['bits_head'],0),42,bits_head=r['free'],bits_length=length,bits_carry=c.mux(c.OR(op(Op.ADD),op(Op.SUB)),carry,0))
    # A final subtraction borrow gives saturated zero. Strip high zero bits
    # from the reverse accumulator before producing a canonical output.
    g=at(58);negative=c.AND(op(Op.SUB),c.NOT(c.eq(r['bits_carry'],0)))
    finish(c.AND(g,negative),(C.NAT_BITS,0,0,0));go(c.AND(g,c.NOT(negative)),59,x=r['bits_head'])
    g=at(59);empty=c.eq(r['bits_length'],0)
    finish(c.AND(g,empty),(C.NAT_BITS,0,0,0))
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.VECTOR_CELL))
    g=check(c.AND(g,c.NOT(empty)),valid);zero=c.eq(n['a'],0)
    go(c.AND(g,zero),59,x=n['b'],bits_head=n['b'],bits_length=c.sub(r['bits_length'],1))
    reverse(c.AND(g,c.NOT(zero)),60,r['bits_head'],r['bits_length'])
    g=at(60,C.VECTOR);finish(g,(C.NAT_BITS,n['a'],n['b'],0))

    # Push a low bit: x ->2*x+bit, sharing the canonical higher-bit tail.
    g=valid_head(at(70,C.NAT_BITS),0);g=check(g,c.NOT(c.lt(1,r['bits_peer'])))
    zero=c.AND(c.eq(n['a'],0),c.eq(r['bits_peer'],0));c.ret(c.AND(g,zero),r['bits_input'])
    g,length=c.checked_add(c.AND(g,c.NOT(zero)),n['a'],1)
    store(g,(C.VECTOR_CELL,r['bits_peer'],n['b'],0),71,bits_head=r['free'],bits_length=length)
    finish(at(71),(C.NAT_BITS,r['bits_length'],r['bits_head'],0))

    # Shift by a physically represented unsigned count; arbitrary large shift
    # operands are classified by the high-level Nat controller before this call.
    g=valid_head(at(80,C.NAT_BITS),0);zero=c.OR(c.eq(n['a'],0),c.eq(r['bits_peer'],0))
    c.ret(c.AND(g,zero),r['bits_input'])
    g=c.AND(g,c.NOT(zero));right=c.NOT(c.eq(r['bits_direction'],0));overshift=c.NOT(c.lt(r['bits_peer'],n['a']))
    finish(c.AND(g,right,overshift),(C.NAT_BITS,0,0,0))
    go(c.AND(g,right,c.NOT(overshift)),83,bits_head=n['b'],bits_remaining=r['bits_peer'],bits_length=c.sub(n['a'],r['bits_peer']))
    g,length=c.checked_add(c.AND(g,c.NOT(right)),n['a'],r['bits_peer'])
    go(g,81,bits_head=n['b'],bits_length=length,bits_remaining=r['bits_peer'])
    g=at(81);done=c.eq(r['bits_remaining'],0)
    finish(c.AND(g,done),(C.NAT_BITS,r['bits_length'],r['bits_head'],0))
    store(c.AND(g,c.NOT(done)),(C.VECTOR_CELL,0,r['bits_head'],0),81,bits_head=r['free'],bits_remaining=c.sub(r['bits_remaining'],1))
    g=at(83);done=c.eq(r['bits_remaining'],0)
    finish(c.AND(g,done),(C.NAT_BITS,r['bits_length'],r['bits_head'],0))
    go(c.AND(g,c.NOT(done)),84,x=r['bits_head'])
    g=at(84,C.VECTOR_CELL);go(g,83,bits_head=n['b'],bits_remaining=c.sub(r['bits_remaining'],1))


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
