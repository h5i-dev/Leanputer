"""Public bounded dependent checker: syntax preparation and fixed-weight runs.

The runtime loop applies shared weights a fixed number of times. It never
consults either reference checker and never chooses a semantic operation.
"""
import time
from dataclasses import asdict

import torch

from .dependent import Declaration, Exhausted, Unsupported, parse_expr
from .machine_spec import Outcome, Reason, prepare

DOCUMENT_FORMAT = 'leanputer.dependent.v1'


def parse_document(document):
    if not isinstance(document, dict) or document.get('format') != DOCUMENT_FORMAT:
        raise ValueError('unsupported dependent document format')
    allowed = {'format', 'name', 'term', 'claim', 'environment', 'provenance'}
    if set(document)-allowed or not {'term', 'claim'} <= set(document):
        raise ValueError('dependent document requires term/claim and documented fields only')
    environment = document.get('environment', [])
    if not isinstance(environment, list):
        raise ValueError('environment must be an ordered declaration array')
    declarations = []
    for declaration in environment:
        if not isinstance(declaration, dict) or set(declaration)-{'name', 'type', 'value', 'opaque'}:
            raise ValueError('malformed environment declaration')
        declarations.append(Declaration(**declaration))
    return parse_expr(document['term']), parse_expr(document['claim']), declarations


def model_statistics(model):
    buffers = list(model.buffers())
    weight_bytes = sum((b.indices().numel()*b.indices().element_size()+b.values().numel()*b.values().element_size())
                       if b.is_sparse else b.numel()*b.element_size() for b in buffers)
    depths = {name: len(getattr(model, name).layers) for name in ('initializer', 'address1', 'address2', 'transition')}
    return dict(config=asdict(model.config), state_bits=model.layout.width,
                shared_ffn_depths=depths, attention_stages_per_step=2,
                shared_stages_per_step=depths['address1']+depths['address2']+depths['transition']+2,
                weight_bytes=weight_bytes,
                sparse_nonzeros=sum(b._nnz() for b in buffers if b.is_sparse),
                trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad))


def run_states(model, bits):
    """Initialize in weights and execute exactly fuel+1 shared transitions."""
    if bits.ndim != 2 or bits.shape[1] != model.layout.width or bits.is_complex():
        raise ValueError('incorrect machine input shape/type')
    if not torch.all((bits == 0) | (bits == 1)):
        raise ValueError('machine input must be Boolean')
    if any(b.dtype != torch.float32 for b in model.buffers() if b.is_floating_point()):
        raise ValueError('machine weights must remain float32')
    device = next(model.buffers()).device
    bits = bits.to(device=device, dtype=torch.float32)
    if device.type == 'cuda':
        torch.cuda.synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)
    start = time.perf_counter()
    with torch.inference_mode(), torch.autocast(device_type=device.type, enabled=False):
        state = model.initializer(bits)
        for _ in range(model.config.fuel+1):
            state = model(state)
    if device.type == 'cuda':
        torch.cuda.synchronize(device)
    elapsed = time.perf_counter()-start
    metrics = dict(forward_seconds=elapsed, applied_steps=model.config.fuel+1,
                   cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(device) if device.type == 'cuda' else None)
    return state.cpu(), metrics


def check_batch(model, documents):
    records, encoded, positions = [], [], []
    for index, document in enumerate(documents):
        name = document.get('name', str(index)) if isinstance(document, dict) else str(index)
        record = dict(name=name)
        try:
            term, claim, declarations = parse_document(document)
            state = prepare(model.config, term, claim, declarations)
            encoded.append(model.layout.encode(state)); positions.append(index)
            record['input_heap_nodes'] = state['regs']['free']-1
            record['assumptions'] = [d.name for d in declarations if d.value is None]
        except Unsupported as error:
            record.update(status='UNSUPPORTED', reason=str(error))
        except Exhausted as error:
            record.update(status='RESOURCE', reason=str(error))
        except (ValueError, TypeError, RecursionError) as error:
            record.update(status='MALFORMED', reason=str(error))
        records.append(record)
    metrics = dict(forward_seconds=0., applied_steps=0, cuda_peak_allocated_bytes=None)
    if encoded:
        final, metrics = run_states(model, torch.cat(encoded))
        for position, row in zip(positions, final.tolist()):
            state = model.layout.decode(row)
            r = state['regs']
            outcome, reason = Outcome(r['status']), Reason(r['reason'])
            executed = model.config.fuel-r['fuel'] + int(reason == Reason.FUEL)
            records[position].update(status=outcome.name, reason=reason.name,
                                     semantic_steps=executed, allocated_heap_nodes=r['free']-1)
    return dict(format='leanputer.report.v1', results=records, runtime=metrics, model=model_statistics(model))
