"""Lower general strict positivity CORE; full-source preconditions stay explicit."""
from .arena import Tag
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_POS_WHNF,
    CALL_POS_OCCURRENCE,CALL_POS_DOMAIN,CALL_POS_OPEN,CALL_POS_APPLICATION)

PRIVATE_PHASES=tuple(range(CALL_POS_WHNF,CALL_POS_APPLICATION+1))


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)))
    at=lambda phase:c.AND(returning,c.eq(f['phase'],phase))
    def call(guard,phase,task,x,mode=Mode.WALK,original=None,**updates):
        c.write('stack',guard,top,(phase,f['original'] if original is None else original,f['depth'],Task.CHECK_POSITIVITY,0,0))
        c.emit(guard,task=task,mode=mode,x=x,depth=0,**updates)
    def done(guard):c.emit(guard,sp=top,ctx=f['depth'],task=Task.CHECK_POSITIVITY);c.ret(guard,1)
    def invalid(guard,reason):c.emit(guard,ctx=f['depth'],task=Task.CHECK_POSITIVITY);c.stop(guard,Outcome.INVALID,reason)
    call(at(CALL_POS_WHNF),CALL_POS_OCCURRENCE,Task.HAS_FAMILIES,r['r'],original=r['r'])
    occurrence=at(CALL_POS_OCCURRENCE)
    done(c.AND(occurrence,c.eq(r['r'],0)))
    c.emit(c.AND(occurrence,c.NOT(c.eq(r['r'],0))),task=Task.CHECK_POSITIVITY,mode=Mode.POSITIVITY_NODE,x=f['original'])
    domain=at(CALL_POS_DOMAIN)
    invalid(c.AND(domain,c.NOT(c.eq(r['r'],0))),Reason.NEGATIVE_OCCURRENCE)
    call(c.AND(domain,c.eq(r['r'],0)),CALL_POS_OPEN,Task.OPEN_TELESCOPE,f['original'],Mode.TELESCOPE,
        open_tag=Tag.PI,bounded=1,limit=c.add(r['ctx'],1))
    call(at(CALL_POS_OPEN),CALL_POS_WHNF,Task.BETA_ZETA,r['r'],Mode.BETA_ZETA)
    application=at(CALL_POS_APPLICATION)
    invalid(c.AND(application,c.eq(r['r'],0)),Reason.INVALID_INDUCTIVE_APPLICATION)
    done(c.AND(application,c.NOT(c.eq(r['r'],0))))
    active=c.task(Task.CHECK_POSITIVITY);init=c.AND(active,c.mode(Mode.WALK));room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    begin=c.AND(init,room)
    c.write('stack',begin,r['sp'],(CALL_POS_WHNF,0,r['ctx'],Task.CHECK_POSITIVITY,0,0))
    c.emit(begin,sp=c.add(r['sp'],1),task=Task.BETA_ZETA,mode=Mode.BETA_ZETA)
    node=c.AND(active,c.mode(Mode.POSITIVITY_NODE));pi=c.tag(Tag.PI)
    c.write('stack',node,top,(c.mux(pi,CALL_POS_DOMAIN,CALL_POS_APPLICATION),r['x'],f['depth'],Task.CHECK_POSITIVITY,0,0))
    c.emit(node,task=c.mux(pi,Task.HAS_FAMILIES,Task.FAMILY_APPLICATION),mode=Mode.WALK,x=c.mux(pi,n['a'],r['x']),depth=0)
