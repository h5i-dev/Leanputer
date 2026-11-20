"""One shared control circuit for a Lean kernel transition.

Task, mode, private continuation PCs and the caller frame are model-owned
checker state. Expression tags, names, declaration shapes and proof bodies stay
data. The circuit evaluates the projected control predicates of the six shared
operators. It is not a word-opcode interpreter and not one neural graph per
handler.

A handler predicate selects guarded field updates. The reference merges
simultaneously true updates with bitwise OR, and at most five handlers are true
on one control state. This module lowers the predicates. It does not run at
inference and it does not emit a torch model unless a caller asks.
"""
from __future__ import annotations

import math
import random
from collections import Counter

from ..native_machine import NativeBuilder
from ..native_vendor.qwenputer.expr import ONE, Expr
from ..native_vendor.qwenputer.ir import FFN
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


def _features(builder, variables, widths):
    words = {}
    for variable in variables:
        width = widths[variable]
        words[variable] = [builder.feature(f'control/{variable}/{bit}') for bit in range(width)]
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
