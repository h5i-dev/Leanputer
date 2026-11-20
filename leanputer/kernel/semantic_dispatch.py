"""Control dispatch for one shared kernel transition.

Task, mode, private continuation PCs and the caller frame select a handler.
Expression tags, names, declaration shapes and proof bodies stay data on that
handler. The projection is the same one the phase partition already uses: a
data predicate that is not a control-field/constant test becomes TRUE here
and remains on the handler effect. This module does not run at inference.
"""
from collections import Counter, defaultdict

from .semantic_operators import OPERATORS, operator_for


def control_variables(compiler):
    """Fields the phase partition is allowed to switch on. Not a proof key."""
    names = {}
    for index, node in enumerate(compiler.g.nodes):
        if node.op != 'input':
            continue
        if node.data in ('mode', 'task', 'read/frame/task', 'read/frame/phase') or str(node.data).endswith('_pc'):
            names[index] = node.data
    if 'mode' not in names.values() or 'task' not in names.values():
        raise ValueError('semantic dispatch is missing task/mode control fields')
    return names


def _combine(op, values):
    operands = []
    for value in values:
        if value == (0 if op == 'and' else 1):
            return value
        if value == (1 if op == 'and' else 0):
            continue
        if isinstance(value, tuple) and value[0] == op:
            operands.extend(value[1])
        else:
            operands.append(value)
    operands = tuple(sorted(set(operands), key=repr))
    if not operands:
        return 1 if op == 'and' else 0
    if len(operands) == 1:
        return operands[0]
    return (op, operands)


def _interval(domains, variable, low, high):
    minimum, maximum = domains[variable]
    low = max(low, minimum)
    high = min(high, maximum)
    if low > high:
        return 0
    if (low, high) == (minimum, maximum):
        return 1
    return ('range', variable, low, high)


def _negate(domains, value):
    if isinstance(value, int):
        return 1 - value
    if value[0] == 'range':
        _, variable, low, high = value
        minimum, maximum = domains[variable]
        return _combine('or', (
            _interval(domains, variable, minimum, low - 1),
            _interval(domains, variable, high + 1, maximum),
        ))
    return _combine('or' if value[0] == 'and' else 'and', (_negate(domains, child) for child in value[1]))


def project_control(compiler, variables, guards):
    """Project each guard onto control fields. Data comparisons stay TRUE."""
    nodes = compiler.g.nodes
    domains = {index: (0, (1 << nodes[index].width) - 1) for index in variables}
    memo = {}

    def children(index, truth):
        node = nodes[index]
        if node.op == 'not':
            return [(node.args[0], not truth)]
        if node.op in ('all', 'any'):
            return [(arg, truth) for arg in node.args]
        return []

    def evaluate(index, truth):
        node = nodes[index]
        if node.op == 'const':
            return int(bool(node.data) == truth)
        if node.op in ('all', 'any'):
            conjunction = (node.op == 'all') == truth
            return _combine('and' if conjunction else 'or', (memo[(arg, truth)] for arg in node.args))
        if node.op == 'not':
            return memo[(node.args[0], not truth)]
        if node.op in ('eq', 'ult'):
            result = 1
            for left, right in (node.args, node.args[::-1]):
                if left not in variables or nodes[right].op != 'const':
                    continue
                value = nodes[right].data
                maximum = (1 << nodes[left].width) - 1
                if node.op == 'eq':
                    low, high = value, value
                elif left == node.args[0]:
                    low, high = 0, value - 1
                else:
                    low, high = value + 1, maximum
                result = _interval(domains, left, low, high)
                if not truth:
                    result = _negate(domains, result)
                break
            return result
        return 1

    pending = [(index, True, False) for index in guards]
    while pending:
        index, truth, ready = pending.pop()
        if (index, truth) in memo:
            continue
        if not ready:
            pending.append((index, truth, True))
            for child in reversed(children(index, truth)):
                if child not in memo:
                    pending.append((child[0], child[1], False))
            continue
        memo[(index, truth)] = evaluate(index, truth)
    return [memo[(index, True)] for index in guards], domains


def _predicate_nodes(predicate, seen):
    if isinstance(predicate, int) or predicate in seen:
        return
    seen.add(predicate)
    if predicate[0] in ('and', 'or'):
        for child in predicate[1]:
            _predicate_nodes(child, seen)


def predicate_unit_account(predicates, domains, variables):
    """One SwiGLU unit per control test and per boolean connective.

    equal-to-constant is one AND of the word bits. A less-than-constant is one
    AND per set bit of the bound, matching PreflightCircuit.less_const. An
    and/or of any fan-in is one gate. This is not a bit-blast of arithmetic.
    """
    seen = set()
    for predicate in predicates:
        _predicate_nodes(predicate, seen)
    ranges = [node for node in seen if node[0] == 'range']
    bools = [node for node in seen if node[0] in ('and', 'or')]
    test_units = 0
    for _, variable, low, high in ranges:
        width = (domains[variable][1]).bit_length()
        # A singleton equality is one unit. A proper interval is two bounds.
        if low == high:
            test_units += 1
        else:
            test_units += _less_units(low, width) + _less_units(high + 1, width)
    return dict(
        distinct_control_predicates=len(set(predicates)),
        predicate_connectives=len(bools),
        predicate_ranges=len(ranges),
        control_test_units=test_units,
        control_boolean_units=len(bools),
        control_dispatch_units=test_units + len(bools),
        control_fields=len(variables),
    )


def _less_units(bound, width):
    if bound <= 0 or bound >= 1 << width:
        return 0
    return bin(bound).count('1')


