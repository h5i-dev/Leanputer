"""General declaration transaction driver, EXECUTABLE SPEC ONLY.

Every declaration body is checked; inductives go through the source nested
queue, checked core, generated recursors, restoration/rechecking and atomic
publication. No returned result or derived metadata feeds a native loader.
Complete conversion/primitives and weighted driver integration remain gaps.
"""
from dataclasses import dataclass
from .admission import analyze_core, check_recursor_claim
from .arena import KernelError, LevelTag, LocalContext, ResourceError
from .nested import NestedRestorer, NestedSpecializer, PriorBlock
from .operations import check_scope
from .recursor import Constructor, Inductive
from .services import KernelServices, MissingOperation, Signature, FamilyInfo, ConstructorInfo
from .syntax import RawBlock, RawDeclaration, RawPrimitive, RawRecursorClaim


class UnsupportedProfile(Exception):
    """A genuine kernel operation outside the authorized safe inference model."""


@dataclass(frozen=True)
class CheckResult:
    status: str
    reason: str
    input_items: int
    checked_input_items: int
    admitted_declarations: int
    assumptions: tuple
    syntax_steps: int
    kernel_steps: int


class EnvironmentDriver:
    def __init__(self, source):
        self.source, self.a, self.symbols = source, source.arena, source.symbols
        self.c = LocalContext(self.a)
        self.services = KernelServices(self.a, self.c)
        self.services.literal_symbols = self.symbols
        self.blocks, self.axioms = [], []
        self.checked_items = 0
        self.syntax_steps = self.a.steps
        self.a.steps = 0

    def _name(self, symbol):
        if not 0 < symbol < len(self.symbols.names):
            raise KernelError('invalid declaration symbol')
        key = self.symbols.names[symbol]
        if key in ((('str', 'Lean'), ('str', 'reduceBool')), (('str', 'Lean'), ('str', 'reduceNat'))):
            # Justified actual kernel native-code interfaces, not ordinary
            # library names. Never execute compiled host code at inference.
            raise UnsupportedProfile('Lean native-code execution is outside the inference model')

    def _scheme(self, parameters, type_ref, value=None):
        if len(set(parameters)) != len(parameters):
            raise KernelError('duplicate universe parameter')
        for symbol in parameters:
            if not 0 < symbol < len(self.symbols.names):
                raise KernelError('invalid universe symbol')
        check_scope(self.a, type_ref, universe_parameters=parameters)
        if value is not None:
            check_scope(self.a, value, universe_parameters=parameters)

    def _new(self, entries):
        names = [symbol for symbol, _ in entries]
        for symbol in names:
            self._name(symbol)
        if len(set(names)) != len(names) or any(n in self.services.constants for n in names):
            raise KernelError('duplicate declaration name')
        if len(names)+len(self.services.constants) > self.a.limits.declarations:
            raise ResourceError('declaration environment')

    def _ordinary(self, declaration, publish):
        s = self.services
        if declaration.kind not in ('axiom', 'definition', 'theorem', 'opaque'):
            raise KernelError('unknown ordinary declaration kind')
        self._name(declaration.symbol)
        self._scheme(declaration.universe_parameters, declaration.type, declaration.value)
        # The target is a new declaration checked under its dependency prefix,
        # not a query allowed to assume an existing declaration of its own name.
        self._new(((declaration.symbol, None),))
        type_level = s.ensure_type(declaration.type)
        if declaration.kind == 'axiom':
            if declaration.value is not None:
                raise KernelError('axiom has a supplied value')
        else:
            if declaration.value is None:
                raise MissingOperation('non-axiom body unavailable; it cannot become an axiom')
            if declaration.kind == 'theorem' and not s.levels.is_zero(type_level):
                raise KernelError('theorem declared type is not a proposition')
            value_type = s.infer(declaration.value)
            if not s.convert(value_type, declaration.type):
                raise KernelError('declaration value type mismatch')
        if publish:
            s.constants[declaration.symbol] = Signature(declaration.universe_parameters,
                declaration.type, declaration.value, declaration.kind == 'opaque')
            if declaration.kind == 'axiom':
                self.axioms.append(declaration.symbol)

    def _block(self, raw):
        a, s = self.a, self.services
        levels = tuple(a.level(LevelTag.PARAM, p) for p in raw.universe_parameters)
        families = []
        original_names = []
        for family in raw.families:
            self._scheme(raw.universe_parameters, family.type)
            if family.recursor_symbol != self.symbols.recursor_name(family.symbol):
                raise KernelError('recursor name is not the kernel-generated name')
            for ctor in family.constructors:
                self._scheme(raw.universe_parameters, ctor.type)
            families.append(Inductive(a.const(family.symbol, levels), family.type,
                tuple(Constructor(ctor.symbol, ctor.type) for ctor in family.constructors), family.recursor_symbol))
            original_names.extend((family.symbol, family.recursor_symbol))
            original_names.extend(ctor.symbol for ctor in family.constructors)
        self._new(tuple((n, None) for n in original_names))
        # Names are finite data and this fresh universe is generated internally,
        # independently of the supplied recursor claims/elimination permissions.
        counter = 0
        while True:
            a.tick()
            fresh = self.symbols.intern_key((('str', '_leanputer_elim'), ('num', counter)))
            if fresh not in raw.universe_parameters:
                break
            counter = a.word(counter+1)
        nested = NestedSpecializer(a, self.c, self.symbols, self.blocks, s.constants).specialize(
            families, raw.universe_parameters, raw.parameters)
        core = analyze_core(s, nested.families, raw.universe_parameters, raw.parameters, fresh)
        restorer = NestedRestorer(a, self.c, self.symbols, nested)
        records = restorer.recursor_records(core.recursors) if nested.templates else core.recursors
        entries = []
        for i, family in enumerate(families):
            entries.append((a.expr(family.constant).a, Signature(raw.universe_parameters, family.type)))
            for ctor in nested.families[i].constructors:
                restored = restorer.expression(ctor.type, rename_recursors=False) if nested.templates else ctor.type
                entries.append((ctor.symbol, Signature(raw.universe_parameters, restored)))
        entries.extend((record.symbol, Signature(record.universe_parameters, record.type)) for record in records)
        self._new(entries)
        # A private overlay allows recursive RHS typing. Nothing is published
        # if any restored signature/rule/claim/scope check fails or is missing.
        family_infos = [(a.expr(family.constant).a,FamilyInfo(raw.parameters,core.families[i].indices,tuple(ct.symbol for ct in family.constructors),core.is_recursive))
                        for i,family in enumerate(families)]
        constructor_infos = [(ct.symbol,ConstructorInfo(a.expr(family.constant).a,raw.parameters,core.families[i].constructors[j].fields)) for i,family in enumerate(families) for j,ct in enumerate(family.constructors)]
        with s.overlay(entries, records, family_infos, constructor_infos):
            for _, signature in entries:
                self._scheme(signature.universe_parameters, signature.type)
                s.ensure_type(signature.type)
            for record in records:
                for rule in record.rules:
                    check_scope(a, rule.rhs, universe_parameters=record.universe_parameters)
                    s.infer(rule.rhs)
            by_name = {record.symbol: record for record in records}
            seen = set()
            for claim in raw.recursor_claims:
                if claim.symbol in seen or claim.symbol not in by_name:
                    raise KernelError('duplicate/unknown recursor claim')
                seen.add(claim.symbol)
                check_recursor_claim(s, by_name[claim.symbol], claim)
            for family in families:
                for ctor in family.constructors:
                    if not s.convert(ctor.type, s.constants[ctor.symbol].type):
                        raise KernelError('restored constructor type differs from input')
        # Atomic publication. Prior container descriptors retain ORIGINAL raw
        # types for the next block's specialization, never auxiliary artifacts.
        s.constants.update(entries)
        s.families.update(family_infos)
        s.constructors.update(constructor_infos)
        s.recursors.update((record.symbol, record) for record in records)
        self.blocks.append(PriorBlock(raw.universe_parameters, raw.parameters, tuple(families)))

    def check(self):
        status, reason = 'ACCEPT', ''
        try:
            for declaration in self.source.declarations:
                if isinstance(declaration, RawDeclaration):
                    self._ordinary(declaration, True)
                elif isinstance(declaration, RawBlock):
                    self._block(declaration)
                elif isinstance(declaration, RawRecursorClaim):
                    if declaration.symbol not in self.services.recursors:
                        raise KernelError('unregistered recursor claim')
                    check_recursor_claim(self.services, self.services.recursors[declaration.symbol], declaration)
                elif isinstance(declaration, RawPrimitive):
                    from .quotient import initialize
                    initialize(self,declaration)
                else:
                    raise KernelError('unknown raw declaration record')
                self.checked_items += 1
            if self.source.target.kind == 'axiom':
                raise KernelError('target must have a checked body')
            self._ordinary(self.source.target, False)
            if self.c.mark():
                raise AssertionError('kernel driver leaked local scope')
        except MissingOperation as error:
            status, reason = 'GAP', str(error)
        except UnsupportedProfile as error:
            status, reason = 'UNSUPPORTED_PROFILE', str(error)
        except ResourceError as error:
            status, reason = 'RESOURCE', str(error)
        except KernelError as error:
            status, reason = 'REJECT', str(error)
        if self.c.mark():
            raise AssertionError('kernel driver leaked local scope on exit')
        return CheckResult(status, reason, len(self.source.declarations), self.checked_items,
            len(self.services.constants), tuple(self.axioms), self.syntax_steps, self.a.steps)
