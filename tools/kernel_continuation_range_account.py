"""Allocate continuation-range dispatch, residuals, and the expression walk once.

The handler identity is the live control key. No torch model is constructed.
The unplaced memory sum is not an allocate result.
"""
import json
from pathlib import Path

from leanputer.kernel.arena import Tag
from leanputer.kernel.semantic_body import (
    _attach_expression_page,
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


def _remaining_joint(storage, shape, placed_expression_layers):
    """Add banks that are not already a head in the allocated graph.

    The sum is not an allocate result. Vector cells stay unplaced.
    """
    if placed_expression_layers > storage['expression_layers']:
        raise ValueError('placed expression page is larger than the domain')
    extra = storage['memory_layers'] - placed_expression_layers
    layers = shape['layers'] + extra
    gdn = shape['memory_layers_included'] + extra
    dense = dense_parameters(shape['hidden'], MODEL_INTERMEDIATE, layers, gdn_layers=gdn)
    vectors_open = storage['vector_cells'] > 0 and not storage['vector_bank_placed']
    return dict(
        placed_graph=False,
        stock_emitted=False,
        mathlib_theorems_checked=0,
        proof_checked=False,
        logic_layers=shape['layers'],
        logic_logical_dense_parameters=shape['logical_dense_parameters'],
        expression_layers_covered=placed_expression_layers,
        memory_layers_unplaced=extra,
        memory_layers=gdn,
        layers=layers,
        logical_dense_parameters=dense,
        dense_gate=(
            dense <= DENSE_LIMIT
            and not storage['exceeds_word_reference']
            and not vectors_open
        ),
        exceeds_word_reference=storage['exceeds_word_reference'],
        vector_cells_unplaced=vectors_open,
        over_dense_limit_by=max(0, dense - DENSE_LIMIT),
        working_dense_limit=DENSE_LIMIT,
        note=(
            'The allocated graph contains the expression page. Remaining '
            'level and small-bank layers are added beside it. Vector cells '
            'are not in this sum. Not a stock forward.'
        ),
    )


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

    def tail(builder):
        level = builder.barrier
        outputs = _lower_walk(
            builder, 16, walk_samples, 'walk', input_level=level,
            address_retained=512,
        )
        selected = _attach_expression_page(
            builder, outputs['address'], 512, page_samples, outputs['inputs'], level,
        )
        keep = kept_output_dims(outputs)
        for bit in selected:
            keep |= _expr_dims(bit)
        return keep

    print('predicted_match_gates', ranged['predicted_match_gates'], 'samples', len(samples), flush=True)
    report = build_continuation_range_select(
        names, widths, plan, samples, wave=96, placement_cap=96,
        residual_predicates=residual, tail=tail,
    )
    if report['memory_layers_included'] != 1:
        raise ValueError('the expression page did not place one linear-attention layer')
    shape = next(item for item in report['candidate_shapes'] if item['hidden'] == 768)
    storage = storage_layout(512, 4, stack=32, context=8)
    joint = _remaining_joint(storage, shape, placed_expression_layers=1)
    recorded = json.loads((
        ROOT / 'benchmarks' / 'mathlib-v4.31.0' / 'fabf563-addressable' / 'capacity.json'
    ).read_text())
    bound = recorded['bounding_domain']
    mathlib_storage = storage_layout(
        bound['expression_rows'], bound['declaration_slots'], stack=32, context=8,
        level_rows=bound['level_rows'], vector_refs=bound['vector_refs'],
        vector_cells=bound['vector_cells'],
    )
    mathlib_joint = _remaining_joint(mathlib_storage, shape, placed_expression_layers=1)
    document = dict(
        format='leanputer.continuation-range.v1',
        full_checker=False,
        joint_delivery_gate=False,
        stock_emitted=False,
        operator_body_included=False,
        proof_checking_not_proof_discovery=True,
        mathlib_theorems_checked=0,
        working_dense_limit=DENSE_LIMIT,
        working_call_limit=CALL_LIMIT,
        handler_identity='live control key',
        expression_address_retained=512,
        expression_page_read=True,
        expression_page_rows=512,
        predicted_match_gates=ranged['predicted_match_gates'],
        exclusive_keys=plan['exclusive_keys'],
        boolean_samples=len(samples),
        continuation_range=report,
        original_domain_memory_unplaced=joint,
        mathlib_bounding_memory_unplaced=mathlib_joint,
        note=(
            'One allocate of continuation-range hits, the 65 residual predicates, '
            'the shared expression walk, and one expression page. The page stores '
            'tag, a, b, and c and is read at the walk child. The handler identity '
            'is the live control key. Head layers are priced as linear attention. '
            'The small bank is not in the graph. No stock forward and no mathlib '
            'proof was checked.'
        ),
    )
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')
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
        joint_dense=joint['logical_dense_parameters'],
        joint_dense_gate=joint['dense_gate'],
        joint_over=joint['over_dense_limit_by'],
        mathlib_joint_dense=mathlib_joint['logical_dense_parameters'],
        mathlib_joint_dense_gate=mathlib_joint['dense_gate'],
        mathlib_joint_over=mathlib_joint['over_dense_limit_by'],
        mathlib_memory_layers=mathlib_joint['memory_layers'],
        samples=len(samples),
    ), sort_keys=True))


if __name__ == '__main__':
    main()