def group_handlers(compiler, predicates, effects):
    """One handler per distinct control predicate. Effects keep their data guards."""
    groups = defaultdict(list)
    for predicate, effect in zip(predicates, effects):
        groups[predicate].append(effect)
    handlers = []
    for predicate, members in groups.items():
        families = Counter(effect.family for effect in members)
        operator = operator_for(families.most_common(1)[0][0])
        handlers.append(dict(predicate=predicate, effects=tuple(members), families=dict(families), operator=operator))
    if sum(len(handler['effects']) for handler in handlers) != len(effects):
        raise ValueError('semantic dispatch dropped source effects')
    return handlers


def dispatch_account(compiler, effects):
    variables = control_variables(compiler)
    predicates, domains = project_control(compiler, variables, [effect.guard for effect in effects])
    handlers = group_handlers(compiler, predicates, effects)
    units = predicate_unit_account(predicates, domains, variables)
    by_operator = Counter(handler['operator'] for handler in handlers)
    missing = [name for name in OPERATORS if by_operator[name] == 0]
    data = handler_data_account(compiler, handlers, set(variables.values()))
    return dict(
        handlers=handlers,
        variables=variables,
        domains=domains,
        report=dict(
            **units,
            handlers=len(handlers),
            handlers_by_operator=dict(by_operator),
            operators_without_handlers=missing,
            source_effects=len(effects),
            largest_handler_effects=max(len(handler['effects']) for handler in handlers),
            **data,
        ),
    )


def _cone(nodes, roots):
    seen = set()
    stack = list(roots)
    while stack:
        cursor = stack.pop()
        if cursor in seen or cursor < 0:
            continue
        seen.add(cursor)
        stack.extend(nodes[cursor].args)
    return seen


def _input_names(nodes, index, memo):
    if index in memo:
        return memo[index]
    node = nodes[index]
    if node.op == 'input':
        names = frozenset((node.data,))
    elif node.op == 'const' or not node.args:
        names = frozenset()
    else:
        names = frozenset().union(*(_input_names(nodes, arg, memo) for arg in node.args))
    memo[index] = names
    return names


def _data_depth(nodes, index, residual, cache):
    if index in cache:
        return cache[index]
    if index not in residual:
        cache[index] = 0
        return 0
    node = nodes[index]
    base = max((_data_depth(nodes, arg, residual, cache) for arg in node.args), default=0)
    cache[index] = base if node.op in ('all', 'any', 'not', 'slice', 'extend', 'splice', 'input', 'const') else base + 1
    return cache[index]


def handler_data_account(compiler, handlers, control_names):
    """Bound the data cone that remains after control dispatch.

    Boolean connectives add no serial depth: one gate takes any fan-in. Add,
    subtract, compare and choice do. A handler inside the shared bound is one
    pipeline stage schedule; a wider handler keeps its own circuit.
    """
    nodes = compiler.g.nodes
    names = {}
    shared_limit = dict(depth=5, boolean=32, compares=16, arithmetic=4, choices=8, nodes=48)
    union_shared = set()
    union_private = set()
    private = Counter()
    depths = []
    words = []
    for handler in handlers:
        roots = []
        for effect in handler['effects']:
            roots.append(effect.guard)
            if effect.address >= 0:
                roots.append(effect.address)
            for value in effect.values:
                roots.append(value[1] if effect.kind == 'merge_fields' else value)
        cone = _cone(nodes, roots)
        residual = {index for index in cone if _input_names(nodes, index, names) - control_names}
        cache = {}
        depth = max((_data_depth(nodes, index, residual, cache) for index in residual), default=0)
        ops = Counter(nodes[index].op for index in residual)
        boolean = ops['all'] + ops['any']
        compares = ops['eq'] + ops['ult']
        arithmetic = ops['add'] + ops['sub']
        choices = ops['choose']
        fits = (
            depth <= shared_limit['depth'] and boolean <= shared_limit['boolean']
            and compares <= shared_limit['compares'] and arithmetic <= shared_limit['arithmetic']
            and choices <= shared_limit['choices'] and len(residual) <= shared_limit['nodes']
        )
        (union_shared if fits else union_private).update(residual)
        depths.append(depth)
        words.append(len(set().union(*(_input_names(nodes, index, names) - control_names for index in residual)) if residual else set()))
        if not fits:
            private[handler['operator']] += 1
            handler['schedule'] = 'private'
        else:
            handler['schedule'] = 'shared'
        handler['data_depth'] = depth
        handler['data_nodes'] = len(residual)
    depths.sort()
    words.sort()

    def quantile(values, fraction):
        return values[min(len(values) - 1, int(fraction * (len(values) - 1)))]

    private_ops = Counter(nodes[index].op for index in union_private)
    # Private handlers are few. Cost them as one gate per boolean/compare/choice
    # and one 24-unit nibble adder per arithmetic node, with cross-handler CSE.
    private_units = (
        private_ops['all'] + private_ops['any'] + private_ops['eq'] + private_ops['ult']
        + private_ops['choose'] + 24 * (private_ops['add'] + private_ops['sub'])
    )
    return dict(
        shared_pipeline_limit=shared_limit,
        shared_handlers=sum(handler['schedule'] == 'shared' for handler in handlers),
        private_handlers=sum(handler['schedule'] == 'private' for handler in handlers),
        private_handlers_by_operator=dict(private),
        data_depth_p50=quantile(depths, 0.5),
        data_depth_p90=quantile(depths, 0.9),
        data_depth_p99=quantile(depths, 0.99),
        data_depth_max=depths[-1],
        data_words_p50=quantile(words, 0.5),
        data_words_p99=quantile(words, 0.99),
        data_words_max=words[-1],
        private_residual_nodes=len(union_private),
        private_residual_ops=dict(private_ops),
        private_circuit_units_with_cse=private_units,
        shared_residual_nodes=len(union_shared),
        joint_units_dispatch_plus_private=None,
    )
