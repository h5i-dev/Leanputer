"""General typed conversion controller (fixed kernel algorithm; DEVELOPMENT).

Task-owned frames retain normalized pairs and context marks across recursive
conversion/inference/WHNF. Primitive-dependent negative boundaries remain GAP.
No native loader can enter this controller or supply a comparison certificate.
"""
from enum import IntEnum
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


class L(IntEnum):
    INIT=0; RIGHT=1; LEFT_CELL=2; RIGHT_CELL=3; COMPARED=4


def emit_level_vector_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.LEVELS_EQUIVALENT),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['levels_eq_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,levels_eq_pc=pc,**kw)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.LEVELS_EQUIVALENT))
    c.emit(returning,sp=top,task=Task.LEVELS_EQUIVALENT,mode=Mode.WALK,levels_eq_pc=L.COMPARED)
    g=at(L.INIT,C.VECTOR);valid=c.eq(n['c'],V.LEVELS)
    c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    go(c.AND(g,valid),L.RIGHT,levels_eq_count=n['a'],levels_eq_left=n['b'],x=r['peer'])
    g=at(L.RIGHT,C.VECTOR);valid=c.eq(n['c'],V.LEVELS)
    c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,valid)
    same=c.eq(n['a'],r['levels_eq_count']);empty=c.eq(n['a'],0)
    c.ret(c.AND(g,c.NOT(same)),0);c.ret(c.AND(g,same,empty),1)
    go(c.AND(g,same,c.NOT(empty)),L.LEFT_CELL,levels_eq_right=n['b'],x=r['levels_eq_left'])
    g=at(L.LEFT_CELL,C.VECTOR_CELL);go(g,L.RIGHT_CELL,levels_eq_value=n['a'],levels_eq_left=n['b'],x=r['levels_eq_right'])
    g=at(L.RIGHT_CELL,C.VECTOR_CELL);room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
    c.write('stack',g,r['sp'],(0,0,0,Task.LEVELS_EQUIVALENT,0,0))
    c.emit(g,sp=c.add(r['sp'],1),levels_eq_right=n['b'],task=Task.LEVEL_EQUIVALENT,mode=Mode.WALK,x=r['levels_eq_value'],peer=n['a'])
    g=at(L.COMPARED);same=c.NOT(c.eq(r['r'],0));last=c.eq(r['levels_eq_count'],1)
    c.ret(c.AND(g,c.NOT(same)),0);c.ret(c.AND(g,same,last),1)
    go(c.AND(g,same,c.NOT(last)),L.LEFT_CELL,levels_eq_count=c.sub(r['levels_eq_count'],1),x=r['levels_eq_left'])


