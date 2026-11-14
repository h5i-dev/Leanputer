"""Weighted Nat literal binding, inference and one-constructor preparation.

Only the genuine finite literal interface has fixed names. Nat formation and
its recursor are produced by the general original-source transaction. Values
are arbitrary canonical little-endian limb vectors, never bounded host ints.
"""
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason
from .quotient_templates import Ref,name_syntax


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    def controller(task,pcname):
        active=c.AND(c.task(task),c.mode(Mode.WALK))
        def at(pc,tag=None):
            g=c.AND(active,c.eq(r[pcname],pc))
            if tag is None:return g
            valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
            c.stop(c.AND(g,c.NOT(valid)),Outcome.GAP if task==Task.NAT_BINDINGS else Outcome.INVALID,Reason.GAP_PRIMITIVE if task==Task.NAT_BINDINGS else Reason.SYNTAX);return c.AND(g,valid)
        def go(g,pc,**kw):c.emit(g,**{pcname:pc},**kw)
        def call(g,pc,subtask,x,**kw):
            room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
            c.write('stack',g,r['sp'],(0,pc,0,task,0,0));c.emit(g,sp=c.add(r['sp'],1),task=subtask,mode=Mode.WALK,x=x,depth=0,**kw)
        def store(g,row,pc,**kw):
            room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
            c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
        def check(g,valid,reason=Reason.GAP_PRIMITIVE):
            # A missing or incompatible genuine primitive binding is an explicit
            # interface gap, never approval of an arbitrary ordinary declaration.
            c.stop(c.AND(g,c.NOT(valid)),Outcome.GAP,reason);return c.AND(g,valid)
        returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],task))
        c.emit(returning,sp=top,task=task,mode=Mode.WALK,x=r['r'],**{pcname:f['original']})
        return at,go,call,store,check
    at,go,call,store,check=controller(Task.NAT_BINDINGS,'nat_binding_pc')
    g=at(0);ready=c.NOT(c.eq(r['nat_validated'],0));c.ret(c.AND(g,ready),1);go(c.AND(g,c.NOT(ready)),100)
    for index,(key,parts) in enumerate([('type',('Nat',)),('zero',('Nat','zero')),('succ',('Nat','succ'))]):
        start=100+index*24;s,path=name_syntax(parts)
        go(at(start),start+1,nat_name_base=r['free'])
        def ptr(x):return c.add(r['nat_name_base'],x.index) if isinstance(x,Ref) else x
        for i,row in enumerate(s.rows):store(at(start+1+i),tuple(ptr(x) for x in row),start+2+i)
        call(at(start+1+len(s.rows)),start+2+len(s.rows),Task.INTERN_NAME_PATH,ptr(path))
        go(at(start+2+len(s.rows)),start+24 if index<2 else 1,**{'nat_symbol_'+key:r['r']})
    # Construct only the finite primitive's required types. Semantic comparison
    # uses the general conversion service, not a family/field-count shortcut.
    store(at(1),(C.VECTOR,0,0,V.LEVELS),2,nat_empty_levels=r['free'])
    store(at(2),(Tag.CONST,r['nat_symbol_type'],r['nat_empty_levels'],0),3,nat_type=r['free'])
    store(at(3),(C.LEVEL_SUCC,r['kernel_zero'],0,0),4,nat_level_one=r['free'])
    store(at(4),(Tag.SORT,r['nat_level_one'],0,0),5,nat_expected_type=r['free'])
    store(at(5),(Tag.PI,r['nat_type'],r['nat_type'],0),6,nat_expected_succ=r['free'])
    for index,(key,kind,expected) in enumerate([('type',8,'nat_expected_type'),('zero',9,'nat_type'),('succ',9,'nat_expected_succ')]):
        pc=10+index*8
        # Preserve the required prefix checking order and source provenance.
        if index==0:go(at(6),pc)
        call(at(pc),pc+1,Task.ENV_LOOKUP,0,query_symbol=r['nat_symbol_'+key],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
        go(at(pc+1),pc+2,x=r['r'])
        g=at(pc+2,C.CHECKED_SIGNATURE);go(g,pc+3,nat_check_type=n['b'],x=n['c'])
        if index==0:c.emit(g,nat_family_signature=r['x'])
        g=check(at(pc+3,C.CHECKED_SCHEME),c.eq(n['b'],kind));go(g,pc+4,x=n['a'])
        g=check(at(pc+4,C.VECTOR),c.AND(c.eq(n['a'],0),c.eq(n['b'],0),c.eq(n['c'],V.SYMBOLS)))
        call(g,pc+5,Task.CONVERT_POSITIVE,r['nat_check_type'],peer=r[expected])
        g=check(at(pc+5),c.NOT(c.eq(r['r'],0)))
        go(g,pc+8 if index<2 else 40)
    call(at(40),41,Task.FAMILY_INFO,r['nat_family_signature'],family_info_pc=0)
    go(at(41),42,x=r['r'])
    g=check(at(42,C.PROJECTION_FAMILY_INFO),c.AND(c.eq(n['a'],0),c.eq(n['b'],0)));go(g,43,x=n['c'])
    g=at(43,C.RAW_FAMILY);go(g,44,x=n['c'])
    g=at(44,C.RAW_FAMILY_AUX);go(g,45,x=n['a'])
    g=check(at(45,C.VECTOR),c.AND(c.eq(n['a'],2),c.eq(n['c'],V.REFERENCES)))
    go(g,46,x=n['b'],nat_binding_remaining=2,nat_binding_seen=0)
    g=at(46,C.VECTOR_CELL);go(g,47,x=n['a'],nat_binding_next=n['b'])
    g=at(47,C.RAW_CONSTRUCTOR);zero=c.eq(n['a'],r['nat_symbol_zero']);succ=c.eq(n['a'],r['nat_symbol_succ'])
    valid=c.AND(c.OR(zero,succ),c.OR(c.eq(r['nat_binding_seen'],0),c.AND(zero,c.eq(r['nat_binding_seen'],2)),c.AND(succ,c.eq(r['nat_binding_seen'],1))))
    g=check(g,valid);more=c.lt(1,r['nat_binding_remaining'])
    go(c.AND(g,more),46,x=r['nat_binding_next'],nat_binding_remaining=1,nat_binding_seen=c.mux(zero,1,2))
    c.emit(c.AND(g,c.NOT(more)),nat_validated=1,nat_type_validated=1);c.ret(c.AND(g,c.NOT(more)),1)

    from .literal_type_rules import emit_type_binding
    emit_type_binding(c,(at,go,call,store,check),300,'nat',('Nat',))

    at,go,call,store,check=controller(Task.NAT_LITERAL,'nat_literal_pc')
    g=at(0,Tag.NAT);c.emit(g,nat_literal_root=r['x'],nat_literal_vector=n['a'])
    call(g,1,Task.NAT_BINDINGS,0,nat_binding_pc=c.mux(c.eq(r['nat_literal_operation'],0),300,0))
    go(at(1),2,x=r['nat_literal_vector'])
    g=at(2,C.VECTOR);shape=c.AND(c.eq(n['c'],V.LIMBS),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    c.stop(c.AND(g,c.NOT(shape)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,shape)
    go(g,3,nat_limb_remaining=n['a'],nat_limb_cursor=n['b'],nat_limb_head=0,nat_limb_count=0,nat_borrow=1,x=n['b'])
    g=at(3);empty=c.eq(r['nat_limb_remaining'],0)
    go(c.AND(g,empty),7)
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.VECTOR_CELL))
    c.stop(c.AND(g,c.NOT(empty),c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,c.NOT(empty),valid)
    more=c.lt(1,r['nat_limb_remaining']);borrow=c.NOT(c.eq(r['nat_borrow'],0));zero=c.eq(n['a'],0)
    valid=c.AND(c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(more,1,0)),c.OR(more,c.NOT(zero)))
    if c.width>16:valid=c.AND(valid,c.lt(n['a'],65536))
    c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,valid)
    go(g,4,nat_limb_next=n['b'],nat_limb_value=c.mux(borrow,c.sub(n['a'],1),n['a']),nat_borrow=c.mux(c.AND(borrow,zero),1,0),nat_limb_drop=c.mux(c.AND(c.NOT(more),borrow,c.eq(n['a'],1)),1,0))
    if c.width<16:
        # A borrow across a zero limb creates65535, which must fit the physical
        # word. Never silently narrow that actual data value to the word mask.
        c.stop(c.AND(g,borrow,zero,c.NOT(c.eq(r['nat_literal_operation'],0))),Outcome.RESOURCE,Reason.INDEX)
    g=at(4);infer=c.eq(r['nat_literal_operation'],0);drop=c.NOT(c.eq(r['nat_limb_drop'],0))
    go(c.AND(g,c.OR(infer,drop)),6)
    store(c.AND(g,c.NOT(infer),c.NOT(drop)),(C.VECTOR_CELL,r['nat_limb_value'],r['nat_limb_head'],0),6,nat_limb_head=r['free'],nat_limb_count=c.add(r['nat_limb_count'],1))
    g=at(6);more=c.lt(1,r['nat_limb_remaining'])
    go(c.AND(g,more),3,x=r['nat_limb_next'],nat_limb_remaining=c.sub(r['nat_limb_remaining'],1))
    go(c.AND(g,c.NOT(more)),7,nat_limb_remaining=0)
    g=at(7);infer=c.eq(r['nat_literal_operation'],0)
    c.ret(c.AND(g,infer),r['nat_type'])
    go(c.AND(g,c.NOT(infer),c.eq(r['nat_limb_count'],0)),8)
    go(c.AND(g,c.NOT(infer),c.NOT(c.eq(r['nat_limb_count'],0))),9,nat_limb_cursor=r['nat_limb_head'],nat_limb_head=0,nat_limb_remaining=r['nat_limb_count'])
    # The original zero literal uses Nat.zero; positive1 has an empty predecessor.
    go(at(8),12,x=r['nat_literal_vector'])
    g=at(12,C.VECTOR);is_zero=c.eq(n['a'],0)
    store(c.AND(g,is_zero),(Tag.CONST,r['nat_symbol_zero'],r['nat_empty_levels'],0),15,nat_literal_result=r['free'])
    store(c.AND(g,c.NOT(is_zero)),(C.VECTOR,0,0,V.LIMBS),13,nat_predecessor_vector=r['free'])
    go(at(9),10,x=r['nat_limb_cursor'])
    g=at(10,C.VECTOR_CELL)
    store(g,(C.VECTOR_CELL,n['a'],r['nat_limb_head'],0),11,nat_limb_head=r['free'],nat_limb_cursor=n['b'])
    g=at(11);more=c.lt(1,r['nat_limb_remaining'])
    go(c.AND(g,more),9,nat_limb_remaining=c.sub(r['nat_limb_remaining'],1))
    store(c.AND(g,c.NOT(more)),(C.VECTOR,r['nat_limb_count'],r['nat_limb_head'],V.LIMBS),13,nat_predecessor_vector=r['free'])
    store(at(13),(Tag.NAT,r['nat_predecessor_vector'],0,0),14,nat_predecessor=r['free'])
    store(at(14),(Tag.CONST,r['nat_symbol_succ'],r['nat_empty_levels'],0),16,nat_succ_expression=r['free'])
    store(at(16),(Tag.APP,r['nat_succ_expression'],r['nat_predecessor'],0),15,nat_literal_result=r['free'])
    c.ret(at(15),r['nat_literal_result'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
