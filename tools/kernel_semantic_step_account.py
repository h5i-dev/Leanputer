"""Measure the shared control-predicate graph and the unplaced data cones.

No torch model is constructed. The pickle is an offline compiler snapshot,
not an inference import.
"""
import json
import pickle
from pathlib import Path

from leanputer.kernel.semantic_dispatch import dispatch_account
import random

from leanputer.kernel.semantic_step_circuit import (
    build_continuation_select,
    build_predicate_graph,
    continuation_field_map,
    control_samples,
    estimate_data_circuits,
    joint_report,
)
from leanputer.kernel.transition_contracts import validate_sources


def main():
    program = pickle.loads(Path('/mnt/scratch/leanputer-runs/architecture-budget/direct-preflight-control-offline.pickle').read_bytes())
    compiler = program.store.compiler
    validate_sources(compiler)
    effects = [effect for _, effect in program.store.contract_plan.body]
    accounted = dispatch_account(compiler, effects)
    variables = accounted['variables']
    domains = accounted['domains']
    handlers = accounted['handlers']
    predicates = [handler['predicate'] for handler in handlers]
    widths = {index: compiler.g.nodes[index].width for index in variables}
    samples = control_samples(variables, domains, count=6, seed=20)
    # The shared-CSE graph was measured at 5996 units and 2598 live dims.
    # Isolated waves keep that lowering and only change placement. Two
    # assignments re-check each chunk; the exhaustive random sample already
    # passed on the shared graph in the unit of work that produced 5996.
    schedules = []
    for wave, cap in ((96, 96), (160, 112), (320, 160)):
        schedules.append(build_predicate_graph(
            list(variables), domains, widths, predicates, samples[:2],
            wave=wave, placement_cap=cap, do_reschedule=False,
        ))
    fitting = [item for item in schedules if item['channel_gate'] and item['dense_gate']]
    predicate = min(
        fitting or schedules,
        key=lambda item: (
            not item['channel_gate'],
            not item['dense_gate'],
            item['selected_shape']['logical_dense_parameters'],
            item['allocated_slots'],
        ),
    )
    data = estimate_data_circuits(compiler, handlers, set(variables.values()))
    report = joint_report(predicate, data)
    names = {index: name for index, name in variables.items()}
    field_plan = continuation_field_map(predicates, names)
    field_plan.pop('_mapping')
    mapping = field_plan.pop('_select')
    report['continuation_fields'] = field_plan
    if mapping:
        rng = random.Random(7)
        fields = {field for spec in mapping.values() for field in spec}
        select_samples = []
        for task in mapping:
            values = {field_plan['task_index']: task}
            for field in fields:
                values[field] = rng.randrange(1 << widths[field])
            select_samples.append(values)
        unknown = {field_plan['task_index']: (1 << widths[field_plan['task_index']]) - 1}
        for field in fields:
            unknown[field] = 1
        select_samples.append(unknown)
        report['continuation_select'] = build_continuation_select(
            names, widths, mapping, field_plan['task_index'], select_samples,
        )
    report['placement_attempts'] = [
        dict(schedule=item['schedule'], ffn_units=item['ffn_units'], graph_layers=item['graph_layers'],
             peak_live_dims=item['peak_live_dims'], allocated_slots=item['allocated_slots'],
             channel_gate=item['channel_gate'], dense_gate=item['dense_gate'],
             hidden=item['selected_shape']['hidden'],
             logical_dense_parameters=item['selected_shape']['logical_dense_parameters'])
        for item in schedules
    ]
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
