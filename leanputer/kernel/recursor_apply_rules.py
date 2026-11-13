"""Compile generic derived recursor rule selection and source RHS application."""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_IOTA_ZIP, CALL_IOTA_PREFIX, CALL_IOTA_FIELDS, CALL_IOTA_EXTRA)

PRIVATE_PHASES = (CALL_IOTA_ZIP, CALL_IOTA_PREFIX, CALL_IOTA_FIELDS, CALL_IOTA_EXTRA)
TAGS = {Mode.WALK: CellTag.CHECKED_SIGNATURE, Mode.IOTA_SCHEME: CellTag.CHECKED_SCHEME,
    Mode.IOTA_METADATA: CellTag.CHECKED_RECURSOR, Mode.IOTA_COUNTS: CellTag.RECURSOR_COUNTS,
    Mode.IOTA_SHARED_COUNTS: CellTag.RECURSOR_SHARED_COUNTS,
    Mode.IOTA_REC_SPINE: CellTag.APPLICATION_SPINE, Mode.IOTA_MAJOR_SPINE: CellTag.APPLICATION_SPINE,
    Mode.IOTA_REC_ARGUMENTS: CellTag.VECTOR, Mode.IOTA_MAJOR_ARGUMENTS: CellTag.VECTOR,
    Mode.IOTA_RULE_VECTOR: CellTag.VECTOR, Mode.IOTA_RULE_CELL: CellTag.VECTOR_CELL,
    Mode.IOTA_RULE: CellTag.CHECKED_RULE, Mode.IOTA_PARAMETER_VECTOR: CellTag.VECTOR,
    Mode.IOTA_LEVEL_VECTOR: CellTag.VECTOR}
