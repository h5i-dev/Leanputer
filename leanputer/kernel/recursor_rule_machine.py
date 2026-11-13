"""General mk_rec_rules computation RHS construction, DEVELOPMENT only."""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_RULE_LEVELS,CALL_RULE_RESTORE,
    CALL_RULE_MINOR_APPLY,CALL_RULE_PREFIX,CALL_RULE_FAMILY,CALL_RULE_PARAMETERS,
    CALL_RULE_MOTIVES,CALL_RULE_MINORS,CALL_RULE_INDICES,CALL_RULE_FUNCTION,
    CALL_RULE_IH_FOLD,CALL_RULE_FINAL_FOLD,CALL_RULE_SCOPE,CALL_RULE_VECTOR)
from .recursor_rule_rules import NO_NODE,TAGS

PRIVATE_PHASES=tuple(range(CALL_RULE_LEVELS,CALL_RULE_VECTOR+1))


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase=frame[0]
    def call(p,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.BUILD_RECURSOR_RULES,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    if phase==CALL_RULE_LEVELS:
        r.update(task=Task.BUILD_RECURSOR_RULES,core_rec_levels=r['r'],mode=Mode.RULE_VECTOR,x=r['core_minors'])
    elif phase==CALL_RULE_RESTORE:
        if r['restore_length']!=r['rule_field_count']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(task=Task.BUILD_RECURSOR_RULES,rule_fields_end=r['ctx'],mode=Mode.RULE_MINOR_RECORD,x=r['rule_minor_record'])
    elif phase==CALL_RULE_MINOR_APPLY:r.update(task=Task.BUILD_RECURSOR_RULES,rule_result=r['r'],mode=Mode.RULE_FIELD_VECTOR,x=r['rule_fields'])
    elif phase==CALL_RULE_PREFIX:r.update(task=Task.BUILD_RECURSOR_RULES,mode=Mode.RULE_OPENED,x=r['r'])
    elif phase==CALL_RULE_FAMILY:r.update(task=Task.BUILD_RECURSOR_RULES,mode=Mode.RULE_FAMILY_INFO,x=r['motive_lookup_info'])
    elif phase==CALL_RULE_PARAMETERS:
        call(CALL_RULE_MOTIVES,Task.APPLY_SCOPE,r['r'],apply_base=r['header_parameter_end'],apply_end=r['header_parameter_end']+r['header_seen'])
    elif phase==CALL_RULE_MOTIVES:
        call(CALL_RULE_MINORS,Task.APPLY_SCOPE,r['r'],apply_base=r['header_parameter_end']+r['header_seen'],apply_end=r['rule_mark'])
    elif phase==CALL_RULE_MINORS:
        r.update(task=Task.BUILD_RECURSOR_RULES,rule_recursive_fn=r['r'],mode=Mode.RULE_INDEX_VECTOR,x=r['rule_index_vector'])
    elif phase==CALL_RULE_INDICES:
        r['rule_ih_target']=r['r']
        call(CALL_RULE_FUNCTION,Task.APPLY_SCOPE,r['rule_recursive_local'],apply_base=r['rule_ih_mark'],apply_end=r['ctx'])
    elif phase==CALL_RULE_FUNCTION:r.update(task=Task.BUILD_RECURSOR_RULES,mode=Mode.RULE_IH_BODY)
    elif phase==CALL_RULE_IH_FOLD:r.update(task=Task.BUILD_RECURSOR_RULES,mode=Mode.RULE_APPEND_IH)
    elif phase==CALL_RULE_FINAL_FOLD:
        r['rule_closed']=r['r'];call(CALL_RULE_SCOPE,Task.EXPR_SCOPE,r['r'])
    elif phase==CALL_RULE_SCOPE:r.update(task=Task.BUILD_RECURSOR_RULES,ctx=r['rule_mark'],mode=Mode.RULE_STORE)
    elif phase==CALL_RULE_VECTOR:
        r.update(task=Task.BUILD_RECURSOR_RULES,core_rules=r['r'],sp=r['sp']-1);ret(r['r'])


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.BUILD_RECURSOR_RULES:return False
    def call(p,task,x,mode=Mode.WALK,**updates):
        s['stack'][r['sp']-1]=[p,0,0,Task.BUILD_RECURSOR_RULES,0,0]
        r.update(task=task,mode=mode,x=x,depth=0,**updates)
    def fold(body):call(CALL_RULE_FINAL_FOLD,Task.FOLD_TELESCOPE,body,Mode.FOLD_SELECT,
        fold_base=r['header_parameter_base'],fold_body=body,fold_tag=Tag.LAM)
    def next_field(body):
        more=r['rule_field_remaining']>1;r['rule_field_remaining']-=1
        if more:r.update(mode=Mode.RULE_FIELD_CELL,x=r['rule_field_next'])
        else:fold(body)
    def room(size=1):
        if r['free']+size>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP);return False
        return True
    mode=r['mode']
    if mode==Mode.WALK:
        if not r['core_rec_types'] or not r['core_minors'] or r['ctx']!=r['header_parameter_end']+r['header_seen']+r['core_ctor_declared']:
            stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_RULE_LEVELS,0,0,Task.BUILD_RECURSOR_RULES,0,0]
            r.update(sp=r['sp']+1,rule_mark=r['ctx'],rule_rev=0,task=Task.FORMAL_LEVELS,mode=Mode.WALK,x=0)
    elif mode==Mode.RULE_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b) or a!=r['core_ctor_declared']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:call(CALL_RULE_VECTOR,Task.REVERSE_LIST,0,reverse_length=0)
        else:r.update(rule_remaining=a,mode=Mode.RULE_CELL,x=b)
    elif mode==Mode.RULE_CELL:
        if not r['rule_remaining'] or bool(b)!=(r['rule_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(rule_next=b,mode=Mode.RULE_INFO,x=a)
    elif mode==Mode.RULE_INFO:r.update(rule_minor_record=b,rule_field_count=c,mode=Mode.RULE_PENDING,x=a)
    elif mode==Mode.RULE_PENDING:r.update(rule_symbol=a,mode=Mode.RULE_ANALYSIS,x=c)
    elif mode==Mode.RULE_ANALYSIS:
        r.update(rule_family=a,rule_fields=b)
        call(CALL_RULE_RESTORE,Task.RESTORE_SCOPE,b)
    elif mode==Mode.RULE_MINOR_RECORD:
        call(CALL_RULE_MINOR_APPLY,Task.APPLY_SCOPE,a,apply_base=r['rule_mark'],apply_end=r['rule_fields_end'])
    elif mode==Mode.RULE_FIELD_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b) or a!=r['rule_field_count']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:fold(r['rule_result'])
        else:r.update(rule_field_remaining=a,mode=Mode.RULE_FIELD_CELL,x=b)
    elif mode==Mode.RULE_FIELD_CELL:
        if not r['rule_field_remaining'] or bool(b)!=(r['rule_field_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(rule_field_next=b,mode=Mode.RULE_FIELD,x=a)
    elif mode==Mode.RULE_FIELD:
        if not b:next_field(r['rule_result'])
        else:r.update(rule_descriptor=b,mode=Mode.RULE_LOCAL,x=a)
    elif mode==Mode.RULE_LOCAL:
        r.update(rule_recursive_local=a,rule_ih_mark=r['ctx'])
        call(CALL_RULE_PREFIX,Task.OPEN_RECURSIVE_PREFIX,r['rule_descriptor'])
    elif mode==Mode.RULE_OPENED:
        r['rule_index_vector']=c
        call(CALL_RULE_FAMILY,Task.FIND_MOTIVE,r['core_motives'],motive_query=a)
    elif mode==Mode.RULE_FAMILY_INFO:r.update(mode=Mode.RULE_TELESCOPE,x=c)
    elif mode==Mode.RULE_TELESCOPE:r.update(rule_recursive_symbol=c,mode=Mode.RULE_CONSTANT)
    elif mode==Mode.RULE_CONSTANT:
        if room():
            ref=r['free'];s['heap'][ref]=[Tag.CONST,r['rule_recursive_symbol'],r['core_rec_levels'],0];r['free']=ref+1
            call(CALL_RULE_PARAMETERS,Task.APPLY_SCOPE,ref,apply_base=r['header_parameter_base'],apply_end=r['header_parameter_end'])
    elif mode==Mode.RULE_INDEX_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        else:call(CALL_RULE_INDICES,Task.APPLY_LIST,r['rule_recursive_fn'],list_head=b,list_skip=0)
    elif mode==Mode.RULE_IH_BODY:
        if room():
            ref=r['free'];s['heap'][ref]=[Tag.APP,r['rule_ih_target'],r['r'],0];r['free']=ref+1
            call(CALL_RULE_IH_FOLD,Task.FOLD_TELESCOPE,ref,Mode.FOLD_SELECT,fold_base=r['rule_ih_mark'],fold_body=ref,fold_tag=Tag.LAM)
    elif mode==Mode.RULE_APPEND_IH:
        if room():
            ref=r['free'];s['heap'][ref]=[Tag.APP,r['rule_result'],r['r'],0]
            r.update(free=ref+1,rule_result=ref);next_field(ref)
    elif mode==Mode.RULE_STORE:
        if room(3):
            ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_RULE,r['rule_symbol'],r['rule_field_count'],r['rule_closed']]
            r.update(free=ref+1,rule_info=ref,mode=Mode.RULE_STORE_FAMILY)
    elif mode==Mode.RULE_STORE_FAMILY:
        ref=r['free'];s['heap'][ref]=[CellTag.FAMILY_RULE,r['rule_family'],r['rule_info'],0]
        r.update(free=ref+1,rule_family_info=ref,mode=Mode.RULE_LINK)
    elif mode==Mode.RULE_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['rule_family_info'],r['rule_rev'],0]
        more=r['rule_remaining']>1;r.update(free=ref+1,rule_rev=ref,rule_remaining=r['rule_remaining']-1)
        if more:r.update(mode=Mode.RULE_CELL,x=r['rule_next'])
        else:call(CALL_RULE_VECTOR,Task.REVERSE_LIST,ref,reverse_length=r['core_ctor_declared'])
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
