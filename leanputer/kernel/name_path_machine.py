"""Generic structured name equality/prefix traversal, DEVELOPMENT reference."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def resume(machine, frame, stop, ret, alloc):
    r = machine.state['regs']
    if frame[0] != 0: stop(Outcome.INVALID, Reason.SYNTAX)
    elif not r['r'] or r['path_left_remaining'] == 1:
        r.update(task=Task.COMPARE_NAME_PATH, sp=r['sp']-1); ret(int(bool(r['r'])))
    else:
        r.update(task=Task.COMPARE_NAME_PATH, mode=Mode.PATH_LEFT_CELL, x=r['path_next_left'],
            path_right_cursor=r['path_next_right'], path_left_remaining=r['path_left_remaining']-1,
            path_right_remaining=r['path_right_remaining']-1)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.COMPARE_NAME_PATH: return False
    def done(value):
        r['sp'] -= 1; ret(value)
    mode = r['mode']
    if mode == Mode.WALK:
        if c != VectorKind.REFERENCES or bool(a) != bool(b) or r['path_prefix'] > 1 or not 0 < r['peer'] < r['free']:
            stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [0, 0, 0, Task.COMPARE_NAME_PATH, 0, 0]
            r.update(sp=r['sp']+1, path_left_remaining=a, path_left_head=b, mode=Mode.PATH_RIGHT_HEADER, x=r['peer'])
    elif mode == Mode.PATH_RIGHT_HEADER:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif a < r['path_left_remaining'] or (not r['path_prefix'] and a != r['path_left_remaining']): done(0)
        elif not r['path_left_remaining']: done(1)
        else: r.update(path_right_remaining=a, path_right_cursor=b, mode=Mode.PATH_LEFT_CELL, x=r['path_left_head'])
    elif mode == Mode.PATH_LEFT_CELL:
        if not r['path_left_remaining'] or bool(b) != (r['path_left_remaining'] > 1): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(path_next_left=b, path_left_part=a, mode=Mode.PATH_RIGHT_CELL, x=r['path_right_cursor'])
    elif mode == Mode.PATH_RIGHT_CELL:
        if not r['path_right_remaining'] or bool(b) != (r['path_right_remaining'] > 1): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(path_next_right=b, path_right_part=a, mode=Mode.PATH_LEFT_PART, x=r['path_left_part'])
    elif mode == Mode.PATH_LEFT_PART:
        r.update(path_part_tag=tag, path_part_payload=a, mode=Mode.PATH_RIGHT_PART, x=r['path_right_part'])
    elif mode == Mode.PATH_RIGHT_PART:
        if tag != r['path_part_tag']: done(0)
        else:
            r.update(task=Task.VECTOR_EQUAL, mode=Mode.WALK, x=r['path_part_payload'], peer=a,
                vector_expected_role=VectorKind.BYTES if tag == CellTag.NAME_STRING else VectorKind.LIMBS)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
