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
from .operations import abstract, has_loose_bvars, instantiate, spine, substitute_levels
from .reduction import BetaZeta


class MissingOperation(Exception):
    """An implementation gap, distinct from rejection or a physical limit."""


@dataclass(frozen=True)
class Signature:
    universe_parameters: tuple
    type: int
    value: Optional[int] = None
    opaque: bool = False


@dataclass(frozen=True)
class FamilyInfo:
    parameters: int
    indices: int
    constructors: tuple
    recursive: bool = False


@dataclass(frozen=True)
class ConstructorInfo:
    family: int
    parameters: int
    fields: int = 0


class KernelServices:
    def __init__(self, arena, context):
        self.a, self.c = arena, context
        self.levels = LevelOps(arena)
        self.constants = {}  # Only a caller's checked environment/private overlay.
        self.recursors = {}
        self.families, self.constructors = {}, {}
        self.beta_zeta = BetaZeta(arena, context)

    @contextmanager
    def overlay(self, entries, recursors=(), families=(), constructors=()):
        """Private, exception-safe declarations. This never publishes a block."""
        original = self.constants.copy()
        original_recursors = self.recursors.copy()
        original_families, original_constructors = self.families.copy(), self.constructors.copy()
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
            self.families.update(families)
            self.constructors.update(constructors)
            yield
        finally:
            self.constants = original
            self.recursors = original_recursors
            self.families, self.constructors = original_families, original_constructors

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
                quotient=getattr(self,'quotient_names',None)
                if quotient is not None and row.a in (quotient[2],quotient[3]):
                    major_position=5 if row.a==quotient[2] else 4
                    if len(args)>major_position:
                        major=self.whnf(args[major_position]);mk,fields=spine(a,major);mk=a.expr(mk)
                        if mk.tag==Tag.CONST and mk.a==quotient[1] and len(fields)==3:
                            root=a.app(a.app(args[3],[fields[2]]),args[major_position+1:]);continue
                if row.a in self.recursors:
                    rec = self.recursors[row.a]
                    if len(args) > rec.major_position:
                        major = args[rec.major_position]
                        if rec.k_eligible:major = self._major_when_k(rec,major)
                        pending.append((root, rec, levels, args))
                        root = major
                        continue
            if row.tag == Tag.PROJ:
                major = self.whnf(row.c)
                if a.expr(major).tag == Tag.STRING:
                    raise MissingOperation('projection String literal preparation not integrated')
                constructor, fields = spine(a, major)
                ctor = a.expr(constructor)
                info = self.constructors.get(ctor.a) if ctor.tag == Tag.CONST else None
                if info is not None and info.parameters+row.b < len(fields):
                    root = a.app(fields[info.parameters+row.b], args)
                    continue
            # K/structure major expansion uses the checked owner family, whose
            # parameter count can differ from a restored auxiliary recursor.
            while pending:
                from .recursor import reduce_constructor_rule
                original, rec, levels, arguments = pending.pop()
                arguments = list(arguments)
                arguments[rec.major_position] = self._major_when_structure(rec,root)
                reduced = reduce_constructor_rule(a, rec, levels, arguments, lambda value: value)
                if reduced is not None:
                    root = reduced
                    break
                root = original
            else:
                return root

    def _nat_primitives(self):
        from .literal_reference import NatPrimitives
        if not hasattr(self,'literal_symbols'):
            raise MissingOperation('Nat literal name context unavailable')
        return NatPrimitives(self,self.literal_symbols)

    def _major_when_k(self,recursor,major):
        a = self.a
        major_type = self.whnf(self.infer(major))
        head,args = spine(a,major_type);head = a.expr(head)
        if head.tag != Tag.CONST or head.a != recursor.owner:return major
        info = self.families.get(head.a)
        if info is None or len(info.constructors) != 1:return major
        constructor = self.constructors.get(info.constructors[0])
        if constructor is None or constructor.fields or len(args) < recursor.parameters:return major
        candidate = a.app(a.const(info.constructors[0],a.vector(head.b)),args[:recursor.parameters])
        return candidate if self.convert(major_type,self.infer(candidate)) else major

    def _major_when_structure(self,recursor,major):
        a = self.a
        row = a.expr(major)
        if row.tag==Tag.NAT:
            return self._nat_primitives().to_constructor(major)
        if row.tag==Tag.STRING:
            raise MissingOperation('String literal recursor-major preparation not integrated')
        head,_ = spine(a,major);head = a.expr(head)
        if head.tag == Tag.CONST and head.a in self.constructors:return major
        info = self._structure(recursor.owner)
        if info is None:return major
        major_type = self.whnf(self.infer(major));head,args = spine(a,major_type);head = a.expr(head)
        if head.tag != Tag.CONST or head.a != recursor.owner:return major
        if self.levels.is_zero(self.ensure_type(major_type)):return major
        constructor = self.constructors.get(info.constructors[0])
        if constructor is None:raise MissingOperation('checked structure constructor metadata unavailable')
        result = a.app(a.const(info.constructors[0],a.vector(head.b)),args[:info.parameters])
        return a.app(result,(a.mk(Tag.PROJ,recursor.owner,index,major) for index in range(constructor.fields)))

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
                    elif row.tag == Tag.PROJ:
                        pending.extend((('projection', ref), ('infer', row.c)))
                    elif row.tag==Tag.NAT:
                        results.append(self._nat_primitives().infer(ref))
                    else:
                        raise MissingOperation('String literal inference not integrated')
                elif operation == 'projection':
                    results.append(self._projection_type(frame[1], self.whnf(results.pop())))
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

    def _projection_type(self, root, major_type):
        """Pinned type_checker::infer_proj, including dependent Prop restrictions."""
        a = self.a
        projection = a.expr(root)
        head, arguments = spine(a, major_type)
        owner = a.expr(head)
        if owner.tag != Tag.CONST or owner.a != projection.a or owner.a not in self.families:
            raise KernelError('invalid projection family')
        info = self.families[owner.a]
        if len(info.constructors) != 1 or len(arguments) != info.parameters+info.indices:
            raise KernelError('invalid projection arity or constructor count')
        type_ref = self._signature_type(a.expr(a.const(info.constructors[0],a.vector(owner.b))))
        for argument in arguments[:info.parameters]:
            a.tick();row = a.expr(self.whnf(type_ref))
            if row.tag != Tag.PI:raise KernelError('invalid projection parameter prefix')
            type_ref = instantiate(a,row.b,(argument,))
        prop = self.levels.is_zero(self.ensure_type(major_type))
        for index in range(projection.b):
            a.tick();row = a.expr(self.whnf(type_ref))
            if row.tag != Tag.PI:raise KernelError('projection field out of range')
            if has_loose_bvars(a,row.b):
                if prop and not self.levels.is_zero(self.ensure_type(row.a)):
                    raise KernelError('dependent data projection from Prop')
                type_ref = instantiate(a,row.b,(a.mk(Tag.PROJ,projection.a,index,projection.c),))
            else:type_ref = row.b
        row = a.expr(self.whnf(type_ref))
        if row.tag != Tag.PI:raise KernelError('projection field out of range')
        if prop and not self.levels.is_zero(self.ensure_type(row.a)):
            raise KernelError('data projection from Prop')
        return row.a

    def _structure(self, symbol):
        info = self.families.get(symbol)
        return info if info is not None and not info.recursive and not info.indices and len(info.constructors) == 1 else None

    def convert(self, left, right):
        """General typed conversion; unfinished genuine primitive extensions GAP.

        Pinned quick binding/literal/Sort rules, checked WHNF, proof irrelevance,
        application congruence, function/structure eta and unit-like equality.
        Eager checked WHNF replaces the pinned lazy delta optimization; different
        physical costs are not an inequality/admission shortcut. Primitive
        preparation remains explicit where the source extension is unfinished.
        """
        a,c = self.a,self.c
        mark = c.mark()
        depth = getattr(self,'_conversion_depth',0)+1
        a.check_stack(range(depth))
        self._conversion_depth = depth
        try:
            return self._convert(left,right)
        finally:
            self._conversion_depth = depth-1
            c.restore(mark)

    def _convert(self,left,right):
        a,c = self.a,self.c
        a.tick()
        if left == right:return True
        def quick(x,y):
            xr,yr = a.expr(x),a.expr(y)
            if x == y:return True
            if xr.tag == yr.tag:
                if xr.tag == Tag.SORT:return self.levels.equal(xr.a,yr.a)
                if xr.tag in (Tag.NAT,Tag.STRING):return a.vector(xr.a) == a.vector(yr.a)
                if xr.tag == Tag.MDATA:return self.convert(xr.a,yr.a)
                if xr.tag in (Tag.PI,Tag.LAM):
                    if not self.convert(xr.a,yr.a):return False
                    with c.scope():
                        local = c.fresh(yr.a,binder_info=yr.c)
                        return self.convert(instantiate(a,xr.b,(local,)),instantiate(a,yr.b,(local,)))
            return None
        result = quick(left,right)
        if result is not None:return result
        x,y = self.whnf(left),self.whnf(right)
        result = quick(x,y)
        if result is not None:return result
        xr,yr = a.expr(x),a.expr(y)
        # If x is a proof, kernel proof irrelevance decides by the proof types.
        tx = self.infer(x)
        if self.levels.is_zero(self.ensure_type(tx)):
            return self.convert(tx,self.infer(y))
        if xr.tag == yr.tag == Tag.CONST and xr.a == yr.a:
            xs,ys = a.vector(xr.b),a.vector(yr.b)
            if len(xs) == len(ys) and all(self.levels.equal(u,v) for u,v in zip(xs,ys)):return True
        if xr.tag == yr.tag == Tag.LOCAL and xr.a == yr.a:return True
        if xr.tag == yr.tag == Tag.PROJ and xr.b == yr.b and self.convert(xr.c,yr.c):return True
        if xr.tag == yr.tag == Tag.APP:
            xf,xa = spine(a,x);yf,ya = spine(a,y)
            if len(xa) == len(ya) and self.convert(xf,yf) and all(self.convert(u,v) for u,v in zip(xa,ya)):
                return True
        for lam,other in ((x,y),(y,x)):
            row = a.expr(lam)
            if row.tag == Tag.LAM and a.expr(other).tag != Tag.LAM:
                ty = a.expr(self.whnf(self.infer(other)))
                if ty.tag == Tag.PI and self.convert(row.a,ty.a):
                    with c.scope():
                        local = c.fresh(ty.a,binder_info=ty.c)
                        if self.convert(instantiate(a,row.b,(local,)),a.app(other,(local,))):return True
        for value,constructed in ((x,y),(y,x)):
            head,args = spine(a,constructed);head = a.expr(head)
            info = self.constructors.get(head.a) if head.tag == Tag.CONST else None
            if info is None or len(args) != info.parameters+info.fields or self._structure(info.family) is None:
                continue
            if not self.convert(self.infer(value),self.infer(constructed)):continue
            if all(self.convert(a.mk(Tag.PROJ,info.family,i,value),args[info.parameters+i]) for i in range(info.fields)):
                return True
        if xr.tag in (Tag.NAT,Tag.STRING) or yr.tag in (Tag.NAT,Tag.STRING):
            raise MissingOperation('literal/constructor conversion preparation not integrated')
        # Unit-like equality is independent of the syntactic form of y.
        type_ref = self.whnf(tx);head,_ = spine(a,type_ref);head = a.expr(head)
        info = self._structure(head.a) if head.tag == Tag.CONST else None
        if info is not None:
            ctor = self.constructors.get(info.constructors[0])
            if ctor is not None and not ctor.fields:return self.convert(type_ref,self.infer(y))
        # Pending Nat/Quot reduction extensions can affect constant-headed apps.
        # Until checked primitive bindings are implemented, do not call their
        # irreducibility a proof of inequality, including literal-free Nat.zero.
        for value in (x,y):
            head,args = spine(a,value)
            if args and a.expr(head).tag == Tag.CONST:
                raise MissingOperation('primitive-aware negative conversion not integrated')
        return False
