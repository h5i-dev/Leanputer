"""Compile complete generic symbolic canonicalization to shared stock IR.

Bottom-up normalize calls a canonical-chain merge; the merge orders/deduplicates
base-offset pairs and defers the global explicit-universe subsumption decision.
Every loop/call/allocation runs in weights. No host sort/normalization answers.
"""
from .native_cells import CellTag
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_NORMAL_IMAX, CALL_MERGE_ORDER, CALL_MERGE_OFFSET,
    CALL_EQUIVALENT_LEFT, CALL_EQUIVALENT_RIGHT)

PRIVATE_PHASES = (CALL_NORMAL_IMAX, CALL_MERGE_ORDER, CALL_MERGE_OFFSET,
                  CALL_EQUIVALENT_LEFT, CALL_EQUIVALENT_RIGHT)


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']
    a, b, x, result = n['a'], n['b'], r['x'], r['r']
    top, room = c.sub(r['sp'], 1), c.lt(r['sp'], c.cfg.stack)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)))
    at_return = lambda phase: c.AND(returning, c.eq(f['phase'], phase))
    nz = lambda word: c.NOT(c.eq(word, 0))
    imax_return = at_return(CALL_NORMAL_IMAX)
    c.emit(imax_return, sp=top, mode=Mode.NORMAL_IMAX_RESULT, task=Task.LEVEL_NORMALIZE, x=result)
    imax_result = c.mode(Mode.NORMAL_IMAX_RESULT)
    c.emit(c.AND(imax_result, c.tag(CellTag.LEVEL_MAX)), mode=Mode.WALK, task=Task.LEVEL_MERGE, x=a, peer=b)
    c.ret(c.AND(imax_result, c.NOT(c.tag(CellTag.LEVEL_MAX))), x)

    eq_left = at_return(CALL_EQUIVALENT_LEFT)
    c.write('stack', eq_left, top, (CALL_EQUIVALENT_RIGHT, result, 0, Task.LEVEL_EQUIVALENT, 0, 0))
    c.emit(eq_left, mode=Mode.WALK, task=Task.LEVEL_NORMALIZE, x=f['original'])
    c.emit(at_return(CALL_EQUIVALENT_RIGHT), sp=top, mode=Mode.WALK, task=Task.LEVEL_EQUAL, x=f['original'], peer=result)
    equivalent = c.AND(c.mode(Mode.WALK), c.task(Task.LEVEL_EQUIVALENT))
    valid_peer = c.AND(nz(r['peer']), c.lt(r['peer'], r['free']))
    c.stop(c.AND(equivalent, c.NOT(valid_peer)), Outcome.INVALID, Reason.SYNTAX)
    c.stop(c.AND(equivalent, valid_peer, c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
    equivalent = c.AND(equivalent, valid_peer, room)
    c.write('stack', equivalent, r['sp'], (CALL_EQUIVALENT_LEFT, r['peer'], 0, Task.LEVEL_EQUIVALENT, 0, 0))
    c.emit(equivalent, sp=c.add(r['sp'], 1), mode=Mode.WALK, task=Task.LEVEL_NORMALIZE)

    order_return = at_return(CALL_MERGE_ORDER)
    same_base = nz(r['order_same_base'])
    pick_right = c.OR(c.AND(same_base, c.eq(result, 1)), c.AND(c.NOT(same_base), c.eq(result, 2)))
    chosen = c.mux(pick_right, r['merge_hr'], r['merge_hl'])
    c.emit(c.AND(order_return, c.OR(same_base, c.NOT(pick_right))), merge_l=r['merge_tl'])
    c.emit(c.AND(order_return, c.OR(same_base, pick_right)), merge_r=r['merge_tr'])
    c.write('stack', order_return, top, (CALL_MERGE_OFFSET, 0, 0, Task.LEVEL_MERGE, 0, 0))
    c.emit(order_return, mode=Mode.WALK, task=Task.LEVEL_OFFSET, x=chosen, level_offset=0, merge_chosen=chosen)
    c.emit(at_return(CALL_MERGE_OFFSET), sp=top, mode=Mode.MERGE_RECORD, task=Task.LEVEL_MERGE, x=result)

    entering = c.AND(c.mode(Mode.WALK), c.task(Task.LEVEL_MERGE))
    c.stop(c.AND(entering, c.NOT(valid_peer)), Outcome.INVALID, Reason.SYNTAX)
    entering = c.AND(entering, valid_peer)
    c.emit(entering, mode=Mode.MERGE_LEFT, merge_anchor=x, merge_l=x, merge_r=r['peer'],
        merge_rev=0, merge_acc=0, merge_explicit=0, merge_exp_offset=0, merge_max_offset=0)
    read_left = c.mode(Mode.MERGE_LEFT)
    left_active = nz(r['merge_l'])
    c.emit(read_left, merge_hl=c.mux(left_active, c.mux(c.tag(CellTag.LEVEL_MAX), a, x), 0),
        merge_tl=c.mux(c.AND(left_active, c.tag(CellTag.LEVEL_MAX)), b, 0),
        mode=Mode.MERGE_RIGHT, x=c.mux(nz(r['merge_r']), r['merge_r'], r['merge_anchor']))
    read_right = c.mode(Mode.MERGE_RIGHT)
    right_active = nz(r['merge_r'])
    head = c.mux(right_active, c.mux(c.tag(CellTag.LEVEL_MAX), a, x), 0)
    tail = c.mux(c.AND(right_active, c.tag(CellTag.LEVEL_MAX)), b, 0)
    c.emit(read_right, merge_hr=head, merge_tr=tail)
    have_left, have_right = nz(r['merge_hl']), nz(head)
    finished = c.AND(read_right, c.NOT(have_left), c.NOT(have_right))
    c.emit(finished, mode=c.mux(nz(r['merge_rev']), Mode.MERGE_FOLD, Mode.MERGE_FINISH),
        x=c.mux(nz(r['merge_rev']), r['merge_rev'], r['merge_anchor']))
    select = c.AND(read_right, c.OR(have_left, have_right))
    c.stop(c.AND(select, c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
    select = c.AND(select, room)
    both = c.AND(have_left, have_right)
    chosen = c.mux(have_left, r['merge_hl'], head)
    c.write('stack', select, r['sp'], (c.mux(both, CALL_MERGE_ORDER, CALL_MERGE_OFFSET), 0, 0, Task.LEVEL_MERGE, 0, 0))
    c.emit(select, sp=c.add(r['sp'], 1), mode=Mode.WALK,
        task=c.mux(both, Task.LEVEL_ORDER, Task.LEVEL_OFFSET), x=chosen, peer=c.mux(both, head, 0))
    c.emit(c.AND(select, c.NOT(both)), merge_chosen=chosen, level_offset=0)
    c.emit(c.AND(select, c.NOT(both), have_left), merge_l=r['merge_tl'])
    c.emit(c.AND(select, c.NOT(both), c.NOT(have_left)), merge_r=tail)

    record = c.mode(Mode.MERGE_RECORD)
    explicit = c.tag(CellTag.LEVEL_ZERO)
    replace_explicit = c.AND(record, explicit,
        c.OR(c.NOT(nz(r['merge_explicit'])), c.lt(r['merge_exp_offset'], r['level_offset'])))
    c.emit(replace_explicit, merge_explicit=r['merge_chosen'], merge_exp_offset=r['level_offset'])
    c.emit(c.AND(record, explicit), mode=Mode.MERGE_LEFT,
        x=c.mux(nz(r['merge_l']), r['merge_l'], r['merge_anchor']))
    heap_room = c.lt(r['free'], c.cfg.heap)
    keep_arg = c.AND(record, c.NOT(explicit))
    c.stop(c.AND(keep_arg, c.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
    keep_arg = c.AND(keep_arg, heap_room)
    c.write('heap', keep_arg, r['free'], (CellTag.VECTOR_CELL, r['merge_chosen'], r['merge_rev'], 0))
    c.emit(keep_arg, merge_rev=r['free'], free=c.add(r['free'], 1),
        merge_max_offset=c.mux(c.lt(r['merge_max_offset'], r['level_offset']), r['level_offset'], r['merge_max_offset']),
        mode=Mode.MERGE_LEFT, x=c.mux(nz(r['merge_l']), r['merge_l'], r['merge_anchor']))

    fold = c.mode(Mode.MERGE_FOLD)
    has_acc = nz(r['merge_acc'])
    c.stop(c.AND(fold, has_acc, c.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
    fold_ok = c.AND(fold, c.OR(c.NOT(has_acc), heap_room))
    build = c.AND(fold_ok, has_acc)
    c.write('heap', build, r['free'], (CellTag.LEVEL_MAX, a, r['merge_acc'], 0))
    c.emit(build, merge_acc=r['free'], free=c.add(r['free'], 1))
    c.emit(c.AND(fold_ok, c.NOT(has_acc)), merge_acc=a)
    c.emit(fold_ok, merge_rev=b, mode=c.mux(nz(b), Mode.MERGE_FOLD, Mode.MERGE_FINISH),
        x=c.mux(nz(b), b, r['merge_anchor']))
    finish = c.mode(Mode.MERGE_FINISH)
    c.ret(c.AND(finish, c.NOT(has_acc)), r['merge_explicit'])
    retain_explicit = c.AND(nz(r['merge_explicit']), c.lt(r['merge_max_offset'], r['merge_exp_offset']))
    c.alloc(c.AND(finish, has_acc, retain_explicit), (CellTag.LEVEL_MAX, r['merge_explicit'], r['merge_acc'], 0))
    c.ret(c.AND(finish, has_acc, c.NOT(retain_explicit)), r['merge_acc'])
