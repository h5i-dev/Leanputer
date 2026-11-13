"""Composable symbol-set occurrence on the SAME complete Expr walk."""
from .traversal_machine import Mode,Task,Outcome,Reason,CALL_OCCURRENCE_FINISH

PRIVATE_PHASES=(CALL_OCCURRENCE_FINISH,)


def emit_rules(c):
    r,f=c.r,c.read['frame']
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['phase'],CALL_OCCURRENCE_FINISH))
    c.emit(returning,sp=c.sub(r['sp'],1),task=Task.HAS_CONSTANTS,occurrence_internal=0)
    c.ret(returning,r['occurrence_found'])
    entering=c.AND(c.task(Task.HAS_CONSTANTS),c.mode(Mode.WALK))
    empty=c.eq(r['count'],0)
    c.ret(c.AND(entering,empty),0)
    room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(entering,c.NOT(empty),c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    begin=c.AND(entering,c.NOT(empty),room)
    c.write('stack',begin,r['sp'],(CALL_OCCURRENCE_FINISH,0,0,Task.HAS_CONSTANTS,0,0))
    c.emit(begin,occurrence_mark=r['sp'],sp=c.add(r['sp'],1),task=Task.OCCURS,
        occurrence_found=0,occurrence_internal=1,depth=0)
