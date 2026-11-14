"""Check standalone source recursor claims against current generated Γ data.

No supplied record authorizes a recursor. The current signature must have the
kernel-generated recursor kind before raw scope/type/scheme conversion is used.
This checks metadata only; successful claims publish no signatures or origins.
"""
from .arena import Tag
from .native_cells import CellTag as C
from .traversal_machine import Mode,Task,Outcome,Reason


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    active=c.AND(c.task(Task.CHECK_PUBLISHED_RECURSOR),c.mode(Mode.WALK))
    def at(pc,tag=None):
        g=c.AND(active,c.eq(r['published_claim_pc'],pc))
        if tag is None:return g
        valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
    def go(g,pc,**kw):c.emit(g,published_claim_pc=pc,**kw)
    def call(g,pc,task,x,mode=Mode.WALK,**kw):
        room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
        c.write('stack',g,r['sp'],(0,pc,0,Task.CHECK_PUBLISHED_RECURSOR,0,0))
        c.emit(g,sp=c.add(r['sp'],1),task=task,mode=mode,x=x,depth=0,**kw)
    def check(g,valid,reason):
        c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,reason);return c.AND(g,valid)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],Task.CHECK_PUBLISHED_RECURSOR))
    c.emit(returning,sp=top,task=Task.CHECK_PUBLISHED_RECURSOR,mode=Mode.WALK,published_claim_pc=f['original'],x=r['r'])
    call(at(0),1,Task.ENV_LOOKUP,0,query_symbol=r['active_symbol'],lookup_head=r['env_head'])
    go(check(at(1),c.NOT(c.eq(r['r'],0)),Reason.UNKNOWN_CONSTANT),2,x=r['r'])
    g=at(2,C.CHECKED_SIGNATURE);go(g,3,published_claim_expected=n['b'],x=n['c'])
    g=check(at(3,C.CHECKED_SCHEME),c.eq(n['b'],10),Reason.INVALID_DECLARATION)
    call(g,4,Task.LOAD_PARAMETERS,n['a'])
    g=at(4);c.emit(g,published_claim_arity=r['count'])
    call(g,5,Task.FORMAL_LEVELS,0)
    g=at(5);c.emit(g,published_claim_levels=r['r'])
    call(g,6,Task.LOAD_PARAMETERS,r['active_parameters'])
    g=check(at(6),c.eq(r['count'],r['published_claim_arity']),Reason.UNIVERSE_ARITY)
    call(g,7,Task.EXPR_SCOPE,r['active_type'])
    call(at(7),8,Task.INFER,r['active_type'],local_base=r['ctx'])
    call(at(8),9,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    g=check(at(9),c.tag(Tag.SORT),Reason.EXPECT_SORT)
    call(g,10,Task.INSTANTIATE_SCHEME,r['active_type'],parameter_vector=r['active_parameters'],level_vector=r['published_claim_levels'])
    call(at(10),11,Task.CONVERT_POSITIVE,r['published_claim_expected'],peer=r['r'])
    go(check(at(11),c.NOT(c.eq(r['r'],0)),Reason.TYPE_MISMATCH),12)
    g=at(12)
    c.emit(g,raw_index=c.add(r['raw_index'],1),decl=c.add(r['decl'],1),ctx=0,count=0,arg_base=0,local_base=0)
    c.ret(g,1)


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
