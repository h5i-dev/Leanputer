"""Boolean IR for ALL-tag erased-syntax and typed-vector equality.

False is representation mismatch, never full definitional inequality. Private
pair/vector frames carry traversal data; no host equality or expected results.
"""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import (Mode, Task, Outcome, Reason,
    EXPR_EQUAL_REST, CALL_VECTOR_LEVEL_EQUAL)

PRIVATE_PHASES = (EXPR_EQUAL_REST, CALL_VECTOR_LEVEL_EQUAL)


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']
    a, b, x, result = n['a'], n['b'], r['x'], r['r']
    room, top = c.lt(r['sp'], c.cfg.stack), c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)))
    truth = c.NOT(c.eq(result, 0))
    rest = c.AND(returning, c.eq(f['phase'], EXPR_EQUAL_REST))
    more_pairs = c.NOT(c.eq(f['first'], 0))
    c.emit(c.AND(rest, c.OR(c.NOT(truth), c.NOT(more_pairs))), sp=top)
    c.ret(c.AND(rest, c.NOT(truth)), 0)
    c.write('stack', c.AND(rest, truth, more_pairs), top, (EXPR_EQUAL_REST, f['first'], f['second'], Task.EXPR_EQUAL, 0, 0))
    c.emit(c.AND(rest, truth), mode=Mode.WALK, task=Task.EXPR_EQUAL, x=f['original'], peer=f['depth'])
    vector_return = c.AND(returning, c.eq(f['phase'], CALL_VECTOR_LEVEL_EQUAL))
    c.emit(vector_return, sp=top)
    c.ret(c.AND(vector_return, c.NOT(truth)), 0)
    c.ret(c.AND(vector_return, truth, c.eq(f['first'], 0)), 1)
    c.emit(c.AND(vector_return, truth, c.NOT(c.eq(f['first'], 0))), mode=Mode.VECTOR_CELL_LEFT,
        task=Task.VECTOR_EQUAL, x=f['original'], peer=f['depth'], vector_remaining=f['first'], vector_expected_role=f['second'])

    entering = c.AND(c.mode(Mode.WALK), c.task(Task.EXPR_EQUAL))
    peer_ok = c.AND(c.NOT(c.eq(r['peer'], 0)), c.lt(r['peer'], r['free']))
    c.stop(c.AND(entering, c.NOT(peer_ok)), Outcome.INVALID, Reason.SYNTAX)
    entering = c.AND(entering, peer_ok)
    c.ret(c.AND(entering, c.eq(x, r['peer'])), 1)
    c.emit(c.AND(entering, c.NOT(c.eq(x, r['peer']))), mode=Mode.EXPR_EQUAL_RIGHT,
        left_tag=n['tag'], left_a=a, left_b=b, left_c=n['c'], x=r['peer'])
    right = c.mode(Mode.EXPR_EQUAL_RIGHT)
    same_tag = c.eq(r['left_tag'], n['tag'])
    c.ret(c.AND(right, c.NOT(same_tag)), 0)
    right = c.AND(right, same_tag)
    c.ret(c.AND(right, c.tag(Tag.BVAR, Tag.LOCAL)), c.mux(c.eq(r['left_a'], a), 1, 0))
    c.emit(c.AND(right, c.tag(Tag.SORT)), mode=Mode.WALK, task=Task.LEVEL_EQUAL, x=r['left_a'], peer=a)
    constant = c.AND(right, c.tag(Tag.CONST))
    c.ret(c.AND(constant, c.NOT(c.eq(r['left_a'], a))), 0)
    c.emit(c.AND(constant, c.eq(r['left_a'], a)), mode=Mode.WALK, task=Task.VECTOR_EQUAL,
        x=r['left_b'], peer=b, vector_expected_role=VectorKind.LEVELS)
    c.emit(c.AND(right, c.tag(Tag.NAT, Tag.STRING)), mode=Mode.WALK, task=Task.VECTOR_EQUAL,
        x=r['left_a'], peer=a, vector_expected_role=c.mux(c.tag(Tag.NAT), VectorKind.LIMBS, VectorKind.BYTES))
    projection = c.AND(right, c.tag(Tag.PROJ))
    same_projection = c.AND(c.eq(r['left_a'], a), c.eq(r['left_b'], b))
    c.ret(c.AND(projection, c.NOT(same_projection)), 0)
    c.emit(c.AND(projection, same_projection), mode=Mode.WALK, x=r['left_c'], peer=n['c'])
    c.emit(c.AND(right, c.tag(Tag.MDATA)), mode=Mode.WALK, x=r['left_a'], peer=a)
    branch = c.AND(right, c.tag(Tag.APP, Tag.PI, Tag.LAM, Tag.LET))
    c.stop(c.AND(branch, c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
    branch = c.AND(branch, room)
    c.write('stack', branch, r['sp'], (EXPR_EQUAL_REST, r['left_b'], b, Task.EXPR_EQUAL,
        c.mux(c.tag(Tag.LET), r['left_c'], 0), c.mux(c.tag(Tag.LET), n['c'], 0)))
    c.emit(branch, sp=c.add(r['sp'], 1), mode=Mode.WALK, x=r['left_a'], peer=a)

    vector_entering = c.AND(c.mode(Mode.WALK), c.task(Task.VECTOR_EQUAL))
    c.stop(c.AND(vector_entering, c.NOT(peer_ok)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(vector_entering, peer_ok), mode=Mode.VECTOR_HEADER_RIGHT, left_a=a, left_b=b, left_c=n['c'], x=r['peer'])
    header = c.mode(Mode.VECTOR_HEADER_RIGHT)
    valid_role = c.OR(*(c.eq(n['c'], role) for role in (VectorKind.LEVELS, VectorKind.LIMBS, VectorKind.BYTES)))
    bool_word = lambda word: c.mux(c.eq(word, 0), 0, 1)
    header_ok = c.AND(c.eq(n['c'], r['vector_expected_role']), c.eq(n['c'], r['left_c']), valid_role,
        c.eq(bool_word(a), bool_word(b)), c.eq(bool_word(r['left_a']), bool_word(r['left_b'])))
    c.stop(c.AND(header, c.NOT(header_ok)), Outcome.INVALID, Reason.SYNTAX)
    header = c.AND(header, header_ok)
    same_length = c.eq(a, r['left_a'])
    c.ret(c.AND(header, c.NOT(same_length)), 0)
    c.ret(c.AND(header, same_length, c.eq(a, 0)), 1)
    c.emit(c.AND(header, same_length, c.NOT(c.eq(a, 0))), mode=Mode.VECTOR_CELL_LEFT,
        x=r['left_b'], peer=b, vector_remaining=a)
    c.emit(c.mode(Mode.VECTOR_CELL_LEFT), mode=Mode.VECTOR_CELL_RIGHT, left_a=a, left_b=b, x=r['peer'])
    cell = c.mode(Mode.VECTOR_CELL_RIGHT)
    more = c.lt(1, r['vector_remaining'])
    cell_ok = c.AND(c.NOT(c.eq(r['vector_remaining'], 0)),
        c.eq(bool_word(b), c.mux(more, 1, 0)), c.eq(bool_word(r['left_b']), c.mux(more, 1, 0)))
    c.stop(c.AND(cell, c.NOT(cell_ok)), Outcome.INVALID, Reason.SYNTAX)
    cell = c.AND(cell, cell_ok)
    level = c.AND(cell, c.eq(r['vector_expected_role'], VectorKind.LEVELS))
    c.stop(c.AND(level, c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
    level = c.AND(level, room)
    c.write('stack', level, r['sp'], (CALL_VECTOR_LEVEL_EQUAL, r['left_b'], b, Task.VECTOR_EQUAL,
        c.sub(r['vector_remaining'], 1), r['vector_expected_role']))
    c.emit(level, sp=c.add(r['sp'], 1), mode=Mode.WALK, task=Task.LEVEL_EQUAL, x=r['left_a'], peer=a)
    scalar = c.AND(cell, c.NOT(c.eq(r['vector_expected_role'], VectorKind.LEVELS)))
    equal_value = c.eq(r['left_a'], a)
    c.ret(c.AND(scalar, c.NOT(equal_value)), 0)
    c.ret(c.AND(scalar, equal_value, c.NOT(more)), 1)
    c.emit(c.AND(scalar, equal_value, more), mode=Mode.VECTOR_CELL_LEFT,
        x=r['left_b'], peer=b, vector_remaining=c.sub(r['vector_remaining'], 1))
