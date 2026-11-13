"""Boolean circuits lowered to sparse residual attention/ReLU weights.

Residual wires are Boolean at layer boundaries. FFN hidden activations can be
larger integers. Singleton attention has softmax([0]) = [1] exactly; there is no
layer normalization. Sparse matrices are fixed weights, not checker dispatch.
"""
import torch
from torch import nn


class Circuit:
    def __init__(self):
        self.inputs = []
        self._input_names = set()
        self.gates = []
        self.depth = []
        self.cache = {}

    def input(self, name):
        if self.gates:
            raise ValueError('declare all inputs before gates')
        try:
            if name in self._input_names:
                raise ValueError('duplicate input name')
            self._input_names.add(name)
        except TypeError as error:
            raise ValueError('input names must be hashable') from error
        i = len(self.depth)
        self.inputs.append(name)
        self.depth.append(0)
        return i

    def gate(self, op, *args):
        if op not in ('and', 'or', 'not') or (op == 'not' and len(args) != 1):
            raise ValueError('unsupported gate or arity')
        if any(type(a) is not int or not 0 <= a < len(self.depth) for a in args):
            raise ValueError('gate operands must be existing wire IDs')
        args = tuple(sorted(set(args))) if op != 'not' else args
        if len(args) > 2**24:
            raise ValueError('gate fan-in exceeds exact float32 integer range')
        if len(args) == 1 and op != 'not':
            return args[0]
        key = (op, args)
        if key not in self.cache:
            i = len(self.depth)
            self.cache[key] = i
            self.gates.append((i, op, args))
            self.depth.append(1 + max((self.depth[a] for a in args), default=0))
        return self.cache[key]

    def AND(self, *args):
        return self.gate('and', *args)

    def OR(self, *args):
        return self.gate('or', *args)

    def NOT(self, arg):
        return self.gate('not', arg)

    def compile(self, outputs):
        return CompiledCircuit(self, outputs)


class ResidualReLU(nn.Module):
    def __init__(self, width, gates):
        super().__init__()
        # Single-token self-attention: Q=K=0, hence softmax(QK^T)=1.
        # V routes operands into a scratch bank, which the FFN consumes/clears.
        operands = sorted({a for _, _, args in gates for a in args})
        self.register_buffer('value', torch.sparse_coo_tensor(
            [[width + a for a in operands], operands], [1.0] * len(operands),
            (2 * width, 2 * width), dtype=torch.float32, device='cpu').coalesce())
        rows, cols, vals, biases, out_rows, out_cols, out_vals = [], [], [], [], [], [], []
        for dest, op, args in gates:
            terms = [(1, 1 - len(args))] if op == 'and' else [(1, 1)] if op == 'not' else [(1, 0), (-1, -1)]
            for sign, bias in terms:
                h = len(biases)
                biases.append(bias)
                for a in args:
                    rows.append(h); cols.append(width + a); vals.append(-1.0 if op == 'not' else 1.0)
                out_rows.append(dest); out_cols.append(h); out_vals.append(float(sign))
        for a in operands:
            h = len(biases)
            biases.append(0)
            rows.append(h); cols.append(width + a); vals.append(1.0)
            out_rows.append(width + a); out_cols.append(h); out_vals.append(-1.0)
        hidden = len(biases)
        self.register_buffer('up', torch.sparse_coo_tensor(
            [rows, cols], vals, (hidden, 2 * width), dtype=torch.float32, device='cpu').coalesce())
        self.register_buffer('bias', torch.tensor(biases, dtype=torch.float32, device='cpu'))
        self.register_buffer('down', torch.sparse_coo_tensor(
            [out_rows, out_cols], out_vals, (2 * width, hidden), dtype=torch.float32, device='cpu').coalesce())

    def forward(self, x):
        v = torch.sparse.mm(self.value, x.T).T.unsqueeze(1)
        scores = x.new_zeros((x.shape[0], 1, 1))
        x = x + torch.bmm(torch.softmax(scores, dim=-1), v).squeeze(1)
        h = torch.relu(torch.sparse.mm(self.up, x.T) + self.bias[:, None])
        return x + torch.sparse.mm(self.down, h).T


class CompiledCircuit(nn.Module):
    def __init__(self, circuit, outputs):
        super().__init__()
        if any(type(o) is not int or not 0 <= o < len(circuit.depth) for o in outputs):
            raise ValueError('outputs must be existing wire IDs')
        self.input_names = tuple(circuit.inputs)
        self.width = len(circuit.depth)
        self.register_buffer('output_ids', torch.tensor(outputs, dtype=torch.long, device='cpu'))
        self.layers = nn.ModuleList([
            ResidualReLU(self.width, [g for g in circuit.gates if circuit.depth[g[0]] == depth])
            for depth in range(1, max(circuit.depth, default=0) + 1)
        ])
        self.requires_grad_(False)

    def forward(self, bits):
        # The boundary rejects malformed/non-Boolean encodings, never rounds them.
        if bits.ndim != 2 or bits.shape[1] != len(self.input_names):
            raise ValueError('incorrect input shape')
        if bits.is_complex():
            raise ValueError('inputs must be real Boolean values')
        if not torch.all((bits == 0) | (bits == 1)):
            raise ValueError('inputs must be finite Boolean values')
        if any(b.dtype != torch.float32 for b in self.buffers() if b.is_sparse):
            raise ValueError('fixed weights require float32; do not cast the model')
        # Autocast can round large gate sums before OR cancellation. Always use
        # float32 for this construction, including inside caller autocast scopes.
        with torch.autocast(device_type=bits.device.type, enabled=False):
            x = torch.zeros((bits.shape[0], 2 * self.width), device=bits.device, dtype=torch.float32)
            x[:, :bits.shape[1]] = bits
            for layer in self.layers:
                x = layer(x)
            return x.index_select(1, self.output_ids)
