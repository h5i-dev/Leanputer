"""Allocate continuation-range dispatch, residuals, and the expression walk once.

The handler identity is the live control key. No torch model is constructed.
The unplaced memory sum is not an allocate result.
"""
import json
from pathlib import Path

from leanputer.kernel.semantic_body import kept_output_dims, _lower_walk
from leanputer.kernel.semantic_operators import CALL_LIMIT, DENSE_LIMIT
from leanputer.kernel.semantic_step_circuit import continuation_range_plan, build_continuation_range_select
from leanputer.kernel.source_capacity import storage_layout, unplaced_logic_joint
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

    def tail(builder):
        return kept_output_dims(_lower_walk(
            builder, 16, walk_samples, 'walk', input_level=builder.barrier,
        ))

    print('predicted_match_gates', ranged['predicted_match_gates'], 'samples', len(samples), flush=True)
    report = build_continuation_range_select(
        names, widths, plan, samples, wave=96, placement_cap=96,
        residual_predicates=residual, tail=tail,
    )
    shape = next(item for item in report['candidate_shapes'] if item['hidden'] == 768)
    storage = storage_layout(512, 4, stack=32, context=8)
    joint = unplaced_logic_joint(
        storage, shape['layers'], shape['logical_dense_parameters'],
    )
    recorded = json.loads((
        ROOT / 'benchmarks' / 'mathlib-v4.31.0' / 'fabf563-addressable' / 'capacity.json'
    ).read_text())
    bound = recorded['bounding_domain']
    mathlib_storage = storage_layout(
        bound['expression_rows'], bound['declaration_slots'], stack=32, context=8,
        level_rows=bound['level_rows'], vector_refs=bound['vector_refs'],
        vector_cells=bound['vector_cells'],
    )
    mathlib_joint = unplaced_logic_joint(
        mathlib_storage, shape['layers'], shape['logical_dense_parameters'],
    )
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
        predicted_match_gates=ranged['predicted_match_gates'],
        exclusive_keys=plan['exclusive_keys'],
        boolean_samples=len(samples),
        continuation_range=report,
        original_domain_memory_unplaced=joint,
        mathlib_bounding_memory_unplaced=mathlib_joint,
        note=(
            'One allocate of continuation-range hits, the 65 residual predicates, '
            'and the shared expression walk. The handler identity is the live '
            'control key. Match gates are fewer than one fused equality per key; '
            'republish and the walk add units. Memory sums add unplaced '
            'linear-attention layers beside this inert stack and are not allocate '
            'results. No stock forward and no mathlib proof was checked.'
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
