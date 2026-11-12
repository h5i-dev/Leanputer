"""Sparse ReLU logic for shared transitions, without ornamental attention.

Semantic memory reads live in addressed attention (memory.py). This module
lowers Boolean control/updates to fixed FFNs. Residual work wires are reset on
entry and only the selected next-state bits leave the module.
"""
import torch
from torch import nn


class LogicLayer(nn.Module):
    def __init__(self, width, gates):
        super().__init__()
        rows, cols, values, biases, dr, dc, dv = [], [], [], [], [], [], []
        for dest, op, args in gates:
            terms = [(1, 1-len(args))] if op == 'and' else [(1, 1)] if op == 'not' else [(1, 0), (-1, -1)]
            for sign, bias in terms:
                h = len(biases)
                biases.append(bias)
                for source in args:
                    rows.append(h); cols.append(source)
                    values.append(-1. if op == 'not' else 1.)
                dr.append(dest); dc.append(h); dv.append(float(sign))
        self.register_buffer('up', torch.sparse_coo_tensor(
            [rows, cols], values, (len(biases), width), dtype=torch.float32, device='cpu').coalesce())
        self.register_buffer('bias', torch.tensor(biases, dtype=torch.float32, device='cpu'))
        self.register_buffer('down', torch.sparse_coo_tensor(
            [dr, dc], dv, (width, len(biases)), dtype=torch.float32, device='cpu').coalesce())

    def forward(self, x):
        h = torch.relu(torch.sparse.mm(self.up, x.T) + self.bias[:, None])
        return x + torch.sparse.mm(self.down, h).T


class CompiledLogic(nn.Module):
    """Internal Boolean-domain module; caller establishes shape/binary inputs."""
    def __init__(self, circuit, outputs):
        super().__init__()
        self.input_width = len(circuit.inputs)
        self.width = len(circuit.depth)
        self.register_buffer('output_ids', torch.tensor(outputs, dtype=torch.long, device='cpu'))
        grouped = [[] for _ in range(max(circuit.depth, default=0))]
        for gate in circuit.gates:
            grouped[circuit.depth[gate[0]]-1].append(gate)
        self.layers = nn.ModuleList([LogicLayer(self.width, gates) for gates in grouped])
        self.requires_grad_(False)

    def forward(self, bits):
        x = bits.new_zeros((bits.shape[0], self.width))
        x[:, :self.input_width] = bits
        for layer in self.layers:
            x = layer(x)
        return x.index_select(1, self.output_ids)
