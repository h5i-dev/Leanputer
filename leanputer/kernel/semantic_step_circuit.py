"""One shared control circuit for a Lean kernel transition.

Task, mode, private continuation PCs and the caller frame are model-owned
checker state. Expression tags, names, declaration shapes and proof bodies stay
data. The circuit evaluates the projected control predicates of the six shared
operators. It is not a word-opcode interpreter and not one neural graph per
handler.

A handler predicate selects guarded field updates. The reference merges
simultaneously true updates with bitwise OR, and at most five handlers are true
on one control state. Pure equality keys partition into exclusive field-set
classes. The continuation-range selector publishes one hit per class and leaves
the handler identity as the live control key, so a dense continuation span is a
range test rather than one gate per key. It does not run the operator body.
This module does not run at inference and it does not emit a torch model
unless a caller asks.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict

from ..native_machine import NativeBuilder
from ..native_vendor.qwenputer.expr import ONE, Expr
from ..native_vendor.qwenputer.ir import FFN, Head
from ..native_vendor.qwenputer.emit import allocate, reads
from .semantic_dispatch import _cone, _input_names
from .semantic_operators import CALL_LIMIT, DENSE_LIMIT, OPERATORS


# Compact AND/OR is one SwiGLU unit. Placement leaves 24 rows for the
# allocator's handover units, so the model intermediate stays 256.
MODEL_INTERMEDIATE = 256
GATE_CAP = MODEL_INTERMEDIATE - 24
HIDDEN_CANDIDATES = (768, 896, 1024)


class BoolNet:
    """Boolean twin of the gate graph. Used to check the lowering, not to run it."""

    def __init__(self):
        self.ops = [('one', None), ('zero', None)]
        self.memo = {}
        self.ONE = 0
        self.ZERO = 1

    def node(self, kind, payload):
        key = (kind, payload)
        found = self.memo.get(key)
        if found is not None:
            return found
        self.ops.append(key)
        ident = len(self.ops) - 1
        self.memo[key] = ident
        return ident

    def value(self, ident, env, cache):
        found = cache.get(ident)
        if found is not None:
            return found
        kind, payload = self.ops[ident]
        if kind == 'one':
            result = 1
        elif kind == 'zero':
            result = 0
        elif kind == 'input':
            result = env[payload]
        elif kind == 'not':
            result = 1 - self.value(payload, env, cache)
        elif kind == 'and':
            result = 1
            for child in payload:
                if not self.value(child, env, cache):
                    result = 0
                    break
        elif kind == 'or':
            result = 0
            for child in payload:
                if self.value(child, env, cache):
                    result = 1
                    break
        else:
            raise ValueError(f'unknown boolean node {kind}')
        cache[ident] = result
        return result


def holds(predicate, values):
    """Direct reading of a projected control predicate. Independent of the gates."""
    if isinstance(predicate, int):
        return bool(predicate)
    kind = predicate[0]
    if kind == 'range':
        _, variable, low, high = predicate
        value = values[variable]
        return low <= value <= high
    if kind == 'and':
        return all(holds(child, values) for child in predicate[1])
    if kind == 'or':
        return any(holds(child, values) for child in predicate[1])
    raise ValueError(f'unknown control predicate {kind}')


class PredicateCircuit:
    """Lower projected predicates to one shared gate graph and a boolean twin."""

    def __init__(self, builder, words, domains):
        self.builder = builder
        self.graph = builder.graph
        self.one = self.graph.one
        self.words = words
        self.domains = domains
        self.net = BoolNet()
        self.memo = {}
        self.bit_ids = {
            variable: [self.net.node('input', (variable, bit)) for bit in range(len(bits))]
            for variable, bits in words.items()
        }

    def compile_all(self, predicates):
        return [self.compile(predicate) for predicate in predicates]

    def compile(self, predicate):
        if isinstance(predicate, int):
            return (self.one, self.net.ONE) if predicate else (Expr(), self.net.ZERO)
        found = self.memo.get(predicate)
        if found is not None:
            return found
        kind = predicate[0]
        if kind == 'range':
            result = self._range(predicate[1], predicate[2], predicate[3])
        elif kind == 'and':
            children = [self.compile(child) for child in predicate[1]]
            result = self._and(children)
        elif kind == 'or':
            children = [self.compile(child) for child in predicate[1]]
            result = self._or(children)
        else:
            raise ValueError(f'unknown control predicate {kind}')
        self.memo[predicate] = result
        return result

    def _and(self, pairs):
        if any(ident == self.net.ZERO for _, ident in pairs):
            return Expr(), self.net.ZERO
        pairs = [(expr, ident) for expr, ident in pairs if ident != self.net.ONE]
        if not pairs:
            return self.one, self.net.ONE
        if len(pairs) == 1:
            return pairs[0]
        expr = self.builder.gate('and', [expr for expr, _ in pairs], 'control-and')
        ident = self.net.node('and', tuple(ident for _, ident in pairs))
        return expr, ident

    def _or(self, pairs):
        if any(ident == self.net.ONE for _, ident in pairs):
            return self.one, self.net.ONE
        pairs = [(expr, ident) for expr, ident in pairs if ident != self.net.ZERO]
        if not pairs:
            return Expr(), self.net.ZERO
        if len(pairs) == 1:
            return pairs[0]
        expr = self.builder.gate('or', [expr for expr, _ in pairs], 'control-or')
        ident = self.net.node('or', tuple(ident for _, ident in pairs))
        return expr, ident

    def _not(self, expr, ident):
        if ident == self.net.ZERO:
            return self.one, self.net.ONE
        if ident == self.net.ONE:
            return Expr(), self.net.ZERO
        kind, payload = self.net.ops[ident]
        if kind == 'not':
            return self.memo[('not-expr', ident)], payload
        new_id = self.net.node('not', ident)
        self.memo[('not-expr', new_id)] = expr
        return self.one - expr, new_id

    def _equal(self, variable, value):
        key = ('eq', variable, value)
        found = self.memo.get(key)
        if found is not None:
            return found
        parts = []
        for bit, (expr, ident) in enumerate(zip(self.words[variable], self.bit_ids[variable])):
            if (value >> bit) & 1:
                parts.append((expr, ident))
            else:
                parts.append(self._not(expr, ident))
        result = self._and(parts)
        self.memo[key] = result
        return result

    def _less(self, variable, bound):
        key = ('lt', variable, bound)
        found = self.memo.get(key)
        if found is not None:
            return found
        width = len(self.words[variable])
        if bound <= 0:
            result = (Expr(), self.net.ZERO)
        elif bound >= 1 << width:
            result = (self.one, self.net.ONE)
        else:
            terms = []
            bits = self.words[variable]
            ids = self.bit_ids[variable]
            for index in range(width):
                if (bound >> index) & 1 == 0:
                    continue
                parts = [self._not(bits[index], ids[index])]
                for higher in range(index + 1, width):
                    if (bound >> higher) & 1:
                        parts.append((bits[higher], ids[higher]))
                    else:
                        parts.append(self._not(bits[higher], ids[higher]))
                terms.append(self._and(parts))
            # The set-bit cases are disjoint, so their sum is Boolean OR with no extra gate.
            result = self._or_sum(terms)
        self.memo[key] = result
        return result

    def _or_sum(self, pairs):
        pairs = [(expr, ident) for expr, ident in pairs if ident != self.net.ZERO]
        if not pairs:
            return Expr(), self.net.ZERO
        if any(ident == self.net.ONE for _, ident in pairs):
            return self.one, self.net.ONE
        if len(pairs) == 1:
            return pairs[0]
        expr = sum((item[0] for item in pairs), Expr())
        ident = pairs[0][1]
        for _, other in pairs[1:]:
            ident = self.net.node('or', (ident, other))
        return expr, ident

    def _range(self, variable, low, high):
        if low == high:
            return self._equal(variable, low)
        below = self._less(variable, low)
        under_high = self._less(variable, high + 1)
        not_below = self._not(*below)
        return self._and([not_below, under_high])

    def agrees(self, predicates, compiled, samples):
        """The gate twin matches the direct predicate reading on every sample."""
        for values in samples:
            env = {}
            for variable, ids in self.bit_ids.items():
                value = values[variable]
                for bit, _ident in enumerate(ids):
                    env[(variable, bit)] = (value >> bit) & 1
            cache = {}
            for predicate, (_, ident) in zip(predicates, compiled):
                got = self.net.value(ident, env, cache)
                expect = int(holds(predicate, values))
                if got != expect:
                    raise AssertionError('control predicate lowering disagrees with the direct reading')


def _features(builder, variables, widths, level=None):
    """Birth control bits at ``level`` when a later section must not overlap earlier peaks.

    The default birth is level 0. Passing the section barrier is a schedule
    annotation. It does not drop a field and it does not change the predicate.
    """
    words = {}
    for variable in variables:
        width = widths[variable]
        bits = []
        for bit in range(width):
            expr = builder.feature(f'control/{variable}/{bit}')
            if level is not None:
                (dim,) = expr.terms
                builder.graph.dims[dim].level = level
            bits.append(expr)
        words[variable] = bits
    return words


def _ffn_units(graph):
    return sum(len(node.terms) for node in graph.nodes if isinstance(node, FFN))


def live_peak(graph, keep):
    """Maximum number of residual dims alive at one sublayer."""
    if not graph.nodes:
        return 0
    last = {dim: graph.dims[dim].level for dim in range(1, len(graph.dims))}
    for node in graph.nodes:
        for dim in reads(node):
            if dim != ONE and dim in last:
                last[dim] = max(last[dim], node.level)
    top = max(node.level for node in graph.nodes) + 1
    for dim in keep:
        if dim != ONE:
            last[dim] = top
    events = []
    for dim, death in last.items():
        events.append((graph.dims[dim].level, 1))
        events.append((death + 1, -1))
    events.sort()
    current = best = 0
    for _, delta in events:
        current += delta
        if current > best:
            best = current
    return best


def layer_dense(hidden, intermediate, kind, value_heads=4):
    mlp = 3 * hidden * intermediate
    if kind == 'linear_attention':
        return mlp + (258 + 386 * value_heads) * hidden + 1152 + 514 * value_heads
    return mlp + 12 * hidden + 4


def dense_parameters(hidden, intermediate, layers, gdn_layers=0, value_heads=4):
    if gdn_layers > layers:
        raise ValueError('more memory layers than model layers')
    logic = layers - gdn_layers
    total = gdn_layers * layer_dense(hidden, intermediate, 'linear_attention', value_heads)
    total += logic * layer_dense(hidden, intermediate, 'full_attention', value_heads)
    return total + 129 * hidden


def _shape(graph_layers, peak_slots, kept_outputs):
    """Smallest candidate hidden size whose ballast, tau and slots fit."""
    shapes = []
    for hidden in HIDDEN_CANDIDATES:
        ballast = hidden // 64
        need = ballast + 1 + peak_slots
        clear_layers = math.ceil(max(hidden - ballast - kept_outputs, 0) / MODEL_INTERMEDIATE)
        layers = graph_layers + clear_layers + 1
        dense = dense_parameters(hidden, MODEL_INTERMEDIATE, layers)
        shapes.append(dict(
            hidden=hidden,
            ballast=ballast,
            channels_needed=need,
            channel_gate=need <= hidden,
            graph_layers=graph_layers,
            scratch_clear_layers=clear_layers,
            feedback_layer=1,
            layers=layers,
            logical_dense_parameters=dense,
            dense_gate=dense <= DENSE_LIMIT,
            memory_layers_included=0,
        ))
    fitting = [shape for shape in shapes if shape['channel_gate'] and shape['dense_gate']]
    return fitting[0] if fitting else shapes[-1], shapes


def build_predicate_graph(variables, domains, widths, predicates, samples, wave=0, placement_cap=GATE_CAP, do_reschedule=None):
    """Build the shared predicate graph.

    ``wave`` 0 keeps cross-handler CSE. A positive wave recomputes each chunk
    after a barrier so later chunks can reuse residual slots. Inputs stay
    shared, so they remain live until the last chunk reads them. Reschedule
    ignores those barriers, so isolated waves keep build order. Placement
    leaves spare MLP rows when ``placement_cap`` is below the allocate cap;
    a full layer cannot hand a residual slot to the next value.
    """
    if do_reschedule is None:
        do_reschedule = wave <= 0
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    builder.graph.target.value_heads = 4
    words = _features(builder, variables, widths)
    chunks = [predicates] if wave <= 0 else [predicates[index:index + wave] for index in range(0, len(predicates), wave)]
    compiled_count = 0
    for chunk in chunks:
        circuit = PredicateCircuit(builder, words, domains)
        compiled = circuit.compile_all(chunk)
        if samples:
            circuit.agrees(chunk, compiled, samples)
        compiled_count += len(compiled)
        if wave > 0:
            builder.barrier = 2 * builder.graph.n_layers()
    graph = builder.graph
    if do_reschedule and graph.nodes:
        graph.reschedule(unit_cap=placement_cap)
    units = _ffn_units(graph)
    root_dims = []
    # Roots are not kept: a local consumer reads a predicate at its birth level.
    # Keeping every root is the rejected materialization of 2212 outputs.
    peak = live_peak(graph, keep=set())
    allocation = allocate(graph, None, set(), GATE_CAP) if graph.nodes else None
    slots = 0 if allocation is None else allocation.n_slots
    shape, shapes = _shape(graph.n_layers(), max(peak, slots), kept_outputs=8)
    return dict(
        schedule='shared-cse' if wave <= 0 else f'isolated-wave-{wave}',
        placement_cap=placement_cap,
        rescheduled=bool(do_reschedule and graph.nodes),
        predicates=compiled_count,
        waves=len(chunks),
        ffn_units=units,
        control_widths={str(width): count for width, count in sorted(Counter(widths.values()).items())},
        ffn_nodes=sum(isinstance(node, FFN) for node in graph.nodes),
        graph_layers=graph.n_layers(),
        peak_live_dims=peak,
        allocated_slots=slots,
        selected_shape=shape,
        candidate_shapes=shapes,
        channel_gate=shape['channel_gate'],
        dense_gate=shape['dense_gate'],
        boolean_samples=len(samples),
        outputs_kept=0,
        root_dims_materialized=len(root_dims),
    )


def control_samples(variables, domains, count, seed):
    rng = random.Random(seed)
    zeros = {variable: 0 for variable in variables}
    highs = {variable: domains[variable][1] for variable in variables}
    samples = [zeros, highs]
    for _ in range(count):
        samples.append({
            variable: rng.randrange(domains[variable][0], domains[variable][1] + 1)
            for variable in variables
        })
    return samples


def _node_units(node, nodes):
    op = node.op
    if op in ('input', 'const', 'slice', 'extend', 'splice', 'not'):
        return 0
    if op in ('all', 'any'):
        return 1
    if op == 'choose':
        return node.width
    if op in ('eq', 'ult'):
        left, right = nodes[node.args[0]], nodes[node.args[1]]
        if left.op == 'const' or right.op == 'const':
            if op == 'eq':
                return 1
            bound = left.data if left.op == 'const' else right.data
            width = right.width if left.op == 'const' else left.width
            if bound <= 0 or bound >= 1 << width:
                return 0
            return bin(bound).count('1') or 1
        return node.width + 1
    if op in ('add', 'sub'):
        return 24
    raise ValueError(f'no unit model for typed operator {op}')


def equality_pairs(predicate):
    """One conjunction of control equalities, or None when the predicate is wider."""
    if isinstance(predicate, int):
        return None
    if predicate[0] == 'range':
        if predicate[2] != predicate[3]:
            return None
        return ((predicate[1], predicate[2]),)
    if predicate[0] != 'and':
        return None
    pairs = []
    for child in predicate[1]:
        if not (isinstance(child, tuple) and child[0] == 'range' and child[2] == child[3]):
            return None
        pairs.append((child[1], child[2]))
    return tuple(pairs)


def continuation_field_map(predicates, names, task_name='task', mode_name='mode'):
    """Task value -> the one continuation word that task's equality keys read.

    Mode is an address bit, not a payload. A task whose keys mention two
    continuation words is a conflict and is not assigned.
    """
    task_index = next(index for index, name in names.items() if name == task_name)
    mode_index = next((index for index, name in names.items() if name == mode_name), None)
    by_task = {}
    skipped = Counter()
    for predicate in predicates:
        pairs = equality_pairs(predicate)
        if pairs is None:
            skipped['not-equality'] += 1
            continue
        mapping = dict(pairs)
        if task_index not in mapping:
            skipped['no-task'] += 1
            continue
        payload = [
            variable for variable in mapping
            if variable not in (task_index, mode_index)
        ]
        bucket = by_task.setdefault(mapping[task_index], set())
        bucket.update(payload)
    unique = {task: next(iter(fields)) for task, fields in by_task.items() if len(fields) == 1}
    conflicts = {str(task): sorted(names[field] for field in fields) for task, fields in by_task.items() if len(fields) != 1}
    select = {
        task: tuple(sorted(fields, key=lambda index: names[index]))
        for task, fields in by_task.items() if fields
    }
    return dict(
        task_index=task_index,
        mode_index=mode_index,
        tasks=len(by_task),
        unique_tasks=len(unique),
        conflict_tasks=len(conflicts),
        payload_tasks=len(select),
        conflicts=conflicts,
        skipped=dict(skipped),
        mapping={str(task): names[field] for task, field in sorted(unique.items())},
        field_names=sorted({names[field] for field in unique.values()}),
        _mapping=unique,
        _select=select,
    )


def _payload(spec):
    return (spec,) if isinstance(spec, int) else tuple(spec)


def build_continuation_select(names, widths, mapping, task_index, samples, wave=8, placement_cap=80):
    """Gather the continuation words named by an equality-key task.

    Each task drives one or two shared buses. Task matches are exclusive, so
    a wave's bit update is a free sum and one OR into the running bus. This
    chooses which continuation registers the step reads. It is not the
    2212-predicate graph and it does not perform the operator body.
    """
    if not mapping:
        raise ValueError('continuation select has no task payload')
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    payloads = {task: _payload(spec) for task, spec in mapping.items()}
    fields = sorted({field for spec in payloads.values() for field in spec})
    buses = max(len(spec) for spec in payloads.values())
    word_width = widths[fields[0]]
    if any(widths[field] != word_width for field in fields):
        raise ValueError('continuation words have different widths')
    words = _features(builder, [task_index, *fields], widths)
    circuit = PredicateCircuit(builder, words, {task_index: (0, (1 << widths[task_index]) - 1)})
    items = sorted(payloads.items())
    acc_expr = [[Expr() for _ in range(word_width)] for _ in range(buses)]
    acc_id = [[circuit.net.ZERO for _ in range(word_width)] for _ in range(buses)]
    for start in range(0, len(items), wave):
        chunk = items[start:start + wave]
        wave_expr = [[Expr() for _ in range(word_width)] for _ in range(buses)]
        wave_id = [[circuit.net.ZERO for _ in range(word_width)] for _ in range(buses)]
        for task_value, spec in chunk:
            match_expr, match_id = circuit._equal(task_index, task_value)
            for bus, field in enumerate(spec):
                for bit, (bit_expr, bit_id) in enumerate(zip(words[field], circuit.bit_ids[field])):
                    term_expr, term_id = circuit._and([(match_expr, match_id), (bit_expr, bit_id)])
                    wave_expr[bus][bit], wave_id[bus][bit] = circuit._or_sum([
                        (wave_expr[bus][bit], wave_id[bus][bit]), (term_expr, term_id),
                    ])
        for bus in range(buses):
            for bit in range(word_width):
                acc_expr[bus][bit], acc_id[bus][bit] = circuit._or([
                    (acc_expr[bus][bit], acc_id[bus][bit]), (wave_expr[bus][bit], wave_id[bus][bit]),
                ])
        builder.barrier = 2 * builder.graph.n_layers()
    if samples:
        _check_continuation(circuit, task_index, payloads, acc_id, samples)
    graph = builder.graph
    units = _ffn_units(graph)
    peak = live_peak(graph, keep=set())
    allocation = allocate(graph, None, set(), GATE_CAP) if graph.nodes else None
    slots = 0 if allocation is None else allocation.n_slots
    shape, shapes = _shape(graph.n_layers(), max(peak, slots), kept_outputs=buses * word_width)
    return dict(
        schedule=f'continuation-select-wave-{wave}',
        tasks=len(payloads),
        buses=buses,
        fields=len(fields),
        field_names=sorted(names[field] for field in fields),
        ffn_units=units,
        graph_layers=graph.n_layers(),
        peak_live_dims=peak,
        allocated_slots=slots,
        selected_shape=shape,
        candidate_shapes=shapes,
        channel_gate=shape['channel_gate'],
        dense_gate=shape['dense_gate'],
        boolean_samples=len(samples),
        full_checker=False,
    )


def _check_continuation(circuit, task_index, mapping, output_ids, samples):
    for values in samples:
        env = {}
        for variable, ids in circuit.bit_ids.items():
            for bit, _ident in enumerate(ids):
                env[(variable, bit)] = (values[variable] >> bit) & 1
        cache = {}
        task = values[task_index]
        spec = mapping[task] if task in mapping else ()
        for bus, ids in enumerate(output_ids):
            expected = values[spec[bus]] if bus < len(spec) else 0
            for bit, ident in enumerate(ids):
                got = circuit.net.value(ident, env, cache)
                if got != ((expected >> bit) & 1):
                    raise AssertionError('continuation select disagrees with the task-to-field map')


def partition_equality_keys(predicates):
    """Group pure equality handlers into exclusive field-set classes.

    Handlers that mention the same control fields and the same immediates are
    one key. Distinct keys in one field set cannot be true together. A repeated
    key stays one selector record and lists every handler, so the commit can
    OR-merge them. Predicates that are not conjunctions of equalities stay in
    ``residual`` and are not dropped.
    """
    grouped = defaultdict(list)
    order = []
    residual = []
    for index, predicate in enumerate(predicates):
        pairs = equality_pairs(predicate)
        if pairs is None:
            residual.append(index)
            continue
        mapping = dict(pairs)
        signature = tuple(sorted(mapping))
        if signature not in grouped:
            order.append(signature)
        grouped[signature].append((index, mapping))
    classes = []
    collisions = 0
    equality_handlers = 0
    for signature in order:
        by_key = defaultdict(list)
        for index, mapping in grouped[signature]:
            key = tuple(mapping[field] for field in signature)
            by_key[key].append(index)
            equality_handlers += 1
        members = []
        for key, indexes in by_key.items():
            if len(indexes) > 1:
                collisions += len(indexes) - 1
            members.append(dict(mapping=dict(zip(signature, key)), handlers=tuple(indexes)))
        classes.append(dict(fields=signature, members=members))
    return dict(
        classes=classes,
        residual=residual,
        collisions=collisions,
        equality_handlers=equality_handlers,
        exclusive_keys=sum(len(item['members']) for item in classes),
        field_set_classes=len(classes),
    )


def _expr_dims(expr):
    return {dim for dim in expr.terms if dim != ONE}


def _free_or(circuit, pairs):
    """Linear sum of mutually exclusive bits, with an OR twin for the checker."""
    if not pairs:
        return Expr(), circuit.net.ZERO
    if len(pairs) == 1:
        return pairs[0]
    expr = sum((item[0] for item in pairs), Expr())
    ident = circuit.net.node('or', tuple(item[1] for item in pairs))
    return expr, ident


def _republish(circuit, expr, ident):
    """One gate, so a wave's match wires die after the index bit is published."""
    if ident == circuit.net.ZERO:
        return expr, ident
    return circuit.builder.gate('or', [expr], 'key-publish'), circuit.net.node('or', (ident,))


