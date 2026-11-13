"""Data-driven motives, minors, rules and constructor-headed reduction.

The builder runs INSIDE block admission, after header/constructor/positivity
checks. Its inputs are private checked descriptors, never supplied certificates.
This module is an executable spec; native lowering is tracked separately.
"""
from dataclasses import dataclass
from .arena import KernelError, LevelTag, Tag
from .operations import check_scope, instantiate_rev, spine, substitute_levels
from .telescope import consume_parameters, fold_telescope, open_telescope


@dataclass(frozen=True)
class Constructor:
    symbol: int
    type: int


@dataclass(frozen=True)
class Inductive:
    constant: int
    type: int
    constructors: tuple
    recursor_symbol: int


@dataclass(frozen=True)
class Rule:
    constructor: int
    fields: int
    rhs: int


@dataclass(frozen=True)
class Recursor:
    symbol: int
    universe_parameters: tuple
    type: int
    parameters: int
    motives: int
    minors: int
    indices: int
    rules: tuple

    @property
    def major_position(self):
        return self.parameters+self.motives+self.minors+self.indices


def open_recursive_prefix(arena, context, descriptor):
    locals_ = []
    for binder in descriptor.prefix:
        arena.tick()
        domain = instantiate_rev(arena, binder.domain, locals_)
        locals_.append(context.fresh(domain, binder_info=binder.binder_info))
    indices = tuple(instantiate_rev(arena, index, locals_) for index in descriptor.indices)
    return tuple(locals_), indices


class RecursorBuilder:
    def __init__(self, traversal, inductives, universe_parameters, elimination_level,
                 convertible):
        self.traversal = traversal
        self.a, self.c = traversal.arena, traversal.context
        self.inductives = tuple(inductives)
        self.uparams = tuple(universe_parameters)
        self.elim = elimination_level
        self.convertible = convertible
        if len(self.inductives) != len(traversal.families):
            raise KernelError('block descriptor length mismatch')
        for header, ind in zip(traversal.families, self.inductives):
            if header.constant != ind.constant:
                raise KernelError('block descriptor family mismatch')

    def _tail(self, type_ref):
        return consume_parameters(self.a, self.c, type_ref,
            self.traversal.parameters, self.traversal.whnf, self.convertible)

    def _fields(self, constructor):
        return open_telescope(self.a, self.c, self._tail(constructor.type), self.traversal.whnf)

    def _recursive_fields(self, fields):
        result = []
        for field in fields:
            self.a.tick()
            descriptor = self.traversal.recursive_argument(self.c.lookup(field).type)
            if descriptor is not None:
                result.append((field, descriptor))
        return result

    def generate(self):
        a, c, traversal = self.a, self.c, self.traversal
        parameters = traversal.parameters
        elim = a.level_row(self.elim)
        rec_uparams = self.uparams
        if elim.tag == LevelTag.PARAM:
            if elim.a in rec_uparams:
                raise KernelError('elimination level must be fresh')
            rec_uparams = (elim.a,)+rec_uparams
        elif self.elim != a.zero:
            raise KernelError('elimination level must be zero or fresh parameter')
        rec_levels = tuple(a.level(LevelTag.PARAM, p) for p in rec_uparams)
        # All locals introduced here disappear before returning closed records.
        with c.scope():
            motives, indices, majors = [], [], []
            for ind in self.inductives:
                opened = open_telescope(a, c, self._tail(ind.type), traversal.whnf)
                if a.expr(opened.body).tag != Tag.SORT:
                    raise KernelError('family telescope does not end in Sort')
                major = c.fresh(a.app(ind.constant, parameters+opened.locals))
                motive_type = fold_telescope(a, c, opened.locals+(major,), a.mk(Tag.SORT, self.elim))
                motives.append(c.fresh(motive_type))
                indices.append(opened.locals); majors.append(major)
            motives = tuple(motives)
            minors = []
            for ind in self.inductives:
                for ctor in ind.constructors:
                    with c.scope():
                        opened = self._fields(ctor)
                        valid = traversal.valid_application(opened.body)
                        if valid is None:
                            raise KernelError('unchecked constructor result')
                        family, result_indices = valid
                        levels = a.vector(a.expr(ind.constant).b)
                        value = a.app(a.const(ctor.symbol, levels), parameters+opened.locals)
                        result = a.app(motives[family], result_indices+(value,))
                        ihs = []
                        for field, descriptor in self._recursive_fields(opened.locals):
                            with c.scope():
                                xs, ks = open_recursive_prefix(a, c, descriptor)
                                ih = a.app(motives[descriptor.family], ks+(a.app(field, xs),))
                                ih_type = fold_telescope(a, c, xs, ih)
                            ihs.append(c.fresh(ih_type))
                        minor_type = fold_telescope(a, c, opened.locals+tuple(ihs), result)
                    minors.append(c.fresh(minor_type))
            minors = tuple(minors)
            records, minor_position = [], 0
            for i, ind in enumerate(self.inductives):
                result = a.app(motives[i], indices[i]+(majors[i],))
                type_ref = fold_telescope(a, c, parameters+motives+minors+indices[i]+(majors[i],), result)
                rules = []
                for ctor in ind.constructors:
                    with c.scope():
                        opened = self._fields(ctor)
                        ihs = []
                        for field, descriptor in self._recursive_fields(opened.locals):
                            with c.scope():
                                xs, ks = open_recursive_prefix(a, c, descriptor)
                                target = self.inductives[descriptor.family].recursor_symbol
                                ih = a.app(a.const(target, rec_levels),
                                    parameters+motives+minors+ks+(a.app(field, xs),))
                                ihs.append(fold_telescope(a, c, xs, ih, Tag.LAM))
                        result = a.app(minors[minor_position], opened.locals+tuple(ihs))
                        rhs = fold_telescope(a, c, parameters+motives+minors+opened.locals, result, Tag.LAM)
                        check_scope(a, rhs, universe_parameters=rec_uparams)
                        rules.append(Rule(ctor.symbol, len(opened.locals), rhs))
                    minor_position += 1
                check_scope(a, type_ref, universe_parameters=rec_uparams)
                records.append(Recursor(ind.recursor_symbol, rec_uparams, type_ref,
                    len(parameters), len(motives), len(minors), len(indices[i]), tuple(rules)))
            return tuple(records)


def reduce_constructor_rule(arena, recursor, levels, arguments, whnf):
    """Source's rule lookup/apply step, after K/structure/literal major handling.

    None means no constructor-headed reduction, not rejection. K eligibility and
    its type-compatibility check belong to the surrounding reduction service;
    this helper cannot turn neutral proofs into constructors on its own.
    """
    levels, arguments = tuple(levels), tuple(arguments)
    if len(levels) != len(recursor.universe_parameters):
        raise KernelError('recursor universe arity')
    major = recursor.major_position
    if len(arguments) <= major:
        return None
    head, fields = spine(arena, whnf(arguments[major]))
    row = arena.expr(head)
    if row.tag != Tag.CONST:
        return None
    for rule in recursor.rules:
        arena.tick()
        if rule.constructor != row.a:
            continue
        # Restored nested constructors can have a DIFFERENT parameter count
        # from the recursor (inductive.h). Select the derived trailing fields.
        if len(fields) < rule.fields:
            return None
        rhs = substitute_levels(arena, rule.rhs, dict(zip(recursor.universe_parameters, levels)))
        prefix = arguments[:recursor.parameters+recursor.motives+recursor.minors]
        return arena.app(rhs, prefix+fields[len(fields)-rule.fields:]+arguments[major+1:])
    return None
