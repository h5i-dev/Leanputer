"""Measure the shared expression walk alone and on one equality-key allocate.

No torch model is constructed. The concatenated dense figure is not an allocate.
Walk inputs are born at the tail barrier. Residual-only control fields are born
after the equality waves. Neither delay drops a rule.
"""
import json
import pickle
import random
from pathlib import Path

from leanputer.kernel.arena import Tag
from leanputer.kernel.semantic_body import (
    ORIGINAL_CONTEXT,
    ORIGINAL_DECLARATIONS,
    ORIGINAL_EXPRESSIONS,
    ORIGINAL_STACK,
    _lower_walk,
    build_checked_index_add,
    build_shared_expression_walk,
    kept_output_dims,
    source_storage_report,
)
from leanputer.kernel.semantic_dispatch import dispatch_account
from leanputer.kernel.semantic_step_circuit import build_equality_key_select, partition_equality_keys
from leanputer.kernel.transition_contracts import validate_sources
from leanputer.kernel.semantic_operators import CALL_LIMIT, DENSE_LIMIT
from leanputer.kernel.traversal_machine import Reason


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / 'benchmarks' / 'kernel-macro-budget' / 'equality-key-select.json'
OUTPUT = ROOT / 'benchmarks' / 'kernel-macro-budget' / 'semantic-body.json'


def _walk_samples(width):
    mask = (1 << width) - 1
    samples = []
    for tag in [0, 15, *(int(item) for item in Tag)]:
        for index in range(4):
            for depth in (0, 1, mask):
                samples.append(dict(
                    tag=tag, child_index=index, a=1, b=2, c=3, depth=depth,
                    require_child=1, service_gap=0, gap_reason=0,
                ))
    samples.append(dict(
        tag=int(Tag.LAM), child_index=1, a=4, b=5, c=6, depth=mask,
        require_child=1, service_gap=1, gap_reason=int(Reason.GAP_CONVERSION),
    ))
    return samples


def _add_samples(width):
    mask = (1 << width) - 1
    corners = [0, 1, mask - 1, mask]
    samples = [{'x': left, 'y': right} for left in corners for right in corners]
    rng = random.Random(11)
    for _ in range(16):
        samples.append({'x': rng.randrange(mask + 1), 'y': rng.randrange(mask + 1)})
    return samples


def _control_samples(plan, widths, fields):
    control = [{field: 0 for field in fields}, {field: (1 << widths[field]) - 1 for field in fields}]
    for item in plan['classes']:
        positive = {field: 0 for field in fields}
        positive.update(item['members'][0]['mapping'])
        control.append(positive)
        negative = dict(positive)
        field = item['fields'][0]
        negative[field] = (negative[field] + 1) & ((1 << widths[field]) - 1)
        control.append(negative)
    rng = random.Random(11)
    for _ in range(4):
        control.append({field: rng.randrange(1 << widths[field]) for field in fields})
    return control


def _selector_inputs():
    program = pickle.loads(Path(
        '/mnt/scratch/leanputer-runs/architecture-budget/direct-preflight-control-offline.pickle'
    ).read_bytes())
    compiler = program.store.compiler
    validate_sources(compiler)
    effects = [effect for _, effect in program.store.contract_plan.body]
    accounted = dispatch_account(compiler, effects)
    names = {index: name for index, name in accounted['variables'].items()}
    nodes = compiler.g.nodes
    widths = {index: nodes[index].width for index in names}
    predicates = [handler['predicate'] for handler in accounted['handlers']]
    plan = partition_equality_keys(predicates)
    fields = sorted({field for item in plan['classes'] for field in item['fields']})
    control = _control_samples(plan, widths, fields)
    residual = [predicates[index] for index in plan['residual']]
    for predicate in residual:
        mentioned = set()

        def walk(node):
            if isinstance(node, int):
                return
            if node[0] == 'range':
                mentioned.add(node[1])
            elif node[0] in ('and', 'or'):
                for child in node[1]:
                    walk(child)

        walk(predicate)
        for field in mentioned:
            for sample in control:
                sample.setdefault(field, 0)
    return names, widths, plan, control, residual


def _joint_selector_and_walk(walk_samples, names, widths, plan, control, residual):
    """One allocate of the equality-key selector plus the expression walk."""

    def tail(builder):
        return kept_output_dims(_lower_walk(
            builder, 16, walk_samples, 'walk', input_level=builder.barrier,
        ))

    equality = build_equality_key_select(
        names, widths, plan, control, wave=96, placement_cap=96, tail=tail,
    )
    equality['one_allocate'] = True
    equality['residual_predicates_not_in_this_graph'] = len(residual)
    with_residual = build_equality_key_select(
        names, widths, plan, control, wave=96, placement_cap=96,
        residual_predicates=residual, tail=tail,
    )
    with_residual['one_allocate'] = True
    return equality, with_residual


