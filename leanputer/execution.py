"""CUDA graph replay of the same fixed semantic forward pass.

Graph capture changes launch scheduling, not checking semantics. The graph
contains only model forward operations and an identity copy of its output into
the next-step input. It neither interprets syntax nor chooses semantic phases.
"""
import time
import weakref

import torch


def buffer_signature(model):
    return tuple((id(buffer), buffer.values().data_ptr() if buffer.is_sparse else buffer.data_ptr())
                 for buffer in model.buffers())


class CudaGraphExecutor:
    def __init__(self, model, batch):
        self.model = weakref.ref(model)
        self.signature = buffer_signature(model)
        device = next(model.buffers()).device
        if device.type != 'cuda':
            raise ValueError('CUDA graph execution requires a CUDA model')
        start = time.perf_counter()
        self.state = torch.zeros((batch, model.layout.width), device=device, dtype=torch.float32)
        stream = torch.cuda.Stream(device=device)
        stream.wait_stream(torch.cuda.current_stream(device))
        with torch.cuda.stream(stream), torch.inference_mode():
            for _ in range(3):
                output = model(self.state)
        torch.cuda.current_stream(device).wait_stream(stream)
        torch.cuda.synchronize(device)
        self.graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph), torch.inference_mode():
            self.output = model(self.state)
            self.state.copy_(self.output)
        torch.cuda.synchronize(device)
        self.setup_seconds = time.perf_counter()-start

    def initialize(self, initial):
        model = self.model()
        if model is None or buffer_signature(model) != self.signature:
            raise ValueError('captured model buffers changed; rebuild CUDA graph')
        self.state.copy_(initial)

    def replay(self):
        self.graph.replay()


def cuda_executor(model, batch):
    cache = getattr(model, '_cuda_graph_cache', None)
    if cache is None:
        cache = {}
        model._cuda_graph_cache = cache
    key = (batch, str(next(model.buffers()).device))
    executor = cache.get(key)
    if executor is None or executor.signature != buffer_signature(model):
        executor = CudaGraphExecutor(model, batch)
        cache[key] = executor
        return executor, executor.setup_seconds
    return executor, 0.


def clear_cuda_graphs(model):
    """Release only this model's captured execution pools, e.g. between ablations."""
    cache = getattr(model, '_cuda_graph_cache', None)
    if cache is not None:
        torch.cuda.synchronize(next(model.buffers()).device)
        cache.clear()