EXPRESSION_MODES = (Mode.IOTA_REC_HEAD, Mode.IOTA_MAJOR_HEAD)


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    def finish(guard, value=0):
        c.emit(guard, task=Task.APPLY_RECURSOR_RULE, sp=top); c.ret(guard, value)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)))
    phase = lambda p: c.AND(returning, c.eq(f['phase'], p))
    def apply(guard, p, vector, start, take):
        c.write('stack', guard, top, (p, 0, 0, Task.APPLY_RECURSOR_RULE, 0, 0))
        c.emit(guard, task=Task.APPLY_VECTOR_SLICE, mode=Mode.WALK, x=vector,
            slice_body=r['r'], slice_start=start, slice_take=take, depth=0)
    apply(phase(CALL_IOTA_ZIP), CALL_IOTA_PREFIX, r['iota_rec_args'], 0, r['iota_prefix'])
    apply(phase(CALL_IOTA_PREFIX), CALL_IOTA_FIELDS, r['iota_major_args'], c.sub(r['iota_major_count'], r['iota_fields']), r['iota_fields'])
    apply(phase(CALL_IOTA_FIELDS), CALL_IOTA_EXTRA, r['iota_rec_args'], c.add(r['iota_major_index'], 1), c.sub(c.sub(r['iota_arg_count'], r['iota_major_index']), 1))
    finish(phase(CALL_IOTA_EXTRA), r['r'])
    active = c.task(Task.APPLY_RECURSOR_RULE); at = lambda m: c.AND(active, c.mode(m))
    init = at(Mode.WALK); room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, room)
    c.write('stack', init, r['sp'], (CALL_IOTA_ZIP, 0, 0, Task.APPLY_RECURSOR_RULE, 0, 0))
    c.emit(init, sp=c.add(r['sp'], 1), iota_symbol=n['a'], mode=Mode.IOTA_SCHEME, x=n['c'])
    scheme = at(Mode.IOTA_SCHEME); rec = c.eq(n['b'], 10)
    finish(c.AND(scheme, c.NOT(rec)))
    c.emit(c.AND(scheme, rec), iota_parameters=n['a'], mode=Mode.IOTA_METADATA, x=n['c'])
    c.emit(at(Mode.IOTA_METADATA), iota_rules=n['c'], mode=Mode.IOTA_COUNTS, x=n['b'])
    c.emit(at(Mode.IOTA_COUNTS), iota_parameters_count=n['a'], iota_indices=n['b'], mode=Mode.IOTA_SHARED_COUNTS, x=n['c'])
    counted, prefix = c.checked_add(at(Mode.IOTA_SHARED_COUNTS), r['iota_parameters_count'], n['a'])
    counted, prefix = c.checked_add(counted, prefix, n['b'])
    counted, major = c.checked_add(counted, prefix, r['iota_indices'])
    c.emit(counted, iota_prefix=prefix, iota_major_index=major, mode=Mode.IOTA_REC_SPINE, x=r['reduction_rec_spine'])
    c.emit(at(Mode.IOTA_REC_SPINE), iota_rec_args=n['b'], mode=Mode.IOTA_REC_HEAD, x=n['a'])
    head = at(Mode.IOTA_REC_HEAD); valid = c.AND(c.tag(Tag.CONST), c.eq(n['a'], r['iota_symbol']))
    finish(c.AND(head, c.NOT(valid)))
    c.emit(c.AND(head, valid), iota_levels=n['b'], mode=Mode.IOTA_REC_ARGUMENTS, x=r['iota_rec_args'])
    def vector(mode, kind):
        guard = at(mode); valid = c.AND(c.eq(n['c'], kind), c.eq(c.mux(c.eq(n['a'], 0), 0, 1), c.mux(c.eq(n['b'], 0), 0, 1)))
        c.stop(c.AND(guard, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
        return c.AND(guard, valid)
    args = vector(Mode.IOTA_REC_ARGUMENTS, VectorKind.REFERENCES); present = c.lt(r['iota_major_index'], n['a'])
    finish(c.AND(args, c.NOT(present)))
    c.emit(c.AND(args, present), iota_arg_count=n['a'], mode=Mode.IOTA_MAJOR_SPINE, x=r['reduction_major_spine'])
    c.emit(at(Mode.IOTA_MAJOR_SPINE), iota_major_args=n['b'], mode=Mode.IOTA_MAJOR_HEAD, x=n['a'])
    head = at(Mode.IOTA_MAJOR_HEAD); valid = c.tag(Tag.CONST)
    finish(c.AND(head, c.NOT(valid)))
    c.emit(c.AND(head, valid), iota_constructor=n['a'], mode=Mode.IOTA_MAJOR_ARGUMENTS, x=r['iota_major_args'])
    args = vector(Mode.IOTA_MAJOR_ARGUMENTS, VectorKind.REFERENCES)
    c.emit(args, iota_major_count=n['a'], mode=Mode.IOTA_RULE_VECTOR, x=r['iota_rules'])
    rules = vector(Mode.IOTA_RULE_VECTOR, VectorKind.REFERENCES); empty = c.eq(n['a'], 0)
    finish(c.AND(rules, empty))
    c.emit(c.AND(rules, c.NOT(empty)), iota_remaining=n['a'], mode=Mode.IOTA_RULE_CELL, x=n['b'])
    cell = at(Mode.IOTA_RULE_CELL); more = c.lt(1, r['iota_remaining'])
    valid = c.AND(c.NOT(c.eq(r['iota_remaining'], 0)), c.eq(c.mux(c.eq(n['b'], 0), 0, 1), c.mux(more, 1, 0)))
    c.stop(c.AND(cell, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(cell, valid), iota_next=n['b'], mode=Mode.IOTA_RULE, x=n['a'])
    rule = at(Mode.IOTA_RULE); found = c.eq(n['a'], r['iota_constructor'])
    c.emit(c.AND(rule, c.NOT(found), more), iota_remaining=c.sub(r['iota_remaining'], 1), mode=Mode.IOTA_RULE_CELL, x=r['iota_next'])
    finish(c.AND(rule, c.NOT(found), c.NOT(more)))
    enough = c.NOT(c.lt(r['iota_major_count'], n['b']))
    finish(c.AND(rule, found, c.NOT(enough)))
    c.emit(c.AND(rule, found, enough), iota_fields=n['b'], iota_rhs=n['c'], mode=Mode.IOTA_PARAMETER_VECTOR, x=r['iota_parameters'])
    params = vector(Mode.IOTA_PARAMETER_VECTOR, VectorKind.SYMBOLS)
    c.emit(params, iota_uparams=n['a'], mode=Mode.IOTA_LEVEL_VECTOR, x=r['iota_levels'])
    levels = vector(Mode.IOTA_LEVEL_VECTOR, VectorKind.LEVELS); arity = c.eq(n['a'], r['iota_uparams'])
    finish(c.AND(levels, c.NOT(arity)))
    c.emit(c.AND(levels, arity), task=Task.INSTANTIATE_SCHEME, mode=Mode.WALK, x=r['iota_rhs'],
        parameter_vector=r['iota_parameters'], level_vector=r['iota_levels'], depth=0)
