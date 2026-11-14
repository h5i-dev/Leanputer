"""Pinned generic K/structure major preparation, DEVELOPMENT reference only.

All state needed across recursive inference/WHNF/conversion is in the private
continuation, never in unprotected scratch registers. Literal primitives GAP.
"""
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason
from .major_rules import Phase, Path, TAGS, EXPRESSION_MODES, NO_NODE


def resume(machine, frame, stop, ret, alloc):
    s, r = machine.state, machine.state['regs']; phase, original, metadata, _, first, second = frame
    def call(p, task, x, mode=Mode.WALK, **updates):
        s['stack'][r['sp']-1] = [p, original, metadata, Task.PREPARE_RECURSOR_MAJOR, first, second]
        r.update(task=task, mode=mode, x=x, depth=0, **updates)
    def meta(path):
        r.update(task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_METADATA, x=metadata, major_path=path)
    if phase in (Phase.K_INFER, Phase.ETA_INFER):
        call(Phase.K_TYPE_WHNF if phase == Phase.K_INFER else Phase.ETA_TYPE_WHNF, Task.BETA_ZETA, r['r'], Mode.BETA_ZETA)
    elif phase in (Phase.K_TYPE_WHNF, Phase.ETA_TYPE_WHNF):
        first = r['r']; call(Phase.K_SPINE if phase == Phase.K_TYPE_WHNF else Phase.ETA_SPINE, Task.APPLICATION_SPINE, first)
    elif phase in (Phase.K_SPINE, Phase.ETA_SPINE):
        s['stack'][r['sp']-1][5] = r['r']; meta(Path.K_TYPE if phase == Phase.K_SPINE else Path.ETA_TYPE)
    elif phase == Phase.K_APPLY:
        second = r['r']; call(Phase.K_CANDIDATE_INFER, Task.INFER, second)
    elif phase == Phase.K_CANDIDATE_INFER:
        call(Phase.K_CONVERT, Task.CONVERT_POSITIVE, first, peer=r['r'])
    elif phase == Phase.K_CONVERT:
        call(Phase.WHNF, Task.BETA_ZETA, second if r['r'] else original, Mode.BETA_ZETA)
    elif phase == Phase.WHNF:
        s['stack'][r['sp']-1][1] = r['r']
        r.update(task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_VALUE, x=r['r'])
    elif phase == Phase.MAJOR_SPINE:
        r.update(task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_APP, x=r['r'])
    elif phase == Phase.HEAD_LOOKUP:
        if not r['r']: meta(Path.ETA_ELIGIBILITY)
        else: r.update(task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_SIGNATURE, x=r['r'])
    elif phase == Phase.ETA_SORT_INFER:
        call(Phase.ETA_SORT_WHNF, Task.BETA_ZETA, r['r'], Mode.BETA_ZETA)
    elif phase == Phase.ETA_SORT_WHNF:
        r.update(task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_SORT, x=r['r'])
    elif phase == Phase.CHECK_STRUCTURE:
        if not r['r']:
            r.update(task=Task.PREPARE_RECURSOR_MAJOR,sp=r['sp']-1);ret(original)
        else:r.update(task=Task.PREPARE_RECURSOR_MAJOR,mode=Mode.MAJOR_STRUCTURE,x=r['r'])
    elif phase == Phase.ETA_APPLY:
        r.update(task=Task.PREPARE_RECURSOR_MAJOR, mode=Mode.MAJOR_PROJECTION,
            major_accumulator=r['r'], major_cursor=0)
    else: stop(Outcome.INVALID, Reason.SYNTAX)