class P(IntEnum):
    INIT=0; FAST=1; QUICK_LEFT=2; QUICK_RIGHT=3; LEFT_WHNF=4; RIGHT_WHNF=5; NORMAL_FAST=6
    DECIDED=7; BINDER_DOMAINS=8; BINDER_LOCAL=9; BINDER_FRESH=10; BINDER_LEFT=11
    BINDER_RIGHT=12; BINDER_COMPARE=13; PROOF_TYPE=14; PROOF_SORT_TYPE=15; PROOF_SORT=16
    PROOF_PROP=17; PROOF_OTHER=18; PROOF_COMPARE=19; RIGID_LEFT=20; RIGID_RIGHT=21
    RIGID_LEVELS=22; PROJECTION_COMPARE=23; APP_LEFT=24; APP_RIGHT=25; APP_SETUP=26
    APP_LEFT_SPINE=27; APP_RIGHT_SPINE=28; APP_HEAD_RECORD=29; APP_HEAD=30
    APP_HEAD_DONE=31; APP_COUNTS=32; APP_COUNT_RIGHT=33; APP_LOOP=34; APP_LEFT_HEADER=35
    APP_LEFT_ARGUMENT=36; APP_RIGHT_ARGUMENT_START=37; APP_RIGHT_ARGUMENT=38; APP_COMPARE=39
    APP_COMPARED=40; APP_ADVANCE=41; ETA_LEFT=42; ETA_RIGHT=43; ETA_TYPE=44
    ETA_PI=45; ETA_DOMAINS=46; ETA_BINDER=47; ETA_FRESH=48; ETA_APPLY=49; ETA_BODY=50
    ETA_COMPARED=51; STRUCTURE_START=52; UNIT_START=53; NEGATIVE=54; NEGATIVE_OTHER=55
    PROOF_BEGIN=56; BINDER_INSTANTIATE=57; ETA_SETUP=58; ETA_SETUP_DOMAIN=59
    APP_BEGIN=60; BINDER_RESULT=61; UNIT_TYPE=62; UNIT_SPINE=63; UNIT_HEAD=64
    UNIT_OWNER=65; UNIT_INFO=66; UNIT_DETAIL=67; UNIT_OTHER=68; UNIT_COMPARE=69
    STRUCTURE_ORIENT=70; STRUCTURE_SPINE=71; STRUCTURE_HEAD=72; STRUCTURE_LOOKUP=73
    STRUCTURE_SIG=74; STRUCTURE_SCHEME=75; STRUCTURE_CTOR_META=76; STRUCTURE_INFO=77
    STRUCTURE_READY=78; STRUCTURE_DETAILS=79; STRUCTURE_ARITY=80; STRUCTURE_TYPES=81
    STRUCTURE_LEFT_TYPE=82; STRUCTURE_RIGHT_TYPE=83; STRUCTURE_TYPE_COMPARE=84
    STRUCTURE_TYPE_RESULT=85; STRUCTURE_LOOP=86; STRUCTURE_LOOP_DETAIL=87
    STRUCTURE_VALUE=88; STRUCTURE_MAKE_PROJECTION=89; STRUCTURE_ARGUMENT=90
    STRUCTURE_FIELD_COMPARE=91; STRUCTURE_FIELD_RESULT=92; STRUCTURE_ADVANCE=93
    STRUCTURE_FAILED=94; STRUCTURE_NEXT=95; UNIT_READY=96; NEGATIVE_SPINE=97
    NEGATIVE_HEAD=98; NEGATIVE_RIGHT_SPINE=99; NEGATIVE_RIGHT_HEAD=100
    BINDER_RIGHT_BODY=101; BINDER_JOIN=102; BINDER_JOIN_READ=103; RIGID_BEGIN=104
    UNIT_TYPE_START=105; APP_LOOP_INFO=106; APP_CONTEXT=107
    APP_ARGUMENT_COUNTS=108; APP_ARGUMENT_PAIR=109; APP_RIGHT_SELECT=110; APP_ARGUMENT_COMPARE=111
    ETA_FIRST=112; ETA_SELECT=113; ETA_LAMBDA=114; ETA_DOMAIN_READ=115; ETA_LOCAL_READ=116; ETA_FINAL_READ=117
    STRUCTURE_SCAN=118; STRUCTURE_ARITY_VECTOR=119; STRUCTURE_TYPE_VALUE=120
    STRUCTURE_LEFT_FOUND=121; STRUCTURE_OTHER_SCAN=122; STRUCTURE_OTHER_VALUE=123
    STRUCTURE_TYPE_RESULT_READ=124; STRUCTURE_LOOP_COUNT=125; STRUCTURE_LOOP_SCAN=126
    STRUCTURE_LOOP_VALUE=127; STRUCTURE_FIELD_RECORD=128; STRUCTURE_FIELD_READ=129
    STRUCTURE_FIELD_RESULT_READ=130; STRUCTURE_ADVANCE_READ=131; UNIT_WHNF=132
    UNIT_SPINE_READ=133; NEGATIVE_LEFT=134


