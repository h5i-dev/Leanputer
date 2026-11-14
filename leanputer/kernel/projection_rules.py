"""Pinned generic projection information, inference and reduction rules.

All family/constructor identities and telescope counts are checked runtime data.
Projection frames own their live state across recursively invoked inference and
WHNF. The development interpreter is never used during native inference.
"""
from enum import IntEnum
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


class F(IntEnum):
    INIT=0; SCHEME=1; META=2; LOOKUP=3; ORIGIN=4; BLOCK=5; PRIVATE=6; CELL=7; SIG=8; RESULT=9


class I(IntEnum):
    INIT=0; MAJOR_TYPE=1; TYPE_WHNF=2; SPINE=3; HEAD=4; ROOT=5; OWNER=6; INFO=7
    SETUP=8; PROP_TYPE=9; PROP_SORT=10; PROP_RESULT=11; STATE_INFO=12; RAW_FAMILY=13
    RAW_AUX=14; CTOR_VECTOR=15; CTOR_CELL=16; CTOR_RAW=17; CTOR_FOUND=18; CTOR_SIG=19
    CTOR_SCHEME=20; LEVEL_STATE=21; LEVEL_SETUP=22; LEVEL_CONST=23; CTOR_TYPE=24
    PARAM_LOOP=25; PARAM_INFO=26; PARAM_PI=27; PARAM_STATE=28; PARAM_SETUP=29
    PARAM_SPINE=30; PARAM_ARGUMENT=31; PARAM_INSTANTIATED=32; FIELD_LOOP=33
    FIELD_PI=34; FIELD_ROOT=35; FIELD_LOOSE_START=36; FIELD_LOOSE=37; SKIP_FIELD=38
    PROP_GATE=39; DOMAIN=40; DOMAIN_TYPE=41; DOMAIN_SORT=42; DOMAIN_PROP=43
    AFTER_PROP=44; RETURN_DOMAIN=45; SUBSTITUTE=46; FIELD_INSTANTIATED=47
    ARG_CHECK_STATE=48; ARG_CHECK_SETUP=49; ARG_CHECK_SPINE=50; ARG_CHECK_VECTOR=51
    BUILD_INFO=52; BUILD_STATE=53; TYPE_START=54; PARAM_ARGUMENT_START=55


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    # Count provenance lookup is nonrecursive and calls only lookup services.
    active=c.AND(c.task(Task.FAMILY_INFO),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['family_info_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.INVALID_PROJECTION);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,family_info_pc=pc,**kw)
    def call(g,pc,task,x,**kw):
        room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
        c.write('stack',g,r['sp'],(0,pc,0,Task.FAMILY_INFO,0,0))
        c.emit(g,sp=c.add(r['sp'],1),task=task,mode=Mode.WALK,x=x,depth=0,**kw)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.FAMILY_INFO))
    c.emit(returning,sp=top,task=Task.FAMILY_INFO,mode=Mode.WALK,family_info_pc=f['original'],x=r['r'])
    g=at(F.INIT,C.CHECKED_SIGNATURE);go(g,F.SCHEME,info_symbol=n['a'],x=n['c'])
    g=at(F.SCHEME,C.CHECKED_SCHEME);family=c.eq(n['b'],8)
    c.stop(c.AND(g,c.NOT(family)),Outcome.INVALID,Reason.INVALID_PROJECTION);go(c.AND(g,family),F.META,x=n['c'])
    g=at(F.META,C.CHECKED_FAMILY);c.emit(g,info_indices=n['a'],info_raw=n['c'])
    call(g,F.LOOKUP,Task.PRIOR_BLOCK_LOOKUP,r['nested_registry_head'],query_symbol=r['info_symbol'])
    g=at(F.LOOKUP);found=c.NOT(c.eq(r['r'],0));go(c.AND(g,found),F.ORIGIN,x=r['r'])
    overlay=c.NOT(c.eq(r['typing_active'],0))
    c.stop(c.AND(g,c.NOT(found),c.NOT(overlay)),Outcome.INVALID,Reason.INVALID_PROJECTION)
    go(c.AND(g,c.NOT(found),overlay),F.PRIVATE,info_remaining=r['header_seen'],x=r['header_head'])
    g=at(F.ORIGIN,C.BLOCK_ORIGIN);go(g,F.BLOCK,x=n['a'])
    g=at(F.BLOCK,C.RAW_BLOCK);go(g,F.RESULT,info_parameters=n['a'])
    g=at(F.PRIVATE);empty=c.eq(r['info_remaining'],0);c.stop(c.AND(g,empty),Outcome.INVALID,Reason.INVALID_PROJECTION)
    go(c.AND(g,c.NOT(empty)),F.CELL)
    g=at(F.CELL,C.VECTOR_CELL);go(g,F.SIG,info_next=n['b'],x=n['a'])
    g=at(F.SIG,C.CHECKED_SIGNATURE);same=c.eq(n['a'],r['info_symbol'])
    go(c.AND(g,same),F.RESULT,info_parameters=r['header_parameter_count'])
    go(c.AND(g,c.NOT(same)),F.PRIVATE,info_remaining=c.sub(r['info_remaining'],1),x=r['info_next'])
    g=at(F.RESULT);room=c.lt(r['free'],c.cfg.heap)
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
    c.write('heap',g,r['free'],(C.PROJECTION_FAMILY_INFO,r['info_parameters'],r['info_indices'],r['info_raw']))
    c.emit(g,free=c.add(r['free'],1));c.ret(g,r['free'])

    # The inference frame is (resume,originalProjection,cursor,owner,state,R).
    # 'state' and R are immutable derived pointers, not global recursive scratch.
    active=c.AND(c.task(Task.PROJECTION_INFER),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['projection_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.INVALID_PROJECTION);return c.AND(g,valid)
    def frame(g,phase=None,cursor=None,state=None,body=None):
        c.write('stack',g,top,(f['phase'] if phase is None else phase,f['original'],f['depth'] if cursor is None else cursor,
            Task.PROJECTION_INFER,f['first'] if state is None else state,f['second'] if body is None else body))
    def go(g,pc,**kw):c.emit(g,projection_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        frame(g,phase=pc);c.emit(g,task=task,mode=mode,x=x,depth=0,**kw)
    def finish(g,value):c.emit(g,sp=top,task=Task.INFER);c.ret(g,value)
    def store(g,row,pc,**kw):
        room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
        c.write('heap',g,r['free'],row);c.emit(g,free=c.add(r['free'],1));go(g,pc,**kw);return g
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.PROJECTION_INFER))
    c.emit(returning,task=Task.PROJECTION_INFER,mode=Mode.WALK,projection_pc=f['phase'],x=r['r'])
    g=at(I.INIT,Tag.PROJ);ready=c.NOT(c.eq(r['env_ready'],0));room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(g,c.NOT(ready)),Outcome.GAP,Reason.GAP_ENVIRONMENT)
    c.stop(c.AND(g,ready,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,ready,room)
    c.write('stack',g,r['sp'],(I.MAJOR_TYPE,r['x'],0,Task.PROJECTION_INFER,0,0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.INFER,mode=Mode.WALK,x=n['c'])
    call(at(I.MAJOR_TYPE),I.TYPE_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    g=at(I.TYPE_WHNF);frame(g,phase=I.SPINE,body=r['r'])
    c.emit(g,task=Task.APPLICATION_SPINE,mode=Mode.WALK,x=r['r'],depth=0)
    g=at(I.SPINE,C.APPLICATION_SPINE);frame(g,state=r['x']);go(g,I.HEAD,x=n['a'])
    g=at(I.HEAD,Tag.CONST)
    g=store(g,(C.PROJECTION_SETUP,f['first'],f['second'],r['x']),I.ROOT,x=f['original'])
    frame(g,state=r['free'],cursor=n['a'],body=0)
    g=at(I.ROOT,Tag.PROJ);same=c.eq(n['a'],f['depth']);c.stop(c.AND(g,c.NOT(same)),Outcome.INVALID,Reason.INVALID_PROJECTION)
    call(c.AND(g,same),I.OWNER,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
    call(at(I.OWNER),I.INFO,Task.FAMILY_INFO,r['r'],family_info_pc=0)
    g=at(I.INFO,C.PROJECTION_FAMILY_INFO);g,total=c.checked_add(g,n['a'],n['b']);frame(g,body=r['x'],cursor=total);go(g,I.SETUP,x=f['first'])
    g=at(I.SETUP,C.PROJECTION_SETUP)
    call(g,I.PROP_TYPE,Task.INFER,n['b'],local_base=r['local_base'])
    call(at(I.PROP_TYPE),I.PROP_SORT,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    g=at(I.PROP_SORT,Tag.SORT);call(g,I.PROP_RESULT,Task.LEVEL_EQUIVALENT,n['a'],peer=r['kernel_zero'])
    g=at(I.PROP_RESULT)
    g=store(g,(C.PROJECTION_STATE,f['first'],f['second'],r['r']),I.ARG_CHECK_STATE,x=r['free'])
    frame(g,state=r['free'],body=0)
    g=at(I.ARG_CHECK_STATE,C.PROJECTION_STATE);go(g,I.ARG_CHECK_SETUP,x=n['a'])
    g=at(I.ARG_CHECK_SETUP,C.PROJECTION_SETUP);go(g,I.ARG_CHECK_SPINE,x=n['a'])
    g=at(I.ARG_CHECK_SPINE,C.APPLICATION_SPINE);go(g,I.ARG_CHECK_VECTOR,x=n['b'])
    g=at(I.ARG_CHECK_VECTOR,C.VECTOR)
    valid=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(n['a'],f['depth']))
    c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.INVALID_PROJECTION)
    go(c.AND(g,valid),I.STATE_INFO,x=f['first'])
    g=at(I.STATE_INFO,C.PROJECTION_STATE);go(g,I.BUILD_INFO,x=n['b'])
    g=at(I.BUILD_INFO,C.PROJECTION_FAMILY_INFO);go(g,I.RAW_FAMILY,x=n['c'])
    g=at(I.RAW_FAMILY,C.RAW_FAMILY);go(g,I.RAW_AUX,x=n['c'])
    g=at(I.RAW_AUX,C.RAW_FAMILY_AUX);go(g,I.CTOR_VECTOR,x=n['a'])
    g=at(I.CTOR_VECTOR,C.VECTOR);one=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(n['a'],1),c.NOT(c.eq(n['b'],0)))
    c.stop(c.AND(g,c.NOT(one)),Outcome.INVALID,Reason.INVALID_PROJECTION);go(c.AND(g,one),I.CTOR_CELL,x=n['b'])
    g=at(I.CTOR_CELL,C.VECTOR_CELL);go(g,I.CTOR_RAW,x=n['a'])
    g=at(I.CTOR_RAW,C.RAW_CONSTRUCTOR)
    call(g,I.CTOR_FOUND,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
    go(at(I.CTOR_FOUND),I.CTOR_SIG,x=r['r'])
    g=at(I.CTOR_SIG,C.CHECKED_SIGNATURE);c.emit(g,signature_type=n['b']);go(g,I.CTOR_SCHEME,x=n['c'])
    g=at(I.CTOR_SCHEME,C.CHECKED_SCHEME);ctor=c.eq(n['b'],9)
    c.stop(c.AND(g,c.NOT(ctor)),Outcome.INVALID,Reason.INVALID_PROJECTION)
    go(c.AND(g,ctor),I.LEVEL_STATE,parameter_vector=n['a'],x=f['first'])
    g=at(I.LEVEL_STATE,C.PROJECTION_STATE);go(g,I.LEVEL_SETUP,x=n['a'])
    g=at(I.LEVEL_SETUP,C.PROJECTION_SETUP);go(g,I.LEVEL_CONST,x=n['c'])
    g=at(I.LEVEL_CONST,Tag.CONST)
    call(g,I.CTOR_TYPE,Task.INSTANTIATE_SCHEME,r['signature_type'],level_vector=n['b'])
    g=at(I.CTOR_TYPE);frame(g,body=r['r'],cursor=0);go(g,I.PARAM_LOOP,x=f['first'])
    g=at(I.PARAM_LOOP,C.PROJECTION_STATE);go(g,I.PARAM_INFO,x=n['b'])
    g=at(I.PARAM_INFO,C.PROJECTION_FAMILY_INFO);more=c.lt(f['depth'],n['a'])
    call(c.AND(g,more),I.PARAM_PI,Task.BETA_ZETA,f['second'],Mode.BETA_ZETA)
    frame(c.AND(g,c.NOT(more)),cursor=0);go(c.AND(g,c.NOT(more)),I.FIELD_LOOP)
    g=at(I.PARAM_PI,Tag.PI);frame(g,body=n['b']);go(g,I.PARAM_STATE,x=f['first'])
    g=at(I.PARAM_STATE,C.PROJECTION_STATE);go(g,I.PARAM_SETUP,x=n['a'])
    g=at(I.PARAM_SETUP,C.PROJECTION_SETUP);go(g,I.PARAM_SPINE,x=n['a'])
    g=at(I.PARAM_SPINE,C.APPLICATION_SPINE);call(g,I.PARAM_ARGUMENT,Task.VECTOR_REFERENCE,n['b'],vector_index=f['depth'])
    call(at(I.PARAM_ARGUMENT),I.PARAM_INSTANTIATED,Task.INSTANTIATE_ONE,f['second'],substitution=r['r'])
    g=at(I.PARAM_INSTANTIATED);frame(g,body=r['r'],cursor=c.add(f['depth'],1));go(g,I.PARAM_LOOP,x=f['first'])
    call(at(I.FIELD_LOOP),I.FIELD_PI,Task.BETA_ZETA,f['second'],Mode.BETA_ZETA)
    g=at(I.FIELD_PI,Tag.PI);g=store(g,(C.PROJECTION_BINDER,n['a'],n['b'],0),I.FIELD_ROOT,x=f['original']);frame(g,body=r['free'])
    g=at(I.FIELD_ROOT,Tag.PROJ);target=c.eq(f['depth'],n['b'])
    go(c.AND(g,target),I.PROP_GATE,x=f['first'])
    go(c.AND(g,c.NOT(target)),I.FIELD_LOOSE_START,x=f['second'])
    g=at(I.FIELD_LOOSE_START,C.PROJECTION_BINDER);call(g,I.FIELD_LOOSE,Task.HAS_LOOSE_BVARS,n['b'])
    g=at(I.FIELD_LOOSE);loose=c.NOT(c.eq(r['r'],0))
    go(c.AND(g,loose),I.PROP_GATE,x=f['first']);go(c.AND(g,c.NOT(loose)),I.SKIP_FIELD,x=f['second'])
    g=at(I.SKIP_FIELD,C.PROJECTION_BINDER);frame(g,body=n['b'],cursor=c.add(f['depth'],1));go(g,I.FIELD_LOOP)
    g=at(I.PROP_GATE,C.PROJECTION_STATE);prop=c.NOT(c.eq(n['c'],0))
    go(c.AND(g,prop),I.DOMAIN,x=f['second']);go(c.AND(g,c.NOT(prop)),I.AFTER_PROP,x=f['original'])
    g=at(I.DOMAIN,C.PROJECTION_BINDER);call(g,I.DOMAIN_TYPE,Task.INFER,n['a'])
    call(at(I.DOMAIN_TYPE),I.DOMAIN_SORT,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    g=at(I.DOMAIN_SORT,Tag.SORT);call(g,I.DOMAIN_PROP,Task.LEVEL_EQUIVALENT,n['a'],peer=r['kernel_zero'])
    g=at(I.DOMAIN_PROP);prop=c.NOT(c.eq(r['r'],0));c.stop(c.AND(g,c.NOT(prop)),Outcome.INVALID,Reason.INVALID_PROJECTION)
    go(c.AND(g,prop),I.AFTER_PROP,x=f['original'])
    g=at(I.AFTER_PROP,Tag.PROJ);target=c.eq(f['depth'],n['b'])
    go(c.AND(g,target),I.RETURN_DOMAIN,x=f['second'])
    g=store(c.AND(g,c.NOT(target)),(Tag.PROJ,n['a'],f['depth'],n['c']),I.SUBSTITUTE,x=f['second'],substitution=r['free'])
    g=at(I.SUBSTITUTE,C.PROJECTION_BINDER);call(g,I.FIELD_INSTANTIATED,Task.INSTANTIATE_ONE,n['b'])
    g=at(I.FIELD_INSTANTIATED);frame(g,body=r['r'],cursor=c.add(f['depth'],1));go(g,I.FIELD_LOOP)
    g=at(I.RETURN_DOMAIN,C.PROJECTION_BINDER);finish(g,n['a'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()


class R(IntEnum):
    INIT=0; MAJOR=1; SPINE=2; HEAD=3; FOUND=4; SIG=5; SCHEME=6; META=7; INFO=8
    ROOT=9; ARGUMENTS=10; SELECTED=11; STRING_PREPARED=12


def emit_reduce_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    bridge=c.AND(c.task(Task.BETA_ZETA),c.mode(Mode.BETA_ZETA),c.tag(Tag.PROJ))
    room=c.lt(r['sp'],c.cfg.stack);ready=c.NOT(c.eq(r['env_ready'],0))
    c.stop(c.AND(bridge,c.NOT(ready)),Outcome.GAP,Reason.GAP_ENVIRONMENT)
    c.stop(c.AND(bridge,ready,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(bridge,ready,room)
    c.write('stack',g,r['sp'],(0,r['x'],r['ctx'],Task.PROJECTION_BRIDGE,r['count'],r['arg_base']))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.PROJECTION_REDUCE,mode=Mode.WALK,projection_reduce_pc=0)
    back=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.PROJECTION_BRIDGE))
    c.emit(back,sp=top,task=Task.BETA_ZETA,ctx=f['depth'],count=f['first'],arg_base=f['second'],depth=0)
    success=c.NOT(c.eq(r['r'],0));c.emit(c.AND(back,success),mode=Mode.BETA_ZETA,x=r['r'])
    c.ret(c.AND(back,c.NOT(success)),f['original'])
    active=c.AND(c.task(Task.PROJECTION_REDUCE),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['projection_reduce_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def frame(g,phase=None,cursor=None,args=None):
        c.write('stack',g,top,(f['phase'] if phase is None else phase,f['original'],f['depth'] if cursor is None else cursor,
            Task.PROJECTION_REDUCE,f['first'] if args is None else args,0))
    def go(g,pc,**kw):c.emit(g,projection_reduce_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        frame(g,phase=pc);c.emit(g,task=task,mode=mode,x=x,depth=0,**kw)
    def finish(g,value=0):c.emit(g,sp=top,task=Task.PROJECTION_REDUCE);c.ret(g,value)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.PROJECTION_REDUCE))
    c.emit(returning,task=Task.PROJECTION_REDUCE,mode=Mode.WALK,projection_reduce_pc=f['phase'],x=r['r'])
    g=at(R.INIT,Tag.PROJ);room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
    c.write('stack',g,r['sp'],(R.MAJOR,r['x'],0,Task.PROJECTION_REDUCE,0,0))
    c.emit(g,sp=c.add(r['sp'],1),task=Task.BETA_ZETA,mode=Mode.BETA_ZETA,x=n['c'])
    g=at(R.MAJOR);string=c.tag(Tag.STRING)
    call(c.AND(g,string),R.STRING_PREPARED,Task.STRING_WHNF,r['r'],string_whnf_pc=0,string_tail_major=0)
    call(c.AND(g,c.NOT(string)),R.SPINE,Task.APPLICATION_SPINE,r['r'])
    call(at(R.STRING_PREPARED),R.SPINE,Task.APPLICATION_SPINE,r['r'])
    g=at(R.SPINE,C.APPLICATION_SPINE);frame(g,args=n['b']);go(g,R.HEAD,x=n['a'])
    g=at(R.HEAD);constant=c.tag(Tag.CONST);finish(c.AND(g,c.NOT(constant)))
    call(c.AND(g,constant),R.FOUND,Task.ENV_LOOKUP,0,query_symbol=n['a'],lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
    g=at(R.FOUND);found=c.NOT(c.eq(r['r'],0));finish(c.AND(g,c.NOT(found)));go(c.AND(g,found),R.SIG,x=r['r'])
    g=at(R.SIG,C.CHECKED_SIGNATURE);go(g,R.SCHEME,x=n['c'])
    g=at(R.SCHEME,C.CHECKED_SCHEME);ctor=c.eq(n['b'],9);finish(c.AND(g,c.NOT(ctor)));go(c.AND(g,ctor),R.META,x=n['c'])
    g=at(R.META,C.CHECKED_CONSTRUCTOR);call(g,R.INFO,Task.FAMILY_INFO,n['a'],family_info_pc=0)
    g=at(R.INFO,C.PROJECTION_FAMILY_INFO);frame(g,cursor=n['a']);go(g,R.ROOT,x=f['original'])
    g=at(R.ROOT,Tag.PROJ);g,index=c.checked_add(g,f['depth'],n['b']);frame(g,cursor=index);go(g,R.ARGUMENTS,x=f['first'])
    g=at(R.ARGUMENTS,C.VECTOR);within=c.lt(f['depth'],n['a'])
    finish(c.AND(g,c.NOT(within)))
    call(c.AND(g,within),R.SELECTED,Task.VECTOR_REFERENCE,r['x'],vector_index=f['depth'])
    finish(at(R.SELECTED),r['r'])


# Both inference and WHNF composition compile these fixed rules.
emit_infer_rules=emit_rules

def emit_rules(c):
    emit_infer_rules(c)
    emit_reduce_rules(c)
