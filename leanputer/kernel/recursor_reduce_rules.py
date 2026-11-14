"""Compile reentrant generic recursor reduction and the stock WHNF-stack bridge."""
from enum import IntEnum
from .arena import Tag
from .native_cells import CellTag
from .traversal_machine import (Mode, Task, Outcome, Reason,
    PENDING_ARGUMENT, CALL_INFER_CONSTANT_LOOKUP)


class Phase(IntEnum):
    SPINE = 0
    LOOKUP = 1
    SELECT = 2
    PREPARED = 3
    PREPARED_SPINE = 4
    APPLIED = 5


NO_NODE = (Mode.GATHER_SCAN, Mode.GATHER_SAVE)
REDUCE_TAGS = {Mode.REDUCE_SPINE: CellTag.APPLICATION_SPINE,
    Mode.REDUCE_SIGNATURE: CellTag.CHECKED_SIGNATURE, Mode.REDUCE_SCHEME: CellTag.CHECKED_SCHEME,
    Mode.REDUCE_METADATA: CellTag.CHECKED_RECURSOR, Mode.REDUCE_COUNTS: CellTag.RECURSOR_COUNTS,
    Mode.REDUCE_SHARED: CellTag.RECURSOR_SHARED_COUNTS, Mode.REDUCE_ARGUMENTS: CellTag.APPLICATION_SPINE}
