"""Syntax-only encoder and independent recursive testing oracle."""
import torch

class ResourceLimit(ValueError):
    pass

def parse_type(value):
    """Canonicalize an atom or a two-element JSON/Python arrow pair."""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return (parse_type(value[0]), parse_type(value[1]))
    raise ValueError('types must be nonempty atom strings or arrow pairs')

def Var(name):
    return ('var', name)

def Lam(name, domain, body):
    return ('lam', name, domain, body)

def App(fn, arg):
    return ('app', fn, arg)

def infer(term, context=None):
    context = {} if context is None else context
    if term[0] == 'var':
        if term[1] not in context:
            raise ValueError('unbound variable')
        return context[term[1]]
    if term[0] == 'lam':
        return (term[2], infer(term[3], {**context, term[1]: term[2]}))
    if term[0] == 'app':
        fn, arg = infer(term[1], context), infer(term[2], context)
        if not isinstance(fn, tuple) or fn[0] != arg:
            raise ValueError('application type mismatch')
        return fn[1]
    raise ValueError('unsupported syntax')

def reference_check(term, claim):
    try:
        return infer(term) == claim
    except ValueError:
        return False

def encode(model, term, claim):
    """Postorder AST encoding with lexical names resolved to binder node IDs.

    No type inference or proof validation. Unknown names become self references,
    rejected by compiled scope checks. Resource limits are separate errors.
    """
    nodes, scopes = [], []
    def visit(t, scope, depth=0):
        if depth > model.config.nodes:
            raise ResourceLimit('AST depth capacity exceeded')
        if not isinstance(t, (tuple, list)):
            raise ValueError('unsupported or malformed term')
        if len(t) == 2 and t[0] == 'var' and isinstance(t[1], str):
            node = ('var', t[1])
        elif len(t) == 4 and t[0] == 'lam' and isinstance(t[1], str):
            handle = []
            child = visit(t[3], {**scope, t[1]: handle}, depth + 1)
            node = ('lam', parse_type(t[2]), child)
        elif len(t) == 3 and t[0] == 'app':
            node = ('app', visit(t[1], scope, depth + 1), visit(t[2], scope, depth + 1))
        else:
            raise ValueError('unsupported or malformed term')
        idx = len(nodes)
        nodes.append(node)
        scopes.append(scope)
        if t[0] == 'lam':
            handle.append(idx)
        if len(nodes) > model.config.nodes:
            raise ResourceLimit('AST node capacity exceeded')
        return idx
    visit(term, {})
    cfg = model.config
    offset = cfg.nodes - len(nodes)
    values = {name: 0.0 for name in model.input_names}
    for i in range(offset):
        values[f'tag/{i}/pad'] = 1.0
    for ix, node in enumerate(nodes):
        i, tag = ix + offset, node[0]
        values[f'tag/{i}/{tag}'] = 1.0
        if tag == 'var':
            handle = scopes[ix].get(node[1])
            target = handle[0] + offset if handle else i
            values[f'bind/{i}/{target}'] = 1.0
        elif tag == 'lam':
            if node[1] not in cfg.types:
                raise ResourceLimit('annotation outside compiled type vocabulary')
            values[f'ann/{i}/{cfg.types.index(node[1])}'] = 1.0
            values[f'a/{i}/{node[2] + offset}'] = 1.0
        else:
            values[f'a/{i}/{node[1] + offset}'] = 1.0
            values[f'b/{i}/{node[2] + offset}'] = 1.0
    claim = parse_type(claim)
    if claim not in cfg.types:
        raise ResourceLimit('statement outside compiled type vocabulary')
    values[f'claim/{cfg.types.index(claim)}'] = 1.0
    return torch.tensor([[values[name] for name in model.input_names]], dtype=torch.float32, device='cpu')
