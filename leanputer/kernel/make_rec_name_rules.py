"""Compile source rec/rec_index construction for arbitrary family name paths."""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def emit_rules(c):
    r, f = c.r, c.read['frame']; top = c.sub(r['sp'], 1)
    returning = c.AND(c.mode(Mode.RETURN), c.NOT(c.eq(r['sp'], 0)), c.eq(f['task'], Task.MAKE_RECURSOR_NAME))
    phase = lambda p: c.AND(returning, c.eq(f['phase'], p))
    def call(guard, p, task, x, path=None, **updates):
        c.write('stack', guard, top, (p, f['original'] if path is None else path, f['depth'], Task.MAKE_RECURSOR_NAME, f['first'], f['second']))
        c.emit(guard, task=task, mode=Mode.WALK, x=x, depth=0, **updates)
    indexed = c.NOT(c.eq(f['first'], 0)); first = phase(0)
    call(c.AND(first, indexed), 1, Task.WORD_DECIMAL, 0, path=r['r'], decimal_value=f['depth'])
    c.write('stack', c.AND(first, c.NOT(indexed)), top, (0, r['r'], f['depth'], Task.MAKE_RECURSOR_NAME, f['first'], f['second']))
    c.emit(c.AND(first, c.NOT(indexed)), task=Task.MAKE_RECURSOR_NAME, mode=Mode.GEN_REC_SUFFIX)
    c.write('stack', phase(1), top, (1, f['original'], f['depth'], Task.MAKE_RECURSOR_NAME, f['first'], r['r']))
    c.emit(phase(1), task=Task.MAKE_RECURSOR_NAME, mode=Mode.GEN_REC_SUFFIX)
    c.emit(phase(2), task=Task.MAKE_RECURSOR_NAME, mode=Mode.GEN_REC_COMPONENT, generated_suffix_bytes=r['r'])
    call(phase(3), 4, Task.INTERN_NAME_PATH, r['r'])
    c.emit(phase(4), task=Task.MAKE_RECURSOR_NAME, sp=top); c.ret(phase(4), r['r'])
    c.stop(c.AND(returning, c.NOT(c.OR(*(c.eq(f['phase'], p) for p in range(5))))), Outcome.INVALID, Reason.SYNTAX)
    active = c.task(Task.MAKE_RECURSOR_NAME); at = lambda m: c.AND(active, c.mode(m))
    init = at(Mode.WALK); valid = c.NOT(c.lt(1, r['generated_rec_indexed'])); room = c.lt(r['sp'], c.cfg.stack)
    c.stop(c.AND(init, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    c.stop(c.AND(init, valid, c.NOT(room)), Outcome.RESOURCE, Reason.STACK); init = c.AND(init, valid, room)
    c.write('stack', init, r['sp'], (0, r['query_symbol'], r['generated_rec_index'], Task.MAKE_RECURSOR_NAME, r['generated_rec_indexed'], 0))
    c.emit(init, sp=c.add(r['sp'], 1), task=Task.GET_NAME_PATH, x=r['symbols_root'])
    length = c.mux(indexed, 4, 3)
    c.emit(at(Mode.GEN_REC_SUFFIX), generated_suffix_head=0, generated_suffix_length=length, generated_suffix_remaining=length, mode=Mode.GEN_REC_BYTE)
    def allocate(guard, row, **updates):
        room = c.lt(r['free'], c.cfg.heap)
        c.stop(c.AND(guard, c.NOT(room)), Outcome.RESOURCE, Reason.HEAP); guard = c.AND(guard, room)
        c.write('heap', guard, r['free'], row); c.emit(guard, free=c.add(r['free'], 1), **updates)
        return guard
    byte = at(Mode.GEN_REC_BYTE); valid = c.AND(c.NOT(c.eq(r['generated_suffix_remaining'], 0)), c.NOT(c.lt(4, r['generated_suffix_remaining'])))
    c.stop(c.AND(byte, c.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
    value = c.mux(c.eq(r['generated_suffix_remaining'], 1), ord('r'), c.mux(c.eq(r['generated_suffix_remaining'], 2), ord('e'), c.mux(c.eq(r['generated_suffix_remaining'], 3), ord('c'), ord('_'))))
    more = c.lt(1, r['generated_suffix_remaining'])
    allocate(c.AND(byte, valid), (CellTag.VECTOR_CELL, value, r['generated_suffix_head'], 0),
        generated_suffix_head=r['free'], generated_suffix_remaining=c.sub(r['generated_suffix_remaining'], 1), mode=c.mux(more, Mode.GEN_REC_BYTE, Mode.GEN_REC_BYTES))
    vector = allocate(at(Mode.GEN_REC_BYTES), (CellTag.VECTOR, r['generated_suffix_length'], r['generated_suffix_head'], VectorKind.BYTES), generated_suffix_bytes=r['free'])
    call(c.AND(vector, indexed), 2, Task.VECTOR_SPLICE, r['free'], peer=f['second'], splice_role=VectorKind.BYTES, splice_skip=0)
    c.emit(c.AND(vector, c.NOT(indexed)), mode=Mode.GEN_REC_COMPONENT)
    allocate(at(Mode.GEN_REC_COMPONENT), (CellTag.NAME_STRING, r['generated_suffix_bytes'], 0, 0), generated_name_component=r['free'], mode=Mode.GEN_REC_CELL)
    allocate(at(Mode.GEN_REC_CELL), (CellTag.VECTOR_CELL, r['generated_name_component'], 0, 0), generated_name_cell=r['free'], mode=Mode.GEN_REC_PATH)
    vector = allocate(at(Mode.GEN_REC_PATH), (CellTag.VECTOR, 1, r['generated_name_cell'], VectorKind.REFERENCES))
    call(vector, 3, Task.VECTOR_SPLICE, f['original'], peer=r['free'], splice_role=VectorKind.REFERENCES, splice_skip=0)
