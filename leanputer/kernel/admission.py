"""Shared inductive admission core from pinned inductive.cpp.

This is the general CORE PHASE after nested-specialization queue processing,
not a raw-declaration admission API. Complete transaction/nested restoration,
primitive initialization and stock lowering remain to be integrated. No caller
may treat this private analysis as a trusted input answer to native inference.
"""
from dataclasses import dataclass
from .arena import KernelError, LevelTag, Tag
from .operations import check_scope, instantiate, spine, substitute_levels
from .positivity import BlockTraversal, Family
from .recursor import RecursorBuilder
from .services import Signature,FamilyInfo,ConstructorInfo
from .telescope import consume_parameters, open_telescope


@dataclass(frozen=True)
class ConstructorAnalysis:
    symbol: int
    fields: int
    recursive_fields: tuple
    has_occurrence: bool
    reflexive: bool


@dataclass(frozen=True)
class FamilyAnalysis:
    symbol: int
    indices: int
    constructors: tuple


@dataclass(frozen=True)
class CoreAnalysis:
    universe_parameters: tuple
    parameters: int
    result_level: int
    families: tuple
    elimination_level: int
    k_eligible: bool
    recursors: tuple

    @property
    def is_recursive(self):
        # The source records syntactic occurrences across the entire mutual
        # block, even if normalization erases one before rec-argument analysis.
        return any(ctor.has_occurrence for family in self.families for ctor in family.constructors)

    @property
    def is_reflexive(self):
        return any(ctor.reflexive for family in self.families for ctor in family.constructors)


def check_recursor_claim(services, expected, claim):
    """Check a supplied scheme against generated data, modulo universe renaming."""
    a = services.a
    if (claim.symbol != expected.symbol or len(set(claim.universe_parameters)) != len(claim.universe_parameters)
            or len(claim.universe_parameters) != len(expected.universe_parameters)):
        raise KernelError('recursor name/universe scheme mismatch')
    check_scope(a, claim.type, universe_parameters=claim.universe_parameters)
    services.ensure_type(claim.type)
    rename = {p: a.level(LevelTag.PARAM, q)
              for p, q in zip(claim.universe_parameters, expected.universe_parameters)}
    if not services.convert(expected.type, substitute_levels(a, claim.type, rename)):
        raise KernelError('recursor scheme differs from generated type')


