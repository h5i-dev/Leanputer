"""Boolean lowering of generic typed inference's shared-service controller.

Raw scope is checked before entry. Local types are derived privately after
domain checking; raw signatures are never consulted as admitted answers.
Environment, projection/literals and complete conversion remain explicit GAP
callbacks. This module is not complete source/declaration admission.
"""
from .arena import Tag
from .native_cells import CellTag
from .traversal_machine import (Mode, Task, Outcome, Reason,
    CALL_INFER_BINDER_DOMAIN, CALL_INFER_DOMAIN_WHNF, CALL_INFER_OPEN,
    CALL_INFER_BODY, CALL_INFER_BODY_WHNF, CALL_INFER_ABSTRACT,
    CALL_INFER_PI_LEVEL, CALL_INFER_FUNCTION, CALL_INFER_FUNCTION_WHNF,
    CALL_INFER_ARGUMENT, CALL_INFER_ARGUMENT_CONVERT, CALL_INFER_LET_TYPE,
    CALL_INFER_LET_TYPE_WHNF, CALL_INFER_LET_VALUE, CALL_INFER_LET_CONVERT,
    CALL_INFER_LET_BODY, CALL_CONVERT_FAST, CALL_CONVERT_LEFT_WHNF,
    CALL_CONVERT_RIGHT_WHNF, CALL_CONVERT_NORMAL)

