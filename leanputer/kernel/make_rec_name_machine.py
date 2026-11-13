"""Kernel mk_rec_name and its indexed restoration call site, DEVELOPMENT."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']; phase, path, index, _, indexed, decimal = frame
    def call(p, task, x, **updates):
        s['stack'][r['sp']-1] = [p, path, index, Task.MAKE_RECURSOR_NAME, indexed, decimal]
        r.update(task=task, mode=Mode.WALK, x=x, depth=0, **updates)
    if phase == 0:
        path = r['r']; s['stack'][r['sp']-1][1] = path
        if indexed: call(1, Task.WORD_DECIMAL, 0, decimal_value=index)
        else: r.update(task=Task.MAKE_RECURSOR_NAME, mode=Mode.GEN_REC_SUFFIX)
    elif phase == 1:
        s['stack'][r['sp']-1][5] = r['r']
        r.update(task=Task.MAKE_RECURSOR_NAME, mode=Mode.GEN_REC_SUFFIX)
    elif phase == 2: r.update(task=Task.MAKE_RECURSOR_NAME, mode=Mode.GEN_REC_COMPONENT, generated_suffix_bytes=r['r'])
    elif phase == 3: call(4, Task.INTERN_NAME_PATH, r['r'])
    elif phase == 4:
        r.update(task=Task.MAKE_RECURSOR_NAME, sp=r['sp']-1); ret(r['r'])
    else: stop(Outcome.INVALID, Reason.SYNTAX)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.MAKE_RECURSOR_NAME: return False
    frame = s['stack'][r['sp']-1] if r['sp'] else None
    def room():
        if r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP); return False
        return True
    def call(p, task, x, **updates):
        frame[0] = p; r.update(task=task, mode=Mode.WALK, x=x, depth=0, **updates)
    mode = r['mode']
    if mode == Mode.WALK:
        if r['generated_rec_indexed'] > 1: stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [0, r['query_symbol'], r['generated_rec_index'], Task.MAKE_RECURSOR_NAME, r['generated_rec_indexed'], 0]
            r.update(sp=r['sp']+1, task=Task.GET_NAME_PATH, x=r['symbols_root'])
    elif mode == Mode.GEN_REC_SUFFIX:
        length = 4 if frame[4] else 3
        r.update(generated_suffix_head=0, generated_suffix_length=length, generated_suffix_remaining=length, mode=Mode.GEN_REC_BYTE)
    elif mode == Mode.GEN_REC_BYTE:
        if not 1 <= r['generated_suffix_remaining'] <= 4: stop(Outcome.INVALID, Reason.SYNTAX)
        elif room():
            ref = r['free']; value = ord('rec_'[r['generated_suffix_remaining']-1])
            s['heap'][ref] = [CellTag.VECTOR_CELL, value, r['generated_suffix_head'], 0]
            more = r['generated_suffix_remaining'] > 1
            r.update(free=ref+1, generated_suffix_head=ref, generated_suffix_remaining=r['generated_suffix_remaining']-1,
                mode=Mode.GEN_REC_BYTE if more else Mode.GEN_REC_BYTES)
    elif mode == Mode.GEN_REC_BYTES:
        if room():
            ref = r['free']; s['heap'][ref] = [CellTag.VECTOR, r['generated_suffix_length'], r['generated_suffix_head'], VectorKind.BYTES]
            r.update(free=ref+1, generated_suffix_bytes=ref)
            if frame[4]: call(2, Task.VECTOR_SPLICE, ref, peer=frame[5], splice_role=VectorKind.BYTES, splice_skip=0)
            else: r['mode'] = Mode.GEN_REC_COMPONENT
    elif mode == Mode.GEN_REC_COMPONENT:
        if room():
            ref = r['free']; s['heap'][ref] = [CellTag.NAME_STRING, r['generated_suffix_bytes'], 0, 0]
            r.update(free=ref+1, generated_name_component=ref, mode=Mode.GEN_REC_CELL)
    elif mode == Mode.GEN_REC_CELL:
        if room():
            ref = r['free']; s['heap'][ref] = [CellTag.VECTOR_CELL, r['generated_name_component'], 0, 0]
            r.update(free=ref+1, generated_name_cell=ref, mode=Mode.GEN_REC_PATH)
    elif mode == Mode.GEN_REC_PATH:
        if room():
            ref = r['free']; s['heap'][ref] = [CellTag.VECTOR, 1, r['generated_name_cell'], VectorKind.REFERENCES]
            r['free'] = ref+1
            call(3, Task.VECTOR_SPLICE, frame[1], peer=ref, splice_role=VectorKind.REFERENCES, splice_skip=0)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