def _merge_exclusive(circuit, previous, pairs):
    fresh = _free_or(circuit, pairs)
    if previous[1] == circuit.net.ZERO:
        return _republish(circuit, fresh[0], fresh[1])
    return circuit._or([previous, fresh])


def _bit_literal(circuit, words, nots, variable, bit, want_one):
    expr = words[variable][bit]
    ident = circuit.bit_ids[variable][bit]
    if want_one:
        return expr, ident
    found = nots.get(ident)
    if found is None:
        found = circuit._not(expr, ident)
        nots[ident] = found
    return found


def _predicate_fields(predicate, found):
    if isinstance(predicate, int):
        return
    if predicate[0] == 'range':
        found.add(predicate[1])
    elif predicate[0] in ('and', 'or'):
        for child in predicate[1]:
            _predicate_fields(child, found)


def build_equality_key_select(names, widths, plan, samples, wave=64, placement_cap=160, residual_predicates=(), tail=None):
    """Fold each exclusive equality class into a hit bit and a handler index.

    One fused equality gate matches a key. Matches in a class are exclusive, so
    a wave's index bits are a free sum and one OR republishes them for the next
    wave. Residual predicates, when passed, are lowered on the same graph after
    the equality waves. The index chooses a handler record; it does not
    evaluate the handler body.
    """
    classes = plan['classes']
    if not classes:
        raise ValueError('equality-key select has no class')
    equality_fields = {field for item in classes for field in item['fields']}
    residual_fields = set()
    for predicate in residual_predicates:
        _predicate_fields(predicate, residual_fields)
    variables = sorted(equality_fields | residual_fields)
    missing = [field for field in variables if field not in widths]
    if missing:
        raise ValueError('equality-key select is missing control widths')
    # Fields that only residual predicates read are born after the equality
    # waves. Equality fields stay at level 0 because those waves read them.
    residual_only = sorted(residual_fields - equality_fields)
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    words = _features(builder, sorted(equality_fields), widths)
    circuit = PredicateCircuit(
        builder, words, {field: (0, (1 << widths[field]) - 1) for field in equality_fields},
    )
    nots = {}
    states = []
    for item in classes:
        count = len(item['members'])
        bits = (count - 1).bit_length() if count else 0
        states.append(dict(
            hit=(Expr(), circuit.net.ZERO),
            bits=[(Expr(), circuit.net.ZERO) for _ in range(bits)],
        ))
    records = [
        (class_index, local_id, member['mapping'])
        for class_index, item in enumerate(classes)
        for local_id, member in enumerate(item['members'])
    ]
    for start in range(0, len(records), wave):
        grouped = defaultdict(list)
        for class_index, local_id, mapping in records[start:start + wave]:
            parts = [
                _bit_literal(circuit, words, nots, variable, bit, bool((value >> bit) & 1))
                for variable, value in mapping.items()
                for bit in range(widths[variable])
            ]
            grouped[class_index].append((local_id, circuit._and(parts)))
        for class_index, group in grouped.items():
            state = states[class_index]
            state['hit'] = _merge_exclusive(circuit, state['hit'], [match for _, match in group])
            for bit in range(len(state['bits'])):
                selected = [match for local_id, match in group if (local_id >> bit) & 1]
                if not selected:
                    continue
                state['bits'][bit] = _merge_exclusive(circuit, state['bits'][bit], selected)
        builder.barrier = 2 * builder.graph.n_layers()
    if samples:
        _check_equality_select(circuit, classes, states, samples)
    residual_compiled = []
    if residual_predicates:
        if residual_only:
            late = _features(builder, residual_only, widths, level=builder.barrier)
            words.update(late)
            circuit.words.update(late)
            for field, bits in late.items():
                circuit.bit_ids[field] = [
                    circuit.net.node('input', (field, bit)) for bit in range(len(bits))
                ]
                circuit.domains[field] = (0, (1 << widths[field]) - 1)
        residual_compiled = circuit.compile_all(residual_predicates)
        if samples:
            circuit.agrees(residual_predicates, residual_compiled, samples)
        builder.barrier = 2 * builder.graph.n_layers()
    tail_kept = set()
    if tail is not None:
        builder.barrier = 2 * builder.graph.n_layers()
        tail_kept = tail(builder)
        if not isinstance(tail_kept, set):
            raise ValueError('equality-key tail must return the dims it keeps')
    graph = builder.graph
    keep = set(tail_kept)
    for state in states:
        keep |= _expr_dims(state['hit'][0])
        for expr, _ident in state['bits']:
            keep |= _expr_dims(expr)
    for expr, _ident in residual_compiled:
        keep |= _expr_dims(expr)
    units = _ffn_units(graph)
    peak = live_peak(graph, keep=keep)
    allocation = allocate(graph, None, keep, GATE_CAP) if graph.nodes else None
    slots = 0 if allocation is None else allocation.n_slots
    index_bits = sum(len(state['bits']) for state in states)
    shape, shapes = _shape(graph.n_layers(), max(peak, slots), kept_outputs=len(keep))
    return dict(
        schedule=f'equality-key-select-wave-{wave}',
        classes=len(classes),
        exclusive_keys=plan['exclusive_keys'],
        equality_handlers=plan['equality_handlers'],
        collisions=plan['collisions'],
        residual_predicates=len(plan['residual']),
        residual_only_fields=len(residual_only),
        residual_lowered=len(residual_compiled),
        index_bits=index_bits,
        hit_bits=len(classes),
        output_bits=index_bits + len(classes),
        field_names=sorted({names[field] for field in variables}),
        class_sizes=[len(item['members']) for item in classes],
        class_fields=[[names[field] for field in item['fields']] for item in classes],
        ffn_units=units,
        graph_layers=graph.n_layers(),
        peak_live_dims=peak,
        allocated_slots=slots,
        selected_shape=shape,
        candidate_shapes=shapes,
        channel_gate=shape['channel_gate'],
        dense_gate=shape['dense_gate'],
        boolean_samples=len(samples),
        outputs_kept=len(keep),
        full_checker=False,
        operator_body_included=False,
        tail_attached=tail is not None,
        memory_layers_included=0,
    )


