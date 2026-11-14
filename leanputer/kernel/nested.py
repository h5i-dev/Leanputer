"""General nested-specialization queue and restoration expression operations.

Source: pinned Lean inductive.cpp:elim_nested_inductive_fn/restore_nested.
Prior inductives are checked environment DATA. Every specialization copies its
entire prior mutual block; neither container names nor arities select rules.
No positivity flag is assumed. Expanded declarations still require core
checking, then restored schemes/rules require checking before publication.
This module is executable spec, not host preprocessing for native inference.
"""
from dataclasses import dataclass
from .arena import KernelError, LevelTag, ResourceError, Tag
from .operations import (abstract, has_constant, has_loose_bvars, instantiate_rev,
    spine, substitute_levels, transform)
from .recursor import Constructor, Inductive, Recursor, Rule
from .telescope import fold_telescope, open_telescope


@dataclass(frozen=True)
class PriorBlock:
    universe_parameters: tuple
    parameters: int
    families: tuple


@dataclass(frozen=True)
class Template:
    auxiliary: int
    specialization: int       # I Ds, abstracted over current-block parameters.
    constructors: tuple       # (auxiliary constructor, original constructor).


@dataclass(frozen=True)
class NestedResult:
    original_count: int
    parameter_count: int
    families: tuple
    templates: tuple


def instantiate_parameters(arena, root, parameters):
    """Strip the declared Pi prefix, then bulk-instantiate in telescope order."""
    for _ in parameters:
        arena.tick()
        row = arena.expr(root)
        if row.tag != Tag.PI:
            raise KernelError('ill-formed nested parameter prefix')
        root = row.b
    return instantiate_rev(arena, root, parameters)


class NestedSpecializer:
    def __init__(self, arena, context, symbols, prior_blocks, reserved_symbols=(),services=None):
        self.a, self.c, self.symbols = arena, context, symbols
        self.prior = {};self.services=services
        self.reserved = set(reserved_symbols)
        for block in prior_blocks:
            for family in block.families:
                symbol = arena.expr(family.constant).a
                if symbol in self.prior:
                    raise KernelError('duplicate prior family')
                if services is None or symbol in services.families:self.prior[symbol] = block
                self.reserved.update((symbol, family.recursor_symbol))
                self.reserved.update(ctor.symbol for ctor in family.constructors)
        self.counter = 0

    def _fresh(self, original):
        while True:
            self.a.tick()
            self.counter = self.a.word(self.counter+1)
            key = (('str', '_leanputer_nested'),)+self.symbols.names[original]+(('num', self.counter),)
            symbol = self.symbols.intern_key(key)
            recursor = self.symbols.recursor_name(symbol)
            if symbol not in self.reserved and recursor not in self.reserved:
                self.reserved.update((symbol, recursor))
                return symbol

    def specialize(self, families, universe_parameters, parameter_count):
        a, c = self.a, self.c
        queue = list(families)
        original_count = len(queue)
        if not queue:
            raise KernelError('empty inductive block')
        block_levels = tuple(a.level(LevelTag.PARAM, p) for p in universe_parameters)
        current = set()
        for family in queue:
            symbol = a.expr(family.constant).a
            current.add(symbol)
            self.reserved.update((symbol, family.recursor_symbol))
            self.reserved.update(ctor.symbol for ctor in family.constructors)
        with c.scope():
            open_telescope(a, c, queue[0].type, lambda ref: ref, count=parameter_count)
        templates, by_specialization = [], {}

        def replace_nested(ref, parameters):
            if a.expr(ref).tag != Tag.APP:
                return None
            head, arguments = spine(a, ref)
            row = a.expr(head)
            if row.tag != Tag.CONST or row.a not in self.prior:
                return None
            prior = self.prior[row.a]
            count = prior.parameters
            if len(arguments) < count:
                return None
            actual = arguments[:count]
            if not any(has_constant(a, arg, current) for arg in actual):
                return None
            if any(has_loose_bvars(a, arg) for arg in actual):
                raise KernelError('nested parameters contain loose bound variables')
            specialization = abstract(a, a.app(head, actual), parameters)
            if specialization in by_specialization:
                auxiliary = by_specialization[specialization]
                return a.app(a.const(auxiliary, block_levels), parameters+arguments[count:])
            levels = a.vector(row.b)
            if len(levels) != len(prior.universe_parameters):
                raise KernelError('nested constant universe arity')
            result = None
            # Copy ALL members, regardless of which family first occurred.
            for family in prior.families:
                a.tick()
                original = a.expr(family.constant).a
                auxiliary = self._fresh(original)
                template = abstract(a, a.app(a.const(original, levels), actual), parameters)
                by_specialization[template] = auxiliary
                family_type,family_levels=family.type,prior.universe_parameters
                if self.services is not None:
                    if original not in self.services.families:
                        from .services import MissingOperation
                        raise MissingOperation('prior mutual member is no longer an inductive after replacement')
                    signature=self.services.constants[original]
                    family_type,family_levels=signature.type,signature.universe_parameters
                if len(levels)!=len(family_levels):raise KernelError('nested family universe arity')
                type_ref = substitute_levels(a,family_type,dict(zip(family_levels,levels)))
                type_ref = instantiate_parameters(a, type_ref, actual)
                type_ref = fold_telescope(a, c, parameters, type_ref)
                ctors, ctor_mapping = [], []
                for ctor in family.constructors:
                    a.tick()
                    ctor_symbol = self.symbols.replace_prefix(ctor.symbol, original, auxiliary)
                    self.reserved.add(ctor_symbol)
                    ctor_type,ctor_levels=ctor.type,prior.universe_parameters
                    if self.services is not None:
                        signature=self.services.constants[ctor.symbol]
                        ctor_type,ctor_levels=signature.type,signature.universe_parameters
                    if len(levels)!=len(ctor_levels):raise KernelError('nested constructor universe arity')
                    ctor_type = substitute_levels(a,ctor_type,dict(zip(ctor_levels,levels)))
                    ctor_type = instantiate_parameters(a, ctor_type, actual)
                    ctor_type = fold_telescope(a, c, parameters, ctor_type)
                    ctors.append(Constructor(ctor_symbol, ctor_type))
                    ctor_mapping.append((ctor_symbol, ctor.symbol))
                queue.append(Inductive(a.const(auxiliary, block_levels), type_ref, tuple(ctors),
                    self.symbols.recursor_name(auxiliary)))
                current.add(auxiliary)
                templates.append(Template(auxiliary, template, tuple(ctor_mapping)))
                if len(queue)+len(templates) > a.limits.vector_cells:
                    raise ResourceError('nested declaration queue')
                if original == row.a:
                    result = a.app(a.const(auxiliary, block_levels), parameters+arguments[count:])
            if result is None:
                raise KernelError('prior mutual block omits owning family')
            return result

        cursor = 0
        while cursor < len(queue):
            a.tick()
            family = queue[cursor]
            constructors = []
            for ctor in family.constructors:
                with c.scope():
                    opened = open_telescope(a, c, ctor.type, lambda ref: ref, count=parameter_count)
                    rewritten = transform(a, opened.body, lambda ref, depth: replace_nested(ref, opened.locals))
                    rewritten = fold_telescope(a, c, opened.locals, rewritten)
                    constructors.append(Constructor(ctor.symbol, rewritten))
            queue[cursor] = Inductive(family.constant, family.type, tuple(constructors), family.recursor_symbol)
            cursor += 1
        return NestedResult(original_count, parameter_count, tuple(queue), tuple(templates))


