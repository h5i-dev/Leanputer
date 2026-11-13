"""Complete source is_nested_inductive_app predicate, DEVELOPMENT reference.

Registry provenance belongs to restored source publication, still unfinished.
This operation never authorizes a block or supplies any inferred type.
"""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason
from .nested_application_rules import TAGS, NO_NODE


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']; phase, parameter, origin, _, spine, arguments = frame
    def call(p, task, x, **updates):
        s['stack'][r['sp']-1] = [p, parameter, origin, Task.IS_NESTED_APPLICATION, spine, arguments]
        r.update(task=task, mode=Mode.WALK, x=x, depth=0, **updates)
    if phase == 0:
        s['stack'][r['sp']-1][4] = r['r']
        r.update(task=Task.IS_NESTED_APPLICATION, mode=Mode.NESTED_APP_SPINE, x=r['r'])
    elif phase == 1:
        if not r['r']:
            r.update(task=Task.IS_NESTED_APPLICATION, sp=r['sp']-1); ret(0)
        else:
            s['stack'][r['sp']-1][2] = r['r']
            r.update(task=Task.IS_NESTED_APPLICATION, mode=Mode.NESTED_APP_ORIGIN, x=r['r'])
    elif phase == 2:
        parameter = r['r']; call(3, Task.HAS_RAW_FAMILIES, parameter)
    elif phase == 3:
        r['nested_has_current'] = int(bool(r['nested_has_current'] or r['r']))
        call(4, Task.HAS_LOOSE_BVARS, parameter)
    elif phase == 4:
        loose = int(bool(r['nested_has_loose'] or r['r'])); r['nested_has_loose'] = loose
        if r['nested_parameter_index']+1 < r['nested_parameter_count']:
            r.update(task=Task.IS_NESTED_APPLICATION, mode=Mode.NESTED_APP_SELECT, nested_parameter_index=r['nested_parameter_index']+1)
        elif not r['nested_has_current']:
            r.update(task=Task.IS_NESTED_APPLICATION, sp=r['sp']-1); ret(0)
        elif loose: stop(Outcome.INVALID, Reason.INVALID_NESTED_PARAMETERS)
        else: r.update(task=Task.IS_NESTED_APPLICATION, mode=Mode.NESTED_APP_RESULT)
    else: stop(Outcome.INVALID, Reason.SYNTAX)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.IS_NESTED_APPLICATION: return False
    frame = s['stack'][r['sp']-1] if r['sp'] else None
    def finish(): r.update(sp=r['sp']-1); ret(0)
    mode = r['mode']
    if mode == Mode.WALK:
        if tag != Tag.APP: ret(0)
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [0, 0, 0, Task.IS_NESTED_APPLICATION, 0, 0]
            r.update(sp=r['sp']+1, task=Task.APPLICATION_SPINE)
    elif mode == Mode.NESTED_APP_SPINE:
        frame[5] = b; r.update(mode=Mode.NESTED_APP_HEAD, x=a)
    elif mode == Mode.NESTED_APP_HEAD:
        if tag != Tag.CONST: finish()
        else:
            frame[0] = 1
            r.update(task=Task.PRIOR_BLOCK_LOOKUP, mode=Mode.WALK, x=r['nested_registry_head'], query_symbol=a, depth=0)
    elif mode == Mode.NESTED_APP_ORIGIN: r.update(mode=Mode.NESTED_APP_BLOCK, x=a)
    elif mode == Mode.NESTED_APP_BLOCK:
        r.update(nested_parameter_count=a, mode=Mode.NESTED_APP_ARGUMENTS, x=frame[5])
    elif mode == Mode.NESTED_APP_ARGUMENTS:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif a < r['nested_parameter_count'] or not r['nested_parameter_count']: finish()
        else: r.update(nested_parameter_index=0, nested_has_current=0, nested_has_loose=0, mode=Mode.NESTED_APP_SELECT)
    elif mode == Mode.NESTED_APP_SELECT:
        frame[0] = 2
        r.update(task=Task.VECTOR_REFERENCE, mode=Mode.WALK, x=frame[5], vector_index=r['nested_parameter_index'], depth=0)
    elif mode == Mode.NESTED_APP_RESULT:
        if r['free'] >= cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP)
        else:
            ref = r['free']; s['heap'][ref] = [CellTag.NESTED_APPLICATION, frame[2], frame[4], 0]
            r.update(free=ref+1, sp=r['sp']-1); ret(ref)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
