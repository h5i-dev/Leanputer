"""Fixed Lean-semantic operators for the stock checker.

These are the execution units selected by checker state. They are not word
opcodes and not a renamed copy of the 22-slot window. Rule modules stay
intact; this table only says which shared operator owns each family. A family
that does not match raises, so a new rule cannot disappear into a default.
"""
from collections import Counter, defaultdict

# Working gate for this redesign. The 2026-11-19 TUI also stated a looser
# <100,000,000 / <=5,000 gate. That looser pair is not the success threshold.
DENSE_LIMIT = 48_290_654
CALL_LIMIT = 4_000
# H768/I256/L65 baseline: 800.1316s check / 230432 forwards.
BASELINE_FORWARD_SECONDS = 800.1316303570056 / 230_432

OPERATORS = (
    'fetch_node',
    'binder_step',
    'reduce_step',
    'judge_step',
    'level_step',
    'commit_outcome',
)

_FAMILY_OPERATOR = {
    'traversal_transition': 'fetch_node',
    'occurrence_rules': 'fetch_node',
    'family_occurrence_rules': 'fetch_node',
    'expression_equal_rules': 'fetch_node',
    'application_ops_rules': 'fetch_node',
    'vector_splice_rules': 'fetch_node',
    'reverse_list_rules': 'fetch_node',
    'raw_prefix_rules': 'fetch_node',
    'open_prefix_rules': 'fetch_node',
    'telescope_rules': 'fetch_node',
    'name_rules': 'fetch_node',
    'name_path_rules': 'fetch_node',
    'name_intern_rules': 'fetch_node',
    'name_prefix_rules': 'fetch_node',
    'make_rec_name_rules': 'fetch_node',
    'decimal_rules': 'fetch_node',
    'binder_ops_rules': 'binder_step',
    'abstract_scope_rules': 'binder_step',
    'pi_parameters_rules': 'binder_step',
    'restore_scope_rules': 'binder_step',
    'generation_ops_rules': 'binder_step',
    'recursive_argument_rules': 'binder_step',
    'major_rules': 'reduce_step',
    'recursor_reduce_rules': 'reduce_step',
    'recursor_apply_rules': 'reduce_step',
    'projection_rules': 'reduce_step',
    'quotient_reduce_rules': 'reduce_step',
    'nat_reduce_rules': 'reduce_step',
    'nat_bridge_rules': 'reduce_step',
    'nat_offset_rules': 'reduce_step',
    'nat_bits_rules': 'reduce_step',
    'nat_high_rules': 'reduce_step',
    'string_bridge_rules': 'reduce_step',
    'string_rules': 'reduce_step',
    'inference_rules': 'judge_step',
    'conversion_rules': 'judge_step',
    'literal_type_rules': 'judge_step',
    'nat_literal_rules': 'judge_step',
    'bool_binding_rules': 'judge_step',
    'level_constructor_rules': 'level_step',
    'level_order_rules': 'level_step',
    'level_normalize_rules': 'level_step',
    'level_geq_rules': 'level_step',
    'formal_levels_rules': 'level_step',
    'source_rules': 'commit_outcome',
    'environment_rules': 'commit_outcome',
    'constant_rules': 'commit_outcome',
    'parameter_rules': 'commit_outcome',
    'header_rules': 'commit_outcome',
    'constructor_rules': 'commit_outcome',
    'declare_constructors_rules': 'commit_outcome',
    'elimination_rules': 'commit_outcome',
    'motive_rules': 'commit_outcome',
    'minor_rules': 'commit_outcome',
    'recursor_type_rules': 'commit_outcome',
    'recursor_rule_rules': 'commit_outcome',
    'assemble_recursors_rules': 'commit_outcome',
    'recursor_name_rules': 'commit_outcome',
    'recursor_claim_rules': 'commit_outcome',
    'claim_lookup_rules': 'commit_outcome',
    'core_names_rules': 'commit_outcome',
    'published_recursor_rules': 'commit_outcome',
    'block_flags_rules': 'commit_outcome',
    'positivity_rules': 'commit_outcome',
    'family_application_rules': 'commit_outcome',
    'prior_block_rules': 'commit_outcome',
    'nested_application_rules': 'commit_outcome',
    'nested_stage_rules': 'commit_outcome',
    'nested_copy_rules': 'commit_outcome',
    'nested_rewrite_rules': 'commit_outcome',
    'nested_restore_rules': 'commit_outcome',
    'nested_transaction_rules': 'commit_outcome',
    'quotient_rules': 'commit_outcome',
    'structure_info_rules': 'commit_outcome',
    'nat_name_rules': 'commit_outcome',
    'nat_bindings_rules': 'commit_outcome',
}


def operator_for(family):
    try:
        return _FAMILY_OPERATOR[family]
    except KeyError as error:
        raise ValueError(f'semantic operator map is missing rule family {family}') from error


def _walk(nodes, index, seen):
    stack = [index]
    while stack:
        cursor = stack.pop()
        if cursor in seen:
            continue
        seen.add(cursor)
        stack.extend(nodes[cursor].args)


def account(compiler):
    """Count typed nodes owned by each operator. This is not a stock forward count."""
    nodes = compiler.g.nodes
    families = [item['module'] for item in compiler.families]
    missing = [name for name in families if name not in _FAMILY_OPERATOR]
    if missing:
        raise ValueError('semantic operator map is missing rule families: ' + ', '.join(missing))
    owned = defaultdict(set)
    effects = Counter()
    for effect in compiler.effects:
        operator = operator_for(effect.family)
        effects[operator] += 1
        roots = [effect.guard]
        if effect.address >= 0:
            roots.append(effect.address)
        for value in effect.values:
            roots.append(value[1] if effect.kind == 'merge_fields' else value)
        for root in roots:
            _walk(nodes, root, owned[operator])
    shared = set.intersection(*(owned[name] for name in OPERATORS if owned[name])) if effects else set()
    union = set.union(*(owned[name] for name in OPERATORS if owned[name])) if effects else set()
    per_operator = {
        name: dict(effects=effects[name], typed_nodes=len(owned[name]),
                   ops=dict(Counter(nodes[index].op for index in owned[name])))
        for name in OPERATORS
    }
    # One stock forward per committed kernel transition, plus the measured
    # 22 boot prefill calls and 5 CUDA-graph setup calls. Valid/invalid
    # semantic counts are the preserved reference measurements.
    check_calls = {'current-general-source-empty-claim-id': 1316,
                   'current-source-invalid-target': 1355}
    totals = {name: 22 + 5 + steps for name, steps in check_calls.items()}
    report = dict(
        format='leanputer.semantic-operator-account.v1',
        operators=list(OPERATORS),
        rule_families=len(families),
        families_mapped=len(families),
        source_effects=len(compiler.effects),
        typed_nodes=len(nodes),
        typed_node_union=len(union),
        typed_nodes_shared_by_every_operator=len(shared),
        per_operator=per_operator,
        typed_ops=dict(Counter(node.op for node in nodes)),
        dense_limit=DENSE_LIMIT,
        call_limit=CALL_LIMIT,
        projected_total_calls_if_one_forward_per_semantic_step=totals,
        call_projection_fits=all(value <= CALL_LIMIT for value in totals.values()),
        baseline_seconds_per_forward=BASELINE_FORWARD_SECONDS,
        unrolled_neural_units_rejected=147402,
        stock_emitted=False,
        joint_delivery_gate=False,
        note='Typed-node counts are not dense parameters. Neural bit-blast of this same graph was 147402 units and does not fit. No stock model is emitted from this account.',
    )
    return report
