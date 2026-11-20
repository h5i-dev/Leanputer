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

The expression page reads and writes one linear-attention layer. A row is the
tag and the three expression fields, addressed by the reference split. The
small bank is the stack, the context, and the declaration slots of the same
address map. Oracle writes are stack rows of six words, heap rows of four, and
context rows of one; a declaration cell is six words and is not a ``write_``
effect. One token of a page writes one row. Published channels are bytes,
because bf16 holds every integer in 0..255 and a bit per residual slot does
not leave room for a second head. Private algorithms are not in this circuit.
It does not emit a torch model and it is not a source checker.
"""
from __future__ import annotations

import math

from ..native_machine import NativeBuilder
from ..native_vendor.qwenputer.emit import allocate
from ..native_vendor.qwenputer.expr import Expr
from ..native_vendor.qwenputer.ir import A_BIT, A_REF, HD, ExactnessError, Head, K, evaluate
from .arena import Row, Tag, children
from .semantic_operators import DENSE_LIMIT
from .semantic_step_circuit import (
    GATE_CAP,
    MODEL_INTERMEDIATE,
    PredicateCircuit,
    _expr_dims,
    _ffn_units,
    _free_or,
    _shape,
    dense_parameters,
    live_peak,
)
from .source_capacity import IN_RANGE, INVALID_REFERENCE, NULL, AddressDomain
from .traversal_machine import Outcome, Reason


# Stock GatedDeltaNet pages. emit.py writes one key row per key-head lane, and
# the pinned head dimension is 128. Four value heads address 512 rows in one
# linear-attention layer, which is the current expression heap.
ROWS_PER_PAGE = 128
VALUE_HEADS_PER_LAYER = 4
ROWS_PER_LAYER = ROWS_PER_PAGE * VALUE_HEADS_PER_LAYER
TAG_BITS = 4
PAGE_WORD_BITS = 16
# tag, a, b, c. Columns 0 and 1 of a value head are the row ballast.
PAYLOAD_BITS = TAG_BITS + 3 * PAGE_WORD_BITS
DATA_COLUMN = 2
BYTE_BITS = 8
# Oracle ``write_`` rows: stack 6, context 1. The declaration read port is
# 6 words and has no write effect. The physical small-bank row is 6 words.
SMALL_WORDS = 6
CONTEXT_WORDS = 1
BANK_STACK = 0
BANK_CONTEXT = 1
BANK_DECLARATION = 2
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


def _evaluate_bound(graph, words, samples):
    """Evaluate ``words`` with every other token feature forced to zero.

    A later page is checked on a graph that already bound an earlier page.
    Restoring the previous bindings keeps that page's own check intact.
    """
    saved = dict(graph.token_fns)
    for dim in saved:
        graph.token_fns[dim] = lambda token: 0
    try:
        return _evaluate_samples(graph, words, samples)
    finally:
        graph.token_fns.clear()
        graph.token_fns.update(saved)


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


def _lower_walk(builder, width, samples, prefix, input_level=None, address_retained=None):
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
        inputs=words,
    )
    if address_retained is not None:
        if width != 16:
            raise ValueError('expression address is attached only to a 16-bit walk')
        outputs['address'] = _address_from_pairs(circuit, child, address_retained)
    if samples:
        _check_walk(builder.graph, words, outputs, samples, width)
        if address_retained is not None:
            _check_walk_address(circuit, outputs['address'], samples, address_retained)
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


def _check_walk_address(circuit, address, samples, retained):
    """The page split reads the walk's child reference, not a second input."""
    domain = AddressDomain(retained, 0)
    for values in samples:
        env = {}
        for name, ids in circuit.bit_ids.items():
            if name == 'ref':
                continue
            for bit, _ident in enumerate(ids):
                env[(name, bit)] = (int(values[name]) >> bit) & 1
        cache = {}

        def bit_value(pairs):
            total = 0
            for index, pair in enumerate(pairs):
                total |= circuit.net.value(pair[1], env, cache) << index
            return total

        direct = direct_expression_child(
            values['tag'], values['child_index'], values['a'], values['b'], values['c'],
        )
        page = domain.expression_address(direct['ref'] if direct['in_range'] else 0)
        null = circuit.net.value(address['null'][1], env, cache)
        in_range = circuit.net.value(address['in_range'][1], env, cache)
        if (null, in_range) != (
            int(page['outcome'] == NULL), int(page['outcome'] == IN_RANGE),
        ):
            raise AssertionError('walk child address outcome disagrees with the page split')
        if page['outcome'] == IN_RANGE:
            if bit_value(address['row']) != page['row'] or bit_value(address['head']) != page['head']:
                raise AssertionError('walk child page disagrees with the page split')
            if bit_value(address['layer']) != page['layer']:
                raise AssertionError('walk child layer disagrees with the page split')
        elif bit_value(address['row']) or bit_value(address['head']) or bit_value(address['layer']):
            raise AssertionError('walk child published a page slot for a null or invalid reference')


def _output_dims(item, keep):
    if isinstance(item, Expr):
        keep |= _expr_dims(item)
        return
    if isinstance(item, tuple) and item and isinstance(item[0], Expr):
        keep |= _expr_dims(item[0])
        return
    if isinstance(item, (list, dict)):
        parts = item.values() if isinstance(item, dict) else item
        for part in parts:
            _output_dims(part, keep)
        return
    raise TypeError(f'walk output is {type(item).__name__}')


def _inclusive_and_scan(circuit, bits):
    """``scan[i]`` is the AND of ``bits[0..i]``.

    One wide AND per output. A binary ladder is the same function, and on a
    16-bit word it is four dependent FFNs. Each dependent FFN starts on the
    next model layer, so the ladder spends the memory margin on depth.
    """
    if not bits:
        return []
    scan = [bits[0]]
    for index in range(1, len(bits)):
        scan.append(circuit._and(bits[:index + 1]))
    return scan