PRIVATE_PHASES = tuple(range(CALL_INFER_BINDER_DOMAIN, CALL_CONVERT_NORMAL+1))


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']
    a, b, x, result = n['a'], n['b'], r['x'], r['r']
    top, room = c.sub(r['sp'], 1), c.lt(r['sp'], c.cfg.stack)
    nonempty = c.NOT(c.eq(r['sp'], 0))
    returning = c.AND(c.mode(Mode.RETURN), nonempty)
    at_return = lambda phase: c.AND(returning, c.eq(f['phase'], phase))
    truth = c.NOT(c.eq(result, 0))
    def replace(guard, phase, original=None, depth=None, first=None, second=None):
        values = [f['original'] if original is None else original,
                  f['depth'] if depth is None else depth,
                  f['first'] if first is None else first,
                  f['second'] if second is None else second]
        c.write('stack', guard, top, (phase, values[0], values[1], Task.INFER, values[2], values[3]))
    def push(guard, phase, original=0, depth=0, first=0, second=0):
        c.stop(c.AND(guard, c.NOT(room)), Outcome.RESOURCE, Reason.STACK)
        guard = c.AND(guard, room)
        c.write('stack', guard, r['sp'], (phase, original, depth, Task.INFER, first, second))
        c.emit(guard, sp=c.add(r['sp'], 1))
        return guard
    def whnf_return(old, new):
        guard = at_return(old)
        replace(guard, new)
        c.emit(guard, mode=Mode.BETA_ZETA, task=Task.BETA_ZETA, x=result, depth=0)
    def inspect_return(phase, mode, original=False):
        c.emit(at_return(phase), mode=mode, task=Task.INFER, x=f['original'] if original else result)
    def ensure(guard):
        stable = c.tag(Tag.BVAR, Tag.LOCAL, Tag.SORT, Tag.PI, Tag.LAM, Tag.NAT, Tag.STRING)
        c.stop(c.AND(guard, stable), Outcome.INVALID, Reason.EXPECT_SORT)
        c.stop(c.AND(guard, c.NOT(stable)), Outcome.GAP, Reason.GAP_CONVERSION)

    whnf_return(CALL_INFER_BINDER_DOMAIN, CALL_INFER_DOMAIN_WHNF)
    inspect_return(CALL_INFER_DOMAIN_WHNF, Mode.INFER_DOMAIN_SORT)
    opened = at_return(CALL_INFER_OPEN)
    replace(opened, CALL_INFER_BODY, second=r['substitution'])
    c.emit(opened, mode=Mode.WALK, task=Task.INFER, x=result)
    whnf_return(CALL_INFER_BODY, CALL_INFER_BODY_WHNF)
    inspect_return(CALL_INFER_BODY_WHNF, Mode.INFER_BINDER_RESULT, True)
    c.emit(at_return(CALL_INFER_ABSTRACT), sp=top, mode=Mode.INFER_LAM_RESULT, task=Task.INFER, x=f['original'], ctx=f['depth'])
    c.emit(at_return(CALL_INFER_PI_LEVEL), sp=top, mode=Mode.INFER_SORT_EXPR, task=Task.INFER, x=f['original'], ctx=f['depth'])
    whnf_return(CALL_INFER_FUNCTION, CALL_INFER_FUNCTION_WHNF)
    inspect_return(CALL_INFER_FUNCTION_WHNF, Mode.INFER_FUNCTION_PI)
    inspect_return(CALL_INFER_ARGUMENT, Mode.INFER_ARGUMENT_TYPE, True)
    for phase, mode in ((CALL_INFER_ARGUMENT_CONVERT, Mode.INFER_APP_RESULT), (CALL_INFER_LET_CONVERT, Mode.INFER_LET_INSTANTIATE)):
        guard = at_return(phase)
        c.stop(c.AND(guard, c.NOT(truth)), Outcome.INVALID, Reason.TYPE_MISMATCH)
        c.emit(c.AND(guard, truth), mode=mode, task=Task.INFER, x=f['original'])
    whnf_return(CALL_INFER_LET_TYPE, CALL_INFER_LET_TYPE_WHNF)
    inspect_return(CALL_INFER_LET_TYPE_WHNF, Mode.INFER_LET_ANNOTATION)
    inspect_return(CALL_INFER_LET_VALUE, Mode.INFER_LET_VALUE_TYPE, True)
    c.emit(at_return(CALL_INFER_LET_BODY), sp=top, mode=Mode.WALK, task=Task.INFER, x=result)

    for phase in (CALL_CONVERT_FAST, CALL_CONVERT_NORMAL):
        guard = at_return(phase)
        c.emit(c.AND(guard, truth), sp=top)
        c.ret(c.AND(guard, truth), 1)
    fast_false = c.AND(at_return(CALL_CONVERT_FAST), c.NOT(truth))
    replace(fast_false, CALL_CONVERT_LEFT_WHNF, original=f['depth'], depth=0, first=0, second=0)
    c.emit(fast_false, mode=Mode.BETA_ZETA, task=Task.BETA_ZETA, x=f['original'], depth=0)
    c.emit(c.AND(at_return(CALL_CONVERT_NORMAL), c.NOT(truth)), mode=Mode.CONVERT_LEFT,
        task=Task.CONVERT_POSITIVE, x=f['original'], peer=f['depth'])
    left_whnf = at_return(CALL_CONVERT_LEFT_WHNF)
    replace(left_whnf, CALL_CONVERT_RIGHT_WHNF, original=result)
    c.emit(left_whnf, mode=Mode.BETA_ZETA, task=Task.BETA_ZETA, x=f['original'], depth=0)
    right_whnf = at_return(CALL_CONVERT_RIGHT_WHNF)
    replace(right_whnf, CALL_CONVERT_NORMAL, depth=result)
    c.emit(right_whnf, mode=Mode.WALK, task=Task.EXPR_EQUAL, x=f['original'], peer=result)
    conversion = c.AND(c.mode(Mode.WALK), c.task(Task.CONVERT_POSITIVE))
    conversion = push(conversion, CALL_CONVERT_FAST, x, r['peer'])
    c.emit(conversion, mode=Mode.WALK, task=Task.EXPR_EQUAL)
    left_conversion = c.mode(Mode.CONVERT_LEFT)
    c.stop(c.AND(left_conversion, c.NOT(c.tag(Tag.SORT))), Outcome.GAP, Reason.GAP_CONVERSION)
    c.emit(c.AND(left_conversion, c.tag(Tag.SORT)), mode=Mode.CONVERT_RIGHT, convert_left_level=a, x=r['peer'])
    right_conversion = c.mode(Mode.CONVERT_RIGHT)
    c.stop(c.AND(right_conversion, c.NOT(c.tag(Tag.SORT))), Outcome.GAP, Reason.GAP_CONVERSION)
    c.emit(c.AND(right_conversion, c.tag(Tag.SORT)), sp=top, mode=Mode.WALK, task=Task.LEVEL_EQUIVALENT,
        x=r['convert_left_level'], peer=a)

    walking = c.AND(c.mode(Mode.WALK), c.task(Task.INFER))
    c.stop(c.AND(walking, c.tag(Tag.BVAR)), Outcome.INVALID, Reason.SCOPE)
    local = c.AND(walking, c.tag(Tag.LOCAL))
    have_local = c.lt(r['local_base'], r['ctx'])
    c.stop(c.AND(local, c.NOT(have_local)), Outcome.INVALID, Reason.SCOPE)
    c.emit(c.AND(local, have_local), mode=Mode.INFER_LOCAL_SELECT, lookup_uid=a, lookup_index=c.sub(r['ctx'], 1))
    sort = c.AND(walking, c.tag(Tag.SORT))
    heap_room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(sort, c.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
    sort = c.AND(sort, heap_room)
    c.write('heap', sort, r['free'], (CellTag.LEVEL_SUCC, a, 0, 0))
    c.emit(sort, free=c.add(r['free'], 1), r=r['free'], mode=Mode.INFER_SORT_EXPR)
    c.stop(c.AND(walking, c.tag(Tag.CONST)), Outcome.GAP, Reason.GAP_ENVIRONMENT)
    c.stop(c.AND(walking, c.tag(Tag.NAT, Tag.STRING)), Outcome.GAP, Reason.GAP_PRIMITIVE)
    c.stop(c.AND(walking, c.tag(Tag.PROJ)), Outcome.GAP, Reason.GAP_PROJECTION)
    c.emit(c.AND(walking, c.tag(Tag.MDATA)), x=a)
    binder = push(c.AND(walking, c.tag(Tag.PI, Tag.LAM)), CALL_INFER_BINDER_DOMAIN, x, r['ctx'], second=n['tag'])
    c.emit(binder, x=a)
    application = push(c.AND(walking, c.tag(Tag.APP)), CALL_INFER_FUNCTION, b)
    c.emit(application, x=a)
    let = push(c.AND(walking, c.tag(Tag.LET)), CALL_INFER_LET_TYPE, x)
    c.emit(let, x=a)
    c.alloc(c.mode(Mode.INFER_SORT_EXPR), (Tag.SORT, result, 0, 0))
    c.emit(c.mode(Mode.INFER_LOCAL_SELECT), mode=Mode.INFER_LOCAL_RECORD, x=c.read['operand']['value'])
    local_record = c.mode(Mode.INFER_LOCAL_RECORD)
    record_ok = c.AND(c.NOT(c.eq(a, 0)), c.lt(a, r['free']), c.NOT(c.eq(b, 0)), c.lt(b, r['free']))
    c.stop(c.AND(local_record, c.NOT(record_ok)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(local_record, record_ok), mode=Mode.INFER_LOCAL_EXPR, x=a, lookup_type=b)
    local_expr = c.mode(Mode.INFER_LOCAL_EXPR)
    c.stop(c.AND(local_expr, c.NOT(c.tag(Tag.LOCAL))), Outcome.INVALID, Reason.SYNTAX)
    local_expr = c.AND(local_expr, c.tag(Tag.LOCAL))
    uid_equal = c.eq(a, r['lookup_uid'])
    c.ret(c.AND(local_expr, uid_equal), r['lookup_type'])
    another = c.lt(r['local_base'], r['lookup_index'])
    c.stop(c.AND(local_expr, c.NOT(uid_equal), c.NOT(another)), Outcome.INVALID, Reason.SCOPE)
    c.emit(c.AND(local_expr, c.NOT(uid_equal), another), mode=Mode.INFER_LOCAL_SELECT, lookup_index=c.sub(r['lookup_index'], 1))

    framed_modes = (Mode.INFER_DOMAIN_SORT, Mode.INFER_BINDER_RESULT, Mode.INFER_PI_BODY_SORT,
        Mode.INFER_FUNCTION_PI, Mode.INFER_ARGUMENT_TYPE, Mode.INFER_APP_RESULT, Mode.INFER_LET_ANNOTATION,
        Mode.INFER_LET_SOURCE, Mode.INFER_LET_VALUE_TYPE, Mode.INFER_LET_INSTANTIATE)
    framed = c.OR(*(c.mode(mode) for mode in framed_modes))
    c.stop(c.AND(framed, c.NOT(nonempty)), Outcome.INVALID, Reason.SYNTAX)
    domain = c.AND(c.mode(Mode.INFER_DOMAIN_SORT), nonempty)
    ensure(c.AND(domain, c.NOT(c.tag(Tag.SORT))))
    domain = c.AND(domain, c.tag(Tag.SORT))
    replace(domain, CALL_INFER_OPEN, first=a)
    c.emit(domain, mode=Mode.TELESCOPE, task=Task.OPEN_TELESCOPE, x=f['original'],
        open_tag=f['second'], bounded=1, limit=c.add(r['ctx'], 1))
    binder_result = c.AND(c.mode(Mode.INFER_BINDER_RESULT), nonempty)
    c.stop(c.AND(binder_result, c.NOT(c.tag(Tag.PI, Tag.LAM))), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(binder_result, c.tag(Tag.PI)), mode=Mode.INFER_PI_BODY_SORT, x=result)
    abstract = c.AND(binder_result, c.tag(Tag.LAM))
    replace(abstract, CALL_INFER_ABSTRACT, first=0, second=0)
    c.emit(abstract, mode=Mode.WALK, task=Task.ABSTRACT_ONE, x=result, abstract_uid=f['second'], depth=0)
    pi_sort = c.AND(c.mode(Mode.INFER_PI_BODY_SORT), nonempty)
    ensure(c.AND(pi_sort, c.NOT(c.tag(Tag.SORT))))
    pi_sort = c.AND(pi_sort, c.tag(Tag.SORT))
    replace(pi_sort, CALL_INFER_PI_LEVEL, first=0, second=0)
    c.emit(pi_sort, mode=Mode.WALK, task=Task.LEVEL_IMAX, x=f['first'], peer=a, ctx=f['depth'])
    lambda_result = c.mode(Mode.INFER_LAM_RESULT)
    c.stop(c.AND(lambda_result, c.NOT(c.tag(Tag.LAM))), Outcome.INVALID, Reason.SYNTAX)
    c.alloc(c.AND(lambda_result, c.tag(Tag.LAM)), (Tag.PI, a, result, n['c']))
    function_pi = c.AND(c.mode(Mode.INFER_FUNCTION_PI), nonempty)
    not_pi = c.AND(function_pi, c.NOT(c.tag(Tag.PI)))
    definitely = c.tag(Tag.SORT, Tag.LAM)
    c.stop(c.AND(not_pi, definitely), Outcome.INVALID, Reason.EXPECT_PI)
    c.stop(c.AND(not_pi, c.NOT(definitely)), Outcome.GAP, Reason.GAP_CONVERSION)
    function_pi = c.AND(function_pi, c.tag(Tag.PI))
    replace(function_pi, CALL_INFER_ARGUMENT, original=x, depth=f['original'], first=0, second=0)
    c.emit(function_pi, mode=Mode.WALK, task=Task.INFER, x=f['original'])
    argument = c.AND(c.mode(Mode.INFER_ARGUMENT_TYPE), nonempty)
    c.stop(c.AND(argument, c.NOT(c.tag(Tag.PI))), Outcome.INVALID, Reason.SYNTAX)
    argument = c.AND(argument, c.tag(Tag.PI))
    replace(argument, CALL_INFER_ARGUMENT_CONVERT, first=0, second=0)
    c.emit(argument, mode=Mode.WALK, task=Task.CONVERT_POSITIVE, x=result, peer=a)
    app_result = c.AND(c.mode(Mode.INFER_APP_RESULT), nonempty)
    c.stop(c.AND(app_result, c.NOT(c.tag(Tag.PI))), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(app_result, c.tag(Tag.PI)), sp=top, mode=Mode.WALK, task=Task.INSTANTIATE_ONE,
        x=b, substitution=f['depth'], depth=0)
    annotation = c.AND(c.mode(Mode.INFER_LET_ANNOTATION), nonempty)
    ensure(c.AND(annotation, c.NOT(c.tag(Tag.SORT))))
    c.emit(c.AND(annotation, c.tag(Tag.SORT)), mode=Mode.INFER_LET_SOURCE, x=f['original'])
    let_source = c.AND(c.mode(Mode.INFER_LET_SOURCE), nonempty)
    c.stop(c.AND(let_source, c.NOT(c.tag(Tag.LET))), Outcome.INVALID, Reason.SYNTAX)
    let_source = c.AND(let_source, c.tag(Tag.LET))
    replace(let_source, CALL_INFER_LET_VALUE, depth=0, first=0, second=0)
    c.emit(let_source, mode=Mode.WALK, task=Task.INFER, x=b)
    let_value = c.AND(c.mode(Mode.INFER_LET_VALUE_TYPE), nonempty)
    c.stop(c.AND(let_value, c.NOT(c.tag(Tag.LET))), Outcome.INVALID, Reason.SYNTAX)
    let_value = c.AND(let_value, c.tag(Tag.LET))
    replace(let_value, CALL_INFER_LET_CONVERT, depth=0, first=0, second=0)
    c.emit(let_value, mode=Mode.WALK, task=Task.CONVERT_POSITIVE, x=result, peer=a)
    let_instantiate = c.AND(c.mode(Mode.INFER_LET_INSTANTIATE), nonempty)
    c.stop(c.AND(let_instantiate, c.NOT(c.tag(Tag.LET))), Outcome.INVALID, Reason.SYNTAX)
    let_instantiate = c.AND(let_instantiate, c.tag(Tag.LET))
    replace(let_instantiate, CALL_INFER_LET_BODY, original=0, depth=0, first=0, second=0)
    c.emit(let_instantiate, mode=Mode.WALK, task=Task.INSTANTIATE_ONE, x=n['c'], substitution=b, depth=0)
