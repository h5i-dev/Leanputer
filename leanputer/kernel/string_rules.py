"""Weighted String literal signature validation and UTF8 helper construction.

Connected to original-source inference, conversion and major preparation.
All layouts are checked by general source algorithms. The only fixed
names/types are the genuine literal helpers in pinned inductive.cpp/Expr.lean.
"""
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason
from .quotient_templates import Syntax,Ref,name_syntax


NAMES=[('type',('String',)),('char',('Char',)),('list',('List',)),('nil',('List','nil')),
       ('cons',('List','cons')),('ofnat',('Char','ofNat')),('oflist',('String','ofList'))]


def templates():
    s=Syntax();levels=s.vector(['kernel_zero'],V.LEVELS)
    const=lambda key:(Tag.CONST,'string_symbol_'+key,'nat_empty_levels')
    list_=lambda:(Tag.CONST,'string_symbol_list',levels)
    def app(fn,*args):
        for a in args:fn=(Tag.APP,fn,a)
        return fn
    pi=lambda x,t,b:(Tag.PI,x,t,b,0)
    type0=(Tag.SORT,'nat_level_one');char=const('char');string=const('type')
    nt=(Tag.CONST,'nat_symbol_type','nat_empty_levels')
    la=app(list_(),'a');lc=app(list_(),char)
    exprs={'type':string,'char':char,'listchar':lc,'expected_type':type0,
        'expected_list':pi('a',type0,type0),'expected_nil':pi('a',type0,la),
        'expected_cons':pi('a',type0,pi('x','a',pi('xs',la,la))),
        'expected_ofnat':pi('n',nt,char),'expected_oflist':pi('xs',lc,string)}
    refs={key:s.expression(expr)for key,expr in exprs.items()}
    return s,refs,levels


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    if c.width<16:
        c.stop(c.AND(c.mode(Mode.WALK),c.OR(c.task(Task.STRING_BINDINGS),c.task(Task.STRING_LITERAL))),Outcome.RESOURCE,Reason.INDEX)
        return
    def controller(task,pcname):
        active=c.AND(c.task(task),c.mode(Mode.WALK))
        def at(pc,tag=None):
            g=c.AND(active,c.eq(r[pcname],pc))
            if tag is None:return g
            valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
            c.stop(c.AND(g,c.NOT(valid)),Outcome.GAP if task==Task.STRING_BINDINGS else Outcome.INVALID,
                Reason.GAP_PRIMITIVE if task==Task.STRING_BINDINGS else Reason.SYNTAX);return c.AND(g,valid)
        def go(g,pc,**kw):c.emit(g,**{pcname:pc},**kw)
        def call(g,pc,subtask,x,**kw):
            room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
            c.write('stack',g,r['sp'],(0,pc,0,task,0,0));c.emit(g,sp=c.add(r['sp'],1),task=subtask,mode=Mode.WALK,x=x,depth=0,**kw)
        def store(g,row,pc,**kw):
            room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
            c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
        def check(g,valid,primitive=False):
            c.stop(c.AND(g,c.NOT(valid)),Outcome.GAP if primitive else Outcome.INVALID,Reason.GAP_PRIMITIVE if primitive else Reason.SYNTAX)
            return c.AND(g,valid)
        returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],task))
        c.emit(returning,sp=top,task=task,mode=Mode.WALK,x=r['r'],**{pcname:f['original']})
        return at,go,call,store,check
    at,go,call,store,check=controller(Task.STRING_BINDINGS,'string_binding_pc')
    g=at(0);ready=c.NOT(c.eq(r['string_validated'],0));c.ret(c.AND(g,ready),1)
    call(c.AND(g,c.NOT(ready)),1,Task.NAT_BINDINGS,0,nat_binding_pc=0)
    go(at(1),100)
    def ptr(value,base):return c.add(r[base],value.index) if isinstance(value,Ref) else r[value] if isinstance(value,str) else value
    for index,(key,parts) in enumerate(NAMES):
        start=100+index*24;s,path=name_syntax(parts)
        go(at(start),start+1,string_name_base=r['free'])
        for i,row in enumerate(s.rows):store(at(start+1+i),tuple(ptr(v,'string_name_base')for v in row),start+2+i)
        call(at(start+1+len(s.rows)),start+2+len(s.rows),Task.INTERN_NAME_PATH,ptr(path,'string_name_base'))
        go(at(start+2+len(s.rows)),start+24 if index<6 else 300,**{'string_symbol_'+key:r['r']})
    s,refs,levels=templates();go(at(300),301,string_template_base=r['free'])
    for i,row in enumerate(s.rows):store(at(301+i),tuple(ptr(v,'string_template_base')for v in row),302+i)
    g=at(301+len(s.rows));go(g,500,string_list_levels=ptr(levels,'string_template_base'),**{'string_'+key:ptr(value,'string_template_base')for key,value in refs.items()})
    for index,(key,_) in enumerate(NAMES):
        pc=500+index*8;one=key in ('list','nil','cons')
        call(at(pc),pc+1,Task.ENV_LOOKUP,0,query_symbol=r['string_symbol_'+key],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
        go(at(pc+1),pc+2,x=r['r'])
        g=at(pc+2,C.CHECKED_SIGNATURE);go(g,pc+3,string_check_type=n['b'],x=n['c'])
        g=at(pc+3,C.CHECKED_SCHEME);go(g,pc+4,string_check_parameters=n['a'],x=n['a'])
        g=check(at(pc+4,C.VECTOR),c.AND(c.eq(n['c'],V.SYMBOLS),c.eq(n['a'],1 if one else 0)),True)
        call(g,pc+5,Task.INSTANTIATE_SCHEME,r['string_check_type'],parameter_vector=r['string_check_parameters'],level_vector=r['string_list_levels']if one else r['nat_empty_levels'])
        expected='string_expected_'+key if key not in ('type','char') else 'string_expected_type'
        call(at(pc+5),pc+6,Task.CONVERT_POSITIVE,r['r'],peer=r[expected])
        go(check(at(pc+6),c.NOT(c.eq(r['r'],0)),True),pc+8 if index<6 else 600)
    store(at(600),(Tag.CONST,r['string_symbol_nil'],r['string_list_levels'],0),601,string_nil=r['free'])
    store(at(601),(Tag.APP,r['string_nil'],r['string_char'],0),602,string_nil_char=r['free'])
    store(at(602),(Tag.CONST,r['string_symbol_cons'],r['string_list_levels'],0),603,string_cons=r['free'])
    store(at(603),(Tag.APP,r['string_cons'],r['string_char'],0),604,string_cons_char=r['free'])
    store(at(604),(Tag.CONST,r['string_symbol_ofnat'],r['nat_empty_levels'],0),605,string_ofnat_expression=r['free'])
    store(at(605),(Tag.CONST,r['string_symbol_oflist'],r['nat_empty_levels'],0),606,string_oflist_expression=r['free'])
    g=at(606);c.emit(g,string_validated=1,string_type_validated=1);c.ret(g,1)

    # Type inference does not depend on the Char/List/ofList expansion closure.
    from .literal_type_rules import emit_type_binding
    emit_type_binding(c,(at,go,call,store,lambda g,v:check(g,v,True)),700,'string',('String',))

    at,go,call,store,check=controller(Task.STRING_LITERAL,'string_pc')
    g=at(0,Tag.STRING);c.emit(g,string_vector=n['a'])
    call(g,1,Task.STRING_BINDINGS,0,string_binding_pc=c.mux(c.eq(r['string_operation'],0),700,0))
    go(at(1),2,x=r['string_vector'])
    g=check(at(2,C.VECTOR),c.AND(c.eq(n['c'],V.BYTES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1))))
    go(g,3,string_remaining=n['a'],string_cursor=n['b'],string_characters=0,string_accumulator=r['string_nil_char'])
    g=at(3);empty=c.eq(r['string_remaining'],0)
    go(c.AND(g,empty),30,x=r['string_characters'])
    go(c.AND(g,c.NOT(empty)),4,x=r['string_cursor'])
    def byte(g):
        valid=c.AND(c.lt(n['a'],256),c.NOT(c.eq(r['string_remaining'],0)),c.eq(c.mux(c.eq(n['b'],0),0,1),c.mux(c.lt(1,r['string_remaining']),1,0)))
        return check(g,valid)
    g=byte(at(4,C.VECTOR_CELL));a=n['a']
    ascii_=c.lt(a,128);two=c.AND(c.NOT(c.lt(a,194)),c.lt(a,224));three=c.AND(c.NOT(c.lt(a,224)),c.lt(a,240));four=c.AND(c.NOT(c.lt(a,240)),c.lt(a,245))
    valid=c.OR(ascii_,two,three,four);g=check(g,valid)
    c.emit(g,string_remaining=c.sub(r['string_remaining'],1),string_cursor=n['b'],string_code_high=0)
    go(c.AND(g,ascii_),10,string_code_low=a,string_total=1)
    go(c.AND(g,two),5,string_code_low=c.sub(a,192),string_needed=1,string_total=2)
    go(c.AND(g,three),5,string_code_low=c.sub(a,224),string_needed=2,string_total=3)
    go(c.AND(g,four),5,string_code_low=c.sub(a,240),string_needed=3,string_total=4)
    g=check(at(5),c.NOT(c.eq(r['string_remaining'],0)));go(g,6,x=r['string_cursor'])
    g=byte(at(6,C.VECTOR_CELL));g=check(g,c.AND(c.NOT(c.lt(n['a'],128)),c.lt(n['a'],192)))
    def shl(value,count):
        for _ in range(count):value=c.word_shl1(value)
        return value
    def shr(value,count):
        for _ in range(count):value=c.word_shr1(value)
        return value
    high=c.add(shl(r['string_code_high'],6),shr(r['string_code_low'],10))
    low=c.word_low_bits(c.add(shl(r['string_code_low'],6),c.sub(n['a'],128)),16)
    go(g,c.mux(c.eq(r['string_needed'],1),10,5),string_code_high=high,string_code_low=low,
        string_needed=c.sub(r['string_needed'],1),string_remaining=c.sub(r['string_remaining'],1),string_cursor=n['b'])
    g=at(10);lo,hi=r['string_code_low'],r['string_code_high']
    surrogate=c.AND(c.NOT(c.lt(lo,55296)),c.lt(lo,57344))
    valid=c.OR(c.eq(r['string_total'],1),c.AND(c.eq(r['string_total'],2),c.NOT(c.lt(lo,128))),
        c.AND(c.eq(r['string_total'],3),c.NOT(c.lt(lo,2048)),c.NOT(surrogate),c.eq(hi,0)),
        c.AND(c.eq(r['string_total'],4),c.NOT(c.eq(hi,0)),c.NOT(c.lt(16,hi))))
    g=check(g,valid);infer=c.eq(r['string_operation'],0)
    go(c.AND(g,infer),3)
    go(c.AND(g,c.NOT(infer)),11,string_limb_head=0,string_limb_count=0)
    g=at(11);nonzero=c.NOT(c.eq(r['string_code_high'],0))
    store(c.AND(g,nonzero),(C.VECTOR_CELL,r['string_code_high'],0,0),12,string_limb_head=r['free'],string_limb_count=1)
    go(c.AND(g,c.NOT(nonzero)),12)
    g=at(12);nonzero=c.OR(c.NOT(c.eq(r['string_code_low'],0)),c.NOT(c.eq(r['string_limb_count'],0)))
    store(c.AND(g,nonzero),(C.VECTOR_CELL,r['string_code_low'],r['string_limb_head'],0),13,string_limb_head=r['free'],string_limb_count=c.add(r['string_limb_count'],1))
    go(c.AND(g,c.NOT(nonzero)),13)
    store(at(13),(C.VECTOR,r['string_limb_count'],r['string_limb_head'],V.LIMBS),14,string_scalar_vector=r['free'])
    store(at(14),(Tag.NAT,r['string_scalar_vector'],0,0),15,string_scalar=r['free'])
    store(at(15),(Tag.APP,r['string_ofnat_expression'],r['string_scalar'],0),16,string_character=r['free'])
    store(at(16),(C.VECTOR_CELL,r['string_character'],r['string_characters'],0),3,string_characters=r['free'])
    g=at(30);infer=c.eq(r['string_operation'],0);c.ret(c.AND(g,infer),r['string_type'])
    empty=c.eq(r['string_characters'],0)
    go(c.AND(g,c.NOT(infer),empty),34)
    go(c.AND(g,c.NOT(infer),c.NOT(empty)),31,x=r['string_characters'])
    g=at(31,C.VECTOR_CELL);go(g,32,string_character=n['a'],string_characters=n['b'])
    store(at(32),(Tag.APP,r['string_cons_char'],r['string_character'],0),33,string_cons_partial=r['free'])
    store(at(33),(Tag.APP,r['string_cons_partial'],r['string_accumulator'],0),30,string_accumulator=r['free'])
    g=at(34);room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
    c.write('heap',g,r['free'],(Tag.APP,r['string_oflist_expression'],r['string_accumulator'],0));c.emit(g,free=c.add(r['free'],1));c.ret(g,r['free'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