def step(machine, tag, a, b, c, stop, ret, alloc):
    s, r, cfg = machine.state, machine.state['regs'], machine.cfg
    if r['task'] != Task.PREPARE_RECURSOR_MAJOR: return False
    mode = r['mode']; frame = s['stack'][r['sp']-1] if r['sp'] else None
    if mode != Mode.WALK and frame is None:
        stop(Outcome.INVALID, Reason.SYNTAX); return True
    def finish(value=None):
        value = frame[1] if value is None else value
        r['sp'] -= 1; ret(value)
    def call(phase, task, x, mode=Mode.WALK, **updates):
        frame[0] = phase; r.update(task=task, mode=mode, x=x, depth=0, **updates)
    def meta(path):
        r.update(major_path=path, mode=Mode.MAJOR_METADATA, x=frame[2])
    def no_expansion():
        if r['major_path'] == Path.K_TYPE: call(Phase.WHNF, Task.BETA_ZETA, frame[1], Mode.BETA_ZETA)
        else: finish()
    def room(n=1):
        if r['free']+n > cfg.heap: stop(Outcome.RESOURCE, Reason.HEAP); return False
        return True
    if mode == Mode.WALK:
        if r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
        else:
            s['stack'][r['sp']] = [Phase.K_INFER, r['major_value'], r['x'], Task.PREPARE_RECURSOR_MAJOR, 0, 0]
            r.update(sp=r['sp']+1, major_path=Path.INITIAL, mode=Mode.MAJOR_METADATA)
    elif mode == Mode.MAJOR_METADATA:
        r.update(major_owner=a, major_rules=c, mode=Mode.MAJOR_COUNTS, x=b)
    elif mode == Mode.MAJOR_COUNTS:
        r.update(major_parameters=a, major_indices=b, mode=Mode.MAJOR_SHARED, x=c)
    elif mode == Mode.MAJOR_SHARED: r.update(mode=Mode.MAJOR_BLOCK, x=c)
    elif mode == Mode.MAJOR_BLOCK:
        path = r['major_path']
        if path == Path.INITIAL:
            if a: call(Phase.K_INFER, Task.INFER, frame[1])
            else: call(Phase.WHNF, Task.BETA_ZETA, frame[1], Mode.BETA_ZETA)
        elif path in (Path.ETA_ELIGIBILITY,Path.ETA_BUILD):
            call(Phase.CHECK_STRUCTURE,Task.STRUCTURE_INFO,r['major_owner'],structure_pc=0)
        else: r.update(mode=Mode.MAJOR_OWNER, x=r['major_owner'])
    elif mode == Mode.MAJOR_STRUCTURE:
        if r['major_path'] == Path.ETA_ELIGIBILITY:r.update(mode=Mode.MAJOR_RULE_VECTOR,x=r['major_rules'])
        else:r.update(major_parameters=b,mode=Mode.MAJOR_OWNER,x=r['major_owner'])
    elif mode == Mode.MAJOR_OWNER:
        r.update(major_owner_symbol=a, mode=Mode.MAJOR_TYPE_APP, x=frame[5])
    elif mode == Mode.MAJOR_TYPE_APP:
        r.update(major_type_arguments=b, mode=Mode.MAJOR_TYPE_HEAD, x=a)
    elif mode == Mode.MAJOR_TYPE_HEAD:
        if tag != Tag.CONST or a != r['major_owner_symbol']: no_expansion()
        elif r['major_path'] == Path.ETA_TYPE: call(Phase.ETA_SORT_INFER, Task.INFER, frame[4])
        else: r.update(major_type_levels=b, mode=Mode.MAJOR_RULE_VECTOR, x=r['major_rules'])
    elif mode == Mode.MAJOR_RULE_VECTOR:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif r['major_path'] == Path.ETA_ELIGIBILITY:
            if a != 1: finish()
            else: call(Phase.ETA_INFER, Task.INFER, frame[1])
        elif a != 1: stop(Outcome.INVALID, Reason.SYNTAX)  # checked K/structure invariant
        else: r.update(mode=Mode.MAJOR_RULE_CELL, x=b)
    elif mode == Mode.MAJOR_RULE_CELL:
        if b: stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(mode=Mode.MAJOR_RULE, x=a)
    elif mode == Mode.MAJOR_RULE:
        r.update(major_constructor=a, major_fields=b, mode=Mode.MAJOR_CONSTRUCTOR)
    elif mode == Mode.MAJOR_CONSTRUCTOR:
        if room():
            ref = r['free']; s['heap'][ref] = [Tag.CONST, r['major_constructor'], r['major_type_levels'], 0]; r['free'] = ref+1
            call(Phase.K_APPLY if r['major_path'] == Path.K_TYPE else Phase.ETA_APPLY,
                Task.APPLY_VECTOR_SLICE, r['major_type_arguments'], slice_body=ref, slice_start=0, slice_take=r['major_parameters'])
    elif mode == Mode.MAJOR_VALUE:
        if tag in (Tag.NAT, Tag.STRING): stop(Outcome.GAP, Reason.GAP_PRIMITIVE)
        else: call(Phase.MAJOR_SPINE, Task.APPLICATION_SPINE, r['x'])
    elif mode == Mode.MAJOR_APP: r.update(mode=Mode.MAJOR_HEAD, x=a)
    elif mode == Mode.MAJOR_HEAD:
        if tag != Tag.CONST: meta(Path.ETA_ELIGIBILITY)
        else: call(Phase.HEAD_LOOKUP, Task.ENV_LOOKUP, r['x'], query_symbol=a,
            lookup_head=r['typing_head'] if r['typing_active'] else r['env_head'])
    elif mode == Mode.MAJOR_SIGNATURE: r.update(mode=Mode.MAJOR_SCHEME, x=c)
    elif mode == Mode.MAJOR_SCHEME:
        if b == 9: finish()
        else: meta(Path.ETA_ELIGIBILITY)
    elif mode == Mode.MAJOR_SORT:
        if tag != Tag.SORT:
            stable = tag in (Tag.PI, Tag.LAM, Tag.BVAR, Tag.LOCAL, Tag.NAT, Tag.STRING)
            stop(Outcome.INVALID if stable else Outcome.GAP, Reason.EXPECT_SORT if stable else Reason.GAP_CONVERSION)
        else: r.update(mode=Mode.MAJOR_SORT_LEVEL, x=a)
    elif mode == Mode.MAJOR_SORT_LEVEL:
        if tag == CellTag.LEVEL_ZERO: finish()
        else: meta(Path.ETA_BUILD)
    elif mode == Mode.MAJOR_PROJECTION:
        if r['major_cursor'] >= r['major_fields']: finish(r['major_accumulator'])
        elif room(2):
            ref = r['free']; s['heap'][ref] = [Tag.PROJ, r['major_owner_symbol'], r['major_cursor'], frame[1]]
            r.update(free=ref+1, major_projection=ref, mode=Mode.MAJOR_APPLY_PROJECTION)
    elif mode == Mode.MAJOR_APPLY_PROJECTION:
        ref = r['free']; s['heap'][ref] = [Tag.APP, r['major_accumulator'], r['major_projection'], 0]
        r.update(free=ref+1, major_accumulator=ref, major_cursor=r['major_cursor']+1, mode=Mode.MAJOR_PROJECTION)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
