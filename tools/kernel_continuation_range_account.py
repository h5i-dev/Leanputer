"""Allocate continuation-range dispatch, residuals, and the expression walk once.

The handler identity is the live control key. No torch model is constructed.
The unplaced memory sum is not an allocate result.
"""
import json
from pathlib import Path

from leanputer.kernel.arena import Tag
from leanputer.native_vendor.qwenputer.expr import Expr
from leanputer.kernel.semantic_body import (
    PAGE_WORD_BITS,
    PAYLOAD_BITS,
    SMALL_WORDS,
    _attach_expression_page,
    _attach_small_bank,
    _continue_after_head,
    _expr_dims,
    kept_output_dims,
    _lower_walk,
)
from leanputer.kernel.semantic_operators import CALL_LIMIT, DENSE_LIMIT
from leanputer.kernel.semantic_step_circuit import (
    MODEL_INTERMEDIATE,
    continuation_range_plan,
    build_continuation_range_select,
    dense_parameters,
)
from leanputer.kernel.source_capacity import storage_layout
from tools.kernel_semantic_body_account import _selector_inputs, _walk_samples


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'benchmarks' / 'kernel-macro-budget' / 'continuation-range.json'


def _extend_samples(plan, widths, ranged, fields, samples):
    def add(values):
        row = {field: sample_default[field] for field in fields}
        row.update(values)
        samples.append(row)

    sample_default = samples[0]
    for item in ranged['classes']:
        for group in item['groups']:
            if group['lowering'] != 'range':
                continue
            fixed = dict(group['fixed'])
            axis = group['axis']
            limit = 1 << widths[axis]
            for low, high in group['spans']:
                for value in (low, high, (low + high) // 2):
                    add({**fixed, axis: value})
                if high + 1 < limit:
                    add({**fixed, axis: high + 1})
    unique = []
    seen = set()
    for sample in samples:
        key = tuple(sample[field] for field in fields)
        if key in seen:
            continue
        seen.add(key)
        unique.append(sample)
    return unique


def _page_samples():
    """Walk child is the page read. Writes happen on earlier tokens."""

    def step(child, write_enable, write_ref, tag, a, b, c):
        return dict(
            tag=int(Tag.APP), child_index=0, a=child, b=0, c=0, depth=0,
            require_child=0, service_gap=0, gap_reason=0,
            write_enable=write_enable, write_ref=write_ref,
            store_tag=tag, store_a=a, store_b=b, store_c=c,
        )

    return [
        step(0, 1, 1, int(Tag.APP), 1, 2, 3),
        step(1, 0, 0, 0, 0, 0, 0),
        step(0, 1, 129, int(Tag.SORT), 4, 5, 6),
        step(129, 0, 0, 0, 0, 0, 0),
        step(0, 1, 512, int(Tag.CONST), 7, 8, 9),
        step(512, 0, 0, 0, 0, 0, 0),
        step(0, 1, 0, int(Tag.LAM), 9, 9, 9),
        step(0, 1, 513, int(Tag.LAM), 8, 8, 8),
        step(513, 0, 0, 0, 0, 0, 0),
        step(3, 0, 0, 0, 0, 0, 0),
    ]


# The working gate stays DENSE_LIMIT. These two are the later numerical bounds
# from the 2026-11-19 TUI. Neither bound is a successful checker by itself.
IDEAL_DENSE_LIMIT = 50_000_000
ABSOLUTE_DENSE_LIMIT = 100_000_000
IDEAL_CALL_LIMIT = 5_000


def _dense_bounds(dense):
    return dict(
        logical_dense_parameters=dense,
        within_working_dense_limit=dense <= DENSE_LIMIT,
        within_ideal_dense_limit=dense <= IDEAL_DENSE_LIMIT,
        within_absolute_dense_limit=dense < ABSOLUTE_DENSE_LIMIT,
        over_working_dense_limit_by=max(0, dense - DENSE_LIMIT),
        over_ideal_dense_limit_by=max(0, dense - IDEAL_DENSE_LIMIT),
    )


def _remaining_joint(storage, shape, placed_expression_layers, placed_small_layers):
    """Add memory layers that are not already heads in the allocated graph.

    The sum is not an allocate result when ``extra`` is nonzero. Vector cells
    stay unplaced. The placed small bank addresses the original 44 keys. A
    wider declaration count needs a different address circuit on that layer,
    not a second small-bank head.
    """
    if placed_expression_layers > storage['expression_layers']:
        raise ValueError('placed expression page is larger than the domain')
    if placed_small_layers > storage['small_bank_layers']:
        raise ValueError('placed small bank is larger than the domain')
    extra = storage['memory_layers'] - placed_expression_layers - placed_small_layers
    if extra < 0:
        raise ValueError('placed pages exceed the domain memory layers')
    layers = shape['layers'] + extra
    gdn = shape['memory_layers_included'] + extra
    dense = dense_parameters(shape['hidden'], MODEL_INTERMEDIATE, layers, gdn_layers=gdn)
    vectors_open = storage['vector_cells'] > 0 and not storage['vector_bank_placed']
    small_gap = storage['small_bank_keys'] != 44
    bounds = _dense_bounds(dense)
    return dict(
        placed_graph=False,
        stock_emitted=False,
        mathlib_theorems_checked=0,
        proof_checked=False,
        logic_layers=shape['layers'],
        logic_logical_dense_parameters=shape['logical_dense_parameters'],
        expression_layers_covered=placed_expression_layers,
        small_layers_covered=placed_small_layers,
        small_bank_address_is_original_44=not small_gap,
        memory_layers_unplaced=extra,
        memory_layers=gdn,
        layers=layers,
        logical_dense_parameters=dense,
        dense_gate=(
            bounds['within_working_dense_limit']
            and not storage['exceeds_word_reference']
            and not vectors_open
            and not small_gap
        ),
        exceeds_word_reference=storage['exceeds_word_reference'],
        vector_cells_unplaced=vectors_open,
        over_dense_limit_by=bounds['over_working_dense_limit_by'],
        within_ideal_dense_limit=bounds['within_ideal_dense_limit'] and not vectors_open and not small_gap,
        within_absolute_dense_limit=bounds['within_absolute_dense_limit'],
        over_ideal_dense_limit_by=bounds['over_ideal_dense_limit_by'],
        working_dense_limit=DENSE_LIMIT,
        ideal_dense_limit=IDEAL_DENSE_LIMIT,
        absolute_dense_limit=ABSOLUTE_DENSE_LIMIT,
        note=(
            'The allocated graph contains one expression page and the original '
            '44-key small bank. A mathlib closure still needs its remaining '
            'expression layers, its level layer, and the 147-declaration address '
            'circuit. Vector cells are not in this sum. Not a stock forward.'
        ),
    )


def _control_payload(builder, width):
    """First ``width`` control channels, in field then bit order.

    A second 96-bit feature port does not fit the H768 slot ceiling. The write
    token reuses these channels. The handler key is not latched across that
    token in this graph.
    """
    named = []
    for index, dim in enumerate(builder.graph.dims):
        if dim.name.startswith('control/'):
            named.append((dim.name, index))

    def sort_key(item):
        _prefix, field, bit = item[0].split('/')
        return int(field), int(bit)

    named.sort(key=sort_key)
    if len(named) < width:
        raise ValueError('control channels do not cover the payload bus')
    return [Expr({index: 1}) for _name, index in named[:width]]


def _small_samples():
    """Original-domain reads. The check fails the allocate if the bus is wrong."""

    def frame(enable, bank, index, words, read_bank, read_index):
        row = dict(
            write_enable=enable, bank=bank, index=index,
            read_bank=read_bank, read_index=read_index,
        )
        for bit, word in enumerate(words):
            row[f'w{bit}'] = word
        return row

    zero = (0, 0, 0, 0, 0, 0)
    return [
        frame(1, 0, 0, (1, 2, 3, 4, 5, 6), 0, 0),
        frame(1, 0, 31, (9, 0, 0, 0, 0, 0), 0, 31),
        frame(1, 1, 7, (3, 0, 0, 0, 0, 0), 1, 7),
        frame(1, 2, 3, (5, 6, 7, 8, 9, 10), 2, 3),
        frame(0, 0, 0, zero, 0, 1),
        frame(1, 0, 32, (99, 0, 0, 0, 0, 0), 0, 32),
        frame(1, 2, 4, (99, 0, 0, 0, 0, 0), 2, 4),
        frame(0, 0, 0, zero, 0, 0),
    ]


def main():
    names, widths, plan, control, residual = _selector_inputs()
    fields = sorted({field for item in plan['classes'] for field in item['fields']})
    for sample in control:
        for field in fields:
            sample.setdefault(field, 0)
    ranged = continuation_range_plan(plan['classes'], widths)
    if ranged['predicted_match_gates'] >= plan['exclusive_keys']:
        raise ValueError('continuation ranges did not shrink the equality keys')
    samples = _extend_samples(plan, widths, ranged, fields, control)
    walk_samples = _walk_samples(16)
    page_samples = _page_samples()
    small_samples = _small_samples()
    observed = {}

    def tail(builder):
        level = builder.barrier
        outputs = _lower_walk(
            builder, 16, walk_samples, 'walk', input_level=level,
            address_retained=512,
        )
        # The write token reuses control channels. New payload features were
        # measured at 740 token features, 834 slots, and 847 H768 channels.
        payload = _control_payload(builder, SMALL_WORDS * PAGE_WORD_BITS)
        if len(payload) <= PAYLOAD_BITS:
            raise ValueError('payload bus does not cover the expression row and the frame')
        selected = _attach_expression_page(
            builder, outputs['address'], 512, page_samples, outputs['inputs'], level,
            store_bits=payload,
        )
        _continue_after_head(builder)
        small = _attach_small_bank(
            builder, 32, 8, 4, small_samples, builder.barrier, payload_bits=payload,
        )
        keep = kept_output_dims(outputs)
        for bit in (*selected, *small):
            keep |= _expr_dims(bit)
        observed['token_features'] = len(builder.graph.token_fns)
        return keep

    print('predicted_match_gates', ranged['predicted_match_gates'], 'samples', len(samples), flush=True)
    report = build_continuation_range_select(
        names, widths, plan, samples, wave=96, placement_cap=96,
        residual_predicates=residual, tail=tail,
    )
    if report['memory_layers_included'] != 2:
        raise ValueError('the expression page and the small bank did not place two linear-attention layers')
    shape = next(item for item in report['candidate_shapes'] if item['hidden'] == 768)
    storage = storage_layout(512, 4, stack=32, context=8)
    joint = _remaining_joint(storage, shape, placed_expression_layers=1, placed_small_layers=1)
    recorded = json.loads((
        ROOT / 'benchmarks' / 'mathlib-v4.31.0' / 'fabf563-addressable' / 'capacity.json'
    ).read_text())
    bound = recorded['bounding_domain']
    mathlib_storage = storage_layout(
        bound['expression_rows'], bound['declaration_slots'], stack=32, context=8,
        level_rows=bound['level_rows'], vector_refs=bound['vector_refs'],
        vector_cells=bound['vector_cells'],
    )
    mathlib_joint = _remaining_joint(
        mathlib_storage, shape, placed_expression_layers=1, placed_small_layers=1,
    )
    h768_fits = bool(shape['channel_gate'] and shape['dense_gate'])
    document = dict(
        format='leanputer.continuation-range.v1',
        full_checker=False,
        joint_delivery_gate=False,
        stock_emitted=False,
        operator_body_included=False,
        private_algorithms_placed=False,
        proof_checking_not_proof_discovery=True,
        mathlib_theorems_checked=0,
        working_dense_limit=DENSE_LIMIT,
        ideal_dense_limit=IDEAL_DENSE_LIMIT,
        absolute_dense_limit=ABSOLUTE_DENSE_LIMIT,
        working_call_limit=CALL_LIMIT,
        ideal_call_limit=IDEAL_CALL_LIMIT,
        handler_identity='live control key',
        expression_address_retained=512,
        expression_page_read=True,
        expression_page_rows=512,
        expression_payload_bytes=7,
        small_bank_placed=True,
        small_bank_keys=44,
        small_bank_payload_bytes=12,
        payload_bus_bits=96,
        one_token_commits_every_bank=False,
        token_features=observed.get('token_features'),
        h768_channel_and_dense_gates=h768_fits,
        predicted_match_gates=ranged['predicted_match_gates'],
        exclusive_keys=plan['exclusive_keys'],
        boolean_samples=len(samples),
        continuation_range=report,
        original_domain_memory_unplaced=joint,
        mathlib_bounding_memory_unplaced=mathlib_joint,
        note=(
            'One allocate of continuation-range hits, the 65 residual predicates, '
            'the shared expression walk, one expression page, and the original '
            '44-key small bank. Both pages publish packed bytes. The write token '
            'reuses 96 control channels as the payload bus, so the handler key is '
            'not present on that token and is not latched. One token writes one '
            'small-bank row. The handler identity on the control token is the live '
            'control key. Head layers are priced as linear attention. Handler '
            'bodies and the 28 private algorithms are not in the graph. No stock '
            'forward and no mathlib proof was checked.'
        ),
    )
    text = json.dumps(document, indent=2, sort_keys=True) + '\n'
    destination = OUTPUT if h768_fits else OUTPUT.with_name('small-bank-joint.json')
    destination.write_text(text)
    print('wrote', destination.name, flush=True)
    print(json.dumps(dict(
        predicted_match_gates=ranged['predicted_match_gates'],
        exclusive_keys=plan['exclusive_keys'],
        factored_classes=ranged['factored_classes'],
        factored_groups=ranged['factored_groups'],
        ffn_units=report['ffn_units'],
        equality_graph_layers=report['equality_graph_layers'],
        residual_graph_layers=report['residual_graph_layers'],
        dispatch_waves=report['dispatch_waves'],
        dispatch_wave_units=report['dispatch_wave_units'],
        graph_layers=report['graph_layers'],
        layers=shape['layers'],
        peak=report['peak_live_dims'],
        slots=report['allocated_slots'],
        channels=shape['channels_needed'],
        channel_gate_h768=shape['channel_gate'],
        dense=shape['logical_dense_parameters'],
        dense_gate_h768=shape['dense_gate'],
        selected_hidden=report['selected_shape']['hidden'],
        selected_channel_gate=report['channel_gate'],
        selected_dense_gate=report['dense_gate'],
        residual_lowered=report['residual_lowered'],
        tail_attached=report['tail_attached'],
        head_layers=report['head_layers'],
        memory_layers_included=report['memory_layers_included'],
        token_features=observed.get('token_features'),
        joint_dense=joint['logical_dense_parameters'],
        joint_dense_gate=joint['dense_gate'],
        joint_over=joint['over_dense_limit_by'],
        joint_within_ideal=joint['within_ideal_dense_limit'],
        joint_within_absolute=joint['within_absolute_dense_limit'],
        mathlib_joint_dense=mathlib_joint['logical_dense_parameters'],
        mathlib_joint_dense_gate=mathlib_joint['dense_gate'],
        mathlib_joint_over=mathlib_joint['over_dense_limit_by'],
        mathlib_memory_layers=mathlib_joint['memory_layers'],
        mathlib_within_absolute=mathlib_joint['within_absolute_dense_limit'],
        shapes=[
            dict(
                hidden=item['hidden'],
                channels=item['channels_needed'],
                channel_gate=item['channel_gate'],
                dense=item['logical_dense_parameters'],
                dense_gate=item['dense_gate'],
                within_ideal=item['logical_dense_parameters'] <= IDEAL_DENSE_LIMIT,
                within_absolute=item['logical_dense_parameters'] < ABSOLUTE_DENSE_LIMIT,
            )
            for item in report['candidate_shapes']
        ],
        samples=len(samples),
    ), sort_keys=True))


if __name__ == '__main__':
    main()
