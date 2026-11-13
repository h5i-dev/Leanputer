"""Source mk_rec_name relation over structured DATA; DEVELOPMENT reference.

Arbitrary parent paths and string/numeral segments use shared vector comparison.
Only the actual kernel suffix 'rec' is literal. Raw recursor names are claims,
not trusted generated declarations; no supplied name/type/admission answer.
"""
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_RECNAME_PARENT,
    CALL_RECNAME_CANDIDATE,CALL_RECNAME_COMPONENT)

PRIVATE_PHASES=(CALL_RECNAME_PARENT,CALL_RECNAME_CANDIDATE,CALL_RECNAME_COMPONENT)


def resume(machine,frame,stop,ret,alloc):
    s,r=machine.state,machine.state['regs'];phase=frame[0]
    if phase==CALL_RECNAME_PARENT:
        r['recname_parent_path']=r['r']
        s['stack'][r['sp']-1]=[CALL_RECNAME_CANDIDATE,0,0,Task.CHECK_RECURSOR_NAME,0,0]
        r.update(task=Task.GET_NAME_PATH,mode=Mode.WALK,x=r['symbols_root'],query_symbol=r['name_candidate_symbol'])
    elif phase==CALL_RECNAME_CANDIDATE:
        r.update(task=Task.CHECK_RECURSOR_NAME,mode=Mode.RECNAME_LEFT_HEADER,x=r['recname_parent_path'],recname_candidate_path=r['r'])
    elif not r['r']:r['sp']-=1;ret(0)
    elif r['recname_remaining']>1:
        r.update(task=Task.CHECK_RECURSOR_NAME,mode=Mode.RECNAME_LEFT_CELL,x=r['recname_next_left'],
            recname_right=r['recname_next_right'],recname_remaining=r['recname_remaining']-1)
    else:r.update(task=Task.CHECK_RECURSOR_NAME,mode=Mode.RECNAME_SUFFIX_CELL,x=r['recname_next_right'],recname_remaining=0)


def step(machine,tag,a,b,c,stop,ret,alloc):
    s,r,cfg=machine.state,machine.state['regs'],machine.cfg
    if r['task']!=Task.CHECK_RECURSOR_NAME:return False
    def done(value):r['sp']-=1;ret(value)
    mode=r['mode']
    if mode==Mode.WALK:
        if r['sp']>=cfg.stack:stop(Outcome.RESOURCE,Reason.STACK)
        else:
            s['stack'][r['sp']]=[CALL_RECNAME_PARENT,0,0,Task.CHECK_RECURSOR_NAME,0,0]
            r.update(sp=r['sp']+1,task=Task.GET_NAME_PATH,x=r['symbols_root'],query_symbol=r['name_parent_symbol'])
    elif mode==Mode.RECNAME_LEFT_HEADER:
        if c!=VectorKind.REFERENCES or not a or not b:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.RECNAME_RIGHT_HEADER,x=r['recname_candidate_path'],recname_length=a,recname_head=b)
    elif mode==Mode.RECNAME_RIGHT_HEADER:
        if c!=VectorKind.REFERENCES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif a!=r['recname_length']+1:done(0)
        else:r.update(mode=Mode.RECNAME_LEFT_CELL,x=r['recname_head'],recname_remaining=r['recname_length'],recname_right=b)
    elif mode==Mode.RECNAME_LEFT_CELL:
        if not r['recname_remaining'] or bool(b)!=(r['recname_remaining']>1):stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.RECNAME_RIGHT_CELL,x=r['recname_right'],recname_next_left=b,recname_part_left=a)
    elif mode==Mode.RECNAME_RIGHT_CELL:
        if not b:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.RECNAME_LEFT_PART,x=r['recname_part_left'],recname_next_right=b,recname_part_right=a)
    elif mode==Mode.RECNAME_LEFT_PART:r.update(mode=Mode.RECNAME_RIGHT_PART,x=r['recname_part_right'],recname_part_tag=tag,recname_part_value=a)
    elif mode==Mode.RECNAME_RIGHT_PART:
        if tag!=r['recname_part_tag']:done(0)
        else:
            s['stack'][r['sp']-1]=[CALL_RECNAME_COMPONENT,0,0,Task.CHECK_RECURSOR_NAME,0,0]
            r.update(task=Task.VECTOR_EQUAL,mode=Mode.WALK,x=r['recname_part_value'],peer=a,
                vector_expected_role=VectorKind.BYTES if tag==CellTag.NAME_STRING else VectorKind.LIMBS)
    elif mode==Mode.RECNAME_SUFFIX_CELL:
        if b:stop(Outcome.INVALID,Reason.SYNTAX)
        else:r.update(mode=Mode.RECNAME_SUFFIX_PART,x=a)
    elif mode==Mode.RECNAME_SUFFIX_PART:
        if tag==CellTag.NAME_NUMERAL:done(0)
        else:r.update(mode=Mode.RECNAME_SUFFIX_HEADER,x=a)
    elif mode==Mode.RECNAME_SUFFIX_HEADER:
        if c!=VectorKind.BYTES or bool(a)!=bool(b):stop(Outcome.INVALID,Reason.SYNTAX)
        elif a!=3:done(0)
        else:r.update(mode=Mode.RECNAME_SUFFIX_BYTE,x=b,recname_byte_index=0)
    elif mode==Mode.RECNAME_SUFFIX_BYTE:
        if r['recname_byte_index']>=3 or bool(b)!=(r['recname_byte_index']<2):stop(Outcome.INVALID,Reason.SYNTAX)
        elif a!=ord('rec'[r['recname_byte_index']]):done(0)
        elif r['recname_byte_index']==2:done(1)
        else:r.update(x=b,recname_byte_index=r['recname_byte_index']+1)
    else:stop(Outcome.INVALID,Reason.SYNTAX)
    return True