def _xor_pair(circuit, left, right):
    if right[1] == circuit.net.ONE:
        return circuit._not(*left)
    if right[1] == circuit.net.ZERO:
        return left
    if left[1] == circuit.net.ONE:
        return circuit._not(*right)
    if left[1] == circuit.net.ZERO:
        return right
    return _free_or(circuit, [
        circuit._and([left, circuit._not(*right)]),
        circuit._and([circuit._not(*left), right]),
    ])


def _address_from_pairs(circuit, ref, retained, name='ref'):
    """Page split of a 1-based reference already present as bit pairs.

    ``name`` is the boolean alias. Two references on one circuit need two
    names, because equality and less-than are memoized by variable name.
    """
    width = len(ref)
    if width != 16:
        raise ValueError('expression address width is the 16-bit reference')
    if type(retained) is not int or retained < 0 or retained >= 1 << width:
        raise ValueError('retained expression rows must fit the reference word')
    # Alias the reference on copies. The caller's word dict is the sample
    # schema, and these pairs may be gates rather than input features.
    circuit.words = dict(circuit.words)
    circuit.bit_ids = dict(circuit.bit_ids)
    circuit.words[name] = [pair[0] for pair in ref]
    circuit.bit_ids[name] = [pair[1] for pair in ref]
    null = circuit._equal(name, 0)
    below_limit = circuit._less(name, retained + 1)
    in_range = circuit._and([circuit._not(*null), below_limit])
    zeros = [circuit._not(*bit) for bit in ref]
    present = _inclusive_and_scan(circuit, zeros)
    # slot = ref - 1. Bit i flips iff every lower bit of ref is 0.
    slot = [_xor_pair(circuit, ref[0], (circuit.one, circuit.net.ONE))]
    slot.extend(_xor_pair(circuit, ref[index], present[index - 1]) for index in range(1, width))
    masked = [circuit._and([in_range, bit]) for bit in slot]
    row_bits = ROWS_PER_PAGE.bit_length() - 1
    head_bits = VALUE_HEADS_PER_LAYER.bit_length() - 1
    if 1 << row_bits != ROWS_PER_PAGE or 1 << head_bits != VALUE_HEADS_PER_LAYER:
        raise ValueError('expression page geometry is not a power of two')
    return dict(
        null=null,
        in_range=in_range,
        row=masked[:row_bits],
        head=masked[row_bits:row_bits + head_bits],
        layer=masked[row_bits + head_bits:],
    )


def _lower_expression_address(builder, retained, width, samples, prefix, input_level=None):
    """Split a 1-based expression reference into layer, head, and row.

    Zero is null. A reference above ``retained`` is invalid even when its
    slot still falls inside the physical page. The page geometry is the
    shared GDN page: 128 rows, 4 heads, 512 rows per layer. This is the
    address the expression gather reads. It does not read the page.
    """
    words = _features(builder, (('ref', width),), prefix, level=input_level)
    circuit = PredicateCircuit(builder, words, {})
    outputs = _address_from_pairs(circuit, _word_pairs(circuit, 'ref'), retained)
    if samples is not None:
        _check_expression_address(circuit, outputs, samples, retained)
    return outputs


def _check_expression_address(circuit, outputs, samples, retained):
    domain = AddressDomain(retained, 0)
    for values in samples:
        env = {}
        for bit, _ident in enumerate(circuit.bit_ids['ref']):
            env[('ref', bit)] = (values['ref'] >> bit) & 1
        cache = {}

        def bit_value(pairs):
            total = 0
            for index, pair in enumerate(pairs):
                total |= circuit.net.value(pair[1], env, cache) << index
            return total

        direct = domain.expression_address(values['ref'])
        null = circuit.net.value(outputs['null'][1], env, cache)
        in_range = circuit.net.value(outputs['in_range'][1], env, cache)
        if direct['outcome'] == NULL:
            if null != 1 or in_range != 0:
                raise AssertionError('expression address did not classify null')
        elif direct['outcome'] == INVALID_REFERENCE:
            if null != 0 or in_range != 0:
                raise AssertionError('expression address did not classify an invalid reference')
        elif direct['outcome'] == IN_RANGE:
            if null != 0 or in_range != 1:
                raise AssertionError('expression address did not classify an in-range reference')
            if bit_value(outputs['row']) != direct['row']:
                raise AssertionError('expression address row disagrees with the page split')
            if bit_value(outputs['head']) != direct['head']:
                raise AssertionError('expression address head disagrees with the page split')
            if bit_value(outputs['layer']) != direct['layer']:
                raise AssertionError('expression address layer disagrees with the page split')
        else:
            raise AssertionError('expression address sample is outside the 16-bit domain')
        if in_range == 0:
            if bit_value(outputs['row']) or bit_value(outputs['head']) or bit_value(outputs['layer']):
                raise AssertionError('an invalid expression reference published a page slot')


def build_expression_address(retained, samples, placement_cap=GATE_CAP):
    """Place the reference split. Not a page read and not a stock forward."""
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    builder.graph.target.value_heads = 4
    outputs = _lower_expression_address(builder, retained, 16, samples, 'expr-addr')
    flat = [outputs['null'], outputs['in_range'], *outputs['row'], *outputs['head'], *outputs['layer']]
    return _place(builder, flat, samples, dict(
        schedule='expression-address',
        retained_rows=retained,
        page_read=False,
        memory_placed=False,
        mathlib_theorems_checked=0,
    ))


def _hot_form(one, bits, value, enabled):
    """Positive iff every literal matches. A miss is at most ``-K``.

    The form is the GDN key and query preactivation. It is linear. It is not
    a second copy of the row.
    """
    width = len(bits) + 1
    total = enabled
    for index, bit in enumerate(bits):
        total = total + (bit if (value >> index) & 1 else one - bit)
    return K * (2 * total - (2 * width - 1) * one)


