"""Evaluation-only references, trace diagnostics and counterexample shrinking."""
from collections import Counter
import copy

import torch

from .corpus import replace_at, syntax_paths
from .dependent import Exhausted, Oracle, Rejected, Unsupported
from .machine_spec import Op, Outcome, SpecMachine, prepare
from .runner import parse_document
from .execution import cuda_executor
from .state_layout import state_digest


def reference_result(document, config):
    if (isinstance(document, dict) and document.get('format') == 'leanputer.dependent.v1'
            and document.get('status') == 'UNSUPPORTED'):
        return dict(status='UNSUPPORTED', reason=document.get('reason'))
    try:
        term, claim, environment = parse_document(document)
        initial = prepare(config, term, claim, environment)
    except Unsupported as error:
        return dict(status='UNSUPPORTED', reason=str(error))
    except Exhausted as error:
        return dict(status='RESOURCE', reason=str(error))
    except (ValueError, TypeError, RecursionError) as error:
        return dict(status='MALFORMED', reason=str(error))
    machine = SpecMachine(config, initial)
    histogram = Counter()
    peak_stack = peak_context = 0
    for _ in range(config.fuel+1):
        r = machine.state['regs']
        if r['status']:
            break
        histogram[Op(r['mode']).name] += 1
        machine.step()
        peak_stack = max(peak_stack, r['sp']); peak_context = max(peak_context, r['ctx'])
    status = Outcome(machine.state['regs']['status']).name
    try:
        Oracle(environment).check(term, claim)
        oracle = 'ACCEPT'
    except Rejected:
        oracle = 'REJECT'
    except (Exhausted, RecursionError):
        oracle = 'RESOURCE'
    return dict(status=status, reason=machine.state['regs']['reason'], recursive=oracle, op_counts=dict(histogram),
                peak_stack=peak_stack, peak_context=peak_context,
                operational_state_sha256=state_digest(machine.state),
                final=machine.state['regs'])


def trace_discrepancy(model, document, execution='eager'):
    """Test instrumentation only: stop at first mismatch against an independent spec."""
    term, claim, environment = parse_document(document)
    initial = prepare(model.config, term, claim, environment)
    spec = SpecMachine(model.config, initial)
    state = model.initializer(model.layout.encode(initial).to(next(model.buffers()).device))
    executor = None
    if execution == 'cuda_graph':
        executor, _ = cuda_executor(model, 1)
        executor.initialize(state)
    with torch.inference_mode():
        for index in range(model.config.fuel+1):
            previous_registers = dict(spec.state['regs'])
            expected = spec.step()
            if executor is None:
                state = model(state)
            else:
                executor.replay(); state = executor.state
            expected_bits = model.layout.encode(expected)
            if not torch.equal(state.cpu(), expected_bits):
                raw = state[0].cpu().tolist()
                try:
                    actual = model.layout.decode(raw)
                except ValueError:
                    invalid = [(i, value) for i, value in enumerate(raw) if value not in (0, 1)]
                    return dict(step=index+1, domain_violation=invalid[:20])
                banks = [name for name in actual if actual[name] != expected[name]]
                cells = []
                for bank in banks:
                    if bank == 'regs': continue
                    for row, (left, right) in enumerate(zip(actual[bank], expected[bank])):
                        if left != right:
                            cells.append(dict(bank=bank, row=row, actual=left, expected=right))
                return dict(step=index+1, banks=banks, changed_cells=cells[:20],
                            previous_registers=previous_registers, actual_registers=actual['regs'], expected_registers=expected['regs'])
            if expected['regs']['status']:
                return None
    return dict(error='no terminal state')


def shrink_candidates(document):
    for field in ('term', 'claim'):
        for path, node in syntax_paths(document[field]):
            if len(node) != 3:
                continue
            for replacement in (node[1], node[2], ['sort', 0], ['var', 0]):
                candidate = copy.deepcopy(document)
                candidate[field] = replace_at(document[field], path, replacement)
                yield candidate
    for length in range(len(document.get('environment', []))):
        candidate = copy.deepcopy(document)
        candidate['environment'] = candidate['environment'][:length]
        yield candidate


def minimize(document, predicate, attempts=100):
    """Greedy syntax/environment shrinker; predicate must exclude resource/nonbugs."""
    current, tested = copy.deepcopy(document), 0
    while tested < attempts:
        smaller = None
        for candidate in shrink_candidates(current):
            tested += 1
            if predicate(candidate):
                smaller = candidate; break
            if tested >= attempts:
                break
        if smaller is None:
            break
        current = smaller
    return current, tested