def _check_equality_select(circuit, classes, states, samples):
    for values in samples:
        env = {}
        for variable, ids in circuit.bit_ids.items():
            if variable not in values:
                raise ValueError('equality-key sample is missing a control field')
            for bit, _ident in enumerate(ids):
                env[(variable, bit)] = (values[variable] >> bit) & 1
        cache = {}
        for class_index, item in enumerate(classes):
            expected = None
            for local_id, member in enumerate(item['members']):
                mapping = member['mapping']
                if all(values[variable] == value for variable, value in mapping.items()):
                    if expected is not None:
                        raise AssertionError('exclusive equality class matched two keys')
                    expected = local_id
            hit = circuit.net.value(states[class_index]['hit'][1], env, cache)
            index = 0
            for bit, (_expr, ident) in enumerate(states[class_index]['bits']):
                index |= circuit.net.value(ident, env, cache) << bit
            if expected is None:
                if hit or index:
                    raise AssertionError('equality-key select hit a class with no matching key')
            elif hit != 1 or index != expected:
                raise AssertionError('equality-key select disagrees with the exclusive class table')


def _spans(values):
    """Inclusive runs of the exact values. Holes stay holes."""
    ordered = sorted(set(values))
    if not ordered:
        return ()
    spans = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        spans.append((start, previous))
        start = previous = value
    spans.append((start, previous))
    return tuple(spans)


