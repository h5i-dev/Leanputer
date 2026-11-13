"""Lower source checking and atomic ordinary publication into stock IR.

Raw declaration kinds/names/schemes are DATA. Types and bodies are checked by
shared weighted services BEFORE checked records are generated. Required missing
inductive/recursor/primitive/conversion callbacks GAP; no placeholder axioms.
"""
from .arena import Tag
from .native_cells import CellTag, DeclarationKind
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_SOURCE_NAME, CALL_SOURCE_DUPLICATE, CALL_SOURCE_PARAMETERS,
    CALL_SOURCE_TYPE_SCOPE, CALL_SOURCE_TYPE_INFER, CALL_SOURCE_TYPE_WHNF,
    CALL_SOURCE_PROPOSITION, CALL_SOURCE_VALUE_SCOPE, CALL_SOURCE_VALUE_INFER,
    CALL_SOURCE_VALUE_CONVERT, CALL_SOURCE_BLOCK_HEADERS, CALL_SOURCE_CORE_CONSTRUCTORS, CALL_SOURCE_CORE_NAMES, CALL_SOURCE_DECLARE_CONSTRUCTORS, CALL_SOURCE_ELIMINATION)

PRIVATE_PHASES = tuple(range(CALL_SOURCE_NAME, CALL_SOURCE_VALUE_CONVERT+1))+(CALL_SOURCE_BLOCK_HEADERS,CALL_SOURCE_CORE_CONSTRUCTORS,CALL_SOURCE_CORE_NAMES,CALL_SOURCE_DECLARE_CONSTRUCTORS,CALL_SOURCE_ELIMINATION,)


