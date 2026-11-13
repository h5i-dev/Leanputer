"""General all-family mk_rec_infos motive pass, DEVELOPMENT reference only."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_MOTIVE_CONSUME,
    CALL_MOTIVE_INDICES,CALL_MOTIVE_PARAMETERS,CALL_MOTIVE_APPLY_INDICES,
    CALL_MOTIVE_MAJOR,CALL_MOTIVE_FOLD,CALL_MOTIVE_LOCAL,CALL_MOTIVE_VECTOR)
from .motive_rules import NO_NODE,TAGS

PRIVATE_PHASES=tuple(range(CALL_MOTIVE_CONSUME,CALL_MOTIVE_VECTOR+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase=frame[0]
    def call(p,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.BUILD_MOTIVES,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    if phase==CALL_MOTIVE_CONSUME:
        call(CALL_MOTIVE_INDICES,Task.OPEN_TELESCOPE,r['r'],Mode.TELESCOPE,open_tag=Tag.PI,bounded=0,limit=0)
    elif phase==CALL_MOTIVE_INDICES:
        r.update(task=Task.BUILD_MOTIVES,mode=Mode.MOTIVE_SORT,x=r['r'])
    elif phase==CALL_MOTIVE_PARAMETERS:
        call(CALL_MOTIVE_APPLY_INDICES,Task.APPLY_SCOPE,r['r'],apply_base=r['motive_mark'],apply_end=r['ctx'])
    elif phase==CALL_MOTIVE_APPLY_INDICES:
        call(CALL_MOTIVE_MAJOR,Task.FRESH_LOCAL,r['r'],binder_info=0)
    elif phase==CALL_MOTIVE_MAJOR:
        size=r['ctx']-1-r['motive_mark']
        r.update(task=Task.BUILD_MOTIVES,motive_major=r['fresh_record'],motive_index_count=size,
            motive_snapshot_remaining=size,motive_snapshot_head=0,motive_snapshot_cursor=r['ctx']-2 if size else 0,
            mode=Mode.MOTIVE_SNAPSHOT_SELECT if size else Mode.MOTIVE_SNAPSHOT_VECTOR)
    elif phase==CALL_MOTIVE_FOLD:call(CALL_MOTIVE_LOCAL,Task.FRESH_LOCAL,r['r'],binder_info=0)
    elif phase==CALL_MOTIVE_LOCAL:
        r.update(task=Task.BUILD_MOTIVES,motive_local=r['fresh_record'],mode=Mode.MOTIVE_STORE_TELESCOPE)
    elif phase==CALL_MOTIVE_VECTOR:
        r.update(task=Task.BUILD_MOTIVES,core_motives=r['r'],sp=r['sp']-1);ret(r['r'])


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.BUILD_MOTIVES:return False
    def call(p,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.BUILD_MOTIVES,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    def room(n=1):
        if r['free']+n>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP);return False
        return True
    mode=r['mode']
    if mode==Mode.WALK:
        if not r['core_elim_info'] or not r['core_rec_names'] or r['ctx']!=r['header_parameter_end']:
            stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_MOTIVE_CONSUME,0,0,Task.BUILD_MOTIVES,0,0]
            r.update(sp=r['sp']+1,motive_remaining=r['header_seen'],motive_rev=0,
                mode=Mode.MOTIVE_NAME,x=r['core_rec_names'])
    elif mode==Mode.MOTIVE_NAME:
        if not r['motive_remaining'] or bool(c)!=(r['motive_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(motive_family=a,motive_symbol=b,motive_next=c,mode=Mode.MOTIVE_SIGNATURE,x=a,motive_mark=r['ctx'])
    elif mode==Mode.MOTIVE_SIGNATURE:
        r['motive_family_symbol']=a
        call(CALL_MOTIVE_CONSUME,Task.CONSUME_PARAMETERS,b,reuse_base=r['header_parameter_base'],
            reuse_end=r['header_parameter_end'],reuse_whnf=1,local_base=r['header_parameter_base'])
    elif mode==Mode.MOTIVE_SORT:
        if tag!=Tag.SORT:stop(Outcome.INVALID,Reason.EXPECT_SORT)
        else:r['mode']=Mode.MOTIVE_CONSTANT
    elif mode==Mode.MOTIVE_CONSTANT:
        if room():
            ref=r['free'];s['heap'][ref]=[Tag.CONST,r['motive_family_symbol'],r['header_levels'],0]
            r['free']=ref+1
            call(CALL_MOTIVE_PARAMETERS,Task.APPLY_SCOPE,ref,apply_base=r['header_parameter_base'],apply_end=r['header_parameter_end'])
    elif mode==Mode.MOTIVE_SNAPSHOT_SELECT:
        if room():
            ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,s['context'][r['motive_snapshot_cursor']][0],r['motive_snapshot_head'],0]
            more=r['motive_snapshot_remaining']>1
            r.update(free=ref+1,motive_snapshot_head=ref,motive_snapshot_remaining=r['motive_snapshot_remaining']-1,
                mode=Mode.MOTIVE_SNAPSHOT_SELECT if more else Mode.MOTIVE_SNAPSHOT_VECTOR)
            if more:r['motive_snapshot_cursor']-=1
    elif mode==Mode.MOTIVE_SNAPSHOT_VECTOR:
        if room():
            ref=r['free'];s['heap'][ref]=[CellTag.VECTOR,r['motive_index_count'],r['motive_snapshot_head'],VectorKind.REFERENCES]
            r.update(free=ref+1,motive_indices=ref,mode=Mode.MOTIVE_ELIM_SORT)
    elif mode==Mode.MOTIVE_ELIM_SORT:
        if room():
            ref=r['free'];s['heap'][ref]=[Tag.SORT,r['core_elim_level'],0,0];r['free']=ref+1
            call(CALL_MOTIVE_FOLD,Task.FOLD_TELESCOPE,ref,Mode.FOLD_SELECT,
                fold_body=ref,fold_tag=Tag.PI,fold_base=r['motive_mark'])
    elif mode==Mode.MOTIVE_STORE_TELESCOPE:
        if room(3):
            ref=r['free'];s['heap'][ref]=[CellTag.MOTIVE_TELESCOPE,r['motive_indices'],r['motive_major'],r['motive_symbol']]
            r.update(free=ref+1,motive_telescope=ref,mode=Mode.MOTIVE_STORE_INFO)
    elif mode==Mode.MOTIVE_STORE_INFO:
        ref=r['free'];s['heap'][ref]=[CellTag.MOTIVE_INFO,r['motive_family'],r['motive_local'],r['motive_telescope']]
        r.update(free=ref+1,motive_info=ref,mode=Mode.MOTIVE_LINK)
    elif mode==Mode.MOTIVE_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['motive_info'],r['motive_rev'],0]
        more=r['motive_remaining']>1
        r.update(free=ref+1,motive_rev=ref,motive_remaining=r['motive_remaining']-1)
        if more:r.update(mode=Mode.MOTIVE_NAME,x=r['motive_next'])
        else:call(CALL_MOTIVE_VECTOR,Task.REVERSE_LIST,ref,reverse_length=r['header_seen'])
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
