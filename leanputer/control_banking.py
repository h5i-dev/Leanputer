"""Compiler-derived ownership and native-cache storage of private controls.

This analyzes the complete Boolean transition, including returning caller
frames. It never examines proof inputs. Unknown data bits remain arbitrary.
Only a field needed by exactly one effective task owner can leave the shared
register file. All other fields stay shared; inactive private groups persist in
native Gated DeltaNet cache, not in a host environment or checker.
"""
from dataclasses import dataclass
from types import SimpleNamespace

import torch

from .control_packing import PackedBit


def register_view(layout, names):
    fields = [(n, w) for n, w in layout.fields if n in names]
    offset = 0; slices = {}
    for name, width in fields:
        slices[name] = slice(offset, offset+width); offset += width
    return SimpleNamespace(fields=fields, width=offset, slices=slices)


def ownership(compiler, address_plans):
    from .kernel.traversal_machine import Task, Mode
    layout = compiler.layout
    # These expressions also certify the dispatch partition outside the named
    # task domain. Adding unused analysis wires removes no compiled operation.
    returning = compiler.eq(compiler.r['mode'], Mode.RETURN)
    empty = compiler.eq(compiler.r['sp'], 0)
    task_bad = compiler.lt(max(Task), compiler.r['task'])
    task_eq = [compiler.eq(compiler.r['task'], t) for t in Task]
    frame_eq = [compiler.eq(compiler.read['frame']['task'], t) for t in Task]
    circuit, outputs = compiler.finish(target=lambda c, o: (c, o))
    fields = circuit.native_packed_fields
    roots = [w for _, keep, updated in fields for w in [keep]+updated]+outputs[layout.width:]
    owners = list(Task)+[None]
    count = len(owners); all_cases = (1 << (3*count))-1
    cases = [sum(1 << (3*i+k) for i in range(count)) for k in range(3)]
    # Cases: non-return; return with empty stack; return to frame.task.
    zero = [all_cases]*len(circuit.depth); one = list(zero)
    frame_bits = [i for i, n in enumerate(circuit.inputs) if n.startswith('read/frame/task/')]
    for positions, unknown, known_pattern in (
            (range(layout.slices['task'].start, layout.slices['task'].stop), cases[2], 3),
            (frame_bits, cases[0] | cases[1], 4)):
        for bit, w in enumerate(positions):
            ones = sum(known_pattern << (3*i) for i, t in enumerate(owners[:-1]) if (t >> bit) & 1)
            invalid = 7 << (3*(count-1))
            unbound = unknown | invalid
            one[w] = ones | unbound; zero[w] = ((all_cases ^ unbound) ^ ones) | unbound
    for bit, w in enumerate(range(layout.slices['mode'].start, layout.slices['mode'].stop)):
        fixed = cases[1] | cases[2]
        one[w] = cases[0] | (fixed if (Mode.RETURN >> bit) & 1 else 0)
        zero[w] = cases[0] | (0 if (Mode.RETURN >> bit) & 1 else fixed)
    forced_zero = {returning: cases[0], empty: cases[2]}
    forced_one = {empty: cases[1], task_bad: 3 << (3*(count-1))}
    for w in task_eq: forced_zero[w] = forced_zero.get(w, 0) | (3 << (3*(count-1)))
    for w in frame_eq: forced_zero[w] = forced_zero.get(w, 0) | (4 << (3*(count-1)))
    for w, op, args in circuit.gates:
        if op == 'not': z, o = one[args[0]], zero[args[0]]
        elif op == 'and':
            z = 0; o = all_cases
            for a in args: z |= zero[a]; o &= one[a]
        else:
            z = all_cases; o = 0
            for a in args: z &= zero[a]; o |= one[a]
        fz = forced_zero.get(w, 0); fo = forced_one.get(w, 0)
        zero[w] = (z | fz) & ~fo; one[w] = (o | fo) & ~fz
    live = [0]*len(circuit.depth)
    for w in roots: live[w] |= zero[w] & one[w]
    for w, op, args in reversed(circuit.gates):
        if live[w]:
            for a in args: live[a] |= live[w] & zero[a] & one[a]
    required = {}
    for name, keep, updated in fields:
        mask = zero[keep]  # A write needs its destination resident, even if constant.
        for w in range(layout.slices[name].start, layout.slices[name].stop): mask |= live[w]
        required[name] = [t for i, t in enumerate(owners) if mask & (7 << (3*i))]
    # Address queries must be available before the private bank is read. Keep
    # their full conservative support shared, without input-dependent pruning.
    address_inputs = set()
    for c, out in address_plans:
        used = set(out)
        for w, op, args in reversed(c.gates):
            if w in used: used.update(args)
        address_inputs.update(i for i in used if i < layout.width)
    shared = {'task', 'mode', 'sp', 'status', 'reason', 'fuel', 'free', 'raw_index', 'published_declarations'}
    shared.update(n for n, s in layout.slices.items() if any(i in address_inputs for i in range(s.start, s.stop)))
    private = {n: int(ts[0]) for n, ts in required.items() if len(ts) == 1 and ts[0] is not None and n not in shared}
    groups = {}
    for name, _ in layout.fields:
        if name in private: groups.setdefault(private[name], []).append(name)
    return circuit, outputs, groups