def _payload_exprs(words):
    bits = []
    for name, width in (
        ('store_tag', TAG_BITS),
        ('store_a', PAGE_WORD_BITS),
        ('store_b', PAGE_WORD_BITS),
        ('store_c', PAGE_WORD_BITS),
    ):
        bits.extend(words[name][:width])
    if len(bits) != PAYLOAD_BITS:
        raise ValueError('expression page payload width drifted')
    return bits


def _decode_packed(values, widths):
    """Unpack page bytes into the field widths. The tail of the last byte is 0."""
    bits = []
    for value in values:
        if type(value) is not int or value < 0 or value > 255:
            raise AssertionError(f'page byte {value} is outside 0..255')
        for shift in range(BYTE_BITS):
            bits.append((value >> shift) & 1)
    cursor = 0
    fields = []
    for width in widths:
        total = 0
        for shift in range(width):
            if cursor >= len(bits):
                raise AssertionError('packed page is short')
            total |= bits[cursor] << shift
            cursor += 1
        fields.append(total)
    while cursor % BYTE_BITS:
        if bits[cursor]:
            raise AssertionError('packed page tail bit is set')
        cursor += 1
    if cursor != len(bits):
        raise AssertionError('packed page has an extra byte')
    return tuple(fields)


def _page_read_ref(sample):
    if 'read_ref' in sample:
        return sample['read_ref']
    direct = direct_expression_child(
        sample['tag'], sample['child_index'], sample['a'], sample['b'], sample['c'],
    )
    return direct['ref'] if direct['in_range'] else 0


def _check_expression_page(graph, words, selected, samples, retained, walk_words=None):
    """Replay writes, then compare each read with the value head that holds it."""
    domain = AddressDomain(retained, 0)
    if walk_words is not None:
        _bind_samples(graph, walk_words, samples)
    matrix = _evaluate_samples(graph, words, samples)
    page = {}
    for index, sample in enumerate(samples):
        if sample['write_enable']:
            placed = domain.expression_address(sample['write_ref'])
            if placed['outcome'] == IN_RANGE:
                if placed['layer'] != 0:
                    raise AssertionError('one expression page does not hold a second layer')
                page[(placed['head'], placed['row'])] = (
                    sample['store_tag'], sample['store_a'], sample['store_b'], sample['store_c'],
                )
        read = domain.expression_address(_page_read_ref(sample))
        if read['outcome'] == IN_RANGE and read['layer'] == 0:
            expect = page.get((read['head'], read['row']), (0, 0, 0, 0))
        else:
            expect = (0, 0, 0, 0)
        got = _decode_packed([
            _expr_value(byte, matrix[index]) for byte in selected
        ], (TAG_BITS, PAGE_WORD_BITS, PAGE_WORD_BITS, PAGE_WORD_BITS))
        if got != expect:
            raise AssertionError(
                f'expression page read {sample["read_ref"]} returned {got}, direct row is {expect}'
            )


def _lower_expression_page(builder, retained, samples):
    """One write port and one read port on one 512-row expression page.

    Value heads are the four blocks of 128 rows. The stored fields are the
    expression tag and ``a``, ``b``, ``c``. The query is the read row. The
    head select is the read head. A null or invalid reference does not write
    and reads as zeros. State persists across the tokens of one evaluation,
    which is the setup write followed by the check read.
    """
    if type(retained) is not int or retained <= 0 or retained > ROWS_PER_LAYER:
        raise ValueError('this expression page is one linear-attention layer')
    spec = (
        ('write_enable', 1),
        ('write_ref', 16),
        ('read_ref', 16),
        ('store_tag', TAG_BITS),
        ('store_a', PAGE_WORD_BITS),
        ('store_b', PAGE_WORD_BITS),
        ('store_c', PAGE_WORD_BITS),
    )
    words = _features(builder, spec, 'page')
    circuit = PredicateCircuit(builder, words, {})
    read = _address_from_pairs(circuit, _word_pairs(circuit, 'read_ref'), retained, name='read_slot')
    write = _address_from_pairs(circuit, _word_pairs(circuit, 'write_ref'), retained, name='write_slot')
    selected = _emit_expression_head(builder, circuit, words, read, write)
    if samples:
        _check_expression_page(builder.graph, words, selected, samples, retained)
    return words, selected, read


def _match_gate(builder, bits, value):
    """One AND of the head bits. Complements are free."""
    one = builder.graph.one
    parts = [bit if (value >> index) & 1 else one - bit for index, bit in enumerate(bits)]
    if len(parts) == 1:
        return parts[0]
    return builder.gate('and', parts, 'expr-page/head')


def _head_matches(builder, head_bits):
    """Head select. A constant head does not add a gate.

    Keys 0..127 are value head 0. The original small bank has 44 keys, so its
    head bits are the constant 0 and only head 0 is open.
    """
    one = builder.graph.one
    value = 0
    for index, bit in enumerate(head_bits):
        expr = _as_expr(bit)
        if not expr.terms:
            continue
        if expr.terms == one.terms:
            value |= 1 << index
            continue
        bits = [_as_expr(item) for item in head_bits]
        return [_match_gate(builder, bits, head) for head in range(VALUE_HEADS_PER_LAYER)]
    return [one if head == value else Expr() for head in range(VALUE_HEADS_PER_LAYER)]


def _zero_channel(builder, name, min_level=None):
    """One residual channel whose value is 0. Identical zeros must not CSE."""
    one = builder.graph.one
    memo = builder.graph.memoize_ffn
    builder.graph.memoize_ffn = False
    try:
        return builder.graph.ffn(
            [(1, one, one - one)], name=name,
            min_level=builder.barrier if min_level is None else min_level,
        )
    finally:
        builder.graph.memoize_ffn = memo


