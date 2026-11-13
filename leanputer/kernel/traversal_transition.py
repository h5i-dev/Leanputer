"""Lower the shared all-tag traversal controller to Boolean semantic IR.

Stock Qwen3.5/GatedDeltaNet emission is provided by native_machine. This module
has no runtime dependency on the Python kernel operations/reference machine.
"""
from ..bitvec import Builder
from .arena import Tag
from .traversal_machine import (MachineConfig, Mode, Outcome, Reason, Task,
    CALL_BETA_ZETA, PENDING_ARGUMENT, CALL_TELESCOPE, LOCAL_DECL_TAG,
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
    index = g.mux(g.eq(r['mode'], g.const(Mode.FIND, width)), r['i'], relative)
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
            self.lt(Mode.BINDER_RECORD, self.r['mode']), self.lt(Task.VARIABLE_SCOPE, self.r['task']),
            self.lt(1, self.r['bounded']), self.lt(1, self.r['pending_open']))
        self.stop(self.AND(self.active, invalid), Outcome.INVALID, Reason.SYNTAX)
        self.active = self.AND(self.active, self.NOT(invalid))
        needs_node = self.NOT(self.eq(self.r['mode'], Mode.RETURN))
        node_bad = self.OR(self.eq(self.r['x'], 0), self.NOT(self.lt(self.r['x'], self.r['free'])),
            self.lt(self.read['node']['tag'], Tag.BVAR), self.lt(Tag.MDATA, self.read['node']['tag']))
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
        self.stop(self.AND(top_return, self.eq(r['pending_open'], 0)), Outcome.DONE)
        internal_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_BETA_ZETA))
        self.emit(internal_return, sp=top, mode=Mode.BETA_ZETA, x=result, depth=0, task=Task.BETA_ZETA)
        telescope_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_TELESCOPE))
        self.emit(telescope_return, sp=top, mode=Mode.TELESCOPE, x=result, depth=0, task=Task.OPEN_TELESCOPE)
        self.emit(self.AND(returning, nonempty, self.NOT(self.OR(self.eq(frame['phase'], CALL_BETA_ZETA), self.eq(frame['phase'], CALL_TELESCOPE)))), mode=Mode.RESUME,
                  x=frame['original'], depth=frame['depth'], task=frame['task'])

        # Consume declared Pi binders by a count-driven loop. Each allocated
        # Local has an arena-address UID and a separate (Local,type,binderInfo)
        # record. The entry scope walk rejects raw free locals before opening.
        telescope = self.mode(Mode.TELESCOPE)
        bounded = self.NOT(self.eq(r['bounded'], 0))
        at_limit = self.AND(bounded, self.eq(r['ctx'], r['limit']))
        self.ret(self.AND(telescope, at_limit), x)
        continue_open = self.AND(telescope, self.NOT(at_limit))
        pi = self.tag(Tag.PI)
        self.stop(self.AND(continue_open, self.NOT(pi), bounded), Outcome.INVALID, Reason.EXPECT_PI)
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
        adding, bound_index = self.checked_add(self.AND(found, self.NOT(self.task(Task.OCCURS))),
            depth, self.sub(self.sub(r['count'], 1), r['i']))
        self.alloc(adding, (Tag.BVAR, bound_index, 0, 0))
        missing = self.AND(finding, valid, self.NOT(matched))
        self.ret(self.AND(missing, self.eq(r['i'], 0)), x)
        self.emit(self.AND(missing, self.NOT(self.eq(r['i'], 0))), i=self.sub(r['i'], 1))

        binary = self.tag(Tag.APP, Tag.PI, Tag.LAM)
        let = self.tag(Tag.LET)
        unary = self.tag(Tag.PROJ, Tag.MDATA)
        branch = self.OR(binary, let, unary)
        walking = self.mode(Mode.WALK)
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
        self.emit(finish, sp=top)
        first, second = frame['first'], frame['second']
        unchanged = self.OR(
            self.AND(unary, self.eq(result, self.mux(self.tag(Tag.PROJ), c, a))),
            self.AND(binary, self.eq(first, a), self.eq(result, b)),
            self.AND(let, self.eq(first, a), self.eq(second, b), self.eq(result, c)))
        self.ret(self.AND(finish, unchanged), x)
        rebuild = self.AND(finish, self.NOT(unchanged))
        self.alloc(self.AND(rebuild, binary), (node['tag'], first, result, c))
        self.alloc(self.AND(rebuild, let), (node['tag'], first, second, result))
        self.alloc(self.AND(rebuild, self.tag(Tag.PROJ)), (node['tag'], a, b, result))
        self.alloc(self.AND(rebuild, self.tag(Tag.MDATA)), (node['tag'], result, b, 0))

        leaf = self.AND(walking, self.NOT(branch))
        scope_bad = self.AND(leaf, self.task(Task.VARIABLE_SCOPE),
            self.OR(self.tag(Tag.LOCAL), self.AND(self.tag(Tag.BVAR), self.NOT(self.lt(a, depth)))))
        self.stop(scope_bad, Outcome.INVALID, Reason.SCOPE)
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
            self.AND(self.tag(Tag.CONST), self.task(Task.OCCURS))), self.NOT(self.eq(r['count'], 0)))
        self.emit(searching, mode=Mode.FIND, i=self.sub(r['count'], 1))
        self.ret(self.AND(leaf, self.NOT(var_transform), self.NOT(searching), self.NOT(scope_bad)), x)

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
