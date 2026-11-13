"""Generic Name.replacePrefix composition, DEVELOPMENT reference only."""
from .native_cells import VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']; phase, original, old, _, new, path = frame
    def call(p, task, x, **updates):
        s['stack'][r['sp']-1] = [p, original, old, Task.REPLACE_NAME_PREFIX, new, path]
        r.update(task=task, mode=Mode.WALK, x=x, depth=0, **updates)
    if phase == 0:
        path = r['r']; call(1, Task.GET_NAME_PATH, r['symbols_root'], query_symbol=old)
    elif phase == 1:
        old = r['r']; call(2, Task.COMPARE_NAME_PATH, old, peer=path, path_prefix=1)
    elif phase == 2:
        if not r['r']:
            r.update(task=Task.REPLACE_NAME_PREFIX, sp=r['sp']-1); ret(original)
        else: call(3, Task.GET_NAME_PATH, r['symbols_root'], query_symbol=new)
    elif phase == 3:
        s['stack'][r['sp']-1][4] = r['r']
        r.update(task=Task.REPLACE_NAME_PREFIX, mode=Mode.REPLACE_PREFIX_HEADER, x=old)
    elif phase == 4: call(5, Task.INTERN_NAME_PATH, r['r'])
    elif phase == 5:
        r.update(task=Task.REPLACE_NAME_PREFIX, sp=r['sp']-1); ret(r['r'])
    else: stop(Outcome.INVALID, Reason.SYNTAX)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.REPLACE_NAME_PREFIX: return False
    if r['mode'] == Mode.WALK:
        if r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [0, r['query_symbol'], r['name_parent_symbol'], Task.REPLACE_NAME_PREFIX, r['name_candidate_symbol'], 0]
            r.update(sp=r['sp']+1, task=Task.GET_NAME_PATH, x=r['symbols_root'])
    elif r['mode'] == Mode.REPLACE_PREFIX_HEADER:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        else:
            frame = s['stack'][r['sp']-1]; frame[0] = 4
            r.update(task=Task.VECTOR_SPLICE, mode=Mode.WALK, x=frame[4], peer=frame[5], splice_role=VectorKind.REFERENCES, splice_skip=a)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
