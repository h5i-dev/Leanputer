"""Lower the shared all-tag traversal controller to Boolean semantic IR.

Stock Qwen3.5/GatedDeltaNet emission is provided by native_machine. This module
has no runtime dependency on the Python kernel operations/reference machine.
"""
from ..bitvec import Builder
from . import level_constructor_rules, level_order_rules, level_normalize_rules, level_geq_rules, expression_equal_rules
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import (MachineConfig, Mode, Outcome, Reason, Task,
    CALL_BETA_ZETA, PENDING_ARGUMENT, CALL_TELESCOPE, CALL_FOLD, CALL_SORT_LEVEL, CALL_CONST_LEVEL, CALL_NORMAL_IMAX, VECTOR_VALUE, LEVEL_EQUAL_SECOND, LEVEL_OR_SECOND, LOCAL_DECL_TAG,
    StateLayout, RegisterLayout, assumptions, boot_length, parse_document, prepare,
    program_name, constant_fields, first_banks, second_banks, primitive_basis)


PORTS = (('node', ('tag', 'a', 'b', 'c')),
         ('frame', ('phase', 'original', 'depth', 'task', 'first', 'second')),
         ('operand', ('value',)))


def port_names(width, ports=PORTS):
    return [f'read/{p}/{f}/{i}' for p, fs in ports for f in fs for i in range(width)]


def state_words(g, layout):
    return {n: tuple(g.inputs[layout.slices[n]]) for n, _ in layout.fields}


def compile_addresses(layout, optimized=True, target=None):
    cfg, width = layout.config, layout.config.word_bits
    g = Builder(layout.names, optimized)
    r = state_words(g, layout)
    minus = g.sub(r['sp'], g.const(1, width))[0]
    first = g.compile(list(r['x'][:cfg.heap.bit_length()-1])+list(minus[:cfg.stack.bit_length()-1]), target)
    g = Builder(layout.names+port_names(width, PORTS[:2]), optimized)
    r = state_words(g, layout)
    a = tuple(g.inputs[len(layout.names)+width:len(layout.names)+2*width])
    base = g.add(r['depth'], r['start'])
    relative = g.sub(a, base)[0]
    selecting = g.OR(g.eq(r['mode'], g.const(Mode.FIND, width)), g.eq(r['mode'], g.const(Mode.LEVEL_SELECT, width)))
    index = g.add(r['arg_base'], g.mux(selecting, r['i'], relative))
    index = g.mux(g.eq(r['mode'], g.const(Mode.FOLD_SELECT, width)),
        g.sub(r['ctx'], g.const(1, width))[0], index)
    second = g.compile(list(index[:cfg.context.bit_length()-1]), target)
    return first, second


