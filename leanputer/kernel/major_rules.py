"""Compile source K/structure major preparation with reentrant continuations."""
from enum import IntEnum
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


class Phase(IntEnum):
    K_INFER = 0
    K_TYPE_WHNF = 1
    K_SPINE = 2
    K_APPLY = 3
    K_CANDIDATE_INFER = 4
    K_CONVERT = 5
    WHNF = 6
    MAJOR_SPINE = 7
    HEAD_LOOKUP = 8
    ETA_INFER = 9
    ETA_TYPE_WHNF = 10
    ETA_SPINE = 11
    ETA_SORT_INFER = 12
    ETA_SORT_WHNF = 13
    ETA_APPLY = 14
    CHECK_STRUCTURE = 15


class Path(IntEnum):
    INITIAL = 0
    K_TYPE = 1
    ETA_ELIGIBILITY = 2
    ETA_TYPE = 3
    ETA_BUILD = 4


NO_NODE = (Mode.MAJOR_CONSTRUCTOR, Mode.MAJOR_PROJECTION, Mode.MAJOR_APPLY_PROJECTION)
EXPRESSION_MODES = (Mode.MAJOR_TYPE_HEAD, Mode.MAJOR_VALUE, Mode.MAJOR_HEAD, Mode.MAJOR_SORT)
TAGS = {Mode.WALK: CellTag.CHECKED_RECURSOR, Mode.MAJOR_METADATA: CellTag.CHECKED_RECURSOR,
    Mode.MAJOR_COUNTS: CellTag.RECURSOR_COUNTS, Mode.MAJOR_SHARED: CellTag.RECURSOR_SHARED_COUNTS,
    Mode.MAJOR_BLOCK: CellTag.RECURSOR_BLOCK, Mode.MAJOR_STRUCTURE: CellTag.STRUCTURE_INFO,
    Mode.MAJOR_OWNER: CellTag.CHECKED_SIGNATURE, Mode.MAJOR_TYPE_APP: CellTag.APPLICATION_SPINE,
    Mode.MAJOR_RULE_VECTOR: CellTag.VECTOR, Mode.MAJOR_RULE_CELL: CellTag.VECTOR_CELL,
    Mode.MAJOR_RULE: CellTag.CHECKED_RULE, Mode.MAJOR_APP: CellTag.APPLICATION_SPINE,
    Mode.MAJOR_SIGNATURE: CellTag.CHECKED_SIGNATURE, Mode.MAJOR_SCHEME: CellTag.CHECKED_SCHEME}


