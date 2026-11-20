"""One physical expression-child walk and one checked index add.

The walk is the shared descent in ``traversal_transition`` together with
``arena.children``: child 0 is field ``c`` for ``PROJ`` and field ``a``
otherwise; child 1 is field ``b``; child 2 is field ``c``. Binder depth
increases on the second child of ``PI`` and ``LAM`` and on the third child of
``LET``. ``checked_add`` matches ``RuleCompiler.checked_add``: the sum is
``width + 1`` bits, and the top bit stops as ``RESOURCE`` / ``INDEX`` rather
than wrapping. The sum is formed one byte at a time. Each centered total stays
in ``[-256, 255]``, where the threshold gate is bf16-exact. The packed digit
is a linear form. It is an up-projection operand, not a silu input: ``K*255``
is the gate-side hazard, and this adder does not put the digit on that side.

``service_gap`` is checker state. When it is set, the step publishes
``Outcome.GAP`` and the reason word already in that state. It does not ask the
host whether a proof is admitted.

This circuit does not gather the heap, apply handler commit records, or place
private algorithms. It does not emit a torch model and it is not a source checker.
"""
from __future__ import annotations

from ..native_machine import NativeBuilder
from ..native_vendor.qwenputer.emit import allocate
from ..native_vendor.qwenputer.expr import Expr
from ..native_vendor.qwenputer.ir import ExactnessError, evaluate
from .arena import Row, Tag, children
from .semantic_operators import DENSE_LIMIT
from .semantic_step_circuit import (
    GATE_CAP,
    MODEL_INTERMEDIATE,
    PredicateCircuit,
    _expr_dims,
    _ffn_units,
    _shape,
    live_peak,
)
from .traversal_machine import Outcome, Reason


# Stock GatedDeltaNet pages. emit.py writes one key row per key-head lane, and
# the pinned head dimension is 128. Four value heads address 512 rows in one
# linear-attention layer, which is the current expression heap.
ROWS_PER_PAGE = 128
VALUE_HEADS_PER_LAYER = 4
ROWS_PER_LAYER = ROWS_PER_PAGE * VALUE_HEADS_PER_LAYER
ORIGINAL_EXPRESSIONS = 512
ORIGINAL_DECLARATIONS = 4
ORIGINAL_STACK = 32
ORIGINAL_CONTEXT = 8
# A 16-bit reference cannot name a row past this bound. Wider arenas are a
# word-width resource, not a truncated table.
WORD_REFERENCE_LIMIT = (1 << 16) - 1

STATUS_WIDTH = 3
REASON_WIDTH = 6


def direct_expression_child(tag, index, a, b, c):
    """Child selected by ``arena.children``. Invalid tags have no children."""
    try:
        row_tag = Tag(tag)
    except ValueError:
        return dict(in_range=0, ref=0, depth_inc=0, child_count=0)
    kids = children(Row(row_tag, a, b, c))
    if index < 0 or index >= len(kids):
        return dict(in_range=0, ref=0, depth_inc=0, child_count=len(kids))
    ref, depth_inc = kids[index]
    return dict(in_range=1, ref=ref, depth_inc=int(depth_inc), child_count=len(kids))


def _word_pairs(circuit, name):
    return list(zip(circuit.words[name], circuit.bit_ids[name]))


def _as_expr(item):
    return item[0] if isinstance(item, tuple) else item


def _pack_bits_expr(bits):
    total = Expr()
    for index, bit in enumerate(bits):
        if bit.terms:
            total = total + bit * (1 << index)
    return total


def _checked_add(builder, left, right):
    """Width-preserving sum and a carry-out, one byte digit at a time.

    ``left`` and ``right`` are low-bit-first linear forms, one per bit. The
    low carry is zero. A digit's centered total ``a + b + carry - base`` lies
    in ``[-256, 255]`` for an 8-bit digit, which is the exact domain of the
    threshold ``relu(-total) - relu(-total - 1)``. The packed digit stays a
    linear form. Callers must not feed it to a silu gate input.
    """
    if len(left) != len(right) or not left or len(left) > 16:
        raise ValueError('checked add needs two equal words of 1 to 16 bits')
    one = builder.graph.one
    digits = []
    carry = Expr()
    for offset in range(0, len(left), 8):
        precision = min(8, len(left) - offset)
        base = 1 << precision
        total = (
            _pack_bits_expr(left[offset:offset + precision])
            + _pack_bits_expr(right[offset:offset + precision])
            + carry
            - base * one
        )
        below = builder.graph.ffn(
            [(1, one, -total), (-1, one, -total - one)],
            name='checked-add/below',
            min_level=builder.barrier,
        )
        carry = one - below
        digits.append(total + base * below)
    return digits, carry


