"""Compile all-family motives, index/major snapshots and scoped Pi folding."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_MOTIVE_CONSUME,
    CALL_MOTIVE_INDICES,CALL_MOTIVE_PARAMETERS,CALL_MOTIVE_APPLY_INDICES,
    CALL_MOTIVE_MAJOR,CALL_MOTIVE_FOLD,CALL_MOTIVE_LOCAL,CALL_MOTIVE_VECTOR,CALL_MOTIVE_SNAPSHOT)

PRIVATE_PHASES=tuple(range(CALL_MOTIVE_CONSUME,CALL_MOTIVE_VECTOR+1))+(CALL_MOTIVE_SNAPSHOT,)
NO_NODE=(Mode.WALK,Mode.MOTIVE_CONSTANT,Mode.MOTIVE_ELIM_SORT,Mode.MOTIVE_STORE_TELESCOPE,
    Mode.MOTIVE_STORE_INFO,Mode.MOTIVE_LINK)
TAGS={Mode.MOTIVE_NAME:CellTag.VALIDATED_RECURSOR_NAME,Mode.MOTIVE_SIGNATURE:CellTag.CHECKED_SIGNATURE}


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)))
    phase=lambda p:c.AND(returning,c.eq(f['phase'],p))
    def call(guard,p,task,x,mode=Mode.WALK,**updates):
        c.write('stack',guard,top,(p,0,0,Task.BUILD_MOTIVES,0,0))
        c.emit(guard,task=task,mode=mode,x=x,depth=0,**updates)
    call(phase(CALL_MOTIVE_CONSUME),CALL_MOTIVE_INDICES,Task.OPEN_TELESCOPE,r['r'],Mode.TELESCOPE,open_tag=Tag.PI,bounded=0,limit=0)
    c.emit(phase(CALL_MOTIVE_INDICES),task=Task.BUILD_MOTIVES,mode=Mode.MOTIVE_SORT,x=r['r'])
    call(phase(CALL_MOTIVE_PARAMETERS),CALL_MOTIVE_APPLY_INDICES,Task.APPLY_SCOPE,r['r'],apply_base=r['motive_mark'],apply_end=r['ctx'])
    call(phase(CALL_MOTIVE_APPLY_INDICES),CALL_MOTIVE_MAJOR,Task.FRESH_LOCAL,r['r'],binder_info=0)
    major=phase(CALL_MOTIVE_MAJOR);c.emit(major,motive_major=r['fresh_record'])
    call(major,CALL_MOTIVE_SNAPSHOT,Task.SNAPSHOT_SCOPE,0,abstract_base=r['motive_mark'],abstract_end=c.sub(r['ctx'],1))
    c.emit(phase(CALL_MOTIVE_SNAPSHOT),task=Task.BUILD_MOTIVES,motive_indices=r['r'],mode=Mode.MOTIVE_ELIM_SORT)
    call(phase(CALL_MOTIVE_FOLD),CALL_MOTIVE_LOCAL,Task.FRESH_LOCAL,r['r'],binder_info=0)
    c.emit(phase(CALL_MOTIVE_LOCAL),task=Task.BUILD_MOTIVES,motive_local=r['fresh_record'],mode=Mode.MOTIVE_STORE_TELESCOPE)
    vector=phase(CALL_MOTIVE_VECTOR)
    c.emit(vector,task=Task.BUILD_MOTIVES,core_motives=r['r'],sp=top);c.ret(vector,r['r'])
    active=c.task(Task.BUILD_MOTIVES);at=lambda m:c.AND(active,c.mode(m))
    def room(guard,size=1):
        wide=c.g.add(c.g.fit(r['free'],c.width+1),c.g.const(size,c.width+1))
        fits=c.NOT(c.g.lt(c.g.const(c.cfg.heap,c.width+1),wide))
        c.stop(c.AND(guard,c.NOT(fits)),Outcome.RESOURCE,Reason.HEAP)
        return c.AND(guard,fits)
    init=at(Mode.WALK);valid=c.AND(c.NOT(c.eq(r['core_elim_info'],0)),c.NOT(c.eq(r['core_rec_names'],0)),c.eq(r['ctx'],r['header_parameter_end']))
    stackroom=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.stop(c.AND(init,valid,c.NOT(stackroom)),Outcome.RESOURCE,Reason.STACK)
    init=c.AND(init,valid,stackroom)
    c.write('stack',init,r['sp'],(CALL_MOTIVE_CONSUME,0,0,Task.BUILD_MOTIVES,0,0))
    c.emit(init,sp=c.add(r['sp'],1),motive_remaining=r['header_seen'],motive_rev=0,mode=Mode.MOTIVE_NAME,x=r['core_rec_names'])
    name=at(Mode.MOTIVE_NAME)
    valid=c.AND(c.NOT(c.eq(r['motive_remaining'],0)),c.eq(c.mux(c.eq(n['c'],0),0,1),c.mux(c.lt(1,r['motive_remaining']),1,0)))
    c.stop(c.AND(name,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(name,valid),motive_family=n['a'],motive_symbol=n['b'],motive_next=n['c'],mode=Mode.MOTIVE_SIGNATURE,x=n['a'],motive_mark=r['ctx'])
    signature=at(Mode.MOTIVE_SIGNATURE);c.emit(signature,motive_family_symbol=n['a'])
    call(signature,CALL_MOTIVE_CONSUME,Task.CONSUME_PARAMETERS,n['b'],reuse_base=r['header_parameter_base'],
        reuse_end=r['header_parameter_end'],reuse_whnf=1,local_base=r['header_parameter_base'])
    sort=at(Mode.MOTIVE_SORT)
    c.stop(c.AND(sort,c.NOT(c.tag(Tag.SORT))),Outcome.INVALID,Reason.EXPECT_SORT)
    c.emit(c.AND(sort,c.tag(Tag.SORT)),mode=Mode.MOTIVE_CONSTANT)
    const=room(at(Mode.MOTIVE_CONSTANT))
    c.write('heap',const,r['free'],(Tag.CONST,r['motive_family_symbol'],r['header_levels'],0))
    c.emit(const,free=c.add(r['free'],1))
    call(const,CALL_MOTIVE_PARAMETERS,Task.APPLY_SCOPE,r['free'],apply_base=r['header_parameter_base'],apply_end=r['header_parameter_end'])
    sort=room(at(Mode.MOTIVE_ELIM_SORT))
    c.write('heap',sort,r['free'],(Tag.SORT,r['core_elim_level'],0,0));c.emit(sort,free=c.add(r['free'],1))
    call(sort,CALL_MOTIVE_FOLD,Task.FOLD_TELESCOPE,r['free'],Mode.FOLD_SELECT,fold_body=r['free'],fold_tag=Tag.PI,fold_base=r['motive_mark'])
    telescope=room(at(Mode.MOTIVE_STORE_TELESCOPE),3)
    c.write('heap',telescope,r['free'],(CellTag.MOTIVE_TELESCOPE,r['motive_indices'],r['motive_major'],r['motive_symbol']))
    c.emit(telescope,free=c.add(r['free'],1),motive_telescope=r['free'],mode=Mode.MOTIVE_STORE_INFO)
    info=at(Mode.MOTIVE_STORE_INFO)
    c.write('heap',info,r['free'],(CellTag.MOTIVE_INFO,r['motive_family'],r['motive_local'],r['motive_telescope']))
    c.emit(info,free=c.add(r['free'],1),motive_info=r['free'],mode=Mode.MOTIVE_LINK)
    link=at(Mode.MOTIVE_LINK);more=c.lt(1,r['motive_remaining'])
    c.write('heap',link,r['free'],(CellTag.VECTOR_CELL,r['motive_info'],r['motive_rev'],0))
    c.emit(link,free=c.add(r['free'],1),motive_rev=r['free'],motive_remaining=c.sub(r['motive_remaining'],1))
    c.emit(c.AND(link,more),mode=Mode.MOTIVE_NAME,x=r['motive_next'])
    call(c.AND(link,c.NOT(more)),CALL_MOTIVE_VECTOR,Task.REVERSE_LIST,r['free'],reverse_length=r['header_seen'])