def emit_rules(c):
    r, n, f = c.r, c.read['node'], c.read['frame']; top = c.sub(r['sp'], 1)
    nonempty = c.NOT(c.eq(r['sp'], 0)); owner = c.eq(f['task'], Task.PREPARE_RECURSOR_MAJOR)
    returning = c.AND(c.mode(Mode.RETURN), nonempty, owner)
    phase = lambda p: c.AND(returning, c.eq(f['phase'], p))
    valid_phase = c.OR(*(c.eq(f['phase'], p) for p in Phase))
    c.stop(c.AND(returning, c.NOT(valid_phase)), Outcome.INVALID, Reason.SYNTAX)
    def frame(guard, p, first=None, second=None, original=None):
        c.write('stack', guard, top, (p, f['original'] if original is None else original,
            f['depth'], Task.PREPARE_RECURSOR_MAJOR, f['first'] if first is None else first, f['second'] if second is None else second))
    def call(guard, p, task, x, mode=Mode.WALK, first=None, second=None, **updates):
        frame(guard, p, first, second)
        c.emit(guard, task=task, mode=mode, x=x, depth=0, **updates)
    def meta(guard, path):
        c.emit(guard, task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_METADATA, x=f['depth'], major_path=path)
    def finish(guard, value=None):
        c.emit(guard, task=Task.PREPARE_RECURSOR_MAJOR, sp=top); c.ret(guard, f['original'] if value is None else value)
    for before, after in ((Phase.K_INFER, Phase.K_TYPE_WHNF), (Phase.ETA_INFER, Phase.ETA_TYPE_WHNF)):
        call(phase(before), after, Task.BETA_ZETA, r['r'], Mode.BETA_ZETA)
    for before, after in ((Phase.K_TYPE_WHNF, Phase.K_SPINE), (Phase.ETA_TYPE_WHNF, Phase.ETA_SPINE)):
        call(phase(before), after, Task.APPLICATION_SPINE, r['r'], first=r['r'])
    for p, path in ((Phase.K_SPINE, Path.K_TYPE), (Phase.ETA_SPINE, Path.ETA_TYPE)):
        frame(phase(p), p, second=r['r']); meta(phase(p), path)
    call(phase(Phase.K_APPLY), Phase.K_CANDIDATE_INFER, Task.INFER, r['r'], second=r['r'])
    call(phase(Phase.K_CANDIDATE_INFER), Phase.K_CONVERT, Task.CONVERT_POSITIVE, f['first'], peer=r['r'])
    call(phase(Phase.K_CONVERT), Phase.WHNF, Task.BETA_ZETA,
        c.mux(c.eq(r['r'], 0), f['original'], f['second']), Mode.BETA_ZETA)
    whnf = phase(Phase.WHNF); frame(whnf, Phase.WHNF, original=r['r'])
    c.emit(whnf, task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_VALUE, x=r['r'])
    c.emit(phase(Phase.MAJOR_SPINE), task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_APP, x=r['r'])
    looked = phase(Phase.HEAD_LOOKUP); found = c.NOT(c.eq(r['r'], 0))
    meta(c.AND(looked, c.NOT(found)), Path.ETA_ELIGIBILITY)
    c.emit(c.AND(looked, found), task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_SIGNATURE, x=r['r'])
    call(phase(Phase.ETA_SORT_INFER), Phase.ETA_SORT_WHNF, Task.BETA_ZETA, r['r'], Mode.BETA_ZETA)
    c.emit(phase(Phase.ETA_SORT_WHNF), task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_SORT, x=r['r'])
    c.emit(phase(Phase.ETA_APPLY), task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_PROJECTION, major_accumulator=r['r'], major_cursor=0)
    checked=phase(Phase.CHECK_STRUCTURE);found=c.NOT(c.eq(r['r'],0))
    finish(c.AND(checked,c.NOT(found)))
    c.emit(c.AND(checked,found),task=Task.PREPARE_RECURSOR_MAJOR,mode=Mode.MAJOR_STRUCTURE,x=r['r'])
    task = c.task(Task.PREPARE_RECURSOR_MAJOR); walk = c.eq(r['mode'], Mode.WALK)
    c.stop(c.AND(c.active, task, c.NOT(walk), c.NOT(c.eq(r['mode'], Mode.RETURN)), c.NOT(nonempty)), Outcome.INVALID, Reason.SYNTAX)
    active = c.AND(task, c.OR(walk, nonempty)); at = lambda m: c.AND(active, c.mode(m))
    init = at(Mode.WALK); room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, room)
    c.write('stack', init, r['sp'], (Phase.K_INFER, r['major_value'], r['x'], Task.PREPARE_RECURSOR_MAJOR, 0, 0))
    c.emit(init, sp=c.add(r['sp'], 1), major_path=Path.INITIAL, mode=Mode.MAJOR_METADATA)
    c.emit(at(Mode.MAJOR_METADATA), major_owner=n['a'], major_rules=n['c'], mode=Mode.MAJOR_COUNTS, x=n['b'])
    c.emit(at(Mode.MAJOR_COUNTS), major_parameters=n['a'], major_indices=n['b'], mode=Mode.MAJOR_SHARED, x=n['c'])
    c.emit(at(Mode.MAJOR_SHARED), mode=Mode.MAJOR_BLOCK, x=n['c'])
    block = at(Mode.MAJOR_BLOCK); path = lambda p: c.eq(r['major_path'], p)
    initial = c.AND(block, path(Path.INITIAL)); k = c.NOT(c.eq(n['a'], 0))
    call(c.AND(initial, k), Phase.K_INFER, Task.INFER, f['original'])
    call(c.AND(initial, c.NOT(k)), Phase.WHNF, Task.BETA_ZETA, f['original'], Mode.BETA_ZETA)
    structure=c.AND(block,c.OR(path(Path.ETA_ELIGIBILITY),path(Path.ETA_BUILD)))
    call(structure,Phase.CHECK_STRUCTURE,Task.STRUCTURE_INFO,r['major_owner'],structure_pc=0)
    c.emit(c.AND(block,c.NOT(path(Path.INITIAL)),c.NOT(c.OR(path(Path.ETA_ELIGIBILITY),path(Path.ETA_BUILD)))),mode=Mode.MAJOR_OWNER,x=r['major_owner'])
    checked=at(Mode.MAJOR_STRUCTURE)
    c.emit(c.AND(checked,path(Path.ETA_ELIGIBILITY)),mode=Mode.MAJOR_RULE_VECTOR,x=r['major_rules'])
    c.emit(c.AND(checked,c.NOT(path(Path.ETA_ELIGIBILITY))),major_parameters=n['b'],mode=Mode.MAJOR_OWNER,x=r['major_owner'])
    c.emit(at(Mode.MAJOR_OWNER), major_owner_symbol=n['a'], mode=Mode.MAJOR_TYPE_APP, x=f['second'])
    c.emit(at(Mode.MAJOR_TYPE_APP), major_type_arguments=n['b'], mode=Mode.MAJOR_TYPE_HEAD, x=n['a'])
    head = at(Mode.MAJOR_TYPE_HEAD); valid = c.AND(c.tag(Tag.CONST), c.eq(n['a'], r['major_owner_symbol']))
    absent = c.AND(head, c.NOT(valid))
    call(c.AND(absent, path(Path.K_TYPE)), Phase.WHNF, Task.BETA_ZETA, f['original'], Mode.BETA_ZETA)
    finish(c.AND(absent, c.NOT(path(Path.K_TYPE))))
    call(c.AND(head, valid, path(Path.ETA_TYPE)), Phase.ETA_SORT_INFER, Task.INFER, f['first'])
    c.emit(c.AND(head, valid, c.NOT(path(Path.ETA_TYPE))), major_type_levels=n['b'], mode=Mode.MAJOR_RULE_VECTOR, x=r['major_rules'])
    vector = at(Mode.MAJOR_RULE_VECTOR)
    valid = c.AND(c.eq(n['c'], VectorKind.REFERENCES), c.eq(c.mux(c.eq(n['a'], 0), 0, 1), c.mux(c.eq(n['b'], 0), 0, 1)))
    c.stop(c.AND(vector, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    eligibility = c.AND(vector, valid, path(Path.ETA_ELIGIBILITY)); singleton = c.eq(n['a'], 1)
    finish(c.AND(eligibility, c.NOT(singleton)))
    call(c.AND(eligibility, singleton), Phase.ETA_INFER, Task.INFER, f['original'])
    build = c.AND(vector, valid, c.NOT(path(Path.ETA_ELIGIBILITY)))
    c.stop(c.AND(build, c.NOT(singleton)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(build, singleton), mode=Mode.MAJOR_RULE_CELL, x=n['b'])
    cell = at(Mode.MAJOR_RULE_CELL); valid = c.eq(n['b'], 0)
    c.stop(c.AND(cell, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(cell, valid), mode=Mode.MAJOR_RULE, x=n['a'])
    c.emit(at(Mode.MAJOR_RULE), major_constructor=n['a'], major_fields=n['b'], mode=Mode.MAJOR_CONSTRUCTOR)
    constructor = at(Mode.MAJOR_CONSTRUCTOR); room = c.lt(r['free'], c.cfg.heap)
    c.stop(c.AND(constructor, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); constructor = c.AND(constructor, room)
    c.write('heap', constructor, r['free'], (Tag.CONST, r['major_constructor'], r['major_type_levels'], 0))
    c.emit(constructor, free=c.add(r['free'], 1))
    call(constructor, c.mux(path(Path.K_TYPE), Phase.K_APPLY, Phase.ETA_APPLY), Task.APPLY_VECTOR_SLICE, r['major_type_arguments'],
        slice_body=r['free'], slice_start=0, slice_take=r['major_parameters'])
    value = at(Mode.MAJOR_VALUE); literal = c.tag(Tag.NAT, Tag.STRING)
    c.emit(c.AND(value,c.tag(Tag.STRING)),task=Task.STRING_WHNF,mode=Mode.WALK,string_whnf_pc=0,string_tail_major=1)
    call(c.AND(value,c.tag(Tag.NAT)),Phase.WHNF,Task.NAT_LITERAL,r['x'],nat_literal_pc=0,nat_literal_operation=1)
    call(c.AND(value, c.NOT(literal)), Phase.MAJOR_SPINE, Task.APPLICATION_SPINE, r['x'])
    c.emit(at(Mode.MAJOR_APP), mode=Mode.MAJOR_HEAD, x=n['a'])
    head = at(Mode.MAJOR_HEAD); constant = c.tag(Tag.CONST)
    meta(c.AND(head, c.NOT(constant)), Path.ETA_ELIGIBILITY)
    call(c.AND(head, constant), Phase.HEAD_LOOKUP, Task.ENV_LOOKUP, r['x'], query_symbol=n['a'],
        lookup_head=c.mux(c.eq(r['typing_active'], 0), r['env_head'], r['typing_head']))
    c.emit(at(Mode.MAJOR_SIGNATURE), mode=Mode.MAJOR_SCHEME, x=n['c'])
    scheme = at(Mode.MAJOR_SCHEME); constructor = c.eq(n['b'], 9)
    finish(c.AND(scheme, constructor)); meta(c.AND(scheme, c.NOT(constructor)), Path.ETA_ELIGIBILITY)
    sort = at(Mode.MAJOR_SORT); is_sort = c.tag(Tag.SORT)
    stable = c.tag(Tag.PI, Tag.LAM, Tag.BVAR, Tag.LOCAL, Tag.NAT, Tag.STRING)
    c.stop(c.AND(sort, c.NOT(is_sort), stable), Outcome.INVALID, Reason.EXPECT_SORT)
    c.stop(c.AND(sort, c.NOT(is_sort), c.NOT(stable)), Outcome.GAP, Reason.GAP_CONVERSION)
    c.emit(c.AND(sort, is_sort), mode=Mode.MAJOR_SORT_LEVEL, x=n['a'])
    level = at(Mode.MAJOR_SORT_LEVEL); prop = c.tag(CellTag.LEVEL_ZERO)
    finish(c.AND(level, prop)); meta(c.AND(level, c.NOT(prop)), Path.ETA_BUILD)
    projection = at(Mode.MAJOR_PROJECTION); done = c.NOT(c.lt(r['major_cursor'], r['major_fields']))
    finish(c.AND(projection, done), r['major_accumulator'])
    room = c.lt(c.add(r['free'], 1), c.cfg.heap)
    c.stop(c.AND(projection, c.NOT(done), c.NOT(room)), Outcome.RESOURCE, Reason.HEAP)
    projection = c.AND(projection, c.NOT(done), room)
    c.write('heap', projection, r['free'], (Tag.PROJ, r['major_owner_symbol'], r['major_cursor'], f['original']))
    c.emit(projection, free=c.add(r['free'], 1), major_projection=r['free'], mode=Mode.MAJOR_APPLY_PROJECTION)
    apply = at(Mode.MAJOR_APPLY_PROJECTION)
    c.write('heap', apply, r['free'], (Tag.APP, r['major_accumulator'], r['major_projection'], 0))
    c.emit(apply, free=c.add(r['free'], 1), major_accumulator=r['free'], major_cursor=c.add(r['major_cursor'], 1), mode=Mode.MAJOR_PROJECTION)