class NestedRestorer:
    def __init__(self, arena, context, symbols, result):
        self.a, self.c, self.symbols, self.result = arena, context, symbols, result
        self.templates = {t.auxiliary: t for t in result.templates}
        self.constructors = {aux: (t, original) for t in result.templates for aux, original in t.constructors}
        main = arena.expr(result.families[0].constant).a
        self.recursors = {family.recursor_symbol: symbols.indexed_recursor_name(main, i+1)
            for i, family in enumerate(result.families[result.original_count:])}

    def expression(self, root, rename_recursors=True):
        a, c, count = self.a, self.c, self.result.parameter_count
        tag = a.expr(root).tag
        if count and tag not in (Tag.PI, Tag.LAM):
            raise KernelError('restored expression lacks leading parameters')
        with c.scope():
            if count:
                opened = open_telescope(a, c, root, lambda ref: ref, tag=tag, count=count)
                parameters, root = opened.locals, opened.body
            else:
                parameters = ()
            def visit(ref, depth):
                row = a.expr(ref)
                if row.tag == Tag.CONST and rename_recursors and row.a in self.recursors:
                    return a.const(self.recursors[row.a], a.vector(row.b))
                head, args = spine(a, ref)
                row = a.expr(head)
                if row.tag != Tag.CONST:
                    return None
                template = self.templates.get(row.a)
                constructor = self.constructors.get(row.a)
                if template is None and constructor is None:
                    return None
                if len(args) < count:
                    raise KernelError('auxiliary application lacks parameters')
                if template is not None:
                    specialized = instantiate_rev(a, template.specialization, parameters)
                    return a.app(specialized, args[count:])
                template, original = constructor
                specialized = instantiate_rev(a, template.specialization, parameters)
                family, old_params = spine(a, specialized)
                old_levels = a.vector(a.expr(family).b)
                return a.app(a.const(original, old_levels), old_params+args[count:])
            restored = transform(a, root, visit)
            return fold_telescope(a, c, parameters, restored, tag if count else Tag.PI)

    def recursor_records(self, records):
        restored = []
        for record in records:
            self.a.tick()
            symbol = self.recursors.get(record.symbol, record.symbol)
            rules = []
            for rule in record.rules:
                constructor = rule.constructor
                if record.symbol in self.recursors:
                    if constructor not in self.constructors:
                        raise KernelError('auxiliary recursor rule has unknown constructor')
                    constructor = self.constructors[constructor][1]
                rules.append(Rule(constructor, rule.fields, self.expression(rule.rhs)))
            owner = record.owner
            if owner in self.templates:
                head, _ = spine(self.a,self.templates[owner].specialization)
                owner = self.a.expr(head).a
            restored.append(Recursor(symbol, record.universe_parameters, self.expression(record.type),
                record.parameters, record.motives, record.minors, record.indices, tuple(rules),
                owner,record.k_eligible,record.recursive))
        return tuple(restored)
