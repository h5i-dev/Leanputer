"""Public bounded dependent checker: syntax preparation and fixed-weight runs.

The runtime loop applies shared weights a fixed number of times. It never
consults either reference checker and never chooses a semantic operation.
"""
import time
from dataclasses import asdict

import torch

from .dependent import Declaration, Exhausted, Unsupported, parse_expr
from .machine_spec import Outcome, Reason, prepare
from .execution import cuda_executor
from .state_layout import state_digest

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
    attention_memory = model.memory_update == 'attention_delta'
    return dict(config=asdict(model.config), lowering='optimized' if model.optimized else 'reference', state_bits=model.layout.width,
                memory_update=model.memory_update,
                state_bytes_per_item=4*model.layout.width,
                ffn_work_widths={name:getattr(model, name).width for name in depths},
                max_ffn_hidden_width=max((layer.up.shape[0] for name in depths for layer in getattr(model, name).layers), default=0),
                shared_ffn_depths=depths, attention_stages_per_step=2+int(attention_memory),
                memory_write_gate_stages=int(attention_memory), rank_one_update_stages=int(attention_memory),
                shared_stages_per_step=depths['address1']+depths['address2']+depths['transition']+2+3*int(attention_memory),
                weight_bytes=weight_bytes,
                sparse_nonzeros=sum(b._nnz() for b in buffers if b.is_sparse),
                trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad))


def run_states(model, bits, execution='eager'):
    """Initialize in weights and execute exactly fuel+1 shared transitions."""
    boundary_start = time.perf_counter()
    if execution not in ('eager', 'cuda_graph'):
        raise ValueError('unknown execution backend')
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
    boundary_seconds = time.perf_counter()-boundary_start
    executor, graph_seconds = cuda_executor(model, bits.shape[0]) if execution == 'cuda_graph' else (None, 0.)
    start = time.perf_counter()
    with torch.inference_mode(), torch.autocast(device_type=device.type, enabled=False):
        if device.type == 'cuda':
            init_start, init_end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            init_start.record()
        initialization_start = time.perf_counter()
        state = model.initializer(bits)
        if executor is not None:
            executor.initialize(state)
        if device.type == 'cuda': init_end.record()
        initialization_seconds = time.perf_counter()-initialization_start
        if executor is None:
            for _ in range(model.config.fuel+1): state = model(state)
        else:
            for _ in range(model.config.fuel+1): executor.replay()
            state = executor.state
    if device.type == 'cuda':
        torch.cuda.synchronize(device)
    elapsed = time.perf_counter()-start
    if device.type == 'cuda': initialization_seconds = init_start.elapsed_time(init_end)/1000
    metrics = dict(forward_seconds=elapsed, applied_steps=model.config.fuel+1, execution=execution,
                   boundary_and_input_transfer_seconds=boundary_seconds, graph_setup_seconds=graph_seconds,
                   initializer_seconds=initialization_seconds,
                   cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(device) if device.type == 'cuda' else None)
    return state.cpu(), metrics


def check_batch(model, documents, execution='eager'):
    preparation_start = time.perf_counter()
    records, encoded, positions = [], [], []
    for index, document in enumerate(documents):
        name = document.get('name', str(index)) if isinstance(document, dict) else str(index)
        record = dict(name=name)
        if (isinstance(document, dict) and document.get('format') == DOCUMENT_FORMAT
                and document.get('status') == 'UNSUPPORTED'):
            record.update(status='UNSUPPORTED', reason=document.get('reason', 'unsupported preparation input'))
            records.append(record)
            continue
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
    preparation_seconds = time.perf_counter()-preparation_start
    metrics = dict(forward_seconds=0., applied_steps=0, execution=execution, graph_setup_seconds=0.,
                   initializer_seconds=0., boundary_and_input_transfer_seconds=0., cuda_peak_allocated_bytes=None)
    if encoded:
        final, metrics = run_states(model, torch.cat(encoded), execution)
        for position, row in zip(positions, final.tolist()):
            state = model.layout.decode(row)
            r = state['regs']
            outcome, reason = Outcome(r['status']), Reason(r['reason'])
            executed = model.config.fuel-r['fuel'] + int(reason == Reason.FUEL)
            records[position].update(status=outcome.name, reason=reason.name,
                                     semantic_steps=executed, allocated_heap_nodes=r['free']-1,
                                     final_registers=r, operational_state_sha256=state_digest(state))
    metrics['syntax_encoding_seconds'] = preparation_seconds
    metrics['total_batch_seconds'] = time.perf_counter()-preparation_start
    return dict(format='leanputer.report.v1', results=records, runtime=metrics, model=model_statistics(model))


def check_corpus(model, documents, batch_size=16, execution='eager', progress=None):
    """Retain every selected case while packing supported preparations for GPU use."""
    if batch_size < 1:
        raise ValueError('positive model batch limit required')
    records, batches, pending, positions = [None]*len(documents), [], [], []
    def flush():
        checked = check_batch(model, pending, execution)
        for index, record in zip(positions, checked['results']):
            records[index] = record
        batches.append(dict(input_positions=list(positions), **checked['runtime']))
        pending.clear(); positions.clear()
        if progress is not None: progress(sum(record is not None for record in records), len(records))
    for index, document in enumerate(documents):
        if (isinstance(document, dict) and document.get('format') == DOCUMENT_FORMAT
                and document.get('status') == 'UNSUPPORTED'):
            records[index] = dict(name=document.get('name', str(index)), status='UNSUPPORTED', reason=document.get('reason', 'unsupported'))
            continue
        pending.append(document); positions.append(index)
        if len(pending) == batch_size: flush()
    if pending: flush()
    if progress is not None: progress(len(records), len(records))
    return dict(format='leanputer.report.v1', results=records, batches=batches, model=model_statistics(model),
                batching='All inputs retained; explicit preparation-unsupported records recorded before packing remaining cases in FIFO order.')