def _features(builder, spec, prefix, level=None):
    words = {}
    for name, width in spec:
        bits = []
        for bit in range(width):
            expr = builder.feature(f'{prefix}/{name}/{bit}')
            if level is not None:
                (dim,) = expr.terms
                builder.graph.dims[dim].level = level
            bits.append(expr)
        words[name] = bits
    return words


def _bind_samples(graph, words, samples):
    for name, bits in words.items():
        for index, expr in enumerate(bits):
            (dim,) = expr.terms

            def fn(token, name=name, index=index, samples=samples):
                return (int(samples[token][name]) >> index) & 1

            graph.token_fns[dim] = fn


def _evaluate_samples(graph, words, samples):
    _bind_samples(graph, words, samples)
    try:
        return evaluate(graph, list(range(len(samples))), check=True)
    except ExactnessError as exc:
        raise AssertionError(f'byte-digit circuit is not bf16-exact: {exc}') from exc


def _expr_value(item, row):
    expr = _as_expr(item)
    total = 0.0
    for dim, coef in expr.terms.items():
        total += float(coef) * float(row[dim])
    rounded = round(total)
    if abs(total - rounded) > 1e-6:
        raise AssertionError(f'output {total} is not an integer')
    return int(rounded)


def _bits_value(items, row):
    if isinstance(items, tuple) or isinstance(items, Expr):
        items = (items,)
    total = 0
    for index, item in enumerate(items):
        bit = _expr_value(item, row)
        if bit not in (0, 1):
            raise AssertionError(f'boolean output is {bit}')
        total |= bit << index
    return total


def _digits_value(digits, width, row):
    total = 0
    shift = 0
    for digit in digits:
        precision = min(8, width - shift)
        got = _expr_value(digit, row)
        if got < 0 or got >= 1 << precision:
            raise AssertionError(f'digit {got} does not fit {precision} bits')
        total += got << shift
        shift += precision
    if shift != width:
        raise AssertionError('digits do not cover the word')
    return total


def _check_add(graph, words, digits, overflow, samples, width):
    matrix = _evaluate_samples(graph, words, samples)
    mask = (1 << width) - 1
    for index, sample in enumerate(samples):
        total = sample['x'] + sample['y']
        got = _digits_value(digits, width, matrix[index])
        carry = _expr_value(overflow, matrix[index])
        if got != (total & mask) or carry != (total >> width):
            raise AssertionError('checked add disagrees with the width+1 sum')


def build_checked_index_add(width, samples, placement_cap=GATE_CAP):
    """One shared ``checked_add``. Samples are ``{'x', 'y'}`` words."""
    if width <= 0 or width > 16:
        raise ValueError('checked index add width must be from 1 to 16')
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    builder.graph.target.value_heads = 4
    words = _features(builder, (('x', width), ('y', width)), 'add')
    digits, overflow = _checked_add(builder, words['x'], words['y'])
    if samples:
        _check_add(builder.graph, words, digits, overflow, samples, width)
    return _place(builder, [overflow, *digits], samples, dict(
        schedule='checked-index-add',
        width=width,
        adder='byte-digit',
        digit_bits=8,
        packed_digit_is_linear_form=True,
        heap_gather_included=False,
        handler_commit_included=False,
        expression_walk_included=False,
    ))


