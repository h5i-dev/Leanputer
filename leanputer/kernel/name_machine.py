"""Development reference of generic structured-name validation/profile guard.

Only ACTUAL kernel native-code interfaces Lean.reduceNat/Lean.reduceBool are
excluded (pinned type_checker.cpp1214..1215). These are not a library feature
catalog. All other names/segments/counts remain DATA, numeric != string. No
native code is executed. Publication/source checking integration is unfinished.
"""
from .native_cells import CellTag, VectorKind
from .traversal_machine import Mode, Task, Outcome, Reason


def valid_tag(mode, tag):
    if mode in (Mode.WALK, Mode.NAME_PATH, Mode.NAME_BYTES): return tag == CellTag.VECTOR
    if mode in (Mode.NAME_TABLE_CELL, Mode.NAME_PATH_CELL, Mode.NAME_BYTE_CELL): return tag == CellTag.VECTOR_CELL
    if mode == Mode.NAME_ENTRY: return tag == CellTag.SYMBOL_ENTRY
    if mode == Mode.NAME_COMPONENT: return tag in (CellTag.NAME_STRING, CellTag.NAME_NUMERAL)
    return False


def step(machine, tag, a, b, c, stop, ret, alloc):
    r = machine.state['regs']
    if r['task'] not in (Task.CHECK_NAME,Task.GET_NAME_PATH): return False
    if r['mode'] == Mode.WALK:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif not a or not r['query_symbol']: stop(Outcome.INVALID, Reason.INVALID_DECLARATION)
        else: r.update(mode=Mode.NAME_TABLE_CELL, x=b, name_table_left=a)
    elif r['mode'] == Mode.NAME_TABLE_CELL:
        if not r['name_table_left'] or bool(b) != (r['name_table_left'] > 1): stop(Outcome.INVALID, Reason.SYNTAX)
        else: r.update(mode=Mode.NAME_ENTRY, x=a, name_table_next=b, name_table_left=r['name_table_left']-1)
    elif r['mode'] == Mode.NAME_ENTRY:
        if a == r['query_symbol']:
            if r['task']==Task.GET_NAME_PATH:ret(b)
            else:r.update(mode=Mode.NAME_PATH, x=b)
        elif not r['name_table_left']: stop(Outcome.INVALID, Reason.INVALID_DECLARATION)
        else: r.update(mode=Mode.NAME_TABLE_CELL, x=r['name_table_next'])
    elif r['mode'] == Mode.NAME_PATH:
        if c != VectorKind.REFERENCES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif not a: stop(Outcome.INVALID, Reason.INVALID_DECLARATION)
        elif a != 2: ret(1) # Only the two-component GENUINE native interfaces need exclusion.
        else: r.update(mode=Mode.NAME_PATH_CELL, x=b, name_part=0)
    elif r['mode'] == Mode.NAME_PATH_CELL:
        if bool(b) != (r['name_part'] == 0): stop(Outcome.INVALID, Reason.SYNTAX)
        else:
            if not r['name_part']: r['name_second'] = b
            r.update(mode=Mode.NAME_COMPONENT, x=a)
    elif r['mode'] == Mode.NAME_COMPONENT:
        if tag == CellTag.NAME_NUMERAL: ret(1)
        else: r.update(mode=Mode.NAME_BYTES, x=a)
    elif r['mode'] == Mode.NAME_BYTES:
        if c != VectorKind.BYTES or bool(a) != bool(b): stop(Outcome.INVALID, Reason.SYNTAX)
        elif not r['name_part'] and a != 4 or r['name_part'] and a not in (9, 10): ret(1)
        else: r.update(mode=Mode.NAME_BYTE_CELL, x=b, name_length=a, name_index=0)
    elif r['mode'] == Mode.NAME_BYTE_CELL:
        more = r['name_index']+1 < r['name_length']
        if bool(b) != more: stop(Outcome.INVALID, Reason.SYNTAX)
        else:
            literal = 'Lean' if not r['name_part'] else 'reduceNat' if r['name_length'] == 9 else 'reduceBool'
            if a != ord(literal[r['name_index']]): ret(1)
            elif more: r.update(name_index=r['name_index']+1, x=b)
            elif not r['name_part']: r.update(name_part=1, mode=Mode.NAME_PATH_CELL, x=r['name_second'])
            else: stop(Outcome.UNSUPPORTED_PROFILE, Reason.NATIVE_EXECUTION)
    else: stop(Outcome.INVALID, Reason.SYNTAX)
    return True
