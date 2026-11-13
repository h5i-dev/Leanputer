"""Typed symbolic-level scope and telescope services in the STOCK controller.

The entry receives raw symbolic level syntax and a parameter vector. The
syntax-only native cell packer loads them; membership/traversal run in weights.
Pi/Lam callers consume that same typed heap. These are reusable kernel services,
not a declaration/proof admission program.
"""
from .arena import KernelError, ResourceError, Tag
from .syntax import RawDeclaration, SourceInput, SyntaxCodec
from .native_cells import CellCapacities, pack_source
from .traversal_machine import (BANK_FIELDS, REGISTERS, MachineConfig, Mode,
    Task, Outcome, Reason, StateLayout, RegisterLayout, boot_length as _boot_length)
from .traversal_transition import RuleCompiler, compile_addresses, constant_fields, first_banks, second_banks


def parse_document(document):
    if document.get('format') == 'leanputer.kernel-data-operation.v1':
        operation = document.get('operation')
        if operation not in ('telescope_roundtrip', 'expr_substitute_raw', 'expr_instantiate'):
            raise KernelError('unknown typed-cell semantic operation')
        codec = SyntaxCodec()
        source = codec.document(document['source'])
        root = document.get('root', 'type')
        if root not in ('type', 'value') or root == 'value' and source.target.value is None:
            raise KernelError('missing syntax root for telescope operation')
        if operation in ('expr_substitute_raw', 'expr_instantiate'):
            bindings = tuple((codec.symbols.intern(binding['parameter']), codec.level(binding['level']))
                             for binding in document['bindings'])
            prefix = tuple(codec.arena.word(value) for value in document.get('argument_prefix', ()))
            return source, dict(operation=operation, root=root, bindings=bindings, argument_prefix=prefix), source.declarations
        kinds = {'pi': int(Tag.PI), 'lam': int(Tag.LAM)}
        open_kind = document.get('open_binder', 'pi')
        fold_kind = document.get('fold_binder', open_kind)
        if open_kind not in kinds or fold_kind not in kinds:
            raise KernelError('invalid telescope binder kind')
        limit = document.get('limit')
        if limit is not None:
            source.arena.word(limit)
        return source, dict(root=root, open_tag=kinds[open_kind], fold_tag=kinds[fold_kind], limit=limit), source.declarations
    operation = document.get('operation')
    if document.get('format') != 'leanputer.kernel-level-operation.v1' or operation not in ('scope', 'substitute_raw', 'substitute_raw_equal', 'equal', 'not_zero', 'offset', 'max', 'imax', 'instantiate', 'compare', 'normalize', 'equivalent'):
        raise KernelError('expected symbolic level-scope operation')
    codec = SyntaxCodec()
    # This is a raw operation argument capsule, not a dummy admitted proof.
    # No value/body or inferred type/admission answer is supplied.
    bindings = ()
    if operation in ('substitute_raw', 'substitute_raw_equal', 'instantiate'):
        bindings = tuple((codec.symbols.intern(binding['parameter']), codec.level(binding['level']))
                         for binding in document['bindings'])
        parameters = tuple(symbol for symbol, _ in bindings)
    else:
        parameters = tuple(codec.symbols.intern(name) for name in document.get('parameters', ()))
    level = codec.level(document['level'])
    peer = codec.level(document['right']) if operation in ('equal', 'substitute_raw_equal', 'max', 'imax', 'compare', 'equivalent') else None
    sort = codec.arena.mk(Tag.SORT, level)
    symbol = codec.symbols.intern([{'str': '_level_operation'}])
    target = RawDeclaration('definition', symbol, parameters, sort, None)
    source = SourceInput(codec.arena, codec.symbols, (), target)
    prefix = tuple(codec.arena.word(value) for value in document.get('argument_prefix', ()))
    arguments = dict(operation=operation, root_level=level, bindings=bindings, argument_prefix=prefix, peer=peer) if operation != 'scope' else level
    return source, arguments, ()