def main():
    walk_samples = _walk_samples(16)
    walk = build_shared_expression_walk(16, walk_samples)
    added = build_checked_index_add(16, _add_samples(16))
    names, widths, plan, control, residual = _selector_inputs()
    joint, joint_residual = _joint_selector_and_walk(
        walk_samples, names, widths, plan, control, residual,
    )
    selector = json.loads(SELECTOR.read_text())
    equality = selector['equality_key_select']
    equality_layers = equality['selected_shape']['graph_layers']
    equality_dense = equality['selected_shape']['logical_dense_parameters']
    body_layers = walk['graph_layers']
    # One stack would be these graph layers plus one clear and one feedback.
    # The two graphs were allocated separately, so this is not that stack.
    from leanputer.kernel.semantic_step_circuit import dense_parameters
    stacked_layers = equality_layers + body_layers + equality['selected_shape']['scratch_clear_layers'] + 1
    stacked_dense = dense_parameters(768, 256, stacked_layers)
    storage = {
        'original': source_storage_report(
            ORIGINAL_EXPRESSIONS, ORIGINAL_DECLARATIONS, ORIGINAL_STACK, ORIGINAL_CONTEXT,
        ),
        'one_extra_expression_row': source_storage_report(
            ORIGINAL_EXPRESSIONS + 1, ORIGINAL_DECLARATIONS, ORIGINAL_STACK, ORIGINAL_CONTEXT,
        ),
        'one_extra_declaration': source_storage_report(
            ORIGINAL_EXPRESSIONS, ORIGINAL_DECLARATIONS + 1, ORIGINAL_STACK, ORIGINAL_CONTEXT,
        ),
    }
    report = dict(
        format='leanputer.semantic-body.v1',
        full_checker=False,
        joint_delivery_gate=False,
        stock_emitted=False,
        operator_body_included=False,
        proof_checking_not_proof_discovery=True,
        mathlib_theorems_checked=0,
        working_dense_limit=DENSE_LIMIT,
        working_call_limit=CALL_LIMIT,
        historical_tui_dense_limit=100_000_000,
        historical_tui_call_limit=5_000,
        historical_limits_are_not_success=True,
        expression_walk=walk,
        checked_index_add=added,
        equality_selector_plus_walk=joint,
        equality_residual_and_walk=joint_residual,
        separate_from_equality_selector=dict(
            equality_graph_layers=equality_layers,
            equality_logical_dense_parameters=equality_dense,
            walk_graph_layers=body_layers,
            stacked_layers_if_concatenated=stacked_layers,
            stacked_dense_if_concatenated=stacked_dense,
            stacked_dense_gate=stacked_dense <= DENSE_LIMIT,
            placed_together=False,
            note=(
                'Selector and walk were allocated as two graphs. '
                'The concatenated dense count includes embedding once and is not an allocate() result.'
            ),
        ),
        storage=storage,
        call_projection_if_one_forward_per_transition=selector['call_projection_if_one_forward_per_transition'],
        call_projection_is_not_a_stock_measurement=True,
    )
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def _hidden(report, hidden):
        for shape in report['candidate_shapes']:
            if shape['hidden'] == hidden:
                return shape
        raise KeyError(hidden)

    joint_h768 = _hidden(joint, 768)
    residual_h768 = _hidden(joint_residual, 768)
    print(json.dumps(dict(
        joint_layers=joint['graph_layers'],
        joint_units=joint['ffn_units'],
        joint_dense=joint['selected_shape']['logical_dense_parameters'],
        joint_channels=joint['channel_gate'],
        joint_dense_gate=joint['dense_gate'],
        residual_joint_layers=joint_residual['graph_layers'],
        residual_joint_dense=joint_residual['selected_shape']['logical_dense_parameters'],
        residual_joint_dense_gate=joint_residual['dense_gate'],
        residual_joint_channel_gate=joint_residual['channel_gate'],
        residual_joint_channels_needed=joint_residual['selected_shape']['channels_needed'],
        residual_joint_peak=joint_residual['peak_live_dims'],
        residual_joint_slots=joint_residual['allocated_slots'],
        residual_only_fields=joint_residual['residual_only_fields'],
        h768_joint_dense=joint_h768['logical_dense_parameters'],
        h768_joint_channels_needed=joint_h768['channels_needed'],
        h768_joint_channel_gate=joint_h768['channel_gate'],
        h768_joint_dense_gate=joint_h768['dense_gate'],
        h768_joint_layers=joint_h768['layers'],
        h768_residual_dense=residual_h768['logical_dense_parameters'],
        h768_residual_channels_needed=residual_h768['channels_needed'],
        h768_residual_channel_gate=residual_h768['channel_gate'],
        h768_residual_dense_gate=residual_h768['dense_gate'],
        h768_residual_layers=residual_h768['layers'],
        h768_residual_graph_layers=residual_h768['graph_layers'],
        joint_slots=joint['allocated_slots'],
        joint_peak=joint['peak_live_dims'],
        walk_layers=walk['graph_layers'],
        walk_units=walk['ffn_units'],
        walk_dense=walk['selected_shape']['logical_dense_parameters'],
        walk_channels=walk['channel_gate'],
        add_layers=added['graph_layers'],
        add_units=added['ffn_units'],
        add_dense=added['selected_shape']['logical_dense_parameters'],
        stacked_dense=stacked_dense,
        stacked_gate=stacked_dense <= DENSE_LIMIT,
        placed_together=False,
        samples=walk['boolean_samples'],
    ), sort_keys=True))


if __name__ == '__main__':
    main()
