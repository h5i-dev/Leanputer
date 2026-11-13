"""Generic private recursor metadata/signature assembly, DEVELOPMENT only."""
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_ASM_FAMILIES,
    CALL_ASM_RULES,CALL_ASM_SIGNATURES)
from .assemble_recursors_rules import NO_NODE,TAGS

PRIVATE_PHASES=(CALL_ASM_FAMILIES,CALL_ASM_RULES,CALL_ASM_SIGNATURES)


def resume(machine,frame,stop,ret,alloc):
    r=machine.state['regs']
    if frame[0]==CALL_ASM_FAMILIES:r.update(task=Task.ASSEMBLE_RECURSORS,core_family_vector=r['r'],mode=Mode.ASM_BLOCK)
    elif frame[0]==CALL_ASM_RULES:
        if r['asm_group_count']!=r['asm_expected']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(task=Task.ASSEMBLE_RECURSORS,asm_group=r['r'],mode=Mode.ASM_COUNTS)
    elif frame[0]==CALL_ASM_SIGNATURES:
        r.update(task=Task.ASSEMBLE_RECURSORS,core_rec_signatures=r['r'],sp=r['sp']-1);ret(r['r'])


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.ASSEMBLE_RECURSORS:return False
    def reverse(p,head,count):
        s['stack'][r['sp']-1]=[p,0,0,Task.ASSEMBLE_RECURSORS,0,0]
        r.update(task=Task.REVERSE_LIST,mode=Mode.WALK,x=head,reverse_length=count,depth=0)
    def advance_rule():
        more=r['asm_rule_remaining']>1;r['asm_rule_remaining']-=1
        if more:r.update(mode=Mode.ASM_RULE_CELL,x=r['asm_rule_next'])
        else:reverse(CALL_ASM_RULES,r['asm_group_rev'],r['asm_group_count'])
    def room(size=1):
        if r['free']+size>cfg.heap:stop(Outcome.RESOURCE,Reason.HEAP);return False
        return True
    mode=r['mode']
    if mode==Mode.WALK:
        if not r['core_rules'] or not r['core_rec_types'] or not r['core_flags'] or not r['typing_active'] or not r['header_seen']:
            stop(Outcome.INVALID,Reason.SYNTAX)
        elif r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_ASM_FAMILIES,0,0,Task.ASSEMBLE_RECURSORS,0,0]
            r.update(sp=r['sp']+1,asm_names_remaining=r['header_seen'],asm_family_rev=0,asm_sig_rev=0,mode=Mode.ASM_NAMES,x=r['core_rec_names'])
    elif mode==Mode.ASM_NAMES:
        if not r['asm_names_remaining'] or bool(c)!=(r['asm_names_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(asm_family_value=a,asm_name_next=c,mode=Mode.ASM_FAMILY_LINK)
    elif mode==Mode.ASM_FAMILY_LINK:
        if room():
            ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['asm_family_value'],r['asm_family_rev'],0]
            more=r['asm_names_remaining']>1;r.update(free=ref+1,asm_family_rev=ref,asm_names_remaining=r['asm_names_remaining']-1)
            if more:r.update(mode=Mode.ASM_NAMES,x=r['asm_name_next'])
            else:reverse(CALL_ASM_FAMILIES,ref,r['header_seen'])
    elif mode==Mode.ASM_BLOCK:
        if room(2):
            ref=r['free'];s['heap'][ref]=[CellTag.RECURSOR_BLOCK,r['core_K'],r['core_flags'],r['core_family_vector']]
            r.update(free=ref+1,asm_block=ref,mode=Mode.ASM_AUX)
    elif mode==Mode.ASM_AUX:
        ref=r['free'];s['heap'][ref]=[CellTag.RECURSOR_SHARED_COUNTS,r['header_seen'],r['core_ctor_declared'],r['asm_block']]
        r.update(free=ref+1,asm_aux=ref,mode=Mode.ASM_VECTOR,x=r['core_rec_types'])
    elif mode==Mode.ASM_VECTOR:
        if c!=VectorKind.REFERENCES or not a or not b or a!=r['header_seen']:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(asm_remaining=a,mode=Mode.ASM_CELL,x=b)
    elif mode==Mode.ASM_CELL:
        if not r['asm_remaining'] or bool(b)!=(r['asm_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(asm_next=b,mode=Mode.ASM_TYPE,x=a)
    elif mode==Mode.ASM_TYPE:r.update(asm_family=a,asm_type=b,asm_symbol=c,asm_group_rev=0,asm_group_count=0,mode=Mode.ASM_OWNER,x=a)
    elif mode==Mode.ASM_OWNER:r.update(mode=Mode.ASM_SCHEME,x=c)
    elif mode==Mode.ASM_SCHEME:
        if b!=8:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.ASM_HEADER,x=c)
    elif mode==Mode.ASM_HEADER:r.update(asm_indices=a,mode=Mode.ASM_RAW_FAMILY,x=c)
    elif mode==Mode.ASM_RAW_FAMILY:r.update(mode=Mode.ASM_RAW_AUX,x=c)
    elif mode==Mode.ASM_RAW_AUX:r.update(mode=Mode.ASM_CTOR_VECTOR,x=a)
    elif mode==Mode.ASM_CTOR_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(asm_expected=a,mode=Mode.ASM_RULE_VECTOR,x=r['core_rules'])
    elif mode==Mode.ASM_RULE_VECTOR:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b) or a!=r['core_ctor_declared']:stop(Outcome.INVALID,Reason.SYNTAX)
        elif not a:reverse(CALL_ASM_RULES,0,0)
        else:r.update(asm_rule_remaining=a,mode=Mode.ASM_RULE_CELL,x=b)
    elif mode==Mode.ASM_RULE_CELL:
        if not r['asm_rule_remaining'] or bool(b)!=(r['asm_rule_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(asm_rule_next=b,mode=Mode.ASM_RULE_INFO,x=a)
    elif mode==Mode.ASM_RULE_INFO:
        if a==r['asm_family']:r.update(asm_rule_ref=b,mode=Mode.ASM_RULE_STORE)
        else:advance_rule()
    elif mode==Mode.ASM_RULE_STORE:
        if room():
            ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['asm_rule_ref'],r['asm_group_rev'],0]
            r.update(free=ref+1,asm_group_rev=ref,asm_group_count=r['asm_group_count']+1);advance_rule()
    elif mode==Mode.ASM_COUNTS:
        if room(6):
            ref=r['free'];s['heap'][ref]=[CellTag.RECURSOR_COUNTS,r['header_parameter_count'],r['asm_indices'],r['asm_aux']]
            r.update(free=ref+1,asm_counts=ref,mode=Mode.ASM_RECURSOR)
    elif mode==Mode.ASM_RECURSOR:
        ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_RECURSOR,r['asm_family'],r['asm_counts'],r['asm_group']]
        r.update(free=ref+1,asm_rec=ref,mode=Mode.ASM_STORE_SCHEME)
    elif mode==Mode.ASM_STORE_SCHEME:
        ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_SCHEME,r['core_rec_parameters'],10,r['asm_rec']]
        r.update(free=ref+1,asm_scheme=ref,mode=Mode.ASM_SIGNATURE)
    elif mode==Mode.ASM_SIGNATURE:
        ref=r['free'];s['heap'][ref]=[CellTag.CHECKED_SIGNATURE,r['asm_symbol'],r['asm_type'],r['asm_scheme']]
        r.update(free=ref+1,asm_signature=ref,mode=Mode.ASM_LINK)
    elif mode==Mode.ASM_LINK:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['asm_signature'],r['typing_head'],0]
        r.update(free=ref+1,typing_head=ref,mode=Mode.ASM_SIG_ORDER)
    elif mode==Mode.ASM_SIG_ORDER:
        ref=r['free'];s['heap'][ref]=[CellTag.VECTOR_CELL,r['asm_signature'],r['asm_sig_rev'],0]
        more=r['asm_remaining']>1;r.update(free=ref+1,asm_sig_rev=ref,asm_remaining=r['asm_remaining']-1)
        if more:r.update(mode=Mode.ASM_CELL,x=r['asm_next'])
        else:reverse(CALL_ASM_SIGNATURES,ref,r['header_seen'])
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