def _lower_walk(builder, width, samples, prefix, input_level=None):
    if width <= 0 or width > 16:
        raise ValueError('expression walk width must be from 1 to 16')
    if max(Outcome) >= 1 << STATUS_WIDTH or max(Reason) >= 1 << REASON_WIDTH:
        raise ValueError('outcome or reason enum does not fit the published word')
    spec = (
        ('tag', 4),
        ('child_index', 2),
        ('a', width),
        ('b', width),
        ('c', width),
        ('depth', width),
        ('require_child', 1),
        ('service_gap', 1),
        ('gap_reason', REASON_WIDTH),
    )
    # ``input_level`` is the section barrier. Leaving it unset births the row
    # at level 0, which overlaps an earlier selector. The tail passes the barrier.
    words = _features(builder, spec, prefix, level=input_level)
    circuit = PredicateCircuit(builder, words, {})
    tag = lambda value: circuit._equal('tag', int(value))
    index = lambda value: circuit._equal('child_index', value)
    let_ = tag(Tag.LET)
    binary = circuit._or([tag(Tag.APP), tag(Tag.PI), tag(Tag.LAM)])
    unary = circuit._or([tag(Tag.PROJ), tag(Tag.MDATA)])
    at0, at1, at2 = index(0), index(1), index(2)
    in_range = circuit._or([
        circuit._and([unary, at0]),
        circuit._and([binary, circuit._or([at0, at1])]),
        circuit._and([let_, circuit._or([at0, at1, at2])]),
    ])
    projection = tag(Tag.PROJ)
    binder_second = circuit._or([tag(Tag.PI), tag(Tag.LAM)])
    depth_inc = circuit._and([in_range, circuit._or([
        circuit._and([at1, binder_second]),
        circuit._and([at2, let_]),
    ])])
    child = []
    for bit in range(width):
        a_bit = _word_pairs(circuit, 'a')[bit]
        b_bit = _word_pairs(circuit, 'b')[bit]
        c_bit = _word_pairs(circuit, 'c')[bit]
        first = circuit._or([
            circuit._and([projection, c_bit]),
            circuit._and([circuit._not(*projection), a_bit]),
        ])
        selected = circuit._or([
            circuit._and([at0, first]),
            circuit._and([at1, b_bit]),
            circuit._and([at2, c_bit]),
        ])
        child.append(circuit._and([in_range, selected]))
    increment = [depth_inc[0]] + [Expr() for _ in range(width - 1)]
    digits, _byte_carry = _checked_add(builder, words['depth'], increment)
    # Adding 0 or 1 carries out exactly when every depth bit is set and the
    # increment is set. That carry matches the byte adder and is ready with
    # depth_inc, so the outcome does not wait for the high digit.
    depth_bits = _word_pairs(circuit, 'depth')
    all_ones = circuit._and(depth_bits)
    overflow_pair = circuit._and([depth_inc, all_ones])
    require = _word_pairs(circuit, 'require_child')[0]
    gap = _word_pairs(circuit, 'service_gap')[0]
    syntax = circuit._and([require, circuit._not(*in_range)])
    not_gap = circuit._not(*gap)
    # Gap, syntax, and the index carry are disjoint. Status and reason are
    # linear sums of those cases, so the priority is one gate, not a mux chain.
    use_syntax = circuit._and([syntax, not_gap])
    use_resource = circuit._and([overflow_pair, circuit._not(*syntax), not_gap])
    status = [
        use_resource,
        _as_expr(use_syntax) + _as_expr(use_resource),
        gap,
    ]
    if len(status) != STATUS_WIDTH:
        raise ValueError('status word width does not match the published cases')
    gap_bits = _word_pairs(circuit, 'gap_reason')
    masked_reason = [circuit._and([gap, bit]) for bit in gap_bits]
    reason = []
    for index in range(REASON_WIDTH):
        expr = _as_expr(masked_reason[index])
        if (int(Reason.SYNTAX) >> index) & 1:
            expr = expr + _as_expr(use_syntax)
        if (int(Reason.INDEX) >> index) & 1:
            expr = expr + _as_expr(use_resource)
        reason.append(expr)
    outputs = dict(
        in_range=in_range,
        depth_inc=depth_inc,
        overflow=overflow_pair,
        child=child,
        next_depth=digits,
        status=status,
        reason=reason,
    )
    if samples:
        _check_walk(builder.graph, words, outputs, samples, width)
    return outputs