def analyze_core(services, inductives, universe_parameters, parameter_count, fresh_elimination_symbol,
                 recursor_claims=()):
    """Check all dependent telescopes; derive metadata and recursors privately.

    The outer driver must eliminate nested occurrences and later restore/recheck
    and atomically publish. This helper has no publication/ACCEPT result and no
    proof-loader entry point. A missing internal service propagates as a gap.
    """
    a, c, levels = services.a, services.c, services.levels
    inductives, universe_parameters = tuple(inductives), tuple(universe_parameters)
    a.word(parameter_count)
    if not inductives:
        raise KernelError('empty inductive block')
    if len(set(universe_parameters)) != len(universe_parameters):
        raise KernelError('duplicate universe parameter')
    for p in universe_parameters:
        if not a.word(p):
            raise KernelError('zero universe symbol')
    block_levels = tuple(a.level(LevelTag.PARAM, p) for p in universe_parameters)
    names = set()
    for ind in inductives:
        row = a.expr(ind.constant)
        if row.tag != Tag.CONST or a.vector(row.b) != block_levels:
            raise KernelError('family constant scheme mismatch')
        for symbol in (row.a, ind.recursor_symbol)+tuple(ct.symbol for ct in ind.constructors):
            if not a.word(symbol) or symbol in names or symbol in services.constants:
                raise KernelError('duplicate/invalid declaration name')
            names.add(symbol)
        check_scope(a, ind.type, universe_parameters=universe_parameters)
        for ctor in ind.constructors:
            check_scope(a, ctor.type, universe_parameters=universe_parameters)
    with c.scope():
        # Header types are checked in the previous environment, before the
        # temporary family overlay (self-referential type formers are invalid).
        for ind in inductives:
            services.ensure_type(ind.type)
        params = open_telescope(a, c, inductives[0].type, services.whnf,
                                count=parameter_count).locals
        headers, result_level = [], None
        for ind in inductives:
            tail = consume_parameters(a, c, ind.type, params, services.whnf, services.convert)
            with c.scope():
                indices = open_telescope(a, c, tail, services.whnf)
                result = a.expr(indices.body)
                if result.tag != Tag.SORT:
                    raise KernelError('family type does not end in Sort')
                if result_level is None:
                    result_level = levels.normalize(result.a)
                elif not levels.equal(result_level, result.a):
                    raise KernelError('mutual result universe mismatch')
                headers.append(Family(ind.constant, len(indices.locals)))
        traversal = BlockTraversal(a, c, headers, params, services.whnf)
        analyses = []
        overlay = [(a.expr(ind.constant).a, Signature(universe_parameters, ind.type)) for ind in inductives]
        family_infos = [(a.expr(ind.constant).a,FamilyInfo(parameter_count,headers[i].index_count,tuple(ct.symbol for ct in ind.constructors)))
                        for i,ind in enumerate(inductives)]
        with services.overlay(overlay,families=family_infos):
            for family_index, ind in enumerate(inductives):
                constructors = []
                for ctor in ind.constructors:
                    services.ensure_type(ctor.type)
                    tail = consume_parameters(a, c, ctor.type, params, lambda ref: ref, services.convert)
                    with c.scope():
                        count, recursive, occurrence, reflexive = 0, [], False, False
                        while a.expr(tail).tag == Tag.PI:
                            a.tick()
                            row = a.expr(tail)
                            raw_occurrence = traversal.has_occurrence(row.a)
                            occurrence = occurrence or raw_occurrence
                            reflexive = reflexive or (a.expr(row.a).tag == Tag.PI and raw_occurrence)
                            field_level = services.ensure_type(row.a)
                            if not (a.level_row(result_level).tag == LevelTag.ZERO or levels.geq(result_level, field_level)):
                                raise KernelError('constructor field universe too large')
                            traversal.check_positivity(row.a)
                            descriptor = traversal.recursive_argument(row.a)
                            if descriptor is not None:
                                recursive.append(count)
                            local = c.fresh(row.a, binder_info=row.c)
                            tail = instantiate(a, row.b, (local,))
                            count += 1
                        application = traversal.valid_application(tail)
                        if application is None or application[0] != family_index:
                            raise KernelError('constructor result does not return owning family uniformly')
                        constructors.append(ConstructorAnalysis(ctor.symbol, count, tuple(recursive), occurrence, reflexive))
                analyses.append(FamilyAnalysis(a.expr(ind.constant).a, headers[family_index].index_count, tuple(constructors)))

            # These branches are the pinned elimination/K rules, not supported
            # class dispatch. All telescope traversal above is count-independent.
            large = levels.not_zero(result_level)
            if not large and len(inductives) == 1:
                ctors = inductives[0].constructors
                if not ctors:
                    large = True
                elif len(ctors) == 1:
                    tail = consume_parameters(a, c, ctors[0].type, params, lambda ref: ref, services.convert)
                    with c.scope():
                        non_prop = []
                        while a.expr(tail).tag == Tag.PI:
                            row = a.expr(tail)
                            local = c.fresh(row.a, binder_info=row.c)
                            if a.level_row(services.ensure_type(row.a)).tag != LevelTag.ZERO:
                                non_prop.append(local)
                            tail = instantiate(a, row.b, (local,))
                        _, args = spine(a, tail)
                        large = all(local in args for local in non_prop)
            if large:
                if fresh_elimination_symbol in universe_parameters or not a.word(fresh_elimination_symbol):
                    raise KernelError('fresh elimination universe required')
                elimination_level = a.level(LevelTag.PARAM, fresh_elimination_symbol)
            else:
                elimination_level = a.zero
            k = (len(analyses) == 1 and a.level_row(result_level).tag == LevelTag.ZERO
                 and len(analyses[0].constructors) == 1 and analyses[0].constructors[0].fields == 0)
            constructors = [(ctor.symbol, Signature(universe_parameters, ctor.type))
                for ind in inductives for ctor in ind.constructors]
            constructor_infos = [(ct.symbol,ConstructorInfo(a.expr(ind.constant).a,parameter_count)) for ind in inductives for ct in ind.constructors]
            with services.overlay(constructors,constructors=constructor_infos):
                recursors = RecursorBuilder(traversal, inductives, universe_parameters,
                    elimination_level, services.convert).generate()
                if recursor_claims:
                    claims = {claim.symbol: claim for claim in recursor_claims}
                    if len(claims) != len(recursor_claims) or set(claims) != {rec.symbol for rec in recursors}:
                        raise KernelError('recursor claim set mismatch')
                    for rec in recursors:
                        check_recursor_claim(services, rec, claims[rec.symbol])
            return CoreAnalysis(universe_parameters, parameter_count, result_level,
                tuple(analyses), elimination_level, k, recursors)
