"""Compile canonical structured-name equality/prefix via shared payload equality."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason

TAGS = {Mode.WALK: CellTag.VECTOR, Mode.PATH_RIGHT_HEADER: CellTag.VECTOR,
    Mode.PATH_LEFT_CELL: CellTag.VECTOR_CELL, Mode.PATH_RIGHT_CELL: CellTag.VECTOR_CELL}
PART_MODES = (Mode.PATH_LEFT_PART, Mode.PATH_RIGHT_PART)


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)), c.eq(f['task'], Task.COMPARE_NAME_PATH))
    valid = c.eq(f['phase'], 0); truth = c.NOT(c.eq(r['r'], 0)); more = c.lt(1, r['path_left_remaining'])
    c.stop(c.AND(returning, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    def done(guard, value):
        c.emit(guard, task=Task.COMPARE_NAME_PATH, sp=top); c.ret(guard, value)
    done(c.AND(returning, valid, c.OR(c.NOT(truth), c.NOT(more))), c.mux(truth, 1, 0))
    c.emit(c.AND(returning, valid, truth, more), task=Task.COMPARE_NAME_PATH, mode=Mode.PATH_LEFT_CELL, x=r['path_next_left'],
        path_right_cursor=r['path_next_right'], path_left_remaining=c.sub(r['path_left_remaining'], 1), path_right_remaining=c.sub(r['path_right_remaining'], 1))
    active = c.task(Task.COMPARE_NAME_PATH); at = lambda m: c.AND(active, c.mode(m))
    wb = lambda v: c.mux(c.eq(v, 0), 0, 1)
    shape = c.AND(c.eq(n['c'], VectorKind.REFERENCES), c.eq(wb(n['a']), wb(n['b'])))
    init = at(Mode.WALK); valid = c.AND(shape, c.NOT(c.lt(1, r['path_prefix'])), c.NOT(c.eq(r['peer'], 0)), c.lt(r['peer'], r['free']))
    c.stop(c.AND(init, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, valid, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, valid, room)
    c.write('stack', init, r['sp'], (0, 0, 0, Task.COMPARE_NAME_PATH, 0, 0))
    c.emit(init, sp=c.add(r['sp'], 1), path_left_remaining=n['a'], path_left_head=n['b'], mode=Mode.PATH_RIGHT_HEADER, x=r['peer'])
    header = at(Mode.PATH_RIGHT_HEADER)
    c.stop(c.AND(header, c.NOT(shape)), Outcome.INVALID, Reason.SYNTAX)
    length = c.AND(c.NOT(c.lt(n['a'], r['path_left_remaining'])), c.OR(c.NOT(c.eq(r['path_prefix'], 0)), c.eq(n['a'], r['path_left_remaining'])))
    done(c.AND(header, shape, c.NOT(length)), 0)
    empty = c.eq(r['path_left_remaining'], 0)
    done(c.AND(header, shape, length, empty), 1)
    c.emit(c.AND(header, shape, length, c.NOT(empty)), path_right_remaining=n['a'], path_right_cursor=n['b'], mode=Mode.PATH_LEFT_CELL, x=r['path_left_head'])
    left = at(Mode.PATH_LEFT_CELL); valid = c.AND(c.NOT(c.eq(r['path_left_remaining'], 0)), c.eq(wb(n['b']), c.mux(more, 1, 0)))
    c.stop(c.AND(left, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(left, valid), path_next_left=n['b'], path_left_part=n['a'], mode=Mode.PATH_RIGHT_CELL, x=r['path_right_cursor'])
    right = at(Mode.PATH_RIGHT_CELL); valid = c.AND(c.NOT(c.eq(r['path_right_remaining'], 0)), c.eq(wb(n['b']), c.mux(c.lt(1, r['path_right_remaining']), 1, 0)))
    c.stop(c.AND(right, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(right, valid), path_next_right=n['b'], path_right_part=n['a'], mode=Mode.PATH_LEFT_PART, x=r['path_left_part'])
    c.emit(at(Mode.PATH_LEFT_PART), path_part_tag=n['tag'], path_part_payload=n['a'], mode=Mode.PATH_RIGHT_PART, x=r['path_right_part'])
    part = at(Mode.PATH_RIGHT_PART); same = c.eq(n['tag'], r['path_part_tag'])
    done(c.AND(part, c.NOT(same)), 0)
    c.emit(c.AND(part, same), task=Task.VECTOR_EQUAL, mode=Mode.WALK, x=r['path_part_payload'], peer=n['a'],
        vector_expected_role=c.mux(c.tag(CellTag.NAME_STRING), VectorKind.BYTES, VectorKind.LIMBS))