def _check_walk(graph, words, outputs, samples, width):
    matrix = _evaluate_samples(graph, words, samples)
    mask = (1 << width) - 1
    for index, sample in enumerate(samples):
        row = matrix[index]
        direct = direct_expression_child(
            sample['tag'], sample['child_index'], sample['a'], sample['b'], sample['c'],
        )
        if _bits_value(outputs['in_range'], row) != direct['in_range']:
            raise AssertionError('expression walk range disagrees with arena.children')
        if _bits_value(outputs['depth_inc'], row) != direct['depth_inc']:
            raise AssertionError('expression walk depth increment disagrees with arena.children')
        if _bits_value(outputs['child'], row) != direct['ref']:
            raise AssertionError('expression walk child disagrees with arena.children')
        added = sample['depth'] + direct['depth_inc'] if direct['in_range'] else sample['depth']
        got_depth = _digits_value(outputs['next_depth'], width, row)
        got_overflow = _expr_value(outputs['overflow'], row)
        if got_depth != (added & mask) or got_overflow != (added >> width):
            raise AssertionError('expression walk checked add disagrees with the width+1 sum')
        syntax = sample['require_child'] == 1 and direct['in_range'] == 0
        resource = got_overflow == 1 and not syntax
        if sample['service_gap']:
            expect_status, expect_reason = int(Outcome.GAP), sample['gap_reason']
        elif syntax:
            expect_status, expect_reason = int(Outcome.INVALID), int(Reason.SYNTAX)
        elif resource:
            expect_status, expect_reason = int(Outcome.RESOURCE), int(Reason.INDEX)
        else:
            expect_status, expect_reason = int(Outcome.RUNNING), int(Reason.NONE)
        if _bits_value(outputs['status'], row) != expect_status:
            raise AssertionError('expression walk status disagrees with the outcome rule')
        if _bits_value(outputs['reason'], row) != expect_reason:
            raise AssertionError('expression walk reason disagrees with the outcome rule')


def _output_dims(item, keep):
    if isinstance(item, Expr):
        keep |= _expr_dims(item)
        return
    if isinstance(item, tuple) and item and isinstance(item[0], Expr):
        keep |= _expr_dims(item[0])
        return
    if isinstance(item, list):
        for part in item:
            _output_dims(part, keep)
        return
    raise TypeError(f'walk output is {type(item).__name__}')


def kept_output_dims(outputs):
    """Residual dims named by walk outputs. Digits may be bare linear forms."""
    keep = set()
    for item in outputs.values():
        _output_dims(item, keep)
    return keep


def _place(builder, outputs, samples, extra):
    graph = builder.graph
    keep = set()
    for item in outputs:
        _output_dims(item, keep)
    units = _ffn_units(graph)
    peak = live_peak(graph, keep=keep)
    allocation = allocate(graph, None, keep, GATE_CAP) if graph.nodes else None
    slots = 0 if allocation is None else allocation.n_slots
    shape, shapes = _shape(graph.n_layers(), max(peak, slots), kept_outputs=len(keep))
    report = dict(
        ffn_units=units,
        graph_layers=graph.n_layers(),
        peak_live_dims=peak,
        allocated_slots=slots,
        selected_shape=shape,
        candidate_shapes=shapes,
        channel_gate=shape['channel_gate'],
        dense_gate=shape['dense_gate'],
        boolean_samples=len(samples) if samples is not None else 0,
        outputs_kept=len(keep),
        full_checker=False,
        joint_delivery_gate=False,
        stock_emitted=False,
        operator_body_included=False,
        memory_layers_included=0,
        private_algorithms_placed=False,
    )
    report.update(extra)
    return report


def build_shared_expression_walk(width, samples, placement_cap=GATE_CAP):
    """Place one walk. ``samples`` carry tag, child index, row fields, and depth."""
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    builder.graph.target.value_heads = 4
    outputs = _lower_walk(builder, width, samples, 'walk')
    flat = [
        outputs['in_range'], outputs['depth_inc'], outputs['overflow'],
        *outputs['child'], *outputs['next_depth'], *outputs['status'], *outputs['reason'],
    ]
    return _place(builder, flat, samples, dict(
        schedule='shared-expression-walk',
        width=width,
        adder='byte-digit',
        digit_bits=8,
        packed_digit_is_linear_form=True,
        expression_walk_included=True,
        checked_add_included=True,
        heap_gather_included=False,
        handler_commit_included=False,
        gap_outcome_included=True,
        resource_outcome_included=True,
    ))


def source_storage_report(expressions, declarations, stack, context, word_bits=16,
                          level_rows=0, vector_refs=0, vector_cells=0):
    """Page count for a source-sized arena. Rows are not dropped to fit a page.

    The original stock domain is 512 expression rows and 4 declaration cells.
    The same address map retains whatever counts the caller measured. One
    linear-attention layer with four value heads has 512 physical rows. A
    reference past the retained table is not a live use of the padding, and a
    key past the declaration slots is not a compiled declaration.
    """
    from .source_capacity import storage_layout
    return storage_layout(
        expressions, declarations, stack, context, word_bits=word_bits,
        level_rows=level_rows, vector_refs=vector_refs, vector_cells=vector_cells,
    )