def _emit_packed_page(builder, name, query, key, payload, write_open, write_matches, read_matches):
    """Store one bit per value column and publish one byte channel per 8 bits.

    The head adds bit weights 1, 2, 4, ..., 128 into channels that already
    exist, so a 96-bit row does not allocate 96 residual slots. Those channels
    are born on the even sublayer under the head. Unselected value heads add
    zero. Columns 0 and 1 stay the row ballast.
    """
    if not payload or len(payload) > HD - DATA_COLUMN:
        raise ValueError('page payload does not fit one value head')
    one = builder.graph.one
    payload_exprs = [_as_expr(bit) for bit in payload]
    write_open = _as_expr(write_open)
    dependencies = [
        _as_expr(item)
        for item in (
            *query.values(), *key.values(), *payload_exprs, write_open,
            *write_matches, *read_matches,
        )
    ]
    dep_level = builder.graph.level(*dependencies) if dependencies else 0
    # An even dependency level places the zero on that sublayer. An odd one
    # places it on the next even sublayer, and the head is placed after that.
    zero_floor = dep_level if dep_level % 2 == 1 else max(dep_level - 1, 0)
    nbytes = (len(payload_exprs) + BYTE_BITS - 1) // BYTE_BITS
    channels = [
        _zero_channel(builder, f'{name}/byte{index}', zero_floor) for index in range(nbytes)
    ]
    placed = max(builder.graph.dims[dim].level for channel in channels for dim in channel.terms)
    values = {0: A_REF * one, 1: A_REF * one}
    for index, bit in enumerate(payload_exprs):
        values[DATA_COLUMN + index] = A_BIT * bit
    outs = []
    into = []
    for index in range(len(payload_exprs)):
        outs.append((DATA_COLUMN + index, 128.0 * float(1 << (index % BYTE_BITS))))
        into.append(channels[index // BYTE_BITS])

    def read_gate(match):
        opened = K * (2 * match - one)
        return {DATA_COLUMN + index: opened for index in range(len(payload_exprs))}

    # a = 0 keeps every stored row. The page is not a decaying scratch file.
    # A constant head match must not add a gate on top of the address.
    betas = []
    for head, match in enumerate(write_matches):
        if not match.terms:
            betas.append(Expr())
        elif match.terms == one.terms:
            betas.append(write_open)
        else:
            betas.append(builder.gate('and', [write_open, match], f'{name}/beta'))
    vx = [
        dict(
            v=dict(values), a=0, z=read_gate(read_matches[head]), outs=list(outs),
            beta=betas[head], into='main',
        )
        for head in range(1, VALUE_HEADS_PER_LAYER)
    ]
    builder.graph.head(
        name, query, key, values, 0, read_gate(read_matches[0]), outs,
        beta=betas[0], min_level=placed, into=into, vx=vx,
    )
    return channels


def _emit_expression_head(builder, circuit, words, read, write):
    """Read ``read`` and write ``write`` through one expression page."""
    one = builder.graph.one
    write_open = circuit._and([_word_pairs(circuit, 'write_enable')[0], write['in_range']])
    query = {
        row: _hot_form(one, [_as_expr(bit) for bit in read['row']], row, _as_expr(read['in_range']))
        for row in range(ROWS_PER_PAGE)
    }
    key = {
        row: _hot_form(one, [_as_expr(bit) for bit in write['row']], row, _as_expr(write_open))
        for row in range(ROWS_PER_PAGE)
    }
    payload = _payload_exprs(words)
    write_head = [_as_expr(bit) for bit in write['head']]
    read_head = [_as_expr(bit) for bit in read['head']]
    write_matches = [_match_gate(builder, write_head, head) for head in range(VALUE_HEADS_PER_LAYER)]
    read_matches = [_match_gate(builder, read_head, head) for head in range(VALUE_HEADS_PER_LAYER)]
    return _emit_packed_page(
        builder, 'kernel.expression.page', query, key, payload, _as_expr(write_open),
        write_matches, read_matches,
    )


def _attach_expression_page(builder, read_address, retained, samples, walk_words, input_level,
                            store_bits=None):
    """Write port plus a read of an address the walk already published.

    The read reference is the walk's child. ``samples`` carry that child in
    the walk fields and the stored row in ``store_tag`` / ``store_a`` /
    ``store_b`` / ``store_c``. One linear-attention layer holds 512 rows.
    ``store_bits`` is an existing bus of ``PAYLOAD_BITS`` expressions. The
    joint uses one payload bus for this page and the small bank, because a
    second 96-bit port does not fit the H768 feature floor.
    """
    if type(retained) is not int or retained <= 0 or retained > ROWS_PER_LAYER:
        raise ValueError('this expression page is one linear-attention layer')
    spec = (
        ('write_enable', 1),
        ('write_ref', 16),
    )
    if store_bits is None:
        spec = spec + (
            ('store_tag', TAG_BITS),
            ('store_a', PAGE_WORD_BITS),
            ('store_b', PAGE_WORD_BITS),
            ('store_c', PAGE_WORD_BITS),
        )
    words = _features(builder, spec, 'page', level=input_level)
    if store_bits is not None:
        if len(store_bits) < PAYLOAD_BITS:
            raise ValueError('expression store bus is shorter than tag, a, b, and c')
        cursor = 0
        for name, width in (
            ('store_tag', TAG_BITS),
            ('store_a', PAGE_WORD_BITS),
            ('store_b', PAGE_WORD_BITS),
            ('store_c', PAGE_WORD_BITS),
        ):
            words[name] = list(store_bits[cursor:cursor + width])
            cursor += width
    circuit = PredicateCircuit(builder, words, {})
    write = _address_from_pairs(
        circuit, _word_pairs(circuit, 'write_ref'), retained, name='write_slot',
    )
    selected = _emit_expression_head(builder, circuit, words, read_address, write)
    if samples:
        _check_expression_page(
            builder.graph, words, selected, samples, retained, walk_words=walk_words,
        )
    return selected


def _price_head_graph(graph, peak_slots, kept_outputs):
    """Price head layers as linear attention. An all-inert price undercounts them."""
    hidden = 768
    ballast = hidden // 64
    graph_layers = graph.n_layers()
    clear_layers = math.ceil(max(hidden - ballast - kept_outputs, 0) / MODEL_INTERMEDIATE)
    layers = graph_layers + clear_layers + 1
    head_layers = sorted({node.level // 2 for node in graph.nodes if isinstance(node, Head)})
    dense = dense_parameters(hidden, MODEL_INTERMEDIATE, layers, gdn_layers=len(head_layers))
    channels = ballast + 1 + peak_slots
    return dict(
        hidden=hidden,
        ballast=ballast,
        channels_needed=channels,
        channel_gate=channels <= hidden,
        graph_layers=graph_layers,
        scratch_clear_layers=clear_layers,
        feedback_layer=1,
        layers=layers,
        gdn_layers=len(head_layers),
        head_layers=head_layers,
        logical_dense_parameters=dense,
        dense_gate=dense <= DENSE_LIMIT,
        memory_layers_included=len(head_layers),
        inert_price_undercounts_head=True,
    )


def _const_pair(circuit, bit):
    if bit:
        return circuit.one, circuit.net.ONE
    return Expr(), circuit.net.ZERO


def _xor_const(circuit, bit, const_bit):
    if const_bit:
        return _xor_pair(circuit, bit, _const_pair(circuit, 1))
    return bit


def _add_const_pairs(circuit, bits, const):
    """Bit pairs of ``bits + const``.

    Each carry is one parallel layer of ANDs and one OR. The sum bit is one
    XOR after that. A constant whose set bits do not overlap a masked index
    takes the wiring path instead, and this adder is not used.
    """
    width = len(bits)
    if type(const) is not int or const < 0 or const >= 1 << width:
        raise ValueError('page constant does not fit the index word')
    carries = [(Expr(), circuit.net.ZERO)]
    for dest in range(1, width):
        terms = []
        for origin in range(dest):
            if (const >> origin) & 1 == 0:
                continue
            parts = [bits[origin]]
            for between in range(origin + 1, dest):
                if (const >> between) & 1 == 0:
                    parts.append(bits[between])
            terms.append(parts[0] if len(parts) == 1 else circuit._and(parts))
        carries.append(circuit._or(terms) if terms else (Expr(), circuit.net.ZERO))
    summed = []
    for index, bit in enumerate(bits):
        mixed = _xor_pair(circuit, bit, carries[index])
        summed.append(_xor_const(circuit, mixed, (const >> index) & 1))
    return summed


def _aligned_base(base, limit):
    """True when ``index < limit`` makes ``index + base`` a bit insert."""
    return (
        type(limit) is int and limit > 0 and limit & (limit - 1) == 0
        and type(base) is int and base >= 0 and (base & (limit - 1)) == 0
    )


def _and_literals(circuit, literals):
    if not literals:
        return circuit.one, circuit.net.ONE
    if len(literals) == 1:
        return literals[0]
    return circuit._and(literals)


def _bank_limit_literals(circuit, bank_bits, index_bits, bank_id, limit, open_literal):
    """Bank select and ``index < limit`` in one literal list.

    The limit is a power of two, so the bound is the high index bits clear.
    Folding the bound into the key AND keeps the address one gate deep.
    """
    b0, b1 = bank_bits
    if bank_id == BANK_STACK:
        bank = (circuit._not(*b0), circuit._not(*b1))
    elif bank_id == BANK_CONTEXT:
        bank = (b0, circuit._not(*b1))
    elif bank_id == BANK_DECLARATION:
        bank = (circuit._not(*b0), b1)
    else:
        raise ValueError('small-bank id is not a placed bank')
    low = limit.bit_length() - 1
    cleared = tuple(circuit._not(*index_bits[bit]) for bit in range(low, len(index_bits)))
    opened = (open_literal,) if open_literal is not None else ()
    return bank + cleared + opened


def _aligned_small_key(circuit, bank_bits, index_bits, bases, limits, open_literal):
    """Masked key and in-range bit. Every AND reads features, not other ANDs."""
    banks = range(len(bases))
    opens = [
        _and_literals(
            circuit,
            _bank_limit_literals(circuit, bank_bits, index_bits, bank, limits[bank], open_literal),
        )
        for bank in banks
    ]
    in_range = opens[0] if len(opens) == 1 else _free_or(circuit, opens)
    key = []
    for bit_index in range(len(index_bits)):
        parts = []
        for bank, base, limit in zip(banks, bases, limits):
            if not _aligned_base(base, limit):
                raise RuntimeError('aligned key saw an unaligned bank')
            low = limit.bit_length() - 1
            if bit_index < low:
                parts.append(_and_literals(circuit, [
                    *_bank_limit_literals(
                        circuit, bank_bits, index_bits, bank, limit, open_literal,
                    ),
                    index_bits[bit_index],
                ]))
            elif (base >> bit_index) & 1:
                parts.append(opens[bank])
        if not parts:
            key.append(_const_pair(circuit, 0))
        elif len(parts) == 1:
            key.append(parts[0])
        else:
            key.append(_free_or(circuit, parts))
    return in_range, key


def _small_page_address(circuit, bank_name, index_name, stack, context, declarations, open_literal=None):
    """Map a bank id and a 0-based index onto the small-bank page.

    Keys follow ``AddressDomain.small_address``: stack, then context, then
    declarations. Zero is a live stack slot. An index past that bank's limit
    is not a spare key lane.
    """
    bank_bits = _word_pairs(circuit, bank_name)
    if len(bank_bits) != 2:
        raise ValueError('small-bank id is two bits')
    index_bits = _word_pairs(circuit, index_name)
    if len(index_bits) != 16:
        raise ValueError('small-bank index width is the 16-bit word')
    bases = (0, stack, stack + context)
    limits = (stack, context, declarations)
    aligned = all(_aligned_base(base, limit) for base, limit in zip(bases, limits))
    if aligned:
        in_range, key = _aligned_small_key(
            circuit, bank_bits, index_bits, bases, limits, open_literal,
        )
        masked = key
    else:
        # One adder per bank. Used when a declaration count is not a power of
        # two, as in a mathlib closure. The aligned page does not build this.
        b0, b1 = bank_bits
        matches = (
            circuit._and([circuit._not(*b0), circuit._not(*b1)]),
            circuit._and([b0, circuit._not(*b1)]),
            circuit._and([circuit._not(*b0), b1]),
        )
        below = []
        for name, limit in zip(
            (f'{index_name}/stack', f'{index_name}/context', f'{index_name}/declaration'),
            limits,
        ):
            circuit.words = dict(circuit.words)
            circuit.bit_ids = dict(circuit.bit_ids)
            circuit.words[name] = [pair[0] for pair in index_bits]
            circuit.bit_ids[name] = [pair[1] for pair in index_bits]
            below.append(circuit._less(name, limit))
        in_parts = [circuit._and([match, limit]) for match, limit in zip(matches, below)]
        in_range = in_parts[0] if len(in_parts) == 1 else _free_or(circuit, in_parts)
        keys = []
        for base, limit in zip(bases, limits):
            if _aligned_base(base, limit):
                low = limit.bit_length() - 1
                bits = list(index_bits[:low])
                for index in range(low, 16):
                    bits.append(_const_pair(circuit, (base >> index) & 1))
                keys.append(bits)
            else:
                keys.append(_add_const_pairs(circuit, index_bits, base))
        key = []
        for index in range(16):
            parts = [circuit._and([match, bits[index]]) for match, bits in zip(matches, keys)]
            key.append(_free_or(circuit, parts))
        masked = [circuit._and([in_range, bit]) for bit in key]
    row_width = ROWS_PER_PAGE.bit_length() - 1
    head_width = VALUE_HEADS_PER_LAYER.bit_length() - 1
    return dict(
        in_range=in_range,
        row=masked[:row_width],
        head=masked[row_width:row_width + head_width],
        layer=masked[row_width + head_width:],
        open_included=aligned and open_literal is not None,
    )


def _guard_bits(circuit, guard, bits):
    return [circuit._and([guard, bit]) for bit in bits]


def _or_columns(circuit, columns):
    if len(columns) == 1:
        return columns[0]
    return [
        circuit._or([column[index] for column in columns])
        for index in range(len(columns[0]))
    ]


def _commit_bus(circuit, writers, zero_extend_context):
    """Present one small-bank row.

    One writer is wired through. The page write gate is the guard, so a cold
    guard does not store. Several writers of one bank OR their guards, their
    indices, and their words, which is the reference merge. A context commit
    keeps word 0 and clears the other five. Two banks in one token are not
    this port: the head has one key.
    """
    if len(writers) == 1 and not zero_extend_context:
        writer = writers[0]
        enable = _word_pairs(circuit, writer['guard'])[0]
        bank = _word_pairs(circuit, writer['bank'])
        index = _word_pairs(circuit, writer['index'])
        words = [_word_pairs(circuit, writer['word'](word)) for word in range(SMALL_WORDS)]
        return enable, bank, index, words
    guarded_banks = []
    guarded_indices = []
    guarded_words = [[] for _ in range(SMALL_WORDS)]
    guards = []
    for writer in writers:
        guard = _word_pairs(circuit, writer['guard'])[0]
        guards.append(guard)
        guarded_banks.append(_guard_bits(circuit, guard, _word_pairs(circuit, writer['bank'])))
        guarded_indices.append(_guard_bits(circuit, guard, _word_pairs(circuit, writer['index'])))
        for word in range(SMALL_WORDS):
            guarded_words[word].append(
                _guard_bits(circuit, guard, _word_pairs(circuit, writer['word'](word))),
            )
    enable = guards[0] if len(guards) == 1 else circuit._or(guards)
    bank = _or_columns(circuit, guarded_banks)
    index = _or_columns(circuit, guarded_indices)
    words = [_or_columns(circuit, guarded_words[word]) for word in range(SMALL_WORDS)]
    if zero_extend_context:
        context = circuit._and([bank[0], circuit._not(*bank[1])])
        for word in range(1, SMALL_WORDS):
            words[word] = [circuit._and([circuit._not(*context), bit]) for bit in words[word]]
    return enable, bank, index, words


def _alias_pairs(circuit, name, pairs):
    circuit.words = dict(circuit.words)
    circuit.bit_ids = dict(circuit.bit_ids)
    circuit.words[name] = [pair[0] for pair in pairs]
    circuit.bit_ids[name] = [pair[1] for pair in pairs]


def _writer_schemas(count):
    if count == 1:
        return [dict(
            guard='write_enable', bank='bank', index='index',
            word=lambda index: f'w{index}',
        )]
    if count != 2:
        raise ValueError('a small-bank token merges one or two writers of one bank')
    schemas = []
    for prefix in ('a', 'b'):
        schemas.append(dict(
            guard=f'{prefix}_guard', bank=f'{prefix}_bank', index=f'{prefix}_index',
            word=lambda index, prefix=prefix: f'{prefix}_w{index}',
        ))
    return schemas


_BANK_NAMES = {BANK_STACK: 'stack', BANK_CONTEXT: 'context', BANK_DECLARATION: 'declaration'}


def _sample_merge(sample, writers, zero_extend_context):
    """Python image of ``_commit_bus``. Different hot banks are rejected."""
    prefixes = ('',) if writers == 1 else ('a_', 'b_')
    enable = 0
    bank = 0
    index = 0
    words = [0] * SMALL_WORDS
    hot = []
    for prefix in prefixes:
        guard_name = 'write_enable' if prefix == '' else f'{prefix}guard'
        if not sample[guard_name]:
            continue
        enable = 1
        writer_bank = sample['bank' if prefix == '' else f'{prefix}bank']
        writer_index = sample['index' if prefix == '' else f'{prefix}index']
        writer_words = [
            sample[f'w{word}' if prefix == '' else f'{prefix}w{word}']
            for word in range(SMALL_WORDS)
        ]
        hot.append(writer_bank)
        bank |= writer_bank
        index |= writer_index
        words = [left | right for left, right in zip(words, writer_words)]
    if len(set(hot)) > 1:
        raise AssertionError('one small-bank token cannot merge two banks')
    if zero_extend_context and enable and bank == BANK_CONTEXT:
        words = [words[0], 0, 0, 0, 0, 0]
    return enable, bank, index, tuple(words)


def _check_small_bank(graph, words, selected, samples, stack, context, declarations, writers, zero_extend_context):
    domain = AddressDomain(0, declarations, stack=stack, context=context)
    matrix = _evaluate_bound(graph, words, samples)
    page = {}
    widths = (PAGE_WORD_BITS,) * SMALL_WORDS
    for index, sample in enumerate(samples):
        enable, bank, slot, stored = _sample_merge(sample, writers, zero_extend_context)
        if enable and bank in _BANK_NAMES:
            placed = domain.small_address(_BANK_NAMES[bank], slot)
            if placed['outcome'] == IN_RANGE:
                if placed['layer'] != 0:
                    raise AssertionError('one small-bank page does not hold a second layer')
                page[(placed['head'], placed['row'])] = stored
        read_bank = sample['read_bank']
        if read_bank in _BANK_NAMES:
            read = domain.small_address(_BANK_NAMES[read_bank], sample['read_index'])
        else:
            read = dict(outcome=INVALID_REFERENCE)
        if read['outcome'] == IN_RANGE and read['layer'] == 0:
            expect = page.get((read['head'], read['row']), (0,) * SMALL_WORDS)
        else:
            expect = (0,) * SMALL_WORDS
        got = _decode_packed([
            _expr_value(byte, matrix[index]) for byte in selected
        ], widths)
        if got != expect:
            raise AssertionError(
                f'small bank read bank {read_bank} index {sample["read_index"]} '
                f'returned {got}, direct row is {expect}'
            )


def _lower_small_bank(builder, stack, context, declarations, samples, writers=1,
                      zero_extend_context=False, input_level=None, payload_bits=None):
    """One write port and one read port on the small-bank page.

    Retained keys are ``stack + context + declarations``. Physical padding
    past that sum is not a live key. The stored row is six words. Context
    effects are one word; ``zero_extend_context`` clears the other five at
    the commit, and the one-writer page stores the row it is given.
    ``payload_bits`` supplies the six words from an existing bus. One writer
    can share that bus with the expression page. Two writers always own
    their words, because the merge is the test of the commit.
    """
    retained = stack + context + declarations
    limits = (stack, context, declarations, retained)
    if any(type(value) is not int for value in limits) or min(stack, context, declarations) < 0:
        raise ValueError('small-bank limits are nonnegative integers')
    if retained <= 0 or retained > ROWS_PER_LAYER:
        raise ValueError('this small bank is one linear-attention layer')
    if payload_bits is not None and (
        writers != 1 or len(payload_bits) != SMALL_WORDS * PAGE_WORD_BITS
    ):
        raise ValueError('shared payload is one writer and six words')
    if input_level is not None:
        builder.barrier = input_level
    schemas = _writer_schemas(writers)
    spec = []
    for writer in schemas:
        spec.append((writer['guard'], 1))
        spec.append((writer['bank'], 2))
        spec.append((writer['index'], 16))
        if payload_bits is None:
            for word in range(SMALL_WORDS):
                spec.append((writer['word'](word), PAGE_WORD_BITS))
    spec.extend((('read_bank', 2), ('read_index', 16)))
    feature_words = _features(builder, spec, 'small', level=input_level)
    circuit = PredicateCircuit(builder, feature_words, {})
    if payload_bits is not None:
        for word in range(SMALL_WORDS):
            bits = list(payload_bits[word * PAGE_WORD_BITS:(word + 1) * PAGE_WORD_BITS])
            name = schemas[0]['word'](word)
            pairs = [
                (bit, circuit.net.node('input', (name, index))) for index, bit in enumerate(bits)
            ]
            _alias_pairs(circuit, name, pairs)
            feature_words[name] = bits
    enable, bank, index, stored = _commit_bus(circuit, schemas, zero_extend_context)
    _alias_pairs(circuit, 'commit_bank', bank)
    _alias_pairs(circuit, 'commit_index', index)
    write = _small_page_address(
        circuit, 'commit_bank', 'commit_index', stack, context, declarations,
        open_literal=enable,
    )
    read = _small_page_address(
        circuit, 'read_bank', 'read_index', stack, context, declarations,
    )
    one = builder.graph.one
    if write['open_included']:
        write_open = write['in_range']
    else:
        write_open = circuit._and([enable, write['in_range']])
    query = {
        row: _hot_form(one, [_as_expr(bit) for bit in read['row']], row, _as_expr(read['in_range']))
        for row in range(ROWS_PER_PAGE)
    }
    key = {
        row: _hot_form(one, [_as_expr(bit) for bit in write['row']], row, _as_expr(write_open))
        for row in range(ROWS_PER_PAGE)
    }
    payload = [_as_expr(bit) for word in stored for bit in word]
    write_matches = _head_matches(builder, write['head'])
    read_matches = _head_matches(builder, read['head'])
    selected = _emit_packed_page(
        builder, 'kernel.small.page', query, key, payload, _as_expr(write_open),
        write_matches, read_matches,
    )
    if samples:
        _check_small_bank(
            builder.graph, feature_words, selected, samples, stack, context, declarations,
            writers, zero_extend_context,
        )
    return selected


def _continue_after_head(builder):
    """Put the next page's gates on the even sublayer after the latest head."""
    heads = [node.level for node in builder.graph.nodes if isinstance(node, Head)]
    builder.barrier = max(heads) if heads else 2 * builder.graph.n_layers()


def _attach_small_bank(builder, stack, context, declarations, samples, input_level, payload_bits=None):
    """Attach the small bank after the caller has set the barrier."""
    return _lower_small_bank(
        builder, stack, context, declarations, samples,
        writers=1, zero_extend_context=False, input_level=input_level,
        payload_bits=payload_bits,
    )


def build_expression_page(retained, samples, placement_cap=GATE_CAP):
    """Place one expression page. Not a stock forward and not a source checker."""
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    builder.graph.target.value_heads = 4
    _words, selected, read = _lower_expression_page(builder, retained, samples)
    flat = [read['null'], read['in_range'], *selected]
    report = _place(builder, flat, samples, dict(
        schedule='expression-page',
        retained_rows=retained,
        payload_bits=PAYLOAD_BITS,
        payload_bytes=(PAYLOAD_BITS + BYTE_BITS - 1) // BYTE_BITS,
        page_read=True,
        expression_page_placed=True,
        small_bank_placed=False,
        memory_placed=False,
        mathlib_theorems_checked=0,
    ))
    priced = _price_head_graph(
        builder.graph, max(report['peak_live_dims'], report['allocated_slots']), report['outputs_kept'],
    )
    report['selected_shape'] = priced
    report['candidate_shapes'] = [priced]
    report['channel_gate'] = priced['channel_gate']
    report['dense_gate'] = priced['dense_gate']
    report['memory_layers_included'] = priced['memory_layers_included']
    return report


def build_child_page(samples, placement_cap=GATE_CAP):
    """Place the walk, the child address, and one expression page together.

    Not the dispatch graph and not a stock forward. ``samples`` are walk rows
    whose child is the page read, plus one write port.
    """
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    builder.graph.target.value_heads = 4
    outputs = _lower_walk(builder, 16, samples, 'walk', address_retained=512)
    selected = _attach_expression_page(
        builder, outputs['address'], 512, samples, outputs['inputs'], input_level=0,
    )
    flat = [
        outputs['in_range'], outputs['overflow'], *outputs['status'], *outputs['reason'], *selected,
    ]
    report = _place(builder, flat, samples, dict(
        schedule='child-page',
        retained_rows=512,
        payload_bits=PAYLOAD_BITS,
        payload_bytes=(PAYLOAD_BITS + BYTE_BITS - 1) // BYTE_BITS,
        page_read=True,
        expression_page_placed=True,
        small_bank_placed=False,
        memory_placed=False,
        mathlib_theorems_checked=0,
    ))
    priced = _price_head_graph(
        builder.graph, max(report['peak_live_dims'], report['allocated_slots']), report['outputs_kept'],
    )
    report['selected_shape'] = priced
    report['candidate_shapes'] = [priced]
    report['channel_gate'] = priced['channel_gate']
    report['dense_gate'] = priced['dense_gate']
    report['memory_layers_included'] = priced['memory_layers_included']
    return report


def build_small_bank(stack, context, declarations, samples, placement_cap=GATE_CAP, writers=1,
                     zero_extend_context=False):
    """Place one small-bank page. Not a stock forward and not a source checker.

    ``writers`` 2 is the guarded OR-merge of one bank. The joint page uses one
    writer. A declaration count that is not a power of two takes the adder.
    """
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    builder.graph.target.value_heads = 4
    selected = _lower_small_bank(
        builder, stack, context, declarations, samples,
        writers=writers, zero_extend_context=zero_extend_context,
    )
    payload_bits = SMALL_WORDS * PAGE_WORD_BITS
    report = _place(builder, list(selected), samples, dict(
        schedule='small-bank',
        payload_bits=payload_bits,
        payload_bytes=(payload_bits + BYTE_BITS - 1) // BYTE_BITS,
        small_bank_keys=stack + context + declarations,
        page_read=True,
        expression_page_placed=False,
        small_bank_placed=True,
        memory_placed=False,
        mathlib_theorems_checked=0,
        writers=writers,
        zero_extend_context=zero_extend_context,
        guarded_merge_included=writers > 1,
        handler_commit_included=False,
    ))
    priced = _price_head_graph(
        builder.graph, max(report['peak_live_dims'], report['allocated_slots']), report['outputs_kept'],
    )
    report['selected_shape'] = priced
    report['candidate_shapes'] = [priced]
    report['channel_gate'] = priced['channel_gate']
    report['dense_gate'] = priced['dense_gate']
    report['memory_layers_included'] = priced['memory_layers_included']
    return report


def kept_output_dims(outputs):
    """Residual dims named by walk outputs. Digits may be bare linear forms."""
    keep = set()
    for key, item in outputs.items():
        if key == 'inputs':
            continue
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


def build_shared_expression_walk(width, samples, placement_cap=GATE_CAP, address_retained=None):
    """Place one walk. ``samples`` carry tag, child index, row fields, and depth.

    ``address_retained`` splits the selected child into a page address. The
    split still does not read the page.
    """
    builder = NativeBuilder(intermediate=MODEL_INTERMEDIATE, reset_layers=0, layout_policy='compact')
    builder.graph.target.intermediate = placement_cap
    builder.graph.target.value_heads = 4
    outputs = _lower_walk(
        builder, width, samples, 'walk', address_retained=address_retained,
    )
    flat = [
        outputs['in_range'], outputs['depth_inc'], outputs['overflow'],
        *outputs['child'], *outputs['next_depth'], *outputs['status'], *outputs['reason'],
    ]
    extra = dict(
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
        page_read=False,
        memory_placed=False,
    )
    if address_retained is not None:
        address = outputs['address']
        flat.extend([address['null'], address['in_range'], *address['row'], *address['head'], *address['layer']])
        extra['address_retained'] = address_retained
    return _place(builder, flat, samples, extra)


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
