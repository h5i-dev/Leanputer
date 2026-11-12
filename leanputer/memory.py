"""Exact addressed reads using nontrivial, fixed-key softmax attention.

The binary control query selects a positional memory token. Match/mismatch
scores differ by at least 256, so float32 max-subtracted softmax underflows all
nonmatching entries to zero on tested CPU/CUDA backends. This numerical domain
assumption is explicit; it is not exact selection over real arithmetic.
"""
import math

import torch
from torch import nn
from torch.nn import functional as F


class AddressedRead(nn.Module):
    def __init__(self, cells):
        super().__init__()
        if cells < 2 or cells & (cells-1):
            raise ValueError('addressed memory capacity must be a power of two >= 2')
        self.cells = cells
        self.bits = int(math.log2(cells))
        if self.bits > 20:
            raise ValueError('address space exceeds supported numerical domain')
        self.register_buffer('query_weight', torch.eye(self.bits, dtype=torch.float32, device='cpu') * 256)
        self.register_buffer('query_bias', torch.full((self.bits,), -128., dtype=torch.float32, device='cpu'))
        self.register_buffer('keys', torch.tensor([
            [1. if i & (1 << b) else -1. for b in range(self.bits)] for i in range(cells)
        ], dtype=torch.float32, device='cpu'))

    def forward(self, addresses, memory):
        # addresses [batch, ports, binary address bits], memory [batch,cells,width]
        with torch.autocast(device_type=memory.device.type, enabled=False):
            queries = F.linear(addresses, self.query_weight, self.query_bias)
            probabilities = torch.softmax(queries @ self.keys.T, dim=-1)
            return probabilities @ memory
