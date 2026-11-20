"""Measure equality-key handler selection and one shared update slot.

No torch model is constructed. The pickle is an offline compiler snapshot,
not an inference import. The selector is not a source checker.
"""
import json
import pickle
import random
from pathlib import Path

from leanputer.kernel.semantic_dispatch import dispatch_account
from leanputer.kernel.semantic_operators import CALL_LIMIT, DENSE_LIMIT
from leanputer.kernel.semantic_step_circuit import (
    MODEL_INTERMEDIATE,
    build_equality_key_select,
    build_predicate_graph,
    build_source_lane,
    control_samples,
    dense_parameters,
    partition_equality_keys,
    update_descriptor_account,
)
from leanputer.kernel.transition_contracts import validate_sources


def _mentioned(predicate, found):
    if isinstance(predicate, int):
        return
    if predicate[0] == 'range':
        found.add(predicate[1])
    elif predicate[0] in ('and', 'or'):
        for child in predicate[1]:
            _mentioned(child, found)


def _stack(hidden, graph_layers, memory_layers, kept_outputs):
    """Layer arithmetic for graphs that were not placed together."""
    ballast = hidden // 64
    clear_layers = max(1, (max(hidden - ballast - kept_outputs, 0) + MODEL_INTERMEDIATE - 1) // MODEL_INTERMEDIATE)
    layers = graph_layers + memory_layers + clear_layers + 1
    dense = dense_parameters(hidden, MODEL_INTERMEDIATE, layers, gdn_layers=memory_layers)
    return dict(
        hidden=hidden,
        graph_layers=graph_layers,
        scratch_clear_layers=clear_layers,
        feedback_layer=1,
        memory_layers=memory_layers,
        layers=layers,
        logical_dense_parameters=dense,
        dense_gate=dense <= DENSE_LIMIT,
        placed_graph=False,
    )


def main():
    program = pickle.loads(Path(
        '/mnt/scratch/leanputer-runs/architecture-budget/direct-preflight-control-offline.pickle'
    ).read_bytes())
    compiler = program.store.compiler
    validate_sources(compiler)
    effects = [effect for _, effect in program.store.contract_plan.body]
    accounted = dispatch_account(compiler, effects)
    handlers = accounted['handlers']
    names = {index: name for index, name in accounted['variables'].items()}
    nodes = compiler.g.nodes
    widths = {index: nodes[index].width for index in names}
    predicates = [handler['predicate'] for handler in handlers]
    plan = partition_equality_keys(predicates)
    fields = sorted({field for item in plan['classes'] for field in item['fields']})
    samples = [{field: 0 for field in fields}, {field: (1 << widths[field]) - 1 for field in fields}]
    for item in plan['classes']:
        positive = {field: 0 for field in fields}
        positive.update(item['members'][0]['mapping'])
        samples.append(positive)
        negative = dict(positive)
        field = item['fields'][0]
        negative[field] = (negative[field] + 1) & ((1 << widths[field]) - 1)
        samples.append(negative)
    rng = random.Random(11)
    for _ in range(4):
        samples.append({field: rng.randrange(1 << widths[field]) for field in fields})
    residual_predicates = [predicates[index] for index in plan['residual']]
    residual_fields = set()
    for predicate in residual_predicates:
        _mentioned(predicate, residual_fields)
    for field in residual_fields:
        for sample in samples:
            sample.setdefault(field, 0)
    residual_fields = sorted(residual_fields)
    # Handover needs a free MLP row per value that dies on that sublayer.
    # A wave as wide as the placement cap cannot reuse slots.
    selector = build_equality_key_select(names, widths, plan, samples, wave=96, placement_cap=96)
    combined = build_equality_key_select(
        names, widths, plan, samples, wave=96, placement_cap=96,
        residual_predicates=residual_predicates,
    )
    residual = build_predicate_graph(
        residual_fields,
        {field: accounted['domains'][field] for field in residual_fields},
        {field: widths[field] for field in residual_fields},
        residual_predicates,
        control_samples(residual_fields, accounted['domains'], count=4, seed=11),
        wave=0,
        placement_cap=96,
        do_reschedule=False,
    )
    lane_rng = random.Random(5)
    lane_samples = []
    for chosen in range(8):
        lane_samples.append(dict(
            select=[1 if index == chosen else 0 for index in range(8)],
            words=[lane_rng.randrange(1 << 16) for _ in range(8)],
        ))
    lane = build_source_lane(8, 16, lane_samples, wave=4, placement_cap=160)
    shared = [handler for handler in handlers if handler['schedule'] == 'shared']
    private = [handler for handler in handlers if handler['schedule'] != 'shared']
    shared_descriptor = update_descriptor_account(nodes, shared)
    private_descriptor = update_descriptor_account(nodes, private)
    # One measured slot, reused serially for every write of the widest shared
    # handler. Five handlers can be true, so the call-budget schedule is five
    # parallel copies or five serial passes. Neither product was placed.
    slot_layers = lane['graph_layers']
    widest = shared_descriptor['data_slots_max']
    # Serial replay of one measured lane is not a fitting body: it is recorded
    # so a later schedule cannot ignore the widest handler's data slots.
    serial_layers = selector['graph_layers'] + residual['graph_layers'] + slot_layers * widest
    five_serial_layers = selector['graph_layers'] + residual['graph_layers'] + slot_layers * widest * 5
    need = max(
        selector['selected_shape']['channels_needed'],
        residual['selected_shape']['channels_needed'],
        lane['selected_shape']['channels_needed'],
    )
    hidden = next((candidate for candidate in (768, 896, 1024) if candidate >= need), 1024)
    kept = max(selector['outputs_kept'], lane['width'])
    one_handler = _stack(hidden, serial_layers, 0, kept)
    one_handler_with_memory = _stack(hidden, serial_layers, 8, kept)
    five_handlers = _stack(hidden, five_serial_layers, 0, kept)
    report = dict(
        format='leanputer.equality-key-select.v1',
        full_checker=False,
        stock_emitted=False,
        joint_delivery_gate=False,
        operator_body_included=False,
        memory_placed=False,
        private_algorithms_placed=False,
        working_dense_limit=DENSE_LIMIT,
        working_call_limit=CALL_LIMIT,
        historical_tui_dense_limit=100_000_000,
        historical_tui_call_limit=5_000,
        historical_limits_are_not_success=True,
        equality_key_select=selector,
        equality_key_select_with_residual=dict(
            ffn_units=combined['ffn_units'],
            graph_layers=combined['graph_layers'],
            peak_live_dims=combined['peak_live_dims'],
            allocated_slots=combined['allocated_slots'],
            channel_gate=combined['channel_gate'],
            dense_gate=combined['dense_gate'],
            boolean_samples=combined['boolean_samples'],
            residual_lowered=combined['residual_lowered'],
            outputs_kept=combined['outputs_kept'],
            selected_shape=combined['selected_shape'],
            full_checker=False,
            operator_body_included=False,
        ),
        residual_control=dict(
            predicates=residual['predicates'],
            ffn_units=residual['ffn_units'],
            graph_layers=residual['graph_layers'],
            peak_live_dims=residual['peak_live_dims'],
            allocated_slots=residual['allocated_slots'],
            channel_gate=residual['channel_gate'],
            dense_gate=residual['dense_gate'],
            boolean_samples=residual['boolean_samples'],
            selected_shape=residual['selected_shape'],
            full_checker=False,
        ),
        source_lane=lane,
        shared_commit_descriptor=shared_descriptor,
        private_commit_descriptor=private_descriptor,
        private_algorithms=dict(
            handlers=accounted['report']['private_handlers'],
            by_operator=accounted['report']['private_handlers_by_operator'],
            data_depth_max=accounted['report']['data_depth_max'],
            private_residual_nodes=accounted['report']['private_residual_nodes'],
            private_circuit_units_with_cse=accounted['report']['private_circuit_units_with_cse'],
            placed_graph=False,
        ),
        extrapolated_schedule=dict(
            note='Selector, residual predicates, and one 8-source lane were placed separately. Slot replay counts are arithmetic on those measurements, not one allocated graph.',
            channels_needed=need,
            hidden=hidden,
            widest_shared_handler_slots=widest,
            one_handler_serial_no_memory=one_handler,
            one_handler_serial_illustrative_8_memory_layers=one_handler_with_memory,
            five_handler_serial_no_memory=five_handlers,
            placed_graph=False,
        ),
        call_projection_if_one_forward_per_transition={
            'boot': 22,
            'setup': 5,
            'current-general-source-empty-claim-id': 22 + 5 + 1316,
            'current-source-invalid-target': 22 + 5 + 1355,
        },
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