def _less_gate_units(bound, width):
    if bound <= 0 or bound >= 1 << width:
        return 0
    return bin(bound).count('1')


def _range_gate_units(low, high, width):
    """FFN units in ``PredicateCircuit._range`` before a fixed-field conjunction."""
    if low == high:
        return 1
    if low <= 0:
        return _less_gate_units(high + 1, width)
    if high + 1 >= 1 << width:
        return _less_gate_units(low, width)
    return _less_gate_units(low, width) + _less_gate_units(high + 1, width) + 1


def continuation_range_plan(classes, widths):
    """Factor each exclusive class along the axis whose ranges beat per-key gates.

    The handler identity is the live control key. No local index is assigned.
    A class is factored only when the range form uses strictly fewer match
    gates than one fused equality per key. Every handler index is kept.
    """
    planned = []
    predicted = 0
    factored_groups = 0
    for item in classes:
        fields = item['fields']
        expected_handlers = [handler for member in item['members'] for handler in member['handlers']]
        best = None
        for axis in fields:
            if axis not in widths:
                raise ValueError('continuation range plan is missing a control width')
            grouped = defaultdict(list)
            order = []
            for member in item['members']:
                key = tuple((field, member['mapping'][field]) for field in fields if field != axis)
                if key not in grouped:
                    order.append(key)
                grouped[key].append(member)
            groups = []
            cost = 0
            for key in order:
                members = tuple(grouped[key])
                values = [member['mapping'][axis] for member in members]
                if len(set(values)) != len(values):
                    raise ValueError('continuation range group repeated an axis value')
                spans = _spans(values)
                covered = sum(high - low + 1 for low, high in spans)
                if covered != len(values):
                    raise ValueError('continuation range spans do not cover the class values')
                range_cost = sum(_range_gate_units(low, high, widths[axis]) for low, high in spans)
                piece = range_cost + (2 if key else 0)
                if piece < len(members):
                    cost += piece
                    groups.append(dict(
                        fixed=key, axis=axis, spans=spans, members=members, lowering='range',
                    ))
                else:
                    cost += len(members)
                    groups.append(dict(
                        fixed=key, axis=axis, spans=None, members=members, lowering='fused',
                    ))
            if best is None or cost < best[0]:
                best = (cost, axis, groups)
        cost, axis, groups = best
        if all(group['lowering'] == 'fused' for group in groups):
            groups = [dict(
                fixed=(), axis=None, spans=None, members=tuple(item['members']), lowering='fused',
            )]
            axis = None
            cost = len(item['members'])
        got = [handler for group in groups for member in group['members'] for handler in member['handlers']]
        if sorted(got) != sorted(expected_handlers):
            raise ValueError('continuation range plan dropped a handler')
        factored_groups += sum(group['lowering'] == 'range' for group in groups)
        predicted += cost
        planned.append(dict(
            fields=fields,
            axis=axis,
            predicted_gates=cost,
            groups=groups,
            members=len(item['members']),
        ))
    return dict(
        classes=planned,
        predicted_match_gates=predicted,
        exclusive_keys=sum(item['members'] for item in planned),
        factored_groups=factored_groups,
        factored_classes=sum(item['axis'] is not None for item in planned),
    )