class RuleCompiler:
    def __init__(self, layout, optimized=True, factor_choices=True):
        self.layout, self.cfg = layout, layout.config
        self.width = self.cfg.word_bits
        self.g = Builder(layout.names+port_names(self.width), optimized)
        self.r = state_words(self.g, layout)
        self.choices = {n: [] for n, _ in layout.fields}
        self.writes = {bank: [] for bank in ('heap', 'stack', 'context')}
        self.factor = factor_choices
        self.read = {}
        offset = len(layout.names)
        for port, fields in PORTS:
            self.read[port] = {}
            for field in fields:
                self.read[port][field] = tuple(self.g.inputs[offset:offset+self.width])
                offset += self.width
        self.active = self.AND(self.eq(self.r['status'], Outcome.RUNNING), self.NOT(self.eq(self.r['fuel'], 0)))
        self.stop(self.AND(self.eq(self.r['status'], Outcome.RUNNING), self.eq(self.r['fuel'], 0)), Outcome.RESOURCE, Reason.FUEL)
        self.emit(self.active, fuel=self.g.sub(self.r['fuel'], self.g.const(1, len(self.r['fuel'])))[0])
        invalid = self.OR(self.eq(self.r['free'], 0), self.lt(self.cfg.heap, self.r['free']),
            self.lt(self.cfg.stack, self.r['sp']), self.lt(self.cfg.context, self.r['count']), self.lt(self.cfg.context, self.r['ctx']),
            self.lt(Mode.VECTOR_CELL_RIGHT, self.r['mode']), self.lt(Task.VECTOR_EQUAL, self.r['task']),
            self.lt(1, self.r['bounded']), self.lt(1, self.r['pending_open']), self.lt(1, self.r['pending_fold']),
            self.lt(1, self.r['vec_changed']), self.lt(2, self.r['pending_compare']), self.lt(1, self.r['order_same_base']),
            self.NOT(self.OR(self.eq(self.r['open_tag'], Tag.PI), self.eq(self.r['open_tag'], Tag.LAM))),
            self.NOT(self.OR(self.eq(self.r['fold_tag'], Tag.PI), self.eq(self.r['fold_tag'], Tag.LAM))))
        self.stop(self.AND(self.active, invalid), Outcome.INVALID, Reason.SYNTAX)
        self.active = self.AND(self.active, self.NOT(invalid))
        uses_arguments = self.OR(*(self.eq(self.r['task'], value) for value in
            (Task.INSTANTIATE, Task.ABSTRACT, Task.OCCURS, Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.EXPR_LEVEL_SUBSTITUTE, Task.LEVEL_INSTANTIATE, Task.EXPR_LEVEL_INSTANTIATE, Task.EXPR_SCOPE)))
        window_end = self.g.add(self.g.fit(self.r['arg_base'], self.width+1), self.g.fit(self.r['count'], self.width+1))
        window_bad = self.AND(uses_arguments, self.g.lt(self.g.const(self.cfg.context, self.width+1), window_end))
        self.stop(self.AND(self.active, window_bad), Outcome.RESOURCE, Reason.CONTEXT)
        self.active = self.AND(self.active, self.NOT(window_bad))
        needs_node = self.NOT(self.eq(self.r['mode'], Mode.RETURN))
        internal_record = self.eq(self.r['mode'], Mode.FOLD_RECORD)
        binding_record = self.eq(self.r['mode'], Mode.LEVEL_BINDING)
        comparing_vector = self.eq(self.r['task'], Task.VECTOR_EQUAL)
        comparing_cell = self.OR(self.eq(self.r['mode'], Mode.VECTOR_CELL_LEFT), self.eq(self.r['mode'], Mode.VECTOR_CELL_RIGHT))
        vector_header = self.OR(self.eq(self.r['mode'], Mode.CONST_VECTOR), self.AND(comparing_vector, self.NOT(comparing_cell)))
        merge_cell = self.eq(self.r['mode'], Mode.MERGE_FOLD)
        vector_cell = self.OR(self.AND(comparing_vector, comparing_cell), merge_cell, self.eq(self.r['mode'], Mode.CONST_CELL), self.eq(self.r['mode'], Mode.CONST_RESULT))
        level_scope = self.OR(*(self.eq(self.r['task'], task) for task in
            (Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.LEVEL_EQUAL, Task.LEVEL_NOT_ZERO, Task.LEVEL_OFFSET, Task.LEVEL_MAX, Task.LEVEL_IMAX, Task.LEVEL_INSTANTIATE, Task.LEVEL_ORDER, Task.LEVEL_NORMALIZE, Task.LEVEL_MERGE, Task.LEVEL_NORMAL_SUCC, Task.LEVEL_EQUIVALENT, Task.LEVEL_GEQ, Task.LEVEL_GEQ_CORE)))
        expression_tag_bad = self.OR(self.lt(self.read['node']['tag'], Tag.BVAR), self.lt(Tag.MDATA, self.read['node']['tag']))
        level_tag_bad = self.OR(self.lt(self.read['node']['tag'], CellTag.LEVEL_ZERO), self.lt(CellTag.LEVEL_PARAM, self.read['node']['tag']))
        tag_bad = self.OR(self.AND(internal_record, self.NOT(self.eq(self.read['node']['tag'], LOCAL_DECL_TAG))),
            self.AND(binding_record, self.NOT(self.eq(self.read['node']['tag'], CellTag.LEVEL_BINDING))),
            self.AND(vector_header, self.NOT(self.eq(self.read['node']['tag'], CellTag.VECTOR))),
            self.AND(vector_cell, self.NOT(self.eq(self.read['node']['tag'], CellTag.VECTOR_CELL))),
            self.AND(self.NOT(internal_record), self.NOT(binding_record), self.NOT(vector_header), self.NOT(vector_cell),
                self.OR(self.AND(level_scope, level_tag_bad), self.AND(self.NOT(level_scope), expression_tag_bad))))
        node_bad = self.OR(self.eq(self.r['x'], 0), self.NOT(self.lt(self.r['x'], self.r['free'])), tag_bad)
        bad = self.AND(needs_node, node_bad)
        self.stop(self.AND(self.active, bad), Outcome.INVALID, Reason.SYNTAX)
        self.active = self.AND(self.active, self.NOT(bad))

    def v(self, value, width=None):
        return self.g.const(int(value), width or self.width) if isinstance(value, int) else value

    def AND(self, *bits): return self.g.AND(*bits)
    def OR(self, *bits): return self.g.OR(*bits)
    def NOT(self, bit): return self.g.NOT(bit)
    def eq(self, x, y): return self.g.eq(self.v(x), self.v(y))
    def lt(self, x, y): return self.g.lt(self.v(x), self.v(y))
    def add(self, x, y): return self.g.add(self.v(x), self.v(y))
    def sub(self, x, y): return self.g.sub(self.v(x), self.v(y))[0]
    def mux(self, bit, x, y): return self.g.mux(bit, self.v(x), self.v(y))
    def mode(self, value): return self.AND(self.active, self.eq(self.r['mode'], value))
    def task(self, value): return self.eq(self.r['task'], value)
    def tag(self, *values): return self.OR(*(self.eq(self.read['node']['tag'], t) for t in values))

    def emit(self, guard, **updates):
        for name, value in updates.items():
            self.choices[name].append((guard, self.v(value, len(self.r[name]))))

    def stop(self, guard, status, reason=Reason.NONE):
        self.emit(guard, status=status, reason=reason)

    def ret(self, guard, ref):
        self.emit(guard, mode=Mode.RETURN, r=ref)

    def checked_add(self, guard, x, y):
        wide = self.g.add(self.g.fit(self.v(x), self.width+1), self.g.fit(self.v(y), self.width+1))
        self.stop(self.AND(guard, wide[-1]), Outcome.RESOURCE, Reason.INDEX)
        return self.AND(guard, self.NOT(wide[-1])), wide[:self.width]

    def write(self, bank, guard, address, row):
        self.writes[bank].append((guard, self.v(address), [self.v(v) for v in row]))

    def alloc(self, guard, row):
        room = self.lt(self.r['free'], self.cfg.heap)
        self.stop(self.AND(guard, self.NOT(room)), Outcome.RESOURCE, Reason.HEAP)
        guard = self.AND(guard, room)
        self.write('heap', guard, self.r['free'], row)
        self.emit(guard, free=self.add(self.r['free'], 1))
        self.ret(guard, self.r['free'])

    def rules(self):
        r, node, frame = self.r, self.read['node'], self.read['frame']
        x, depth, task, result = (r[n] for n in ('x', 'depth', 'task', 'r'))
        a, b, c = (node[n] for n in ('a', 'b', 'c'))
        operand = self.read['operand']['value']
        nonempty = self.NOT(self.eq(r['sp'], 0))
        top = self.sub(r['sp'], 1)
        returning = self.mode(Mode.RETURN)
        top_return = self.AND(returning, self.NOT(nonempty))
        start_open = self.AND(top_return, self.NOT(self.eq(r['pending_open'], 0)))
        self.emit(start_open, mode=Mode.TELESCOPE, x=r['root'], task=Task.OPEN_TELESCOPE, depth=0, pending_open=0)
        after_open = self.AND(top_return, self.eq(r['pending_open'], 0))
        start_fold = self.AND(after_open, self.NOT(self.eq(r['pending_fold'], 0)))
        self.emit(start_fold, mode=Mode.FOLD_SELECT, x=result, fold_body=result, task=Task.FOLD_TELESCOPE, pending_fold=0)
        after_fold = self.AND(after_open, self.eq(r['pending_fold'], 0))
        self.emit(self.AND(after_fold, self.NOT(self.eq(r['pending_compare'], 0))),
            mode=Mode.WALK, x=result, peer=r['comparison_root'],
            task=self.mux(self.eq(r['pending_compare'], 1), Task.LEVEL_EQUAL, Task.EXPR_EQUAL), pending_compare=0)
        self.stop(self.AND(after_fold, self.eq(r['pending_compare'], 0)), Outcome.DONE)
        internal_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_BETA_ZETA))
        self.emit(internal_return, sp=top, mode=Mode.BETA_ZETA, x=result, depth=0, task=Task.BETA_ZETA)
        telescope_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_TELESCOPE))
        self.emit(telescope_return, sp=top, mode=Mode.TELESCOPE, x=result, depth=0, task=Task.OPEN_TELESCOPE)
        fold_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_FOLD))
        self.emit(fold_return, sp=top, mode=Mode.FOLD_BUILD, x=result, task=Task.FOLD_TELESCOPE)
        sort_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_SORT_LEVEL))
        self.emit(sort_return, sp=top, mode=Mode.SORT_RESULT, x=frame['original'], depth=frame['depth'], task=frame['task'])
        const_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_CONST_LEVEL))
        self.emit(const_return, sp=top, mode=Mode.CONST_RESULT, x=frame['original'], depth=frame['depth'], task=frame['task'])
        compare_return = self.AND(returning, nonempty, self.eq(frame['phase'], LEVEL_EQUAL_SECOND))
        self.emit(compare_return, sp=top)
        self.ret(self.AND(compare_return, self.eq(result, 0)), 0)
        self.emit(self.AND(compare_return, self.NOT(self.eq(result, 0))),
            mode=Mode.WALK, x=frame['original'], peer=frame['depth'], task=Task.LEVEL_EQUAL)
        or_return = self.AND(returning, nonempty, self.eq(frame['phase'], LEVEL_OR_SECOND))
        self.emit(or_return, sp=top)
        self.ret(self.AND(or_return, self.NOT(self.eq(result, 0))), 1)
        self.emit(self.AND(or_return, self.eq(result, 0)), mode=Mode.WALK, x=frame['original'], task=Task.LEVEL_NOT_ZERO)
        private_phase = self.OR(*(self.eq(frame['phase'], value) for value in
            (CALL_BETA_ZETA, CALL_TELESCOPE, CALL_FOLD, CALL_SORT_LEVEL, CALL_CONST_LEVEL, LEVEL_EQUAL_SECOND, LEVEL_OR_SECOND)+level_constructor_rules.PRIVATE_PHASES+level_order_rules.PRIVATE_PHASES+level_normalize_rules.PRIVATE_PHASES+level_geq_rules.PRIVATE_PHASES+expression_equal_rules.PRIVATE_PHASES))
        self.emit(self.AND(returning, nonempty, self.NOT(private_phase)), mode=Mode.RESUME,
                  x=frame['original'], depth=frame['depth'], task=frame['task'])

        # Structural == walks pairs. A native allocation can duplicate a DAG;
        # address identity is only a fast path, never the complete predicate.
        comparing = self.AND(self.mode(Mode.WALK), self.task(Task.LEVEL_EQUAL))
        peer_ok = self.AND(self.NOT(self.eq(r['peer'], 0)), self.lt(r['peer'], r['free']))
        self.stop(self.AND(comparing, self.NOT(peer_ok)), Outcome.INVALID, Reason.SYNTAX)
        comparing = self.AND(comparing, peer_ok)
        identical = self.eq(x, r['peer'])
        self.ret(self.AND(comparing, identical), 1)
        self.emit(self.AND(comparing, self.NOT(identical)), mode=Mode.LEVEL_EQUAL_RIGHT,
            left_tag=node['tag'], left_a=a, left_b=b, x=r['peer'])
        right = self.mode(Mode.LEVEL_EQUAL_RIGHT)
        same_tag = self.eq(node['tag'], r['left_tag'])
        self.ret(self.AND(right, self.NOT(same_tag)), 0)
        right = self.AND(right, same_tag)
        self.ret(self.AND(right, self.tag(CellTag.LEVEL_ZERO)), 1)
        self.ret(self.AND(right, self.tag(CellTag.LEVEL_PARAM)), self.mux(self.eq(a, r['left_a']), 1, 0))
        self.emit(self.AND(right, self.tag(CellTag.LEVEL_SUCC)), mode=Mode.WALK, x=r['left_a'], peer=a)
        pair = self.AND(right, self.tag(CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX))
        pair_room = self.lt(r['sp'], self.cfg.stack)
        self.stop(self.AND(pair, self.NOT(pair_room)), Outcome.RESOURCE, Reason.STACK)
        pair = self.AND(pair, pair_room)
        self.write('stack', pair, r['sp'], (LEVEL_EQUAL_SECOND, r['left_b'], b, Task.LEVEL_EQUAL, 0, 0))
        self.emit(pair, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=r['left_a'], peer=a)
        not_zero = self.AND(self.mode(Mode.WALK), self.task(Task.LEVEL_NOT_ZERO))
        self.ret(self.AND(not_zero, self.tag(CellTag.LEVEL_ZERO, CellTag.LEVEL_PARAM)), 0)
        self.ret(self.AND(not_zero, self.tag(CellTag.LEVEL_SUCC)), 1)
        self.emit(self.AND(not_zero, self.tag(CellTag.LEVEL_IMAX)), x=b)
        or_branch = self.AND(not_zero, self.tag(CellTag.LEVEL_MAX))
        self.stop(self.AND(or_branch, self.NOT(pair_room)), Outcome.RESOURCE, Reason.STACK)
        or_branch = self.AND(or_branch, pair_room)
        self.write('stack', or_branch, r['sp'], (LEVEL_OR_SECOND, b, 0, Task.LEVEL_NOT_ZERO, 0, 0))
        self.emit(or_branch, sp=self.add(r['sp'], 1), x=a)
        offset = self.AND(self.mode(Mode.WALK), self.task(Task.LEVEL_OFFSET))
        self.ret(self.AND(offset, self.NOT(self.tag(CellTag.LEVEL_SUCC))), x)
        increment, next_offset = self.checked_add(self.AND(offset, self.tag(CellTag.LEVEL_SUCC)), r['level_offset'], 1)
        self.emit(increment, x=a, level_offset=next_offset)

        level_constructor_rules.emit_rules(self)
        level_order_rules.emit_rules(self)
        level_normalize_rules.emit_rules(self)
        level_geq_rules.emit_rules(self)
        expression_equal_rules.emit_rules(self)

        sorting = self.mode(Mode.SORT_RESULT)
        self.stop(self.AND(sorting, self.NOT(self.tag(Tag.SORT))), Outcome.INVALID, Reason.SYNTAX)
        self.ret(self.AND(sorting, self.tag(Tag.SORT), self.eq(a, result)), x)
        self.alloc(self.AND(sorting, self.tag(Tag.SORT), self.NOT(self.eq(a, result))), (Tag.SORT, result, 0, 0))
        vector = self.mode(Mode.CONST_VECTOR)
        empty = self.eq(a, 0)
        vector_ok = self.AND(self.eq(c, VectorKind.LEVELS), self.eq(self.mux(empty, 1, 0), self.mux(self.eq(b, 0), 1, 0)))
        self.stop(self.AND(vector, self.NOT(vector_ok)), Outcome.INVALID, Reason.SYNTAX)
        self.ret(self.AND(vector, vector_ok, empty), r['const_original'])
        self.emit(self.AND(vector, vector_ok, self.NOT(empty)), vec_length=a, vec_left=a, vec_build=a,
            vec_head=0, vec_changed=0, mode=Mode.CONST_CELL, x=b)
        cell = self.mode(Mode.CONST_CELL)
        more_values = self.lt(1, r['vec_left'])
        cell_ok = self.AND(self.NOT(self.eq(r['vec_left'], 0)),
            self.eq(self.mux(more_values, 1, 0), self.mux(self.NOT(self.eq(b, 0)), 1, 0)))
        self.stop(self.AND(cell, self.NOT(cell_ok)), Outcome.INVALID, Reason.SYNTAX)
        stack_room = self.lt(r['sp'], self.cfg.stack)
        self.stop(self.AND(cell, cell_ok, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        call_level = self.AND(cell, cell_ok, stack_room)
        self.write('stack', call_level, r['sp'], (CALL_CONST_LEVEL, x, r['expr_depth'], task, 0, 0))
        self.emit(call_level, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=a, depth=0, task=self.mux(self.task(Task.EXPR_SCOPE), Task.LEVEL_SCOPE, self.mux(self.task(Task.EXPR_LEVEL_INSTANTIATE), Task.LEVEL_INSTANTIATE, Task.LEVEL_SUBSTITUTE)))
        value = self.mode(Mode.CONST_RESULT)
        value_ok = self.NOT(self.eq(r['vec_left'], 0))
        self.stop(self.AND(value, self.NOT(value_ok)), Outcome.INVALID, Reason.SYNTAX)
        changed = self.OR(self.NOT(self.eq(r['vec_changed'], 0)), self.NOT(self.eq(a, result)))
        push_value = self.AND(value, value_ok, self.OR(more_values, changed))
        self.stop(self.AND(push_value, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        push_value = self.AND(push_value, stack_room)
        self.write('stack', push_value, r['sp'], (VECTOR_VALUE, result, 0, task, 0, 0))
        self.emit(push_value, sp=self.add(r['sp'], 1), vec_left=self.sub(r['vec_left'], 1),
            vec_changed=self.mux(changed, 1, 0), mode=self.mux(more_values, Mode.CONST_CELL, Mode.CONST_BUILD),
            x=self.mux(more_values, b, r['const_original']))
        unchanged_vector = self.AND(value, value_ok, self.NOT(more_values), self.NOT(changed))
        self.emit(unchanged_vector, sp=self.sub(r['sp'], self.sub(r['vec_length'], 1)))
        self.ret(unchanged_vector, r['const_original'])
        building = self.mode(Mode.CONST_BUILD)
        has_value = self.NOT(self.eq(r['vec_build'], 0))
        build_ok = self.OR(self.NOT(has_value), self.AND(nonempty, self.eq(frame['phase'], VECTOR_VALUE)))
        self.stop(self.AND(building, self.NOT(build_ok)), Outcome.INVALID, Reason.SYNTAX)
        heap_room = self.lt(r['free'], self.cfg.heap)
        self.stop(self.AND(building, build_ok, self.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
        build_cell = self.AND(building, build_ok, heap_room, has_value)
        self.write('heap', build_cell, r['free'], (CellTag.VECTOR_CELL, frame['original'], r['vec_head'], 0))
        self.emit(build_cell, free=self.add(r['free'], 1), vec_head=r['free'], vec_build=self.sub(r['vec_build'], 1), sp=top)
        build_header = self.AND(building, build_ok, heap_room, self.NOT(has_value))
        self.write('heap', build_header, r['free'], (CellTag.VECTOR, r['vec_length'], r['vec_head'], VectorKind.LEVELS))
        self.emit(build_header, free=self.add(r['free'], 1), vector_result=r['free'], mode=Mode.CONST_FINISH)
        const_finish = self.mode(Mode.CONST_FINISH)
        self.stop(self.AND(const_finish, self.NOT(self.tag(Tag.CONST))), Outcome.INVALID, Reason.SYNTAX)
        self.alloc(self.AND(const_finish, self.tag(Tag.CONST)), (Tag.CONST, a, r['vector_result'], 0))

        self.emit(self.mode(Mode.LEVEL_SELECT), mode=Mode.LEVEL_BINDING, x=operand)
        binding = self.mode(Mode.LEVEL_BINDING)
        value_valid = self.AND(self.NOT(self.eq(b, 0)), self.lt(b, r['free']))
        self.stop(self.AND(binding, self.NOT(value_valid)), Outcome.INVALID, Reason.SYNTAX)
        binding = self.AND(binding, value_valid)
        matches = self.eq(a, r['parameter'])
        self.ret(self.AND(binding, matches), b)
        another_binding = self.lt(self.add(r['i'], 1), r['count'])
        self.emit(self.AND(binding, self.NOT(matches), another_binding),
            mode=Mode.LEVEL_SELECT, x=r['lookup_level'], i=self.add(r['i'], 1))
        self.ret(self.AND(binding, self.NOT(matches), self.NOT(another_binding)), r['lookup_level'])

        folding = self.mode(Mode.FOLD_SELECT)
        active_local = self.NOT(self.eq(r['ctx'], 0))
        self.ret(self.AND(folding, self.NOT(active_local)), r['fold_body'])
        self.emit(self.AND(folding, active_local), mode=Mode.FOLD_RECORD, x=operand)
        record = self.mode(Mode.FOLD_RECORD)
        valid_record = self.AND(self.NOT(self.eq(a, 0)), self.lt(a, r['free']), self.NOT(self.eq(b, 0)), self.lt(b, r['free']))
        self.stop(self.AND(record, self.NOT(valid_record)), Outcome.INVALID, Reason.SYNTAX)
        self.emit(self.AND(record, valid_record), mode=Mode.FOLD_LOCAL, x=a, domain=b, binder_info=c)
        local = self.mode(Mode.FOLD_LOCAL)
        valid_local = self.tag(Tag.LOCAL)
        self.stop(self.AND(local, self.NOT(valid_local)), Outcome.INVALID, Reason.SYNTAX)
        stack_room = self.lt(r['sp'], self.cfg.stack)
        self.stop(self.AND(local, valid_local, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        local = self.AND(local, valid_local, stack_room)
        self.write('stack', local, r['sp'], (CALL_FOLD, 0, 0, Task.FOLD_TELESCOPE, 0, 0))
        self.emit(local, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=r['fold_body'], depth=0,
            task=Task.ABSTRACT_ONE, abstract_uid=a)
        build = self.mode(Mode.FOLD_BUILD)
        self.stop(self.AND(build, self.NOT(active_local)), Outcome.INVALID, Reason.SYNTAX)
        heap_room = self.lt(r['free'], self.cfg.heap)
        self.stop(self.AND(build, active_local, self.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
        build = self.AND(build, active_local, heap_room)
        self.write('heap', build, r['free'], (r['fold_tag'], r['domain'], result, r['binder_info']))
        self.emit(build, free=self.add(r['free'], 1), fold_body=r['free'], ctx=self.sub(r['ctx'], 1),
            mode=Mode.FOLD_SELECT, x=r['free'])

        # Consume declared Pi binders by a count-driven loop. Each allocated
        # Local has an arena-address UID and a separate (Local,type,binderInfo)
        # record. The entry scope walk rejects raw free locals before opening.
        telescope = self.mode(Mode.TELESCOPE)
        bounded = self.NOT(self.eq(r['bounded'], 0))
        at_limit = self.AND(bounded, self.eq(r['ctx'], r['limit']))
        self.ret(self.AND(telescope, at_limit), x)
        continue_open = self.AND(telescope, self.NOT(at_limit))
        pi = self.eq(node['tag'], r['open_tag'])
        expected = self.mux(self.eq(r['open_tag'], Tag.PI), Reason.EXPECT_PI, Reason.EXPECT_LAM)
        self.stop(self.AND(continue_open, self.NOT(pi), bounded), Outcome.INVALID, expected)
        self.ret(self.AND(continue_open, self.NOT(pi), self.NOT(bounded)), x)
        opening = self.AND(continue_open, pi)
        context_room = self.lt(r['ctx'], self.cfg.context)
        stack_room = self.lt(r['sp'], self.cfg.stack)
        heap_room = self.lt(self.add(r['free'], 1), self.cfg.heap)
        self.stop(self.AND(opening, self.NOT(context_room)), Outcome.RESOURCE, Reason.CONTEXT)
        self.stop(self.AND(opening, context_room, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        self.stop(self.AND(opening, context_room, stack_room, self.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
        opening = self.AND(opening, context_room, stack_room, heap_room)
        self.write('heap', opening, r['free'], (Tag.LOCAL, r['free'], 0, 0))
        self.emit(opening, free=self.add(r['free'], 1), r=r['free'], mode=Mode.BINDER_RECORD)
        recording = self.mode(Mode.BINDER_RECORD)
        self.write('heap', recording, r['free'], (LOCAL_DECL_TAG, result, a, c))
        self.write('context', recording, r['ctx'], (r['free'],))
        self.write('stack', recording, r['sp'], (CALL_TELESCOPE, 0, 0, Task.OPEN_TELESCOPE, 0, 0))
        self.emit(recording, free=self.add(r['free'], 1), ctx=self.add(r['ctx'], 1), sp=self.add(r['sp'], 1),
            mode=Mode.WALK, x=b, depth=0, task=Task.INSTANTIATE_ONE, substitution=result)

        # The beta/zeta service calls the SAME capture-avoiding substitution
        # walk, then resumes through a private continuation. App arguments are
        # internal stack frames, never an input-provided traversal schedule.
        reducing = self.mode(Mode.BETA_ZETA)
        self.emit(self.AND(reducing, self.tag(Tag.MDATA)), x=a)
        room = self.lt(r['sp'], self.cfg.stack)
        argument = self.AND(nonempty, self.eq(frame['phase'], PENDING_ARGUMENT))
        push_argument = self.AND(reducing, self.tag(Tag.APP))
        let_call = self.AND(reducing, self.tag(Tag.LET))
        pushing = self.OR(push_argument, let_call)
        self.stop(self.AND(pushing, self.NOT(room)), Outcome.RESOURCE, Reason.STACK)
        self.write('stack', self.AND(push_argument, room), r['sp'],
            (PENDING_ARGUMENT, x, 0, Task.BETA_ZETA, b, 0))
        self.emit(self.AND(push_argument, room), sp=self.add(r['sp'], 1), x=a)
        beta = self.AND(reducing, self.tag(Tag.LAM), argument)
        self.write('stack', beta, top, (CALL_BETA_ZETA, 0, 0, Task.BETA_ZETA, 0, 0))
        self.emit(beta, mode=Mode.WALK, x=b, substitution=frame['first'], depth=0, task=Task.INSTANTIATE_ONE)
        self.write('stack', self.AND(let_call, room), r['sp'], (CALL_BETA_ZETA, 0, 0, Task.BETA_ZETA, 0, 0))
        self.emit(self.AND(let_call, room), sp=self.add(r['sp'], 1), mode=Mode.WALK,
            x=c, substitution=b, depth=0, task=Task.INSTANTIATE_ONE)
        stuck = self.AND(reducing, self.NOT(self.OR(self.tag(Tag.MDATA, Tag.APP, Tag.LET), self.AND(self.tag(Tag.LAM), argument))))
        self.ret(stuck, x)

        # Reverse list search implements Local abstraction and symbol-set DFS.
        finding = self.mode(Mode.FIND)
        valid = self.lt(r['i'], r['count'])
        self.stop(self.AND(finding, self.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
        matched = self.eq(operand, a)
        found = self.AND(finding, valid, matched)
        self.emit(self.AND(found, self.task(Task.OCCURS)), found=1, sp=0, r=r['root'])
        self.stop(self.AND(found, self.task(Task.OCCURS)), Outcome.DONE)
        self.ret(self.AND(found, self.task(Task.LEVEL_SCOPE)), x)
        adding, bound_index = self.checked_add(self.AND(found, self.NOT(self.OR(self.task(Task.OCCURS), self.task(Task.LEVEL_SCOPE)))),
            depth, self.sub(self.sub(r['count'], 1), r['i']))
        self.alloc(adding, (Tag.BVAR, bound_index, 0, 0))
        missing = self.AND(finding, valid, self.NOT(matched))
        last = self.AND(missing, self.eq(r['i'], 0))
        self.stop(self.AND(last, self.task(Task.LEVEL_SCOPE)), Outcome.INVALID, Reason.UNIVERSE)
        self.ret(self.AND(last, self.NOT(self.task(Task.LEVEL_SCOPE))), x)
        self.emit(self.AND(missing, self.NOT(self.eq(r['i'], 0))), i=self.sub(r['i'], 1))

        level_task = self.OR(*(self.task(t) for t in (Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.LEVEL_INSTANTIATE, Task.LEVEL_NORMALIZE, Task.LEVEL_NORMAL_SUCC)))
        binary = self.OR(self.tag(Tag.APP, Tag.PI, Tag.LAM),
            self.AND(level_task, self.OR(self.tag(CellTag.LEVEL_MAX), self.AND(self.tag(CellTag.LEVEL_IMAX), self.NOT(self.task(Task.LEVEL_NORMAL_SUCC))))))
        let = self.tag(Tag.LET)
        unary = self.OR(self.tag(Tag.PROJ, Tag.MDATA),
            self.AND(level_task, self.tag(CellTag.LEVEL_SUCC), self.NOT(self.task(Task.LEVEL_NORMAL_SUCC))))
        branch = self.OR(binary, let, unary)
        walking = self.mode(Mode.WALK)
        expression_level = self.AND(walking, self.OR(self.task(Task.EXPR_LEVEL_SUBSTITUTE), self.task(Task.EXPR_LEVEL_INSTANTIATE), self.task(Task.EXPR_SCOPE)))
        no_bindings = self.AND(self.eq(r['count'], 0), self.NOT(self.task(Task.EXPR_SCOPE)))
        self.ret(self.AND(expression_level, no_bindings), x)
        sort_call = self.AND(expression_level, self.NOT(no_bindings), self.tag(Tag.SORT))
        self.stop(self.AND(sort_call, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        sort_call = self.AND(sort_call, stack_room)
        self.write('stack', sort_call, r['sp'], (CALL_SORT_LEVEL, x, depth, task, 0, 0))
        self.emit(sort_call, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=a, depth=0, task=self.mux(self.task(Task.EXPR_SCOPE), Task.LEVEL_SCOPE, self.mux(self.task(Task.EXPR_LEVEL_INSTANTIATE), Task.LEVEL_INSTANTIATE, Task.LEVEL_SUBSTITUTE)))
        self.emit(self.AND(expression_level, self.NOT(no_bindings), self.tag(Tag.CONST)),
            const_original=x, expr_depth=depth, mode=Mode.CONST_VECTOR, x=b)
        intercepted = self.AND(expression_level, self.OR(no_bindings, self.tag(Tag.SORT, Tag.CONST)))
        walking = self.AND(walking, self.NOT(intercepted),
            self.NOT(self.OR(self.task(Task.LEVEL_EQUAL), self.task(Task.LEVEL_NOT_ZERO), self.task(Task.LEVEL_OFFSET), self.task(Task.LEVEL_MAX), self.task(Task.LEVEL_IMAX), self.task(Task.LEVEL_ORDER), self.task(Task.LEVEL_MERGE), self.task(Task.LEVEL_EQUIVALENT), self.task(Task.LEVEL_GEQ), self.task(Task.LEVEL_GEQ_CORE), self.task(Task.EXPR_EQUAL), self.task(Task.VECTOR_EQUAL))))
        descending = self.AND(walking, branch)
        room = self.lt(r['sp'], self.cfg.stack)
        self.stop(self.AND(descending, self.NOT(room)), Outcome.RESOURCE, Reason.STACK)
        down = self.AND(descending, room)
        self.write('stack', down, r['sp'], (1, x, depth, task, 0, 0))
        self.emit(down, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=self.mux(self.tag(Tag.PROJ), c, a))

        # Revisit a completed child using the original row and continuation data.
        resume_argument = self.AND(self.mode(Mode.RESUME), self.eq(frame['phase'], PENDING_ARGUMENT))
        valid_argument = self.AND(nonempty, self.tag(Tag.APP))
        self.stop(self.AND(resume_argument, self.NOT(valid_argument)), Outcome.INVALID, Reason.SYNTAX)
        resume_argument = self.AND(resume_argument, valid_argument)
        self.emit(resume_argument, sp=top)
        self.ret(self.AND(resume_argument, self.eq(a, result)), x)
        self.alloc(self.AND(resume_argument, self.NOT(self.eq(a, result))), (Tag.APP, result, frame['first'], 0))
        resuming = self.AND(self.mode(Mode.RESUME), self.NOT(self.eq(frame['phase'], PENDING_ARGUMENT)))
        child_count = self.mux(let, 3, self.mux(binary, 2, self.mux(unary, 1, 0)))
        phase_valid = self.AND(nonempty, self.NOT(self.eq(frame['phase'], 0)), self.NOT(self.lt(child_count, frame['phase'])))
        self.stop(self.AND(resuming, self.NOT(phase_valid)), Outcome.INVALID, Reason.SYNTAX)
        another = self.AND(resuming, phase_valid, self.lt(frame['phase'], child_count))
        first_phase = self.eq(frame['phase'], 1)
        binder_child = self.OR(self.AND(self.tag(Tag.PI, Tag.LAM), first_phase), self.AND(let, self.eq(frame['phase'], 2)))
        another, next_depth = self.checked_add(another, depth, self.mux(binder_child, 1, 0))
        self.write('stack', another, top, (self.add(frame['phase'], 1), x, depth, task,
            self.mux(first_phase, result, frame['first']), self.mux(first_phase, frame['second'], result)))
        self.emit(another, mode=Mode.WALK, x=self.mux(first_phase, b, c), depth=next_depth)

        finish = self.AND(resuming, phase_valid, self.eq(frame['phase'], child_count))
        normal = self.task(Task.LEVEL_NORMALIZE)
        normal_imax = self.AND(finish, normal, self.tag(CellTag.LEVEL_IMAX))
        self.emit(self.AND(finish, self.NOT(normal_imax)), sp=top)
        self.write('stack', normal_imax, top, (CALL_NORMAL_IMAX, 0, 0, Task.LEVEL_NORMALIZE, 0, 0))
        self.emit(normal_imax, mode=Mode.WALK, task=Task.LEVEL_IMAX, x=frame['first'], peer=result)
        self.emit(self.AND(finish, normal, self.tag(CellTag.LEVEL_MAX)), mode=Mode.WALK, task=Task.LEVEL_MERGE, x=frame['first'], peer=result)
        self.emit(self.AND(finish, normal, self.tag(CellTag.LEVEL_SUCC)), mode=Mode.WALK, task=Task.LEVEL_NORMAL_SUCC, x=result)
        first, second = frame['first'], frame['second']
        unchanged = self.OR(
            self.AND(unary, self.eq(result, self.mux(self.tag(Tag.PROJ), c, a))),
            self.AND(binary, self.eq(first, a), self.eq(result, b)),
            self.AND(let, self.eq(first, a), self.eq(second, b), self.eq(result, c)))
        self.ret(self.AND(finish, unchanged, self.NOT(normal)), x)
        rebuild = self.AND(finish, self.NOT(unchanged), self.NOT(normal))
        source_construct = self.AND(rebuild, self.task(Task.LEVEL_INSTANTIATE), self.tag(CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX))
        self.emit(source_construct, mode=Mode.WALK, x=first, peer=result,
            task=self.mux(self.tag(CellTag.LEVEL_MAX), Task.LEVEL_MAX, Task.LEVEL_IMAX))
        self.alloc(self.AND(rebuild, binary, self.NOT(source_construct)), (node['tag'], first, result, c))
        self.alloc(self.AND(rebuild, let), (node['tag'], first, second, result))
        self.alloc(self.AND(rebuild, self.tag(Tag.PROJ)), (node['tag'], a, b, result))
        self.alloc(self.AND(rebuild, self.tag(Tag.MDATA)), (node['tag'], result, b, 0))
        self.alloc(self.AND(rebuild, self.tag(CellTag.LEVEL_SUCC)), (node['tag'], result, 0, 0))

        leaf = self.AND(walking, self.NOT(branch))
        normal_successor = self.AND(leaf, self.task(Task.LEVEL_NORMAL_SUCC))
        self.alloc(normal_successor, (CellTag.LEVEL_SUCC, x, 0, 0))
        scope_bad = self.AND(leaf, self.OR(self.task(Task.VARIABLE_SCOPE), self.task(Task.EXPR_SCOPE)),
            self.OR(self.tag(Tag.LOCAL), self.AND(self.tag(Tag.BVAR), self.NOT(self.lt(a, depth)))))
        self.stop(scope_bad, Outcome.INVALID, Reason.SCOPE)
        unbound_level = self.AND(leaf, self.task(Task.LEVEL_SCOPE), self.tag(CellTag.LEVEL_PARAM), self.eq(r['count'], 0))
        self.stop(unbound_level, Outcome.INVALID, Reason.UNIVERSE)
        substitute_level = self.AND(leaf, self.OR(self.task(Task.LEVEL_SUBSTITUTE), self.task(Task.LEVEL_INSTANTIATE)), self.tag(CellTag.LEVEL_PARAM), self.NOT(self.eq(r['count'], 0)))
        self.emit(substitute_level, mode=Mode.LEVEL_SELECT, i=0, parameter=a, lookup_level=x)
        abstract_one = self.AND(leaf, self.task(Task.ABSTRACT_ONE), self.tag(Tag.LOCAL), self.eq(a, r['abstract_uid']))
        self.alloc(abstract_one, (Tag.BVAR, depth, 0, 0))
        inst = self.OR(self.task(Task.INSTANTIATE), self.task(Task.INSTANTIATE_ONE))
        var_transform = self.AND(leaf, self.tag(Tag.BVAR), self.OR(self.task(Task.LIFT), inst))
        start = self.mux(self.task(Task.INSTANTIATE_ONE), 0, self.mux(self.task(Task.LIFT), r['cutoff'], r['start']))
        count = self.mux(self.task(Task.INSTANTIATE_ONE), 1, r['count'])
        offset_guard, offset = self.checked_add(var_transform, depth,
            start)
        under = self.lt(a, offset)
        self.ret(self.AND(offset_guard, under), x)
        above = self.AND(offset_guard, self.NOT(under))
        lifting = self.AND(above, self.task(Task.LIFT))
        lifting, lifted = self.checked_add(lifting, a, r['delta'])
        unchanged_lift = self.eq(lifted, a)
        self.ret(self.AND(lifting, unchanged_lift), x)
        self.alloc(self.AND(lifting, self.NOT(unchanged_lift)), (Tag.BVAR, lifted, 0, 0))
        instantiating = self.AND(above, inst)
        relative = self.sub(a, offset)
        within = self.lt(relative, count)
        beyond = self.AND(instantiating, self.NOT(within))
        self.ret(self.AND(beyond, self.eq(count, 0)), x)
        self.alloc(self.AND(beyond, self.NOT(self.eq(count, 0))), (Tag.BVAR, self.sub(a, count), 0, 0))
        substituting = self.AND(instantiating, within)
        operand = self.mux(self.task(Task.INSTANTIATE_ONE), r['substitution'], operand)
        valid_operand = self.AND(self.NOT(self.eq(operand, 0)), self.lt(operand, r['free']))
        self.stop(self.AND(substituting, self.NOT(valid_operand)), Outcome.INVALID, Reason.SYNTAX)
        substituting = self.AND(substituting, valid_operand)
        self.ret(self.AND(substituting, self.eq(depth, 0)), operand)
        self.emit(self.AND(substituting, self.NOT(self.eq(depth, 0))),
            x=operand, depth=0, task=Task.LIFT, delta=depth, cutoff=0)
        searching = self.AND(leaf, self.OR(self.AND(self.tag(Tag.LOCAL), self.task(Task.ABSTRACT)),
            self.AND(self.tag(Tag.CONST), self.task(Task.OCCURS)),
            self.AND(self.tag(CellTag.LEVEL_PARAM), self.task(Task.LEVEL_SCOPE))), self.NOT(self.eq(r['count'], 0)))
        self.emit(searching, mode=Mode.FIND, i=self.sub(r['count'], 1))
        self.ret(self.AND(leaf, self.NOT(normal_successor), self.NOT(var_transform), self.NOT(searching), self.NOT(scope_bad), self.NOT(abstract_one), self.NOT(unbound_level), self.NOT(substitute_level)), x)

    def finish(self, memory_update='attention_delta', target=None):
        if memory_update != 'attention_delta':
            raise ValueError('kernel traversal uses addressed native memory ABI')
        self.rules()
        outputs = []
        for name, _ in self.layout.fields:
            choices = self.choices[name]
            keep = self.NOT(self.OR(*(guard for guard, _ in choices)))
            for i, old in enumerate(self.r[name]):
                outputs.append(self.g.masked_or([(keep, old)]+[(guard, value[i]) for guard, value in choices], self.factor))
        for bank, fields in (('heap', 4), ('stack', 6), ('context', 1)):
            choices = self.writes[bank]
            bits = getattr(self.cfg, bank).bit_length()-1
            outputs.extend(self.g.masked_or([(guard, address[i]) for guard, address, row in choices], self.factor) for i in range(bits))
            outputs.append(self.OR(*(guard for guard, address, row in choices)))
            for field in range(fields):
                outputs.extend(self.g.masked_or([(guard, row[field][i]) for guard, address, row in choices], self.factor) for i in range(self.width))
        return self.g.compile(outputs, target)
