"""Version-one operational state serialization; no checking or normalization."""
import torch
import hashlib
import json

from .bitvec import pack_words, unpack_words
from .machine_spec import FRAME_FIELDS, HEAP_FIELDS, REGISTERS


def state_digest(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class StateLayout:
    def __init__(self, config):
        self.config = config
        width = config.word_bits
        self.fields = []
        for name in REGISTERS:
            self.fields.append((name, max(width, config.fuel.bit_length()) if name == 'fuel' else width))
        self.banks = {}
        for bank, capacity, names in (
            ('heap', config.heap, HEAP_FIELDS), ('stack', config.stack, FRAME_FIELDS),
            ('context', config.context, ('type',)), ('constants', config.constants, ('kind', 'type', 'value')),
        ):
            start = sum(w for _, w in self.fields)
            for row in range(capacity):
                self.fields.extend((f'{bank}/{row}/{name}', width) for name in names)
            self.banks[bank] = (start, capacity, len(names)*width)
        self.slices, self.names = {}, []
        for name, bits in self.fields:
            start = len(self.names)
            self.names.extend(f'{name}/{i}' for i in range(bits))
            self.slices[name] = slice(start, len(self.names))
        self.width = len(self.names)
        self.widths = [w for _, w in self.fields]

    def encode(self, state):
        words = [state['regs'][name] for name in REGISTERS]
        for bank in ('heap', 'stack', 'context', 'constants'):
            words.extend(value for row in state[bank] for value in row)
        return torch.tensor([pack_words(words, self.widths)], dtype=torch.float32, device='cpu')

    def decode(self, bits):
        if len(bits) != self.width or any(bit not in (0, 1) for bit in bits):
            raise ValueError('operational state must contain exactly Boolean bits; no rounding')
        words = unpack_words(bits, self.widths)
        state = dict(regs=dict(zip(REGISTERS, words[:len(REGISTERS)])))
        offset = len(REGISTERS)
        for bank, fields in (('heap', 4), ('stack', 6), ('context', 1), ('constants', 3)):
            capacity = getattr(self.config, bank)
            state[bank] = [words[offset+i*fields:offset+(i+1)*fields] for i in range(capacity)]
            offset += capacity*fields
        return state


class RegisterLayout:
    """Fixed projection of the public state onto control registers only."""
    def __init__(self, state_layout):
        self.config = state_layout.config
        self.fields = [(name, width) for name, width in state_layout.fields if '/' not in name]
        self.width = sum(width for _, width in self.fields)
        self.names = state_layout.names[:self.width]
        self.slices = {name: state_layout.slices[name] for name, _ in self.fields}
