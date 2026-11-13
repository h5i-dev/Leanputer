"""Internal expression/level services for the general kernel specification.

This is development code, NOT a native-checker callback. Incomplete conversion
and primitive operations raise MissingOperation rather than returning false or
admitting supplied answers. The complete service contract is target.md.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional
from .arena import KernelError, ResourceError, Tag
from .levels import LevelOps
from .operations import abstract, instantiate, spine, substitute_levels
from .reduction import BetaZeta


class MissingOperation(Exception):
    """An implementation gap, distinct from rejection or a physical limit."""


@dataclass(frozen=True)
class Signature:
    universe_parameters: tuple
    type: int
    value: Optional[int] = None
    opaque: bool = False


class KernelServices:
    def __init__(self, arena, context):
        self.a, self.c = arena, context
        self.levels = LevelOps(arena)
        self.constants = {}  # Only a caller's checked environment/private overlay.
        self.recursors = {}
        self.beta_zeta = BetaZeta(arena, context)

    @contextmanager
    def overlay(self, entries, recursors=()):
        """Private, exception-safe declarations. This never publishes a block."""
        original = self.constants.copy()
        original_recursors = self.recursors.copy()
        try:
            for symbol, signature in entries:
                if symbol in self.constants:
                    raise KernelError('duplicate declaration name')
                if len(self.constants) >= self.a.limits.declarations:
                    raise ResourceError('private declaration environment')
                self.constants[symbol] = signature
            for record in recursors:
                if record.symbol in self.recursors or record.symbol not in self.constants:
                    raise KernelError('invalid staged recursor registration')
                self.recursors[record.symbol] = record
            yield
        finally:
            self.constants = original
            self.recursors = original_recursors

    def _signature_type(self, row):
        if row.a not in self.constants:
            raise KernelError('undeclared constant')
        sig = self.constants[row.a]
        levels = self.a.vector(row.b)
        if len(levels) != len(sig.universe_parameters):
            raise KernelError('constant universe arity')
        return substitute_levels(self.a, sig.type, dict(zip(sig.universe_parameters, levels)))

    def whnf(self, root):
        a, pending = self.a, []
        while True:
            a.tick(); a.check_stack(pending)
            root = self.beta_zeta(root)
            head, args = spine(a, root)
            row = a.expr(head)
            if row.tag == Tag.CONST and row.a in self.constants:
                sig = self.constants[row.a]
                levels = a.vector(row.b)
                if len(levels) != len(sig.universe_parameters):
                    raise KernelError('constant universe arity')
                if sig.value is not None and not sig.opaque:
                    value = substitute_levels(a, sig.value, dict(zip(sig.universe_parameters, levels)))
                    root = a.app(value, args)
                    continue
                if row.a in self.recursors:
                    rec = self.recursors[row.a]
                    if len(args) > rec.major_position:
                        pending.append((root, rec, levels, args))
                        root = args[rec.major_position]
                        continue
            # Constructor-headed reduction is implemented. K/structure/literal
            # major expansion, projection and genuine primitives are still gaps.
            while pending:
                from .recursor import reduce_constructor_rule
                original, rec, levels, arguments = pending.pop()
                arguments = list(arguments)
                arguments[rec.major_position] = root
                reduced = reduce_constructor_rule(a, rec, levels, arguments, lambda value: value)
                if reduced is not None:
                    root = reduced
                    break
                root = original
            else:
                return root

    def ensure_type(self, root):
        type_ref = self.whnf(self.infer(root))
        row = self.a.expr(type_ref)
        if row.tag != Tag.SORT:
            raise KernelError('expected type with inferred Sort')
        return self.levels.normalize(row.a)

    def infer(self, root):
        """Finite expression-tag rules with explicit continuation/scope frames."""
        a, c = self.a, self.c
        initial_scope = c.mark()
        pending, results = [('infer', root)], []
        try:
            while pending:
                a.check_stack(pending); a.tick()
                frame = pending.pop()
                operation = frame[0]
                if operation == 'infer':
                    ref = frame[1]
                    row = a.expr(ref)
                    if row.tag == Tag.BVAR:
                        raise KernelError('loose bound variable in opened inference')
                    if row.tag == Tag.LOCAL:
                        results.append(c.lookup(ref).type)
                    elif row.tag == Tag.SORT:
                        results.append(a.mk(Tag.SORT, self.levels.succ(row.a)))
                    elif row.tag == Tag.CONST:
                        results.append(self._signature_type(row))
                    elif row.tag == Tag.MDATA:
                        pending.append(('infer', row.a))
                    elif row.tag in (Tag.PI, Tag.LAM):
                        pending.extend((('binder_domain', ref), ('infer', row.a)))
                    elif row.tag == Tag.APP:
                        pending.extend((('function', row.b), ('infer', row.a)))
                    elif row.tag == Tag.LET:
                        pending.extend((('let_type', ref), ('infer', row.a)))
                    else:
                        raise MissingOperation('projection/literal inference not integrated')
                elif operation == 'binder_domain':
                    row = a.expr(frame[1])
                    domain_sort = a.expr(self.whnf(results.pop()))
                    if domain_sort.tag != Tag.SORT:
                        raise KernelError('binder domain is not a type')
                    mark = c.mark()
                    local = c.fresh(row.a, binder_info=row.c)
                    body = instantiate(a, row.b, (local,))
                    pending.extend((('binder_body', frame[1], local, mark, domain_sort.a), ('infer', body)))
                elif operation == 'binder_body':
                    _, ref, local, mark, domain_level = frame
                    row, body_type = a.expr(ref), results.pop()
                    if row.tag == Tag.PI:
                        body_sort = a.expr(self.whnf(body_type))
                        if body_sort.tag != Tag.SORT:
                            raise KernelError('Pi body is not a type')
                        result = a.mk(Tag.SORT, self.levels.imax(
                            self.levels.normalize(domain_level), self.levels.normalize(body_sort.a)))
                    else:
                        result = a.mk(Tag.PI, row.a, abstract(a, body_type, (local,)), row.c)
                    c.restore(mark)
                    results.append(result)
                elif operation == 'function':
                    function_type = a.expr(self.whnf(results.pop()))
                    if function_type.tag != Tag.PI:
                        raise KernelError('application function does not infer Pi')
                    pending.extend((('argument', function_type.a, function_type.b, frame[1]), ('infer', frame[1])))
                elif operation == 'argument':
                    _, domain, body, value = frame
                    if not self.convert(results.pop(), domain):
                        raise KernelError('application argument type mismatch')
                    results.append(instantiate(a, body, (value,)))
                elif operation == 'let_type':
                    row = a.expr(frame[1])
                    if a.expr(self.whnf(results.pop())).tag != Tag.SORT:
                        raise KernelError('let annotation is not a type')
                    pending.extend((('let_value', frame[1]), ('infer', row.b)))
                elif operation == 'let_value':
                    row = a.expr(frame[1])
                    if not self.convert(results.pop(), row.a):
                        raise KernelError('let value type mismatch')
                    pending.append(('infer', instantiate(a, row.c, (row.b,))))
                else:
                    raise AssertionError('unknown internal continuation')
            if len(results) != 1:
                raise AssertionError('inference continuation result imbalance')
            return results[0]
        finally:
            c.restore(initial_scope)

    def convert(self, left, right):
        """Implemented positive congruence fragment; gaps cannot mean false.

        A top-level Sort comparison can return false. A failed congruence child
        cannot establish inequality of its parent (proof irrelevance/delta/eta
        may still apply), so it raises MissingOperation.
        """
        a, c = self.a, self.c
        initial_scope = c.mark()
        pending = [(left, right, True)]
        try:
            while pending:
                a.check_stack(pending); a.tick()
                x, y, top = pending.pop()
                x, y = self.whnf(x), self.whnf(y)
                if x == y:
                    continue
                xr, yr = a.expr(x), a.expr(y)
                if xr.tag == yr.tag == Tag.SORT:
                    if self.levels.equal(xr.a, yr.a):
                        continue
                    if top:
                        return False
                elif xr.tag == yr.tag == Tag.CONST and xr.a == yr.a:
                    xs, ys = a.vector(xr.b), a.vector(yr.b)
                    if len(xs) == len(ys) and all(self.levels.equal(p, q) for p, q in zip(xs, ys)):
                        continue
                elif xr.tag == yr.tag and xr.tag in (Tag.PI, Tag.LAM):
                    # Infer/validate callers establish the binder types. The
                    # Local remains live until this conversion scope finishes.
                    local = c.fresh(xr.a)
                    pending.extend(((instantiate(a, xr.b, (local,)), instantiate(a, yr.b, (local,)), False),
                                    (xr.a, yr.a, False)))
                    continue
                elif xr.tag == yr.tag == Tag.APP:
                    pending.extend(((xr.a, yr.a, False), (xr.b, yr.b, False)))
                    continue
                raise MissingOperation('typed proof irrelevance/eta/full conversion not integrated')
            return True
        finally:
            c.restore(initial_scope)