def emit_rules(c):
    r, n, f, raw = c.r, c.read['node'], c.read['frame'], c.read['declaration']
    result, top = r['r'], c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)))
    at_return = lambda phase: c.AND(returning, c.eq(f['phase'], phase))
    def call(guard, phase, task, x, mode=Mode.WALK, **updates):
        c.write('stack', guard, top, (phase, 0, 0, Task.CHECK_SOURCE, 0, 0))
        c.emit(guard, mode=mode, task=task, x=x, depth=0, **updates)
    core = c.AND(c.NOT(c.eq(r['core_operation'],0)),c.eq(r['raw_index'],r['core_index']))
    c.stop(c.AND(at_return(CALL_SOURCE_BLOCK_HEADERS),c.NOT(core)), Outcome.GAP, Reason.GAP_INDUCTIVE)
    call(c.AND(at_return(CALL_SOURCE_BLOCK_HEADERS),core),CALL_SOURCE_CORE_CONSTRUCTORS,Task.CHECK_CONSTRUCTORS,0)
    call(at_return(CALL_SOURCE_CORE_CONSTRUCTORS),CALL_SOURCE_CORE_NAMES,Task.CHECK_CORE_NAMES,0)
    call(at_return(CALL_SOURCE_CORE_NAMES),CALL_SOURCE_DECLARE_CONSTRUCTORS,Task.DECLARE_CONSTRUCTORS,0)
    call(at_return(CALL_SOURCE_DECLARE_CONSTRUCTORS),CALL_SOURCE_ELIMINATION,Task.INIT_ELIMINATION,0)
    c.stop(at_return(CALL_SOURCE_ELIMINATION),Outcome.GAP,Reason.GAP_RECURSOR_GENERATION)
    call(at_return(CALL_SOURCE_NAME), CALL_SOURCE_DUPLICATE, Task.ENV_LOOKUP, r['active_type'], query_symbol=r['active_symbol'], lookup_head=r['env_head'])
    duplicate = at_return(CALL_SOURCE_DUPLICATE)
    c.stop(c.AND(duplicate, c.NOT(c.eq(result, 0))), Outcome.INVALID, Reason.DUPLICATE_DECLARATION)
    call(c.AND(duplicate, c.eq(result, 0)), CALL_SOURCE_PARAMETERS, Task.LOAD_PARAMETERS, r['active_parameters'])
    call(at_return(CALL_SOURCE_PARAMETERS), CALL_SOURCE_TYPE_SCOPE, Task.EXPR_SCOPE, r['active_type'])
    call(at_return(CALL_SOURCE_TYPE_SCOPE), CALL_SOURCE_TYPE_INFER, Task.INFER, r['active_type'], local_base=r['ctx'])
    call(at_return(CALL_SOURCE_TYPE_INFER), CALL_SOURCE_TYPE_WHNF, Task.BETA_ZETA, result, Mode.BETA_ZETA)
    c.emit(at_return(CALL_SOURCE_TYPE_WHNF), task=Task.CHECK_SOURCE, mode=Mode.SOURCE_TYPE_SORT, x=result)
    proposition = at_return(CALL_SOURCE_PROPOSITION)
    c.stop(c.AND(proposition, c.eq(result, 0)), Outcome.INVALID, Reason.INVALID_DECLARATION)
    c.emit(c.AND(proposition, c.NOT(c.eq(result, 0))), task=Task.CHECK_SOURCE, mode=Mode.SOURCE_REQUIRE_VALUE, x=r['active_type'])
    call(at_return(CALL_SOURCE_VALUE_SCOPE), CALL_SOURCE_VALUE_INFER, Task.INFER, r['active_value'], local_base=r['ctx'])
    call(at_return(CALL_SOURCE_VALUE_INFER), CALL_SOURCE_VALUE_CONVERT, Task.CONVERT_POSITIVE, result, peer=r['active_type'])
    converted = at_return(CALL_SOURCE_VALUE_CONVERT)
    c.stop(c.AND(converted, c.eq(result, 0)), Outcome.INVALID, Reason.TYPE_MISMATCH)
    c.emit(c.AND(converted, c.NOT(c.eq(result, 0))), task=Task.CHECK_SOURCE, mode=Mode.SOURCE_COMMIT, x=r['active_type'])

    init = c.AND(c.mode(Mode.WALK), c.task(Task.CHECK_SOURCE))
    counts_ok = c.AND(c.NOT(c.eq(r['decl_count'], 0)), c.NOT(c.lt(c.cfg.constants, r['decl_count'])),
        c.eq(r['target_index'], c.sub(r['decl_count'], 1)),
        c.OR(c.eq(r['core_operation'],0),c.lt(r['core_index'],r['target_index'])))
    c.stop(c.AND(init, c.NOT(counts_ok)), Outcome.INVALID, Reason.SYNTAX)
    heap_room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(init, counts_ok, c.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
    init = c.AND(init, counts_ok, heap_room)
    c.write('heap', init, r['free'], (CellTag.LEVEL_ZERO, 0, 0, 0))
    c.emit(init, free=c.add(r['free'], 1), kernel_zero=r['free'], env_ready=1, env_head=0, typing_active=0, typing_head=0, decl=0, raw_index=0,
        ctx=0, count=0, arg_base=0, local_base=0, sp=0, pending_scope=0, pending_infer=0,
        pending_open=0, pending_fold=0, pending_compare=0, mode=Mode.SOURCE_READ, x=0)
    read = c.mode(Mode.SOURCE_READ)
    row_ok = c.lt(r['raw_index'], r['decl_count'])
    c.stop(c.AND(read, c.NOT(row_ok)), Outcome.INVALID, Reason.SYNTAX)
    read = c.AND(read, row_ok)
    target_axiom = c.AND(c.eq(r['raw_index'], r['target_index']), c.eq(raw['kind'], DeclarationKind.AXIOM))
    c.stop(c.AND(read, target_axiom), Outcome.INVALID, Reason.INVALID_DECLARATION)
    block = c.AND(read, c.eq(raw['kind'], DeclarationKind.BLOCK))
    block_room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(block, c.NOT(block_room)), Outcome.RESOURCE, Reason.STACK)
    c.write('stack', c.AND(block, block_room), r['sp'], (CALL_SOURCE_BLOCK_HEADERS,0,0,Task.CHECK_SOURCE,0,0))
    c.emit(c.AND(block, block_room), sp=c.add(r['sp'],1), task=Task.ANALYZE_HEADERS, mode=Mode.WALK, x=raw['extra'], header_parameters=raw['parameters'])
    c.stop(c.AND(read, c.eq(raw['kind'], DeclarationKind.RECURSOR_CLAIM)), Outcome.GAP, Reason.GAP_RECURSOR_CLAIM)
    c.stop(c.AND(read, c.eq(raw['kind'], DeclarationKind.QUOT_PRIMITIVE)), Outcome.GAP, Reason.GAP_PRIMITIVE)
    ordinary = c.OR(*(c.eq(raw['kind'], kind) for kind in (DeclarationKind.AXIOM, DeclarationKind.DEFINITION, DeclarationKind.THEOREM, DeclarationKind.OPAQUE)))
    known = c.OR(ordinary, *(c.eq(raw['kind'], kind) for kind in (DeclarationKind.BLOCK, DeclarationKind.RECURSOR_CLAIM, DeclarationKind.QUOT_PRIMITIVE)))
    c.stop(c.AND(read, c.NOT(known)), Outcome.INVALID, Reason.INVALID_DECLARATION)
    stack_room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(read, ordinary, c.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
    ordinary = c.AND(read, ordinary, stack_room, c.NOT(target_axiom))
    c.emit(ordinary, active_kind=raw['kind'], active_symbol=raw['symbol'], active_parameters=raw['parameters'],
        active_type=raw['type'], active_value=raw['value'], active_extra=raw['extra'], query_symbol=raw['symbol'])
    c.write('stack', ordinary, r['sp'], (CALL_SOURCE_NAME, 0, 0, Task.CHECK_SOURCE, 0, 0))
    c.emit(ordinary, sp=c.add(r['sp'], 1), task=Task.CHECK_NAME, mode=Mode.WALK, x=r['symbols_root'])
    type_sort = c.mode(Mode.SOURCE_TYPE_SORT)
    stable = c.tag(Tag.PI, Tag.LAM, Tag.BVAR, Tag.LOCAL, Tag.NAT, Tag.STRING)
    c.stop(c.AND(type_sort, c.NOT(c.tag(Tag.SORT)), stable), Outcome.INVALID, Reason.EXPECT_SORT)
    c.stop(c.AND(type_sort, c.NOT(c.tag(Tag.SORT)), c.NOT(stable)), Outcome.GAP, Reason.GAP_CONVERSION)
    theorem = c.eq(r['active_kind'], DeclarationKind.THEOREM)
    call(c.AND(type_sort, c.tag(Tag.SORT), theorem), CALL_SOURCE_PROPOSITION, Task.LEVEL_EQUIVALENT, n['a'], peer=r['kernel_zero'])
    c.emit(c.AND(type_sort, c.tag(Tag.SORT), c.NOT(theorem)), mode=Mode.SOURCE_REQUIRE_VALUE, x=r['active_type'])
    require = c.mode(Mode.SOURCE_REQUIRE_VALUE)
    axiom = c.eq(r['active_kind'], DeclarationKind.AXIOM)
    have_value = c.NOT(c.eq(r['active_value'], 0))
    c.stop(c.AND(require, axiom, have_value), Outcome.INVALID, Reason.INVALID_DECLARATION)
    c.emit(c.AND(require, axiom, c.NOT(have_value)), mode=Mode.SOURCE_COMMIT)
    c.stop(c.AND(require, c.NOT(axiom), c.NOT(have_value)), Outcome.GAP, Reason.UNAVAILABLE_BODY)
    call(c.AND(require, c.NOT(axiom), have_value), CALL_SOURCE_VALUE_SCOPE, Task.EXPR_SCOPE, r['active_value'])

    commit = c.mode(Mode.SOURCE_COMMIT)
    target = c.eq(r['raw_index'], r['target_index'])
    c.emit(c.AND(commit, target), sp=top, r=1)
    c.stop(c.AND(commit, target), Outcome.DONE)
    wide = c.g.add(c.g.fit(r['free'], c.width+1), c.g.const(3, c.width+1))
    room3 = c.NOT(c.g.lt(c.g.const(c.cfg.heap, c.width+1), wide))
    c.stop(c.AND(commit, c.NOT(target), c.NOT(room3)), Outcome.RESOURCE, Reason.HEAP)
    store_scheme = c.AND(commit, c.NOT(target), room3)
    c.write('heap', store_scheme, r['free'], (CellTag.CHECKED_SCHEME, r['active_parameters'], r['active_kind'], r['active_value']))
    c.emit(store_scheme, free=c.add(r['free'], 1), commit_scheme=r['free'], mode=Mode.SOURCE_SIGNATURE)
    store_signature = c.mode(Mode.SOURCE_SIGNATURE)
    c.write('heap', store_signature, r['free'], (CellTag.CHECKED_SIGNATURE, r['active_symbol'], r['active_type'], r['commit_scheme']))
    c.emit(store_signature, free=c.add(r['free'], 1), commit_signature=r['free'], mode=Mode.SOURCE_LINK)
    link = c.mode(Mode.SOURCE_LINK)
    c.write('heap', link, r['free'], (CellTag.VECTOR_CELL, r['commit_signature'], r['env_head'], 0))
    c.emit(link, free=c.add(r['free'], 1), env_head=r['free'], decl=c.add(r['decl'], 1), raw_index=c.add(r['raw_index'], 1),
        sp=top, mode=Mode.SOURCE_READ, x=0)
