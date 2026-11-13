"""Lower structured name traversal and ONLY genuine native-interface guards.

Literal bytes below are the two pinned kernel host-code interface names, not
ordinary declaration/type cases. No host name/profile classification is loaded.
"""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def emit_rules(c):
    r, n = c.r, c.read['node']
    a, b = n['a'], n['b']
    entering = c.AND(c.mode(Mode.WALK), c.task(Task.CHECK_NAME))
    wb = lambda word: c.mux(c.eq(word, 0), 0, 1)
    shape = c.eq(wb(a), wb(b))
    valid_header = c.AND(c.eq(n['c'], VectorKind.REFERENCES), shape)
    c.stop(c.AND(entering, c.NOT(valid_header)), Outcome.INVALID, Reason.SYNTAX)
    exists = c.AND(c.NOT(c.eq(a, 0)), c.NOT(c.eq(r['query_symbol'], 0)))
    c.stop(c.AND(entering, valid_header, c.NOT(exists)), Outcome.INVALID, Reason.INVALID_DECLARATION)
    c.emit(c.AND(entering, valid_header, exists), mode=Mode.NAME_TABLE_CELL, x=b, name_table_left=a)
    cell = c.mode(Mode.NAME_TABLE_CELL)
    valid_cell = c.AND(c.NOT(c.eq(r['name_table_left'], 0)), c.eq(wb(b), c.mux(c.lt(1, r['name_table_left']), 1, 0)))
    c.stop(c.AND(cell, c.NOT(valid_cell)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(cell, valid_cell), mode=Mode.NAME_ENTRY, x=a, name_table_next=b, name_table_left=c.sub(r['name_table_left'], 1))
    entry = c.mode(Mode.NAME_ENTRY)
    matches = c.eq(a, r['query_symbol'])
    c.emit(c.AND(entry, matches), mode=Mode.NAME_PATH, x=b)
    c.stop(c.AND(entry, c.NOT(matches), c.eq(r['name_table_left'], 0)), Outcome.INVALID, Reason.INVALID_DECLARATION)
    c.emit(c.AND(entry, c.NOT(matches), c.NOT(c.eq(r['name_table_left'], 0))), mode=Mode.NAME_TABLE_CELL, x=r['name_table_next'])
    path = c.mode(Mode.NAME_PATH)
    c.stop(c.AND(path, c.NOT(valid_header)), Outcome.INVALID, Reason.SYNTAX)
    path = c.AND(path, valid_header)
    c.stop(c.AND(path, c.eq(a, 0)), Outcome.INVALID, Reason.INVALID_DECLARATION)
    c.ret(c.AND(path, c.NOT(c.eq(a, 0)), c.NOT(c.eq(a, 2))), 1)
    c.emit(c.AND(path, c.eq(a, 2)), mode=Mode.NAME_PATH_CELL, x=b, name_part=0)
    component_cell = c.mode(Mode.NAME_PATH_CELL)
    cell_ok = c.eq(wb(b), c.mux(c.eq(r['name_part'], 0), 1, 0))
    c.stop(c.AND(component_cell, c.NOT(cell_ok)), Outcome.INVALID, Reason.SYNTAX)
    c.emit(c.AND(component_cell, cell_ok, c.eq(r['name_part'], 0)), name_second=b)
    c.emit(c.AND(component_cell, cell_ok), mode=Mode.NAME_COMPONENT, x=a)
    component = c.mode(Mode.NAME_COMPONENT)
    c.ret(c.AND(component, c.tag(CellTag.NAME_NUMERAL)), 1)
    c.emit(c.AND(component, c.tag(CellTag.NAME_STRING)), mode=Mode.NAME_BYTES, x=a)
    header = c.mode(Mode.NAME_BYTES)
    byte_shape = c.AND(c.eq(n['c'], VectorKind.BYTES), shape)
    c.stop(c.AND(header, c.NOT(byte_shape)), Outcome.INVALID, Reason.SYNTAX)
    header = c.AND(header, byte_shape)
    first = c.eq(r['name_part'], 0)
    candidate = c.OR(c.AND(first, c.eq(a, 4)), c.AND(c.NOT(first), c.OR(c.eq(a, 9), c.eq(a, 10))))
    c.ret(c.AND(header, c.NOT(candidate)), 1)
    c.emit(c.AND(header, candidate), mode=Mode.NAME_BYTE_CELL, x=b, name_length=a, name_index=0)
    # Fixed source primitive-interface literals; index is data, traversal loops.
    def literal_bytes(value):
        output = c.v(0)
        for index, char in enumerate(value): output = c.mux(c.eq(r['name_index'], index), ord(char), output)
        return output
    expected = c.mux(first, literal_bytes('Lean'), c.mux(c.eq(r['name_length'], 9), literal_bytes('reduceNat'), literal_bytes('reduceBool')))
    byte = c.mode(Mode.NAME_BYTE_CELL)
    more = c.lt(c.add(r['name_index'], 1), r['name_length'])
    byte_ok = c.eq(wb(b), c.mux(more, 1, 0))
    c.stop(c.AND(byte, c.NOT(byte_ok)), Outcome.INVALID, Reason.SYNTAX)
    byte = c.AND(byte, byte_ok)
    equal = c.eq(a, expected)
    c.ret(c.AND(byte, c.NOT(equal)), 1)
    c.emit(c.AND(byte, equal, more), name_index=c.add(r['name_index'], 1), x=b)
    c.emit(c.AND(byte, equal, c.NOT(more), first), name_part=1, mode=Mode.NAME_PATH_CELL, x=r['name_second'])
    c.stop(c.AND(byte, equal, c.NOT(more), c.NOT(first)), Outcome.UNSUPPORTED_PROFILE, Reason.NATIVE_EXECUTION)
