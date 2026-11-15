"""Compile-time operand contracts for complete, source-derived control regions.

This is an accounting/lowering IR, never an inference interpreter. Existing
family-factored regions are retained as composition pieces; they must not be
reported as full semantic transitions or as a verified native schedule.
"""
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class RegionContract:
    index: int
    source_effects: tuple
    families: tuple
    inputs: tuple
    updates: tuple
    bank_writes: tuple
    dag_nodes: int
    operations: tuple
    template_sha256: str

    def summary(self, widths):
        state = tuple(n for n in self.inputs if not n.startswith('read/'))
        state_union = set(state) | set(self.updates)
        return dict(index=self.index, source_effects=len(self.source_effects),
                    families=self.families, state_read_fields=len(state),
                    state_read_bits=sum(widths[n] for n in state),
                    read_port_fields=len(self.inputs)-len(state),
                    candidate_update_fields=len(self.updates),
                    simultaneous_access_state_fields=len(state_union),
                    simultaneous_access_state_bits=sum(widths[n] for n in state_union),
                    bank_writes=self.bank_writes, dag_nodes=self.dag_nodes,
                    operations=dict(self.operations), template_sha256=self.template_sha256)


def validate_sources(compiler):
    """Reject a stale trusted-local compiler cache before reading its contracts."""
    from .traversal_machine import MachineConfig
    if compiler.cfg != MachineConfig(heap=512, stack=32, context=8, constants=4, word_bits=16, fuel=8192):
        raise ValueError('contract cache does not preserve the original bounded domain')
    if len(compiler.families) != 73 or len(compiler.effects) != 6454:
        raise ValueError('contract cache does not contain the complete current rule set')
    for family in compiler.families:
        path = Path(__file__).parent / family['source']
        if hashlib.sha256(path.read_bytes()).hexdigest() != family['sha256']:
            raise ValueError('stale rule source in contract cache: '+family['source'])


def compile_contracts(compiler, partition):
    """Retain every factored piece, its source aliases and operand dependencies.

    Alpha-renaming private input/output fields exposes reusable *compile-time*
    DAG templates. This neither lowers those DAGs to weights nor claims their
    count is a complete checker control store. Control routing/dispatch, prefix
    validation, frame ownership and multi-piece composition still need lowering.
    """
    nodes = compiler.g.nodes
    contracts = []
    for index, leaf in enumerate(partition.leaves):
        reachable, inputs, updates, writes = set(), set(), set(), []
        memo, variable_ids, canonical = {}, {}, []

        def variable(name, width):
            # Read-port names designate independent external bank operands;
            # ordinary logical fields are alpha-renamed with aliasing retained.
            key = ('read' if name.startswith('read/') else 'state', name)
            if key not in variable_ids:
                variable_ids[key] = len(variable_ids)
            return (key[0], variable_ids[key], width)

        def visit(i):
            if i in memo:
                return memo[i]
            reachable.add(i)
            node = nodes[i]
            args = tuple(visit(child) for child in node.args)
            if node.op == 'input':
                inputs.add(node.data)
                value = variable(node.data, node.width)
            else:
                value = (node.op, node.width, args, node.data)
            # Intern canonical nodes; repeated expressions stay a shared DAG.
            encoded = json.dumps(value, separators=(',', ':'))
            if encoded not in canonical_ids:
                canonical_ids[encoded] = len(canonical)
                canonical.append(value)
            memo[i] = canonical_ids[encoded]
            return memo[i]

        canonical_ids = {}
        effects = []
        for source_index, effect in leaf['effects']:
            guard = visit(effect.guard)
            if effect.kind == 'merge_fields':
                values = []
                for name, node in effect.values:
                    updates.add(name)
                    # Use the same namespace for an old read and its new value.
                    destination = variable(name, nodes[node].width)
                    values.append((destination, visit(node)))
                effects.append((effect.kind, guard, values))
            else:
                writes.append(effect.kind.removeprefix('write_'))
                effects.append((effect.kind, guard, visit(effect.address),
                                tuple(visit(node) for node in effect.values)))
        shape = json.dumps((canonical, effects), separators=(',', ':')).encode()
        aliases = tuple(sorted(leaf['aliases'] | {i for i, e in leaf['effects']}))
        families = tuple(sorted({compiler.effects[i].family for i in aliases}))
        operations = Counter(nodes[i].op for i in reachable if nodes[i].op not in ('input', 'const'))
        contracts.append(RegionContract(index, aliases, families, tuple(sorted(inputs)),
                                        tuple(sorted(updates)), tuple(sorted(set(writes))),
                                        len(reachable), tuple(sorted(operations.items())),
                                        hashlib.sha256(shape).hexdigest()))
    return tuple(contracts)


def account_contracts(compiler, partition, contracts):
    widths = dict(compiler.layout.fields)
    rows = [c.summary(widths) for c in contracts]
    covered = set().union(*(set(c.source_effects) for c in contracts),
                          *(set(v) for v in partition.region_aliases.values()),
                          {i for i, e in partition.prefix + partition.fallback})
    missing = sorted(set(range(len(compiler.effects))) - covered)
    if missing:
        raise ValueError('source effects missing from contract composition: '+str(missing))
    maximum = max(rows, key=lambda r: r['simultaneous_access_state_bits'])
    return dict(format='leanputer.source-region-operand-contracts.v1',
                source_rule_families=len(compiler.families), source_effects=len(compiler.effects),
                source_effects_accounted=len(covered), source_effects_missing=missing,
                family_factored_regions=len(rows),
                alpha_renamed_compile_time_templates=len({c.template_sha256 for c in contracts}),
                dispatch_nodes=len(partition.dispatch), prefix_effects=len(partition.prefix),
                max_state_read_fields=max(r['state_read_fields'] for r in rows),
                max_simultaneous_access_state_fields=max(r['simultaneous_access_state_fields'] for r in rows),
                max_simultaneous_access_state_bits=maximum['simultaneous_access_state_bits'],
                widest_region=maximum,
                max_candidate_update_fields=max(r['candidate_update_fields'] for r in rows),
                max_region_dag_nodes=max(r['dag_nodes'] for r in rows),
                full_transition_descriptor_count=None, full_transition_composition_verified=False,
                cross_transition_liveness_verified=False, frame_ownership_verified=False,
                native_schedule_verified=False, stock_emitted=False, joint_delivery_gate=False,
                evidence_scope='Static dependency unions, including alternative data guards; not liveness bounds or stock execution')