def prepare(config, source, level, _declarations=()):
    operation = level.get('operation') if isinstance(level, dict) else 'scope'
    expression = operation in ('expr_substitute_raw', 'expr_instantiate')
    substitute = operation in ('substitute_raw', 'substitute_raw_equal', 'expr_substitute_raw', 'instantiate', 'expr_instantiate')
    service = operation in ('equal', 'not_zero', 'offset', 'max', 'imax', 'compare', 'equivalent', 'normalize')
    telescope = isinstance(level, dict) and not (substitute or service)
    peer = level.get('peer') if isinstance(level, dict) else None
    bindings = level['bindings'] if substitute else ()
    packed = pack_source(source, CellCapacities(heap=config.heap, constants=config.constants, word_bits=config.word_bits),
                         level_bindings=bindings, level_roots=() if peer is None else (peer,))
    parameters = packed.level_bindings if substitute else () if telescope or service else source.target.universe_parameters
    prefix = level.get('argument_prefix', ()) if substitute else ()
    if any(value >= 1 << config.word_bits for value in prefix):
        raise ResourceError('caller data word width')
    if len(parameters)+len(prefix) > config.context:
        raise ResourceError('universe parameter vector')
    state = {'regs': dict.fromkeys(REGISTERS, 0)}
    for bank, width in BANK_FIELDS.items():
        state[bank] = [[0]*width for _ in range(getattr(config, bank))]
    state['heap'][:packed.initial_free] = [list(row) for row in packed.heap]
    state['constants'][:len(packed.constants)] = [list(row) for row in packed.constants]
    state['context'][:len(prefix)+len(parameters)] = [[p] for p in prefix+tuple(parameters)]
    if telescope or expression:
        raw_root = source.target.type if level['root'] == 'type' else source.target.value
        root = packed.expression_map[raw_root]
    else:
        root = packed.level_map[level['root_level'] if substitute or service else level]
    task = ({'equal': Task.LEVEL_EQUAL, 'not_zero': Task.LEVEL_NOT_ZERO, 'offset': Task.LEVEL_OFFSET, 'max': Task.LEVEL_MAX, 'imax': Task.LEVEL_IMAX, 'compare': Task.LEVEL_ORDER, 'normalize': Task.LEVEL_NORMALIZE, 'equivalent': Task.LEVEL_EQUIVALENT}[operation] if service else
            Task.VARIABLE_SCOPE if telescope else Task.EXPR_LEVEL_INSTANTIATE if operation == 'expr_instantiate' else Task.EXPR_LEVEL_SUBSTITUTE if expression else Task.LEVEL_INSTANTIATE if operation == 'instantiate' else Task.LEVEL_SUBSTITUTE if substitute else Task.LEVEL_SCOPE)
    state['regs'].update(mode=int(Mode.WALK), task=int(task),
        root=root, x=root, free=packed.initial_free, count=len(parameters), ctx=len(prefix)+len(parameters), arg_base=len(prefix),
        fuel=config.fuel, decl_count=len(packed.constants), open_tag=int(Tag.PI), fold_tag=int(Tag.PI))
    if peer is not None:
        state['regs'].update(peer=packed.level_map[peer], pending_compare=int(operation == 'substitute_raw_equal'))
    if telescope:
        limit = level['limit']
        if limit is not None and limit >= 1 << config.word_bits:
            raise ResourceError('telescope prefix word width')
        state['regs'].update(pending_open=1, pending_fold=1, open_tag=level['open_tag'], fold_tag=level['fold_tag'],
                             bounded=int(limit is not None), limit=limit or 0)
    return state


def assumptions(declarations):
    return [d.symbol for d in declarations if isinstance(d, RawDeclaration) and d.kind == 'axiom']


def boot_length(bank, state):
    return (state['regs']['decl_count'] if bank == 'constants' else state['regs']['ctx'] if bank == 'context'
            else _boot_length(bank, state))


program_name = 'kernel.typed-symbolic-services.v8'
primitive_basis = ()
