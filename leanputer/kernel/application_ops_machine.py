"""Application spines and bounded vector slices, DEVELOPMENT reference only.

These syntax operations do not normalize, infer or admit their operands.
"""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason

NO_NODE = (Mode.SPINE_VECTOR, Mode.SPINE_RESULT)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    mode = r['mode']
    if r['task'] == Task.APPLICATION_SPINE:
        if mode == Mode.WALK:
            r.update(spine_head=0, spine_count=0, mode=Mode.SPINE_SCAN)
        elif mode == Mode.SPINE_SCAN:
            if tag != Tag.APP:
                r.update(spine_function=r['x'], mode=Mode.SPINE_VECTOR)
            elif r['free'] >= cfg.heap:
                stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                ref = r['free']; s['heap'][ref] = [CellTag.VECTOR_CELL, b, r['spine_head'], 0]
                r.update(free=ref+1, spine_head=ref, spine_count=r['spine_count']+1, x=a)
        elif mode == Mode.SPINE_VECTOR:
            if r['free']+2 > cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                ref = r['free']; s['heap'][ref] = [CellTag.VECTOR, r['spine_count'], r['spine_head'], VectorKind.REFERENCES]
                r.update(free=ref+1, spine_arguments=ref, mode=Mode.SPINE_RESULT)
        elif mode == Mode.SPINE_RESULT:
            ref = r['free']; s['heap'][ref] = [CellTag.APPLICATION_SPINE, r['spine_function'], r['spine_arguments'], 0]
            r['free'] = ref+1; ret(ref)
        else: stop(Outcome.INVALID, Reason.SYNTAX)
        return True
    if r['task'] == Task.VECTOR_REFERENCE:
        if mode == Mode.WALK:
            if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['vector_index'] >= a: ret(0)
            else: r.update(reference_remaining=a, mode=Mode.SLICE_CELL, x=b)
        elif mode == Mode.SLICE_CELL:
            if not r['reference_remaining'] or bool(b) != (r['reference_remaining'] > 1): stop(Outcome.INVALID, Reason.SYNTAX)
            elif not r['vector_index']: ret(a)
            else: r.update(vector_index=r['vector_index']-1, reference_remaining=r['reference_remaining']-1, x=b)
        else: stop(Outcome.INVALID, Reason.SYNTAX)
        return True
    if r['task'] != Task.APPLY_VECTOR_SLICE: return False
    if mode == Mode.WALK:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['slice_start'] > a or r['slice_take'] > a-r['slice_start']: stop(Outcome.INVALID, Reason.SYNTAX)
        elif not r['slice_take']: ret(r['slice_body'])
        else: r.update(slice_remaining=a, mode=Mode.SLICE_CELL, x=b)
    elif mode == Mode.SLICE_CELL:
        if not r['slice_remaining'] or bool(b) != (r['slice_remaining'] > 1): stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['slice_start']:
            r.update(slice_start=r['slice_start']-1, slice_remaining=r['slice_remaining']-1, x=b)
        else: r.update(slice_next=b, mode=Mode.SLICE_ARGUMENT, x=a)
    elif mode == Mode.SLICE_ARGUMENT:
        if r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            ref = r['free']; s['heap'][ref] = [Tag.APP, r['slice_body'], r['x'], 0]
            more = r['slice_take'] > 1
            r.update(free=ref+1, slice_body=ref, slice_take=r['slice_take']-1, slice_remaining=r['slice_remaining']-1)
            if more: r.update(mode=Mode.SLICE_CELL, x=r['slice_next'])
            else: ret(ref)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