@dataclass
class ControlBank:
    common_fields: list
    groups: dict
    word_bits: int

    def __post_init__(self):
        self.groups = {int(k): v for k, v in self.groups.items()}
        if any(owner<0 or owner>=128 for owner in self.groups):raise ValueError('private control owner exceeds native row capacity')
        self.common = register_view(SimpleNamespace(fields=self.common_fields), {n for n, _ in self.common_fields})
        self.private = {name: (owner, slot) for owner, names in self.groups.items() for slot, name in enumerate(names)}
        self.digits_per_word = (self.word_bits+7)//8
        self.columns = max(map(len, self.groups.values()), default=0)*self.digits_per_word
        self.cache_columns = max(map(len, self.groups.values()), default=0)*self.word_bits

    def metadata(self):
        return dict(common_fields=self.common_fields, groups=self.groups, word_bits=self.word_bits)

    def initial_row(self, owner, registers):
        values = [0]*self.columns
        for slot, name in enumerate(self.groups[owner]):
            for digit in range(self.digits_per_word):
                values[slot*self.digits_per_word+digit] = (registers[name] >> (8*digit)) & 255
        return values

    def common_bits(self, layout, bits):
        indices = [i for name, _ in self.common_fields for i in range(layout.slices[name].start, layout.slices[name].stop)]
        return bits.index_select(-1, torch.tensor(indices, device=bits.device))

    def logical_inputs(self, layout, common_inputs, aliases, bit_aliases=None):
        inputs = [None]*layout.width
        for name, width in layout.fields:
            if name in self.private:
                _, slot = self.private[name]
                values = bit_aliases[slot*self.word_bits:slot*self.word_bits+width] if bit_aliases is not None else [PackedBit(aliases[slot*self.digits_per_word+bit//8], bit % 8,
                    min(8, width-8*(bit//8))) for bit in range(width)]
            else: values = common_inputs[self.common.slices[name]]
            inputs[layout.slices[name]] = values
        return inputs

    def aggregate(self, compiler, circuit, outputs):
        fields = {n: (keep, updated) for n, keep, updated in circuit.native_packed_fields}
        merged = [(n, *fields[n]) for n, _ in self.common_fields]
        for slot in range(self.columns//self.digits_per_word):
            names = [names[slot] for names in self.groups.values() if slot < len(names)]
            keep = compiler.AND(*(fields[n][0] for n in names))
            updated = [compiler.OR(*(fields[n][1][i] for n in names)) for i in range(self.word_bits)]
            merged.append((f'private/{slot}', keep, updated))
        circuit.native_packed_fields = merged
        common_width = self.common.width+self.columns//self.digits_per_word*self.word_bits
        # The prefix is ignored by packed_update_outputs; bank writes retain
        # their exact existing output wires after it.
        return circuit, [compiler.g.zero]*common_width+outputs[compiler.layout.width:]

    def registers(self, cache, heads, common_registers, pending=None, offsets=None):
        """Output serialization only; never used to construct model feedback."""
        result = [dict(r) for r in common_registers]
        for head in heads:
            if head['bank'] != 'control': continue
            first = head['column_offset']; count = head['columns']
            memory = cache.layers[head['layer']].recurrent_states[0]
            values = memory[:, 0, :128, 2:2+count].float().cpu()/128
            if not torch.all((values==0)|(values==1)):
                raise ValueError('private native control cache left exact binary domain')
            for owner, names in self.groups.items():
                for slot, name in enumerate(names):
                    for bit in range(self.word_bits):
                        column = slot*self.word_bits+bit
                        if first <= column < first+count:
                            for batch, r in enumerate(result):
                                r[name] = r.get(name, 0) | (int(values[batch, owner, column-first]) << bit)
        # A transition's final write is a model-produced pending packet until
        # the next stock forward. Overlay it when serializing intermediate
        # diagnostics; normal halting also performs a native cache flush.
        if pending is not None:
            for batch, r in enumerate(result):
                if not pending[batch, offsets['pending/control/enable']]:continue
                address=offsets['pending/control/address']
                owner=sum(int(pending[batch,address+bit])<<bit for bit in range(7))
                if owner not in self.groups:raise ValueError('invalid pending private control owner')
                first=offsets['pending/control/payload']
                values=pending[batch,first:first+self.columns]
                if not torch.all((values>=0)&(values<=255)&(values==values.floor())):
                    raise ValueError('pending private control packet left exact byte domain')
                for slot,name in enumerate(self.groups[owner]):
                    r[name]=sum(int(values[slot*self.digits_per_word+digit])<<(8*digit)for digit in range(self.digits_per_word))
        return result