def _fused_key_match(circuit, words, nots, widths, mapping):
    parts = [
        _bit_literal(circuit, words, nots, variable, bit, bool((value >> bit) & 1))
        for variable, value in mapping.items()
        for bit in range(widths[variable])
    ]
    return circuit._and(parts)


def build_continuation_range_select(
    names, widths, plan, samples, wave=96, placement_cap=96, residual_predicates=(), tail=None,
):
    """Hit bit per exclusive class. The live key, not a decoded index, is the handler.

    Dense continuation spans share one range test. A class that does not shrink
    keeps one fused equality per key. Residual predicates, when passed, are
    lowered on the same graph. This does not evaluate the operator body.
    """
    classes = plan['classes']
    if not classes:
        raise ValueError('continuation range select has no class')
    if wave <= 0:
        raise ValueError('continuation range select wave must be positive')
    ranged = continuation_range_plan(classes, widths)
    equality_fields = {field for item in classes for field in item['fields']}
    residual_fields = set()
    for predicate in residual_predicates:
        _predicate_fields(predicate, residual_fields)
    variables = sorted(equality_fields | residual_fields)
    missing = [field for field in variables if field not in widths]
    if missing:
        raise ValueError('continuation range select is missing control widths')
    residual_only = sorted(residual_fields - equality_fields)
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    builder.graph.target.value_heads = 4
    words = _features(builder, sorted(equality_fields), widths)
    circuit = PredicateCircuit(
        builder, words, {field: (0, (1 << widths[field]) - 1) for field in equality_fields},
    )
    nots = {}
    states = [dict(hit=(Expr(), circuit.net.ZERO)) for _ in classes]
    meter = {'units': 0, 'last': 0, 'open': False, 'waves': 0, 'wave_units': 0}

    def fixed_parts(fixed):
        return [
            _bit_literal(circuit, words, nots, variable, bit, bool((value >> bit) & 1))
            for variable, value in fixed
            for bit in range(widths[variable])
        ]

    def less_cases(variable, bound):
        """Disjoint bit-cases of ``value < bound``. None means the comparison is constant."""
        width = len(words[variable])
        if bound <= 0:
            return None, False
        if bound >= 1 << width:
            return None, True
        cases = []
        for index in range(width):
            if (bound >> index) & 1 == 0:
                continue
            parts = [_bit_literal(circuit, words, nots, variable, index, False)]
            for higher in range(index + 1, width):
                parts.append(_bit_literal(
                    circuit, words, nots, variable, higher, bool((bound >> higher) & 1),
                ))
            cases.append(parts)
        return cases, None

    def below(variable, bound, prefix):
        """``prefix AND value < bound`` with the prefix folded into every case."""
        cases, constant = less_cases(variable, bound)
        if constant is False:
            return Expr(), circuit.net.ZERO
        if constant is True:
            return circuit._and(prefix) if prefix else (circuit.one, circuit.net.ONE)
        return _free_or(circuit, [circuit._and(prefix + case) for case in cases])

    def emit_span(axis, fixed, low, high):
        prefix = fixed_parts(fixed)
        width = widths[axis]
        if low == high:
            parts = prefix + [
                _bit_literal(circuit, words, nots, axis, bit, bool((low >> bit) & 1))
                for bit in range(width)
            ]
            return circuit._and(parts)
        if low <= 0:
            return below(axis, high + 1, prefix)
        if high + 1 >= 1 << width:
            not_below = circuit._not(*below(axis, low, []))
            if not prefix:
                return not_below
            return circuit._and([circuit._and(prefix), not_below])
        not_below = circuit._not(*below(axis, low, []))
        return circuit._and([not_below, below(axis, high + 1, prefix)])

    def span_job(axis, fixed, low, high):
        width = widths[axis]
        if low == high:
            return 1, 1
        if low <= 0:
            units = _less_gate_units(high + 1, width)
            return 1, units if units else (1 if fixed else 0)
        units = _range_gate_units(low, high, width)
        return 2, units

    jobs = {1: [], 2: []}
    for class_index, item in enumerate(ranged['classes']):
        for group in item['groups']:
            if group['lowering'] == 'fused':
                for member in group['members']:
                    jobs[1].append((1, class_index, 'fused', member['mapping']))
                continue
            axis = group['axis']
            for low, high in group['spans']:
                depth, cost = span_job(axis, group['fixed'], low, high)
                jobs[depth].append((cost, class_index, 'span', axis, group['fixed'], low, high))

    def pack(items):
        waves = []
        current = []
        cost = 0
        for item in items:
            item_cost = item[0]
            if current and cost + item_cost > wave:
                waves.append(current)
                current = []
                cost = 0
            current.append(item)
            cost += item_cost
        if current:
            waves.append(current)
        return waves

    def close_wave():
        if not meter['open']:
            return
        meter['waves'] += 1
        meter['wave_units'] += meter['units']
        builder.barrier = 2 * builder.graph.n_layers()
        meter['units'] = 0
        meter['open'] = False

    for depth in (1, 2):
        for wave_jobs in pack(jobs[depth]):
            produced = defaultdict(list)
            for item in wave_jobs:
                if item[2] == 'fused':
                    _, class_index, _, mapping = item
                    produced[class_index].append(
                        _fused_key_match(circuit, words, nots, widths, mapping),
                    )
                else:
                    _, class_index, _, axis, fixed, low, high = item
                    produced[class_index].append(emit_span(axis, fixed, low, high))
            for class_index, pairs in produced.items():
                states[class_index]['hit'] = _merge_exclusive(
                    circuit, states[class_index]['hit'], pairs,
                )
            now = _ffn_units(builder.graph)
            delta = now - meter['last']
            meter['last'] = now
            if delta:
                meter['units'] += delta
                meter['open'] = True
            close_wave()
    equality_layers = builder.graph.n_layers()
    if samples:
        _check_range_select(circuit, classes, states, samples)
    residual_compiled = []
    if residual_predicates:
        if residual_only:
            late = _features(builder, residual_only, widths, level=builder.barrier)
            words.update(late)
            circuit.words.update(late)
            for field, bits in late.items():
                circuit.bit_ids[field] = [
                    circuit.net.node('input', (field, bit)) for bit in range(len(bits))
                ]
                circuit.domains[field] = (0, (1 << widths[field]) - 1)
        residual_compiled = circuit.compile_all(residual_predicates)
        if samples:
            circuit.agrees(residual_predicates, residual_compiled, samples)
        builder.barrier = 2 * builder.graph.n_layers()
    residual_layers = builder.graph.n_layers()
    tail_kept = set()
    if tail is not None:
        builder.barrier = 2 * builder.graph.n_layers()
        tail_kept = tail(builder)
        if not isinstance(tail_kept, set):
            raise ValueError('continuation range tail must return the dims it keeps')
    graph = builder.graph
    keep = set(tail_kept)
    for state in states:
        keep |= _expr_dims(state['hit'][0])
    for expr, _ident in residual_compiled:
        keep |= _expr_dims(expr)
    units = _ffn_units(graph)
    peak = live_peak(graph, keep=keep)
    allocation = allocate(graph, None, keep, GATE_CAP) if graph.nodes else None
    slots = 0 if allocation is None else allocation.n_slots
    shape, shapes = _shape(graph.n_layers(), max(peak, slots), kept_outputs=len(keep))
    head_layers = sorted({node.level // 2 for node in graph.nodes if isinstance(node, Head)})
    if head_layers:
        # _shape prices every layer as full attention. A page head is linear attention.
        for item in shapes:
            priced = dense_parameters(
                item['hidden'], MODEL_INTERMEDIATE, item['layers'], gdn_layers=len(head_layers),
            )
            item['logical_dense_parameters'] = priced
            item['dense_gate'] = priced <= DENSE_LIMIT
            item['memory_layers_included'] = len(head_layers)
            item['gdn_layers'] = len(head_layers)
        fitting = [item for item in shapes if item['channel_gate'] and item['dense_gate']]
        shape = fitting[0] if fitting else shapes[-1]
    return dict(
        schedule=f'continuation-range-wave-{wave}',
        classes=len(classes),
        exclusive_keys=plan['exclusive_keys'],
        equality_handlers=plan['equality_handlers'],
        collisions=plan['collisions'],
        predicted_match_gates=ranged['predicted_match_gates'],
        factored_classes=ranged['factored_classes'],
        factored_groups=ranged['factored_groups'],
        handler_identity='live control key',
        index_bits=0,
        hit_bits=len(classes),
        residual_predicates=len(plan['residual']),
        residual_only_fields=len(residual_only),
        residual_lowered=len(residual_compiled),
        field_names=sorted({names[field] for field in variables}),
        class_sizes=[len(item['members']) for item in classes],
        class_axes=[
            None if item['axis'] is None else names[item['axis']]
            for item in ranged['classes']
        ],
        equality_graph_layers=equality_layers,
        residual_graph_layers=residual_layers,
        dispatch_waves=meter['waves'],
        dispatch_wave_units=meter['wave_units'],
        ffn_units=units,
        graph_layers=graph.n_layers(),
        peak_live_dims=peak,
        allocated_slots=slots,
        selected_shape=shape,
        candidate_shapes=shapes,
        channel_gate=shape['channel_gate'],
        dense_gate=shape['dense_gate'],
        boolean_samples=len(samples),
        outputs_kept=len(keep),
        full_checker=False,
        operator_body_included=False,
        tail_attached=tail is not None,
        head_layers=head_layers,
        memory_layers_included=len(head_layers),
        stock_emitted=False,
        joint_delivery_gate=False,
        mathlib_theorems_checked=0,
    )


def _check_range_select(circuit, classes, states, samples):
    for values in samples:
        env = {}
        for variable, ids in circuit.bit_ids.items():
            if variable not in values:
                raise ValueError('continuation range sample is missing a control field')
            for bit, _ident in enumerate(ids):
                env[(variable, bit)] = (values[variable] >> bit) & 1
        cache = {}
        for class_index, item in enumerate(classes):
            expected = 0
            for member in item['members']:
                if all(values[variable] == value for variable, value in member['mapping'].items()):
                    expected = 1
                    break
            hit = circuit.net.value(states[class_index]['hit'][1], env, cache)
            if hit != expected:
                raise AssertionError('continuation range select disagrees with the exclusive class table')


def build_source_lane(source_count, width, samples, wave=8, placement_cap=160):
    """Select one gathered source word with an exclusive one-hot.

    This is one update slot of the shared operator body. The one-hot is the
    matched handler's source choice, not a word opcode. Waves republish the
    word so source compares can reuse channels.
    """
    if source_count <= 0 or width <= 0:
        raise ValueError('source lane needs a source and a width')
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    selects = [builder.feature(f'select/{index}') for index in range(source_count)]
    sources = [
        [builder.feature(f'source/{index}/{bit}') for bit in range(width)]
        for index in range(source_count)
    ]
    circuit = PredicateCircuit(builder, {}, {})
    select_ids = [circuit.net.node('input', ('select', index)) for index in range(source_count)]
    source_ids = [
        [circuit.net.node('input', ('source', index, bit)) for bit in range(width)]
        for index in range(source_count)
    ]
    output = [(Expr(), circuit.net.ZERO) for _ in range(width)]
    for start in range(0, source_count, wave):
        for bit in range(width):
            terms = []
            for index in range(start, min(source_count, start + wave)):
                terms.append(circuit._and([
                    (selects[index], select_ids[index]),
                    (sources[index][bit], source_ids[index][bit]),
                ]))
            output[bit] = circuit._or([output[bit], _free_or(circuit, terms)])
        builder.barrier = 2 * builder.graph.n_layers()
    if samples:
        _check_source_lane(circuit, output, samples, source_count, width)
    graph = builder.graph
    keep = set()
    for expr, _ident in output:
        keep |= _expr_dims(expr)
    units = _ffn_units(graph)
    peak = live_peak(graph, keep=keep)
    allocation = allocate(graph, None, keep, GATE_CAP) if graph.nodes else None
    slots = 0 if allocation is None else allocation.n_slots
    shape, shapes = _shape(graph.n_layers(), max(peak, slots), kept_outputs=len(keep))
    return dict(
        schedule=f'source-lane-wave-{wave}',
        sources=source_count,
        width=width,
        ffn_units=units,
        graph_layers=graph.n_layers(),
        peak_live_dims=peak,
        allocated_slots=slots,
        selected_shape=shape,
        candidate_shapes=shapes,
        channel_gate=shape['channel_gate'],
        dense_gate=shape['dense_gate'],
        boolean_samples=len(samples),
        full_checker=False,
        one_slot_only=True,
    )


def _check_source_lane(circuit, output, samples, source_count, width):
    for sample in samples:
        select = sample['select']
        words = sample['words']
        if len(select) != source_count or sum(select) != 1 or any(bit not in (0, 1) for bit in select):
            raise ValueError('source-lane sample select must be one-hot')
        chosen = select.index(1)
        env = {}
        for index, bit_value in enumerate(select):
            env[('select', index)] = bit_value
        for index, word in enumerate(words):
            for bit in range(width):
                env[('source', index, bit)] = (word >> bit) & 1
        cache = {}
        got = 0
        for bit, (_expr, ident) in enumerate(output):
            got |= circuit.net.value(ident, env, cache) << bit
        if got != (words[chosen] & ((1 << width) - 1)):
            raise AssertionError('source lane disagrees with the one-hot source')


def _update_kind(nodes, index):
    node = nodes[index]
    if node.op == 'const':
        return 'const', None
    if node.op == 'input':
        return 'copy', node.data
    if node.op in ('add', 'sub') and len(node.args) == 2:
        left, right = nodes[node.args[0]], nodes[node.args[1]]
        if left.op == 'input' and right.op == 'const':
            return node.op, left.data
        if right.op == 'input' and left.op == 'const':
            return node.op, right.data
    if node.op == 'choose':
        return 'choose', None
    return 'other', None


def update_descriptor_account(nodes, handlers):
    """Bit width of the per-handler commit record. Not a placed ROM and not dense parameters."""
    field_ids = {}
    source_ids = {}
    kinds = Counter()
    per_handler = []
    data_slots = []
    const_slots = []
    bank_writes = 0
    for handler in handlers:
        slots = data = consts = 0
        for effect in handler['effects']:
            if effect.kind != 'merge_fields':
                bank_writes += 1
                slots += 1
                data += 1
                kinds['bank'] += 1
                continue
            for field, value in effect.values:
                slots += 1
                kind, source = _update_kind(nodes, value)
                kinds[kind] += 1
                field_ids.setdefault(field, len(field_ids))
                if kind == 'const':
                    consts += 1
                else:
                    data += 1
                if source is not None:
                    source_ids.setdefault(source, len(source_ids))
        per_handler.append(slots)
        data_slots.append(data)
        const_slots.append(consts)
    per_handler.sort()
    dest_count = max(len(field_ids), 1)
    source_count = max(len(source_ids), 1)
    op_count = 7
    dest_bits = (dest_count - 1).bit_length() or 1
    source_bits = (source_count - 1).bit_length() or 1
    op_bits = (op_count - 1).bit_length()
    immediate_bits = 16
    bits_per_slot = dest_bits + op_bits + source_bits + immediate_bits
    maximum = per_handler[-1] if per_handler else 0
    data_slots.sort()
    const_slots.sort()
    max_data = data_slots[-1] if data_slots else 0

    def quantile(values, fraction):
        if not values:
            return 0
        return values[min(len(values) - 1, int(fraction * (len(values) - 1)))]

    return dict(
        handlers=len(handlers),
        write_slots_p50=quantile(per_handler, 0.5),
        write_slots_p90=quantile(per_handler, 0.9),
        write_slots_p99=quantile(per_handler, 0.99),
        write_slots_max=maximum,
        const_slots_max=const_slots[-1] if const_slots else 0,
        data_slots_p50=quantile(data_slots, 0.5),
        data_slots_p99=quantile(data_slots, 0.99),
        data_slots_max=max_data,
        distinct_dest_fields=len(field_ids),
        distinct_copy_sources=len(source_ids),
        kind_counts=dict(kinds),
        dest_bits=dest_bits,
        source_bits=source_bits,
        op_bits=op_bits,
        immediate_bits=immediate_bits,
        bits_per_slot=bits_per_slot,
        max_descriptor_bits=maximum * bits_per_slot,
        total_write_slots=sum(per_handler),
        bank_writes=bank_writes,
        placed_graph=False,
        note='Descriptor bits are the handler commit record. They are not dense Transformer parameters.',
    )


def estimate_data_circuits(compiler, handlers, control_names):
    """CSE unit estimate of the data cones. Not a placed Graph."""
    nodes = compiler.g.nodes
    names = {}
    by_operator = {
        name: dict(shared=set(), private=set(), shared_handlers=0, private_handlers=0)
        for name in OPERATORS
    }
    fields = set()
    banks = Counter()
    for handler in handlers:
        roots = []
        for effect in handler['effects']:
            roots.append(effect.guard)
            if effect.address >= 0:
                roots.append(effect.address)
            if effect.kind == 'merge_fields':
                for name, value in effect.values:
                    fields.add(name)
                    roots.append(value)
            else:
                banks[effect.kind] += 1
                roots.extend(effect.values)
        cone = _cone(nodes, roots)
        residual = {index for index in cone if _input_names(nodes, index, names) - control_names}
        bucket = by_operator[handler['operator']]
        key = 'shared' if handler['schedule'] == 'shared' else 'private'
        bucket[key].update(residual)
        bucket[key + '_handlers'] += 1
    reports = {}
    union = set()
    for name, bucket in by_operator.items():
        shared_units = sum(_node_units(nodes[index], nodes) for index in bucket['shared'])
        private_units = sum(_node_units(nodes[index], nodes) for index in bucket['private'])
        union.update(bucket['shared'])
        union.update(bucket['private'])
        reports[name] = dict(
            shared_handlers=bucket['shared_handlers'],
            private_handlers=bucket['private_handlers'],
            shared_residual_nodes=len(bucket['shared']),
            private_residual_nodes=len(bucket['private']),
            shared_units=shared_units,
            private_units=private_units,
        )
    return dict(
        operators=reports,
        data_units_with_cse=sum(_node_units(nodes[index], nodes) for index in union),
        data_residual_nodes=len(union),
        commit_fields=len(fields),
        bank_write_effects=dict(banks),
        unit_model='boolean/compare 1, const-less popcount, choose per bit, add/sub 24-unit nibble; wiring and not are free',
        placed_graph=False,
    )


def joint_report(predicate_report, data_estimate):
    """Dispatch graph plus the still-unplaced data estimate. Not a delivery claim."""
    dispatch_units = predicate_report['ffn_units']
    data_units = data_estimate['data_units_with_cse']
    # Memory is not in either number. Eight grouped value-head layers are the
    # existing arena shape's order of magnitude, counted here so the joint
    # figure cannot ignore gather and commit.
    memory_layers = 8
    value_heads = 4
    shape = predicate_report['selected_shape']
    hidden = shape['hidden']
    # Lower bound: pack dispatch and data units into GATE_CAP, then add memory.
    packed_layers = math.ceil((dispatch_units + data_units) / GATE_CAP) if dispatch_units + data_units else 0
    clear_layers = shape['scratch_clear_layers']
    layers = packed_layers + memory_layers + clear_layers + 1
    dense = dense_parameters(hidden, MODEL_INTERMEDIATE, layers, gdn_layers=memory_layers, value_heads=value_heads)
    inert = layer_dense(hidden, MODEL_INTERMEDIATE, 'full_attention')
    linear = layer_dense(hidden, MODEL_INTERMEDIATE, 'linear_attention', value_heads)
    return dict(
        format='leanputer.semantic-step-circuit.v1',
        full_checker=False,
        stock_emitted=False,
        joint_delivery_gate=False,
        operators=list(OPERATORS),
        execution='one stock forward per kernel transition; control predicates select shared operators; at most five true handlers OR-merge',
        working_dense_limit=DENSE_LIMIT,
        working_call_limit=CALL_LIMIT,
        historical_tui_dense_limit=100_000_000,
        historical_tui_call_limit=5_000,
        historical_limits_are_not_success=True,
        predicate_graph=predicate_report,
        data_estimate=data_estimate,
        dispatch_ffn_units=dispatch_units,
        data_units_estimated=data_units,
        packed_logic_layers_lower_bound=packed_layers,
        illustrative_memory_layers=memory_layers,
        illustrative_total_layers=layers,
        illustrative_dense_parameters=dense,
        illustrative_dense_gate=dense <= DENSE_LIMIT,
        inert_layer_parameters=inert,
        linear_attention_layer_parameters=linear,
        unique_tied_storage_is_not_logical_dense=True,
        call_projection_if_one_forward_per_transition={
            'boot': 22,
            'setup': 5,
            'current-general-source-empty-claim-id': 22 + 5 + 1316,
            'current-source-invalid-target': 22 + 5 + 1355,
        },
        rejected_tied_window=dict(
            unique_parameters=82_235_516,
            layers=1958,
            total_calls=(4690, 4815),
            check_seconds=(1192.783, 1211.029),
            delivery_candidate=False,
        ),
    )
