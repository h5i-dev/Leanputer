"""Input-independent whole-register row layout for checker operators.

Every logical word keeps distinct permanent storage. This conservative layout
does not depend on unproved cross-call lifetimes or erase inactive old state.
Packing uses ALL source control regions, never a proof/source trace.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from .macro_budget import TransitionArchitecture


@dataclass(frozen=True)
class RegisterRows:
    globals: tuple
    rows: tuple

    def locations(self):
        return {name: (row, slot) for row, names in enumerate(self.rows)
                for slot, name in enumerate(names)}

    def touched_rows(self, fields):
        locations = self.locations()
        return tuple(sorted({locations[name][0] for name in fields if name in locations}))


def pack_register_rows(compiler, contracts, architecture=TransitionArchitecture(),global_policy='boundary'):
    names = tuple(name for name, width in compiler.layout.fields)
    if any(width != 16 for name, width in compiler.layout.fields):
        raise ValueError('joint layout requires preserving every original 16bit word')
    edges = [set(c.updates) | {n for n in c.inputs if not n.startswith('read/')}
             for c in contracts]
    frequency = Counter(n for edge in edges for n in edge)
    # Fixed checker boundary state and raw prefix operands, not input names.
    global_names = ['status', 'reason', 'fuel', 'free', 'mode', 'task', 'sp', 'x',
                    'arg_base', 'count', 'r', 'ctx', 'local_base', 'decl']
    if global_policy=='frequency':global_names=global_names[:10]
    elif global_policy!='boundary':raise ValueError('unknown complete-program global policy')
    candidates = sorted(set(names)-set(global_names), key=lambda n: (-frequency[n], n))
    global_names.extend(candidates[:architecture.global_words-len(global_names)])
    if len(global_names) != architecture.global_words:
        raise ValueError('global frame budget cannot hold fixed controller fields')
    globals_set = set(global_names)
    adjacency = defaultdict(Counter)
    for edge in edges:
        private = sorted(edge-globals_set)
        for a in private:
            adjacency[a].update(b for b in private if b != a)
    remaining = set(names)-globals_set
    rows = []
    while remaining:
        seed = min(remaining, key=lambda n: (-sum(adjacency[n].values()), n))
        row = [seed]
        remaining.remove(seed)
        score = Counter(adjacency[seed])
        while remaining and len(row) < architecture.frame_words:
            selected = min(remaining, key=lambda n: (-score[n], -frequency[n], n))
            row.append(selected)
            remaining.remove(selected)
            score.update(adjacency[selected])
        rows.append(tuple(row))
    layout = RegisterRows(tuple(global_names), tuple(rows))
    flattened = list(layout.globals) + [name for row in layout.rows for name in row]
    if len(flattened) != len(names) or set(flattened) != set(names):
        raise AssertionError('layout loses/aliases logical state')
    return layout


def account_layout(compiler, contracts, layout):
    widths = Counter(len(layout.touched_rows(set(c.updates) | set(c.inputs))) for c in contracts)
    locations = layout.locations()
    return dict(format='leanputer.checker-register-row-layout.v1',
                logical_words=len(compiler.layout.fields), global_words=len(layout.globals),
                row_words=28, rows=len(layout.rows), rf_key_capacity=128,
                globals=layout.globals, all_logical_words_distinct_and_retained=True,
                liveness_based_erasure=False, input_independent=True,
                all_rule_region_row_touch_histogram=dict(sorted(widths.items())),
                max_region_rows=max(widths),
                placement={name: [row, slot] for name, (row, slot) in locations.items()},
                source_call_counts=None, native_schedule_verified=False,
                frame_memory_operator_composition_verified=False,
                joint_delivery_gate=False)