GATHER_TAGS = {Mode.WALK: Tag.CONST, Mode.GATHER_RESTORE: CellTag.REDUCER_CALL}


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    nonempty = c.NOT(c.eq(r['sp'], 0)); returning = c.AND(c.mode(Mode.RETURN), nonempty)
    owner = c.eq(f['task'], Task.REDUCE_RECURSOR)
    phase = lambda p: c.AND(returning, owner, c.eq(f['phase'], p))
    def call(guard, p, task, x, **updates):
        c.write('stack', guard, top, (p, f['original'], f['depth'], Task.REDUCE_RECURSOR, f['first'], f['second']))
        c.emit(guard, task=task, mode=Mode.WALK, x=x, depth=0, **updates)
    def finish(guard, value=0):
        c.emit(guard, task=Task.REDUCE_RECURSOR, sp=top); c.ret(guard, value)
    valid_phase = c.OR(*(c.eq(f['phase'], p) for p in Phase))
    c.stop(c.AND(returning, owner, c.NOT(valid_phase)), Outcome.INVALID, Reason.SYNTAX)
    split = phase(Phase.SPINE)
    c.write('stack', split, top, (Phase.SPINE, f['original'], f['depth'], Task.REDUCE_RECURSOR, r['r'], f['second']))
    c.emit(split, task=Task.REDUCE_RECURSOR, mode=Mode.REDUCE_SPINE, x=r['r'])
    looked = phase(Phase.LOOKUP); found = c.NOT(c.eq(r['r'], 0))
    finish(c.AND(looked, c.NOT(found))); looked = c.AND(looked, found)
    c.write('stack', looked, top, (Phase.LOOKUP, f['original'], f['depth'], Task.REDUCE_RECURSOR, f['first'], r['r']))
    c.emit(looked, task=Task.REDUCE_RECURSOR, mode=Mode.REDUCE_SIGNATURE, x=r['r'])
    selected = phase(Phase.SELECT); present = c.NOT(c.eq(r['r'], 0))
    finish(c.AND(selected, c.NOT(present)))
    call(c.AND(selected, present), Phase.PREPARED, Task.PREPARE_RECURSOR_MAJOR, f['depth'], major_value=r['r'])
    call(phase(Phase.PREPARED), Phase.PREPARED_SPINE, Task.APPLICATION_SPINE, r['r'])
    call(phase(Phase.PREPARED_SPINE), Phase.APPLIED, Task.APPLY_RECURSOR_RULE, f['second'],
        reduction_rec_spine=f['first'], reduction_major_spine=r['r'])
    finish(phase(Phase.APPLIED), r['r'])
    reduce = c.task(Task.REDUCE_RECURSOR); at = lambda m: c.AND(reduce, c.mode(m))
    init = at(Mode.WALK); ready = c.NOT(c.eq(r['env_ready'], 0)); room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, c.NOT(ready)), Outcome.GAP, Reason.GAP_ENVIRONMENT)
    c.stop(c.AND(init, ready, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, ready, room)
    c.write('stack', init, r['sp'], (Phase.SPINE, r['x'], 0, Task.REDUCE_RECURSOR, 0, 0))
    c.emit(init, sp=c.add(r['sp'], 1), task=Task.APPLICATION_SPINE)
    c.emit(at(Mode.REDUCE_SPINE), mode=Mode.REDUCE_HEAD, x=n['a'])
    head = at(Mode.REDUCE_HEAD); constant = c.tag(Tag.CONST)
    finish(c.AND(head, c.NOT(constant)))
    call(c.AND(head, constant), Phase.LOOKUP, Task.ENV_LOOKUP, r['x'], query_symbol=n['a'],
        lookup_head=c.mux(c.eq(r['typing_active'], 0), r['env_head'], r['typing_head']))
    c.emit(at(Mode.REDUCE_SIGNATURE), mode=Mode.REDUCE_SCHEME, x=n['c'])
    scheme = at(Mode.REDUCE_SCHEME); recursor = c.eq(n['b'], 10)
    finish(c.AND(scheme, c.NOT(recursor)))
    c.write('stack', c.AND(scheme, recursor), top, (f['phase'], f['original'], n['c'], Task.REDUCE_RECURSOR, f['first'], f['second']))
    c.emit(c.AND(scheme, recursor), mode=Mode.REDUCE_METADATA, x=n['c'])
    c.emit(at(Mode.REDUCE_METADATA), mode=Mode.REDUCE_COUNTS, x=n['b'])
    counted, total = c.checked_add(at(Mode.REDUCE_COUNTS), n['a'], n['b'])
    c.emit(counted, reduce_major_index=total, mode=Mode.REDUCE_SHARED, x=n['c'])
    counted, total = c.checked_add(at(Mode.REDUCE_SHARED), r['reduce_major_index'], n['a'])
    counted, total = c.checked_add(counted, total, n['b'])
    c.emit(counted, reduce_major_index=total, mode=Mode.REDUCE_ARGUMENTS, x=f['first'])
    call(at(Mode.REDUCE_ARGUMENTS), Phase.SELECT, Task.VECTOR_REFERENCE, n['b'], vector_index=r['reduce_major_index'])
    gather_owner = c.eq(f['task'], Task.GATHER_RECURSOR_ARGUMENTS)
    resumed = c.AND(returning, gather_owner); valid = c.eq(f['phase'], 0)
    c.stop(c.AND(resumed, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(resumed, valid), task=Task.GATHER_RECURSOR_ARGUMENTS, mode=Mode.GATHER_RESTORE, x=f['original'], gather_result=r['r'])
    gather = c.task(Task.GATHER_RECURSOR_ARGUMENTS); at = lambda m: c.AND(gather, c.mode(m))
    init = at(Mode.WALK); valid = c.AND(nonempty, c.eq(f['phase'], CALL_INFER_CONSTANT_LOOKUP), c.eq(f['task'], Task.BETA_ZETA))
    c.stop(c.AND(init, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX); init = c.AND(init, valid)
    c.write('stack', init, top, (0, f['original'], f['depth'], Task.GATHER_RECURSOR_ARGUMENTS, f['first'], f['second']))
    c.emit(init, gather_saved_sp=r['sp'], gather_expression=f['original'], sp=top, mode=Mode.GATHER_SCAN)
    scan = at(Mode.GATHER_SCAN); argument = c.AND(nonempty, c.eq(f['phase'], PENDING_ARGUMENT), c.eq(f['task'], Task.BETA_ZETA))
    room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(scan, argument, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP)
    argument = c.AND(scan, argument, room)
    c.write('heap', argument, r['free'], (Tag.APP, r['gather_expression'], f['first'], 0))
    c.emit(argument, free=c.add(r['free'], 1), gather_expression=r['free'], sp=top)
    done = c.AND(scan, c.NOT(c.AND(nonempty, c.eq(f['phase'], PENDING_ARGUMENT), c.eq(f['task'], Task.BETA_ZETA))))
    c.emit(done, gather_base_sp=r['sp'], sp=r['gather_saved_sp'], mode=Mode.GATHER_SAVE)
    save = at(Mode.GATHER_SAVE); room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(save, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); save = c.AND(save, room)
    c.write('heap', save, r['free'], (CellTag.REDUCER_CALL, f['original'], r['gather_base_sp'], 0))
    c.write('stack', save, top, (0, r['free'], f['depth'], Task.GATHER_RECURSOR_ARGUMENTS, f['first'], f['second']))
    c.emit(save, free=c.add(r['free'], 1), task=c.mux(c.eq(r['gather_service'],Task.QUOT_REDUCE),Task.QUOT_REDUCE,Task.REDUCE_RECURSOR),quot_reduce_pc=0,mode=Mode.WALK,x=r['gather_expression'],depth=0)
    restored = at(Mode.GATHER_RESTORE); neutral = c.eq(r['gather_result'], 0)
    c.emit(restored, task=Task.BETA_ZETA, ctx=f['depth'], arg_base=f['first'], count=f['second'], depth=0)
    c.emit(c.AND(restored, neutral), sp=top); c.ret(c.AND(restored, neutral), n['a'])
    c.emit(c.AND(restored, c.NOT(neutral)), sp=n['b'], mode=Mode.BETA_ZETA, x=r['gather_result'])