def emit_rules(c):
    emit_level_vector_rules(c)
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.CONVERT),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['convert_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def frame(g,phase=None,left=None,right=None,info=None):
        c.write('stack',g,top,(f['phase'] if phase is None else phase,f['original'] if left is None else left,
            f['depth'] if right is None else right,Task.CONVERT,f['first'],f['second'] if info is None else info))
    def go(g,pc,**kw):c.emit(g,convert_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        frame(g,phase=pc);c.emit(g,task=task,mode=mode,x=x,depth=0,**kw)
    def finish(g,result):c.emit(g,sp=top,task=Task.CONVERT_POSITIVE,ctx=f['first']);c.ret(g,result)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);c.emit(g,free=c.add(r['free'],1));go(g,pc,**kw);return g
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.CONVERT))
    c.emit(returning,task=Task.CONVERT,mode=Mode.WALK,convert_pc=f['phase'],x=r['r'])
    init=at(P.INIT);zero=c.eq(r['kernel_zero'],0);heap=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(init,zero,c.NOT(heap)),Outcome.RESOURCE,Reason.HEAP)
    z=c.AND(init,zero,heap);c.write('heap',z,r['free'],(C.LEVEL_ZERO,0,0,0));c.emit(z,kernel_zero=r['free'],free=c.add(r['free'],1))
    g=c.AND(init,c.NOT(zero));room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
    c.write('stack',g,r['sp'],(P.FAST,r['x'],r['peer'],Task.CONVERT,r['ctx'],0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.EXPR_EQUAL)
    for pc in (P.FAST,P.NORMAL_FAST):
        g=at(pc);same=c.NOT(c.eq(r['r'],0));finish(c.AND(g,same),1)
        go(c.AND(g,c.NOT(same)),P.QUICK_LEFT,x=f['original'])
    g=at(P.QUICK_LEFT)
    c.emit(g,left_tag=n['tag'],left_a=n['a'],left_b=n['b'],left_c=n['c']);go(g,P.QUICK_RIGHT,x=f['depth'])
    g=at(P.QUICK_RIGHT);same=c.eq(n['tag'],r['left_tag']);sort=c.AND(same,c.tag(Tag.SORT));literal=c.AND(same,c.tag(Tag.NAT,Tag.STRING));metadata=c.AND(same,c.tag(Tag.MDATA));binder=c.AND(same,c.tag(Tag.PI,Tag.LAM))
    call(c.AND(g,sort),P.DECIDED,Task.LEVEL_EQUIVALENT,r['left_a'],peer=n['a'])
    call(c.AND(g,literal),P.DECIDED,Task.VECTOR_EQUAL,r['left_a'],peer=n['a'],vector_expected_role=c.mux(c.tag(Tag.NAT),V.LIMBS,V.BYTES))
    call(c.AND(g,metadata),P.DECIDED,Task.CONVERT_POSITIVE,r['left_a'],peer=n['a'])
    b=store(c.AND(g,binder),(C.CONVERT_BINDER,r['left_b'],n['b'],n['a']),P.BINDER_DOMAINS,x=r['left_a'],peer=n['a']);frame(b,info=r['free'])
    other=c.AND(g,c.NOT(c.OR(sort,literal,metadata,binder)));normalized=c.eq(f['second'],1)
    call(c.AND(other,c.NOT(normalized)),P.LEFT_WHNF,Task.BETA_ZETA,f['original'],Mode.BETA_ZETA)
    go(c.AND(other,normalized),P.PROOF_BEGIN)
    g=at(P.LEFT_WHNF);frame(g,left=r['r'],phase=P.RIGHT_WHNF);c.emit(g,task=Task.BETA_ZETA,mode=Mode.BETA_ZETA,x=f['depth'],depth=0)
    g=at(P.RIGHT_WHNF);frame(g,right=r['r'],info=1,phase=P.NORMAL_FAST);c.emit(g,task=Task.EXPR_EQUAL,mode=Mode.WALK,x=f['original'],peer=r['r'],depth=0)
    finish(at(P.DECIDED),r['r'])
    call(at(P.BINDER_DOMAINS),P.BINDER_LOCAL,Task.CONVERT_POSITIVE,r['x'])
    g=at(P.BINDER_LOCAL);ok=c.NOT(c.eq(r['r'],0));finish(c.AND(g,c.NOT(ok)),0);go(c.AND(g,ok),P.BINDER_FRESH,x=f['second'])
    g=at(P.BINDER_FRESH,C.CONVERT_BINDER);call(g,P.BINDER_LEFT,Task.FRESH_LOCAL,n['c'],binder_info=0)
    g=at(P.BINDER_LEFT);go(g,P.BINDER_INSTANTIATE,x=f['second'],substitution=r['r'])
    g=at(P.BINDER_INSTANTIATE,C.CONVERT_BINDER)
    b=store(g,(C.CONVERT_BINDER,n['a'],n['b'],r['substitution']),P.BINDER_RIGHT,x=n['a']);frame(b,info=r['free'])
    call(at(P.BINDER_RIGHT),P.BINDER_COMPARE,Task.INSTANTIATE_ONE,r['x'])
    g=at(P.BINDER_COMPARE);go(g,P.BINDER_RESULT,x=f['second'])
    g=at(P.BINDER_RESULT,C.CONVERT_BINDER)
    b=store(g,(C.CONVERT_BINDER,r['r'],n['b'],n['c']),P.BINDER_RIGHT_BODY,x=n['b'],substitution=n['c']);frame(b,info=r['free'])
    call(at(P.BINDER_RIGHT_BODY),P.BINDER_JOIN,Task.INSTANTIATE_ONE,r['x'])
    go(at(P.BINDER_JOIN),P.BINDER_JOIN_READ,x=f['second'])
    g=at(P.BINDER_JOIN_READ,C.CONVERT_BINDER);call(g,P.DECIDED,Task.CONVERT_POSITIVE,n['a'],peer=r['r'])
    call(at(P.PROOF_BEGIN),P.PROOF_TYPE,Task.INFER,f['original'])
    g=at(P.PROOF_TYPE);frame(g,info=r['r'],phase=P.PROOF_SORT_TYPE);c.emit(g,task=Task.INFER,mode=Mode.WALK,x=r['r'],depth=0)
    call(at(P.PROOF_SORT_TYPE),P.PROOF_SORT,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    g=at(P.PROOF_SORT,Tag.SORT);call(g,P.PROOF_PROP,Task.LEVEL_EQUIVALENT,n['a'],peer=r['kernel_zero'])
    g=at(P.PROOF_PROP);prop=c.NOT(c.eq(r['r'],0))
    call(c.AND(g,prop),P.PROOF_OTHER,Task.INFER,f['depth'])
    go(c.AND(g,c.NOT(prop)),P.RIGID_BEGIN)
    call(at(P.PROOF_OTHER),P.DECIDED,Task.CONVERT_POSITIVE,f['second'],peer=r['r'])
    go(at(P.RIGID_BEGIN),P.RIGID_LEFT,x=f['original'])
    g=at(P.RIGID_LEFT);c.emit(g,left_tag=n['tag'],left_a=n['a'],left_b=n['b'],left_c=n['c']);go(g,P.RIGID_RIGHT,x=f['depth'])
    g=at(P.RIGID_RIGHT);same=c.eq(n['tag'],r['left_tag'])
    const=c.AND(same,c.tag(Tag.CONST),c.eq(n['a'],r['left_a']))
    local=c.AND(same,c.tag(Tag.LOCAL),c.eq(n['a'],r['left_a']))
    projection=c.AND(same,c.tag(Tag.PROJ),c.eq(n['b'],r['left_b']))
    call(c.AND(g,const),P.RIGID_LEVELS,Task.LEVELS_EQUIVALENT,r['left_b'],peer=n['b'],levels_eq_pc=0)
    finish(c.AND(g,local),1)
    call(c.AND(g,projection),P.PROJECTION_COMPARE,Task.CONVERT_POSITIVE,r['left_c'],peer=n['c'])
    go(c.AND(g,c.NOT(c.OR(const,local,projection))),P.APP_BEGIN)
    for pc in (P.RIGID_LEVELS,P.PROJECTION_COMPARE):
        g=at(pc);equal=c.NOT(c.eq(r['r'],0));finish(c.AND(g,equal),1);go(c.AND(g,c.NOT(equal)),P.APP_BEGIN)
    go(at(P.APP_BEGIN),P.APP_LEFT,x=f['original'])
    g=at(P.APP_LEFT);app=c.tag(Tag.APP);go(c.AND(g,c.NOT(app)),P.ETA_LEFT,x=f['original'])
    go(c.AND(g,app),P.APP_RIGHT,x=f['depth'])
    g=at(P.APP_RIGHT);app=c.tag(Tag.APP);go(c.AND(g,c.NOT(app)),P.ETA_LEFT,x=f['original'])
    call(c.AND(g,app),P.APP_SETUP,Task.APPLICATION_SPINE,f['original'])
    g=at(P.APP_SETUP);frame(g,info=r['r'],phase=P.APP_LEFT_SPINE);c.emit(g,task=Task.APPLICATION_SPINE,mode=Mode.WALK,x=f['depth'],depth=0)
    g=at(P.APP_LEFT_SPINE,C.APPLICATION_SPINE)
    b=store(g,(C.CONVERT_PAIR,f['second'],r['x'],0),P.APP_RIGHT_SPINE,x=f['second']);frame(b,info=r['free'])
    g=at(P.APP_RIGHT_SPINE,C.APPLICATION_SPINE);c.emit(g,slice_body=n['a'],splice_prefix_head=n['b']);go(g,P.APP_HEAD_RECORD,x=f['second'])
    g=at(P.APP_HEAD_RECORD,C.CONVERT_PAIR);go(g,P.APP_HEAD,x=n['b'])
    g=at(P.APP_HEAD,C.APPLICATION_SPINE)
    b=store(g,(C.CONVERT_PAIR,r['slice_body'],n['a'],0),P.APP_CONTEXT,peer=n['b']);frame(b,info=r['free'])
    # The argument vectors outlive recursive comparison of the two heads.
    g=at(P.APP_CONTEXT)
    b=store(g,(C.CONVERT_APP,r['splice_prefix_head'],r['peer'],f['second']),P.APP_COUNTS,x=f['second']);frame(b,info=r['free'])
    g=at(P.APP_COUNTS,C.CONVERT_PAIR);call(g,P.APP_HEAD_DONE,Task.CONVERT_POSITIVE,n['a'],peer=n['b'])
    g=at(P.APP_HEAD_DONE);same=c.NOT(c.eq(r['r'],0));go(c.AND(g,c.NOT(same)),P.ETA_LEFT,x=f['original'])
    go(c.AND(g,same),P.APP_COUNT_RIGHT,x=f['second'])
    g=at(P.APP_COUNT_RIGHT,C.CONVERT_APP);c.emit(g,splice_prefix_head=n['a'],splice_tail=n['b']);go(g,P.APP_LEFT_HEADER,x=n['a'])
    g=at(P.APP_LEFT_HEADER,C.VECTOR);c.emit(g,reference_remaining=n['a']);go(g,P.APP_ARGUMENT_COUNTS,x=r['splice_tail'])
    g=at(P.APP_ARGUMENT_COUNTS,C.VECTOR);same=c.eq(n['a'],r['reference_remaining'])
    go(c.AND(g,c.NOT(same)),P.ETA_LEFT,x=f['original'])
    b=store(c.AND(g,same),(C.CONVERT_LOOP,f['second'],0,0),P.APP_LOOP,x=r['free']);frame(b,info=r['free'])
    g=at(P.APP_LOOP,C.CONVERT_LOOP);c.emit(g,vector_index=n['b']);go(g,P.APP_LOOP_INFO,x=n['a'])
    g=at(P.APP_LOOP_INFO,C.CONVERT_APP);c.emit(g,splice_tail=n['b']);go(g,P.APP_ARGUMENT_PAIR,x=n['a'])
    g=at(P.APP_ARGUMENT_PAIR,C.VECTOR);done=c.NOT(c.lt(r['vector_index'],n['a']))
    finish(c.AND(g,done),1);call(c.AND(g,c.NOT(done)),P.APP_LEFT_ARGUMENT,Task.VECTOR_REFERENCE,r['x'])
    go(at(P.APP_LEFT_ARGUMENT),P.APP_RIGHT_ARGUMENT_START,x=f['second'])
    g=at(P.APP_RIGHT_ARGUMENT_START,C.CONVERT_LOOP)
    b=store(g,(C.CONVERT_LOOP,n['a'],n['b'],r['r']),P.APP_RIGHT_SELECT,x=n['a'],vector_index=n['b']);frame(b,info=r['free'])
    g=at(P.APP_RIGHT_SELECT,C.CONVERT_APP);call(g,P.APP_RIGHT_ARGUMENT,Task.VECTOR_REFERENCE,n['b'])
    go(at(P.APP_RIGHT_ARGUMENT),P.APP_ARGUMENT_COMPARE,x=f['second'])
    g=at(P.APP_ARGUMENT_COMPARE,C.CONVERT_LOOP);call(g,P.APP_COMPARED,Task.CONVERT_POSITIVE,n['c'],peer=r['r'])
    g=at(P.APP_COMPARED);same=c.NOT(c.eq(r['r'],0));go(c.AND(g,c.NOT(same)),P.ETA_LEFT,x=f['original'])
    go(c.AND(g,same),P.APP_ADVANCE,x=f['second'])
    g=at(P.APP_ADVANCE,C.CONVERT_LOOP)
    b=store(g,(C.CONVERT_LOOP,n['a'],c.add(n['b'],1),0),P.APP_LOOP,x=r['free']);frame(b,info=r['free'])
    # Exactly one normalized side may be lambda here; two lambdas were decided
    # by the pinned quick binding rule before proof/eta processing.
    g=at(P.ETA_LEFT);lam=c.tag(Tag.LAM)
    go(c.AND(g,lam),P.ETA_FIRST,x=f['depth'])
    go(c.AND(g,c.NOT(lam)),P.ETA_RIGHT,x=f['depth'])
    g=at(P.ETA_FIRST);other_lam=c.tag(Tag.LAM)
    go(c.AND(g,other_lam),P.STRUCTURE_START)
    go(c.AND(g,c.NOT(other_lam)),P.ETA_SELECT,x=f['original'])
    g=at(P.ETA_SELECT,Tag.LAM)
    b=store(g,(C.CONVERT_BINDER,n['b'],n['a'],f['depth']),P.ETA_TYPE,x=f['depth']);frame(b,info=r['free'])
    g=at(P.ETA_RIGHT);lam=c.tag(Tag.LAM)
    go(c.AND(g,c.NOT(lam)),P.STRUCTURE_START)
    b=store(c.AND(g,lam),(C.CONVERT_BINDER,n['b'],n['a'],f['original']),P.ETA_TYPE,x=f['original']);frame(b,info=r['free'])
    call(at(P.ETA_TYPE),P.ETA_PI,Task.INFER,r['x'])
    call(at(P.ETA_PI),P.ETA_SETUP,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    g=at(P.ETA_SETUP);pi=c.tag(Tag.PI);go(c.AND(g,c.NOT(pi)),P.STRUCTURE_START)
    b=store(c.AND(g,pi),(C.CONVERT_ETA,f['second'],n['a'],n['c']),P.ETA_SETUP_DOMAIN,x=f['second']);frame(b,info=r['free'])
    g=at(P.ETA_SETUP_DOMAIN,C.CONVERT_BINDER);c.emit(g,slice_body=n['b']);go(g,P.ETA_DOMAIN_READ,x=f['second'])
    g=at(P.ETA_DOMAIN_READ,C.CONVERT_ETA);call(g,P.ETA_DOMAINS,Task.CONVERT_POSITIVE,r['slice_body'],peer=n['b'])
    g=at(P.ETA_DOMAINS);same=c.NOT(c.eq(r['r'],0));go(c.AND(g,c.NOT(same)),P.STRUCTURE_START)
    go(c.AND(g,same),P.ETA_BINDER,x=f['second'])
    g=at(P.ETA_BINDER,C.CONVERT_ETA);call(g,P.ETA_FRESH,Task.FRESH_LOCAL,n['b'],binder_info=n['c'])
    go(at(P.ETA_FRESH),P.ETA_LOCAL_READ,x=f['second'],substitution=r['r'])
    g=at(P.ETA_LOCAL_READ,C.CONVERT_ETA);go(g,P.ETA_APPLY,x=n['a'])
    g=at(P.ETA_APPLY,C.CONVERT_BINDER)
    b=store(g,(Tag.APP,n['c'],r['substitution'],0),P.ETA_FINAL_READ,x=n['a']);frame(b,info=r['free'])
    call(at(P.ETA_FINAL_READ),P.ETA_BODY,Task.INSTANTIATE_ONE,r['x'])
    call(at(P.ETA_BODY),P.ETA_COMPARED,Task.CONVERT_POSITIVE,r['r'],peer=f['second'])
    g=at(P.ETA_COMPARED);same=c.NOT(c.eq(r['r'],0));finish(c.AND(g,same),1)
    c.emit(c.AND(g,c.NOT(same)),ctx=f['first']);go(c.AND(g,c.NOT(same)),P.STRUCTURE_START)
    b=store(at(P.STRUCTURE_START),(C.CONVERT_ORIENTATION,f['original'],f['depth'],0),P.STRUCTURE_ORIENT,x=f['depth']);frame(b,info=r['free'])
    call(at(P.STRUCTURE_ORIENT),P.STRUCTURE_SPINE,Task.APPLICATION_SPINE,r['x'])
    g=at(P.STRUCTURE_SPINE,C.APPLICATION_SPINE)
    b=store(g,(C.CONVERT_SCAN,f['second'],n['b'],0),P.STRUCTURE_HEAD,x=n['a']);frame(b,info=r['free'])
    g=at(P.STRUCTURE_HEAD);constant=c.tag(Tag.CONST)
    go(c.AND(g,c.NOT(constant)),P.STRUCTURE_FAILED,x=f['second'])
    call(c.AND(g,constant),P.STRUCTURE_LOOKUP,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
    g=at(P.STRUCTURE_LOOKUP);found=c.NOT(c.eq(r['r'],0))
    go(c.AND(g,c.NOT(found)),P.STRUCTURE_FAILED,x=f['second']);go(c.AND(g,found),P.STRUCTURE_SIG,x=r['r'])
    g=at(P.STRUCTURE_SIG,C.CHECKED_SIGNATURE);go(g,P.STRUCTURE_SCHEME,x=n['c'])
    g=at(P.STRUCTURE_SCHEME,C.CHECKED_SCHEME);ctor=c.eq(n['b'],9)
    go(c.AND(g,c.NOT(ctor)),P.STRUCTURE_FAILED,x=f['second']);go(c.AND(g,ctor),P.STRUCTURE_CTOR_META,x=n['c'])
    g=at(P.STRUCTURE_CTOR_META,C.CHECKED_CONSTRUCTOR);call(g,P.STRUCTURE_INFO,Task.STRUCTURE_INFO,n['a'],structure_pc=0)
    g=at(P.STRUCTURE_INFO);found=c.NOT(c.eq(r['r'],0));go(c.AND(g,c.NOT(found)),P.STRUCTURE_FAILED,x=f['second'])
    go(c.AND(g,found),P.STRUCTURE_READY,x=r['r'])
    g=at(P.STRUCTURE_READY,C.STRUCTURE_INFO)
    b=store(g,(C.CONVERT_STRUCTURE,f['second'],r['x'],0),P.STRUCTURE_DETAILS,x=n['c'],slice_start=n['b']);frame(b,info=r['free'])
    g=at(P.STRUCTURE_DETAILS,C.STRUCTURE_DETAIL);g,total=c.checked_add(g,r['slice_start'],n['b'])
    go(g,P.STRUCTURE_ARITY,x=f['second'],reference_remaining=total)
    g=at(P.STRUCTURE_ARITY,C.CONVERT_STRUCTURE);go(g,P.STRUCTURE_SCAN,x=n['a'])
    g=at(P.STRUCTURE_SCAN,C.CONVERT_SCAN);go(g,P.STRUCTURE_ARITY_VECTOR,x=n['b'])
    g=at(P.STRUCTURE_ARITY_VECTOR,C.VECTOR);same=c.eq(n['a'],r['reference_remaining'])
    go(c.AND(g,c.NOT(same)),P.STRUCTURE_FAILED,x=f['second'])
    go(c.AND(g,same),P.STRUCTURE_TYPES,x=f['second'])
    g=at(P.STRUCTURE_TYPES,C.CONVERT_STRUCTURE);go(g,P.STRUCTURE_LEFT_TYPE,x=n['a'])
    g=at(P.STRUCTURE_LEFT_TYPE,C.CONVERT_SCAN);go(g,P.STRUCTURE_TYPE_VALUE,x=n['a'])
    g=at(P.STRUCTURE_TYPE_VALUE,C.CONVERT_ORIENTATION);call(g,P.STRUCTURE_LEFT_FOUND,Task.INFER,n['a'])
    g=at(P.STRUCTURE_LEFT_FOUND)
    b=store(g,(C.CONVERT_TYPES,f['second'],r['r'],0),P.STRUCTURE_RIGHT_TYPE,x=f['second']);frame(b,info=r['free'])
    g=at(P.STRUCTURE_RIGHT_TYPE,C.CONVERT_STRUCTURE);go(g,P.STRUCTURE_OTHER_SCAN,x=n['a'])
    g=at(P.STRUCTURE_OTHER_SCAN,C.CONVERT_SCAN);go(g,P.STRUCTURE_OTHER_VALUE,x=n['a'])
    g=at(P.STRUCTURE_OTHER_VALUE,C.CONVERT_ORIENTATION);call(g,P.STRUCTURE_TYPE_COMPARE,Task.INFER,n['b'])
    go(at(P.STRUCTURE_TYPE_COMPARE),P.STRUCTURE_TYPE_RESULT,x=f['second'])
    g=at(P.STRUCTURE_TYPE_RESULT,C.CONVERT_TYPES);call(g,P.STRUCTURE_TYPE_RESULT_READ,Task.CONVERT_POSITIVE,n['b'],peer=r['r'])
    go(at(P.STRUCTURE_TYPE_RESULT_READ),P.STRUCTURE_LOOP,x=f['second'])
    g=at(P.STRUCTURE_LOOP)
    types=c.tag(C.CONVERT_TYPES);checked=c.tag(C.CONVERT_STRUCTURE)
    # A type comparison first unwraps its temporary record, then enters the
    # same field loop used after every successful field comparison.
    ok=c.NOT(c.eq(r['r'],0))
    frame(c.AND(g,types),info=n['a'])
    go(c.AND(g,types,ok),P.STRUCTURE_LOOP,x=n['a'])
    go(c.AND(g,types,c.NOT(ok)),P.STRUCTURE_FAILED,x=n['a'])
    c.emit(c.AND(g,checked),vector_index=n['c']);go(c.AND(g,checked),P.STRUCTURE_LOOP_DETAIL,x=n['b'])
    c.stop(c.AND(g,c.NOT(c.OR(types,checked))),Outcome.INVALID,Reason.SYNTAX)
    g=at(P.STRUCTURE_LOOP_DETAIL,C.STRUCTURE_INFO)
    go(g,P.STRUCTURE_LOOP_COUNT,x=n['c'],query_symbol=n['a'],slice_start=n['b'])
    g=at(P.STRUCTURE_LOOP_COUNT,C.STRUCTURE_DETAIL);done=c.NOT(c.lt(r['vector_index'],n['b']))
    finish(c.AND(g,done),1)
    g,index=c.checked_add(c.AND(g,c.NOT(done)),r['slice_start'],r['vector_index'])
    go(g,P.STRUCTURE_VALUE,x=f['second'],slice_start=index)
    g=at(P.STRUCTURE_VALUE,C.CONVERT_STRUCTURE);go(g,P.STRUCTURE_LOOP_SCAN,x=n['a'])
    g=at(P.STRUCTURE_LOOP_SCAN,C.CONVERT_SCAN);go(g,P.STRUCTURE_LOOP_VALUE,x=n['a'],slice_body=n['b'])
    g=at(P.STRUCTURE_LOOP_VALUE,C.CONVERT_ORIENTATION)
    b=store(g,(Tag.PROJ,r['query_symbol'],r['vector_index'],n['a']),P.STRUCTURE_FIELD_RECORD,x=r['free'])
    g=at(P.STRUCTURE_FIELD_RECORD)
    b=store(g,(C.CONVERT_FIELD,f['second'],r['x'],r['slice_start']),P.STRUCTURE_ARGUMENT,x=r['slice_body']);frame(b,info=r['free'])
    call(at(P.STRUCTURE_ARGUMENT),P.STRUCTURE_FIELD_COMPARE,Task.VECTOR_REFERENCE,r['x'],vector_index=r['slice_start'])
    go(at(P.STRUCTURE_FIELD_COMPARE),P.STRUCTURE_FIELD_READ,x=f['second'])
    g=at(P.STRUCTURE_FIELD_READ,C.CONVERT_FIELD);call(g,P.STRUCTURE_FIELD_RESULT,Task.CONVERT_POSITIVE,n['b'],peer=r['r'])
    go(at(P.STRUCTURE_FIELD_RESULT),P.STRUCTURE_FIELD_RESULT_READ,x=f['second'])
    g=at(P.STRUCTURE_FIELD_RESULT_READ,C.CONVERT_FIELD);ok=c.NOT(c.eq(r['r'],0))
    frame(g,info=n['a']);go(c.AND(g,c.NOT(ok)),P.STRUCTURE_FAILED,x=n['a'])
    go(c.AND(g,ok),P.STRUCTURE_ADVANCE,x=n['a'])
    g=at(P.STRUCTURE_ADVANCE,C.CONVERT_STRUCTURE)
    b=store(g,(C.CONVERT_STRUCTURE,n['a'],n['b'],c.add(n['c'],1)),P.STRUCTURE_LOOP,x=r['free']);frame(b,info=r['free'])
    g=at(P.STRUCTURE_FAILED);orientation=c.tag(C.CONVERT_ORIENTATION)
    chain=c.tag(C.CONVERT_SCAN,C.CONVERT_STRUCTURE,C.CONVERT_TYPES,C.CONVERT_FIELD)
    go(c.AND(g,chain),P.STRUCTURE_FAILED,x=n['a'])
    second=c.NOT(c.eq(n['c'],0));go(c.AND(g,orientation,second),P.UNIT_START)
    b=store(c.AND(g,orientation,c.NOT(second)),(C.CONVERT_ORIENTATION,f['depth'],f['original'],1),P.STRUCTURE_ORIENT,x=f['original']);frame(b,info=r['free'])
    c.stop(c.AND(g,c.NOT(c.OR(orientation,chain))),Outcome.INVALID,Reason.SYNTAX)
    # Unit-like comparison uses checked structure metadata and inferred types.
    call(at(P.UNIT_START),P.UNIT_TYPE,Task.INFER,f['original'])
    call(at(P.UNIT_TYPE),P.UNIT_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    g=at(P.UNIT_WHNF);frame(g,info=r['r'],phase=P.UNIT_SPINE);c.emit(g,task=Task.APPLICATION_SPINE,mode=Mode.WALK,x=r['r'],depth=0)
    g=at(P.UNIT_SPINE,C.APPLICATION_SPINE);go(g,P.UNIT_HEAD,x=n['a'])
    g=at(P.UNIT_HEAD);constant=c.tag(Tag.CONST);go(c.AND(g,c.NOT(constant)),P.NEGATIVE,x=f['original'])
    call(c.AND(g,constant),P.UNIT_OWNER,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
    g=at(P.UNIT_OWNER);found=c.NOT(c.eq(r['r'],0));go(c.AND(g,c.NOT(found)),P.NEGATIVE,x=f['original'])
    call(c.AND(g,found),P.UNIT_INFO,Task.STRUCTURE_INFO,r['r'],structure_pc=0)
    g=at(P.UNIT_INFO);found=c.NOT(c.eq(r['r'],0));go(c.AND(g,c.NOT(found)),P.NEGATIVE,x=f['original'])
    go(c.AND(g,found),P.UNIT_READY,x=r['r'])
    g=at(P.UNIT_READY,C.STRUCTURE_INFO);go(g,P.UNIT_DETAIL,x=n['c'])
    g=at(P.UNIT_DETAIL,C.STRUCTURE_DETAIL);empty=c.eq(n['b'],0)
    go(c.AND(g,c.NOT(empty)),P.NEGATIVE,x=f['original']);call(c.AND(g,empty),P.UNIT_OTHER,Task.INFER,f['depth'])
    call(at(P.UNIT_OTHER),P.UNIT_COMPARE,Task.CONVERT_POSITIVE,f['second'],peer=r['r'])
    g=at(P.UNIT_COMPARE);same=c.NOT(c.eq(r['r'],0));finish(c.AND(g,same),1);go(c.AND(g,c.NOT(same)),P.NEGATIVE,x=f['original'])
    g=at(P.NEGATIVE);literal=c.tag(Tag.NAT,Tag.STRING);app=c.tag(Tag.APP)
    c.stop(c.AND(g,literal),Outcome.GAP,Reason.GAP_PRIMITIVE)
    call(c.AND(g,app),P.NEGATIVE_SPINE,Task.APPLICATION_SPINE,f['original'])
    go(c.AND(g,c.NOT(c.OR(literal,app))),P.NEGATIVE_OTHER,x=f['depth'])
    g=at(P.NEGATIVE_SPINE,C.APPLICATION_SPINE);go(g,P.NEGATIVE_HEAD,x=n['a'])
    g=at(P.NEGATIVE_HEAD);constant=c.tag(Tag.CONST)
    c.stop(c.AND(g,constant),Outcome.GAP,Reason.GAP_CONVERSION);go(c.AND(g,c.NOT(constant)),P.NEGATIVE_OTHER,x=f['depth'])
    g=at(P.NEGATIVE_OTHER);literal=c.tag(Tag.NAT,Tag.STRING);app=c.tag(Tag.APP)
    c.stop(c.AND(g,literal),Outcome.GAP,Reason.GAP_PRIMITIVE)
    call(c.AND(g,app),P.NEGATIVE_RIGHT_SPINE,Task.APPLICATION_SPINE,f['depth'])
    finish(c.AND(g,c.NOT(c.OR(literal,app))),0)
    g=at(P.NEGATIVE_RIGHT_SPINE,C.APPLICATION_SPINE);go(g,P.NEGATIVE_RIGHT_HEAD,x=n['a'])
    g=at(P.NEGATIVE_RIGHT_HEAD);constant=c.tag(Tag.CONST)
    c.stop(c.AND(g,constant),Outcome.GAP,Reason.GAP_CONVERSION);finish(c.AND(g,c.NOT(constant)),0)


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
