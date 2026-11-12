"""Ground-universe dependent syntax and independent recursive checking oracle.

This module is preparation/testing code. Its infer/convert/reduction functions
are never used by the compiled transition engine's runtime checking path.
"""
from dataclasses import dataclass
from enum import IntEnum


class Unsupported(ValueError):
    pass


class Rejected(ValueError):
    pass


class Exhausted(ValueError):
    pass


class Tag(IntEnum):
    EMPTY = 0
    VAR = 1
    SORT = 2
    PI = 3
    LAM = 4
    APP = 5
    CONST = 6


TAGS = {'var': Tag.VAR, 'sort': Tag.SORT, 'pi': Tag.PI, 'lam': Tag.LAM, 'app': Tag.APP, 'const': Tag.CONST}


def parse_expr(value):
    if not isinstance(value, (tuple, list)) or not value or not isinstance(value[0], str):
        raise ValueError('dependent expressions must be tagged arrays')
    tag = value[0]
    if tag not in TAGS:
        raise Unsupported(f'unsupported expression: {tag}')
    if tag in ('var', 'sort') and len(value) == 2 and type(value[1]) is int and value[1] >= 0:
        return (tag, value[1])
    if tag == 'const' and len(value) == 2 and isinstance(value[1], str) and value[1]:
        return (tag, value[1])
    if tag in ('pi', 'lam', 'app') and len(value) == 3:
        return (tag, parse_expr(value[1]), parse_expr(value[2]))
    raise ValueError(f'malformed dependent {tag} expression')


@dataclass(frozen=True)
class Declaration:
    name: str
    type: tuple
    value: object = None

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError('declaration name required')
        object.__setattr__(self, 'type', parse_expr(self.type))
        if self.value is not None:
            object.__setattr__(self, 'value', parse_expr(self.value))


class Oracle:
    """Recursive algorithm, independently structured from operational frames."""
    def __init__(self, declarations=(), fuel=100000):
        self.environment = {}
        self.remaining = fuel
        for declaration in declarations:
            if declaration.name in self.environment:
                raise Rejected('duplicate declaration')
            if self.whnf(self.infer(declaration.type))[0] != 'sort':
                raise Rejected('declaration type is not a type')
            if declaration.value is not None and not self.convert(self.infer(declaration.value), declaration.type):
                raise Rejected('declaration value type mismatch')
            self.environment[declaration.name] = declaration

    def tick(self):
        self.remaining -= 1
        if self.remaining < 0:
            raise Exhausted('oracle fuel')

    def shift(self, term, delta, cutoff=0):
        self.tick()
        tag = term[0]
        if tag == 'var':
            return ('var', term[1] + (delta if term[1] >= cutoff else 0))
        if tag in ('sort', 'const'):
            return term
        return (tag, self.shift(term[1], delta, cutoff),
                self.shift(term[2], delta, cutoff + int(tag in ('pi', 'lam'))))

    def substitute(self, term, replacement, depth=0):
        self.tick()
        tag = term[0]
        if tag == 'var':
            index = term[1]
            if index == depth:
                return self.shift(replacement, depth)
            return ('var', index - int(index > depth))
        if tag in ('sort', 'const'):
            return term
        return (tag, self.substitute(term[1], replacement, depth),
                self.substitute(term[2], replacement, depth + int(tag in ('pi', 'lam'))))

    def whnf(self, term):
        self.tick()
        if term[0] == 'const':
            declaration = self.environment.get(term[1])
            if declaration is None:
                raise Rejected('unknown constant')
            return self.whnf(declaration.value) if declaration.value is not None else term
        if term[0] == 'app':
            fn = self.whnf(term[1])
            if fn[0] == 'lam':
                return self.whnf(self.substitute(fn[2], term[2]))
            return ('app', fn, term[2])
        return term

    def convert(self, left, right):
        self.tick()
        left, right = self.whnf(left), self.whnf(right)
        if left == right:
            return True
        if left[0] != right[0] or left[0] in ('var', 'sort', 'const'):
            return False
        return self.convert(left[1], right[1]) and self.convert(left[2], right[2])

    def infer(self, term, context=()):
        self.tick()
        tag = term[0]
        if tag == 'sort':
            return ('sort', term[1] + 1)
        if tag == 'var':
            if term[1] >= len(context):
                raise Rejected('unbound de Bruijn variable')
            return self.shift(context[-1-term[1]], term[1]+1)
        if tag == 'const':
            if term[1] not in self.environment:
                raise Rejected('unknown constant')
            return self.environment[term[1]].type
        if tag in ('lam', 'pi'):
            domain_sort = self.whnf(self.infer(term[1], context))
            if domain_sort[0] != 'sort':
                raise Rejected('binder domain is not a type')
            body_type = self.infer(term[2], context + (term[1],))
            if tag == 'lam':
                return ('pi', term[1], body_type)
            body_sort = self.whnf(body_type)
            if body_sort[0] != 'sort':
                raise Rejected('Pi codomain is not a type')
            # Lean imax on ground numeric levels: impredicative Prop.
            return ('sort', 0 if body_sort[1] == 0 else max(domain_sort[1], body_sort[1]))
        fn_type = self.whnf(self.infer(term[1], context))
        if fn_type[0] != 'pi' or not self.convert(self.infer(term[2], context), fn_type[1]):
            raise Rejected('application type mismatch')
        return self.substitute(fn_type[2], term[2])

    def check(self, term, claim):
        if self.whnf(self.infer(claim))[0] != 'sort':
            raise Rejected('claim is not a type')
        if not self.convert(self.infer(term), claim):
            raise Rejected('claim mismatch')
        return True
