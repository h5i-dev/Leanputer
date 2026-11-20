"""Source-sized address map for expression, level, and declaration rows.

The original stock domain remains 512 expression rows, 4 declaration slots,
stack 32 and context 8. A larger closure uses the same map with the measured
row counts. Rows are not clipped to those original bounds, and spare physical
key lanes are not extra declaration slots.

This module transports raw exported syntax into an arena. It does not check a
proof, normalize a proof term, or choose weights from a theorem name.
"""
from __future__ import annotations

import math

from .arena import KernelError, Limits, ResourceError
from .semantic_operators import DENSE_LIMIT
from .syntax import SourceUnavailable, SyntaxCodec


NULL = 'null'
IN_RANGE = 'in_range'
INVALID_REFERENCE = 'invalid_reference'
WORD_OVERFLOW = 'word_overflow'

_EXPR_TAGS = frozenset((
    'var', 'local', 'sort', 'const', 'app', 'pi', 'lam', 'let', 'proj',
    'nat', 'string', 'mdata',
))


def _geometry():
    from .semantic_body import (
        ORIGINAL_CONTEXT,
        ORIGINAL_DECLARATIONS,
        ORIGINAL_EXPRESSIONS,
        ORIGINAL_STACK,
        ROWS_PER_LAYER,
        ROWS_PER_PAGE,
        VALUE_HEADS_PER_LAYER,
        WORD_REFERENCE_LIMIT,
    )
    return dict(
        rows_per_page=ROWS_PER_PAGE,
        value_heads=VALUE_HEADS_PER_LAYER,
        rows_per_layer=ROWS_PER_LAYER,
        original_expressions=ORIGINAL_EXPRESSIONS,
        original_declarations=ORIGINAL_DECLARATIONS,
        original_stack=ORIGINAL_STACK,
        original_context=ORIGINAL_CONTEXT,
        word_reference_limit=WORD_REFERENCE_LIMIT,
    )


def _pages(rows, per_page):
    if rows < 0:
        raise ValueError('storage sizes must be nonnegative')
    return math.ceil(rows / per_page) if rows else 0


class AddressDomain:
    """Retained rows are the addressable domain. Physical page padding is not.

    Expression and level references are 1-based, matching the arena. Zero is
    null. A reference above the retained table is an invalid reference even
    when it still lands in the physical page. Declaration indices are 0-based.
    """

    def __init__(self, expression_rows, declaration_slots, stack=32, context=8,
                 level_rows=0, vector_refs=0, vector_cells=0, word_bits=16):
        sizes = (expression_rows, declaration_slots, stack, context,
                 level_rows, vector_refs, vector_cells)
        if any(type(n) is not int or n < 0 for n in sizes):
            raise ValueError('storage sizes must be nonnegative integers')
        if type(word_bits) is not int or word_bits < 1:
            raise ValueError('word width must be positive')
        self.expression_rows = expression_rows
        self.declaration_slots = declaration_slots
        self.stack = stack
        self.context = context
        self.level_rows = level_rows
        self.vector_refs = vector_refs
        self.vector_cells = vector_cells
        self.word_bits = word_bits

    def layout(self):
        geo = _geometry()
        expression_layers = _pages(self.expression_rows, geo['rows_per_layer'])
        level_layers = _pages(self.level_rows, geo['rows_per_layer'])
        small_keys = self.stack + self.context + self.declaration_slots
        small_pages = _pages(small_keys, geo['rows_per_page'])
        small_layers = _pages(small_pages, geo['value_heads'])
        physical_expression_rows = expression_layers * geo['rows_per_layer']
        physical_level_rows = level_layers * geo['rows_per_layer']
        physical_small_keys = small_layers * geo['rows_per_layer']
        indexed = (
            self.expression_rows, self.declaration_slots, self.level_rows,
            self.vector_refs, self.vector_cells,
        )
        exceeds_word = self.word_bits != 16 or any(
            n > geo['word_reference_limit'] for n in indexed
        )
        return dict(
            expression_rows_retained=self.expression_rows,
            declaration_slots=self.declaration_slots,
            declaration_base=self.stack + self.context,
            level_rows=self.level_rows,
            vector_refs=self.vector_refs,
            vector_cells=self.vector_cells,
            vector_bank_placed=False,
            stack=self.stack,
            context=self.context,
            expression_layers=expression_layers,
            level_layers=level_layers,
            small_bank_keys=small_keys,
            small_bank_pages=small_pages,
            small_bank_layers=small_layers,
            memory_layers=expression_layers + level_layers + small_layers,
            physical_expression_rows=physical_expression_rows,
            spare_expression_rows=physical_expression_rows - self.expression_rows,
            spare_expression_rows_are_live=False,
            physical_level_rows=physical_level_rows,
            spare_level_rows=physical_level_rows - self.level_rows,
            spare_level_rows_are_live=False,
            physical_small_keys=physical_small_keys,
            spare_key_lanes=physical_small_keys - small_keys,
            spare_lanes_are_declaration_slots=False,
            fits_word_reference=not exceeds_word,
            exceeds_word_reference=exceeds_word,
            exceeds_original_expression_bound=self.expression_rows > geo['original_expressions'],
            exceeds_original_declaration_bound=self.declaration_slots > geo['original_declarations'],
        )

    def _word(self, ref):
        if type(ref) is not int or ref < 0:
            return INVALID_REFERENCE
        if ref >= 1 << self.word_bits:
            return WORD_OVERFLOW
        return None

    def _fixed_row(self, ref, retained, bank):
        status = self._word(ref)
        if status is not None:
            return dict(bank=bank, outcome=status, reference=ref)
        if ref == 0:
            return dict(bank=bank, outcome=NULL, reference=0)
        if ref > retained:
            return dict(bank=bank, outcome=INVALID_REFERENCE, reference=ref)
        slot = ref - 1
        geo = _geometry()
        return dict(
            bank=bank,
            outcome=IN_RANGE,
            reference=ref,
            layer=slot // geo['rows_per_layer'],
            head=(slot // geo['rows_per_page']) % geo['value_heads'],
            row=slot % geo['rows_per_page'],
        )

    def expression_address(self, ref):
        return self._fixed_row(ref, self.expression_rows, 'expression')

    def level_address(self, ref):
        return self._fixed_row(ref, self.level_rows, 'level')

    def small_address(self, bank, index):
        if bank == 'stack':
            base, limit = 0, self.stack
        elif bank == 'context':
            base, limit = self.stack, self.context
        elif bank == 'declaration':
            base, limit = self.stack + self.context, self.declaration_slots
        else:
            raise ValueError('unknown small bank')
        status = self._word(index)
        if status == WORD_OVERFLOW:
            return dict(bank=bank, outcome=WORD_OVERFLOW, index=index)
        if status is not None or index >= limit:
            return dict(bank=bank, outcome=INVALID_REFERENCE, index=index)
        key = base + index
        if key >= 1 << self.word_bits:
            return dict(bank=bank, outcome=WORD_OVERFLOW, index=index, key=key)
        geo = _geometry()
        page = key // geo['rows_per_page']
        return dict(
            bank=bank,
            outcome=IN_RANGE,
            index=index,
            key=key,
            layer=page // geo['value_heads'],
            head=page % geo['value_heads'],
            row=key % geo['rows_per_page'],
        )


def storage_layout(expressions, declarations, stack, context, word_bits=16,
                   level_rows=0, vector_refs=0, vector_cells=0):
    """Page report for retained rows. Not a placed heap and not a stock forward."""
    if word_bits != 16:
        raise ValueError('the current reference word is 16 bits')
    domain = AddressDomain(
        expressions, declarations, stack, context, level_rows, vector_refs, vector_cells,
        word_bits=word_bits,
    )
    layout = domain.layout()
    geo = _geometry()
    memory_layers = layout['memory_layers']
    dense = 0
    if memory_layers:
        from .semantic_step_circuit import MODEL_INTERMEDIATE, dense_parameters
        dense = dense_parameters(
            768, MODEL_INTERMEDIATE, memory_layers, gdn_layers=memory_layers, value_heads=4,
        )
    layout.update(
        expressions=expressions,
        declarations=declarations,
        rows_per_page=geo['rows_per_page'],
        rows_per_expression_layer=geo['rows_per_layer'],
        memory_only_logical_dense_parameters=dense,
        original_domain=dict(
            expressions=geo['original_expressions'],
            declarations=geo['original_declarations'],
            stack=geo['original_stack'],
            context=geo['original_context'],
        ),
        placed_graph=False,
        stock_emitted=False,
        mathlib_theorems_checked=0,
        proof_checked=False,
        address_map='retained-rows',
        note=(
            'Retained expression, level, and declaration rows are the addressable '
            'domain. Physical page padding is not a live row. Spare small-bank key '
            'lanes are not declaration slots. Vector cells stay counted and are not '
            'placed: a vector is a variable-length word sequence and has no page row '
            'yet. The original-pair compiler contract remains heap512/constants4. '
            'Not a placed heap and not a stock forward.'
        ),
    )
    return layout


def unplaced_logic_joint(storage, logic_layers, logic_dense, hidden=768):
    """Add unplaced memory layers beside an inert logic stack.

    ``logic_dense`` must already be the full-attention parameter count of
    ``logic_layers``, including the embedding once. Memory layers are extra
    linear-attention layers. This sum is not an ``allocate()`` result.
    """
    from .semantic_step_circuit import MODEL_INTERMEDIATE, dense_parameters
    if type(logic_layers) is not int or logic_layers < 0:
        raise ValueError('logic layers must be a nonnegative integer')
    expected = dense_parameters(hidden, MODEL_INTERMEDIATE, logic_layers, gdn_layers=0)
    if logic_dense != expected:
        raise ValueError('logic dense does not match an inert stack of logic_layers')
    memory = storage['memory_layers']
    layers = logic_layers + memory
    dense = dense_parameters(hidden, MODEL_INTERMEDIATE, layers, gdn_layers=memory)
    vectors_open = storage['vector_cells'] > 0 and not storage['vector_bank_placed']
    return dict(
        placed_graph=False,
        stock_emitted=False,
        mathlib_theorems_checked=0,
        proof_checked=False,
        logic_layers=logic_layers,
        logic_logical_dense_parameters=logic_dense,
        memory_layers=memory,
        layers=layers,
        logical_dense_parameters=dense,
        dense_gate=dense <= DENSE_LIMIT and not storage['exceeds_word_reference'] and not vectors_open,
        exceeds_word_reference=storage['exceeds_word_reference'],
        vector_cells_unplaced=vectors_open,
        over_dense_limit_by=max(0, dense - DENSE_LIMIT),
        working_dense_limit=DENSE_LIMIT,
        note=(
            'Unplaced sum of the measured inert logic graph and source-sized '
            'memory layers. Vector cells are not in this sum. Not a stock forward.'
        ),
    )


def name_key(parts):
    """Structured export name. Components stay data; nothing is admitted."""
    if not isinstance(parts, list):
        raise KernelError('name must be a structured component array')
    key = []
    for part in parts:
        if not isinstance(part, dict) or len(part) != 1:
            raise KernelError('invalid name component')
        (tag, value), = part.items()
        if tag == 'str' and isinstance(value, str):
            key.append(('str', value))
        elif tag == 'num' and type(value) is int and value >= 0:
            key.append(('num', value))
        else:
            raise KernelError('invalid name component value')
    return tuple(key)


def declaration_names(row):
    """Kernel constants named by the exported closure, including the target.

    An inductive block contributes its families, constructors, and recursor
    names. Recursor claims that repeat the block recursor stay one constant.
    """
    names = set()

    def add(parts):
        names.add(name_key(parts))

    for item in row['declarations']:
        kind = item['kind']
        if kind == 'inductive_block':
            for family in item['families']:
                add(family['name'])
                add(family['recursor_name'])
                for ctor in family['constructors']:
                    add(ctor['name'])
            for claim in item['recursor_claims']:
                add(claim['name'])
        elif kind in ('axiom', 'definition', 'theorem', 'opaque', 'recursor_claim', 'quot_primitive'):
            add(item['name'])
        else:
            raise KernelError('unknown exported declaration kind')
    add(row['target']['name'])
    return names


def _walk_expr(node, found):
    if not isinstance(node, list) or not node or not isinstance(node[0], str):
        return
    tag = node[0]
    if tag not in _EXPR_TAGS:
        return
    if tag == 'const':
        found.add(name_key(node[1]))
    elif tag == 'proj':
        found.add(name_key(node[1]))
        _walk_expr(node[3], found)
    elif tag in ('pi', 'lam'):
        _walk_expr(node[2], found)
        _walk_expr(node[3], found)
    elif tag in ('app', 'let'):
        for child in node[1:]:
            _walk_expr(child, found)
    elif tag == 'mdata':
        _walk_expr(node[1], found)


def _walk_obj(obj, found):
    if isinstance(obj, list):
        _walk_expr(obj, found)
        for child in obj:
            if isinstance(child, (list, dict)):
                _walk_obj(child, found)
    elif isinstance(obj, dict):
        for value in obj.values():
            _walk_obj(value, found)


def const_references(row):
    """Constant and projection names that occur in exported expressions."""
    found = set()
    _walk_obj(row['target'], found)
    _walk_obj(row['declarations'], found)
    return found


def missing_const_references(row):
    """Referenced constants with no exported declaration. Empty means closed."""
    return const_references(row) - declaration_names(row)


def transport_exported(row, word_bits=16):
    """Intern one exported closure. Parsing is not admission or type checking."""
    if row.get('format') != 'leanputer.kernel-source.v1':
        raise KernelError('expected kernel-source format')
    if row.get('status') != 'EXPORTED':
        raise SourceUnavailable(row.get('reason', 'source was not exported'))
    if 'levels' in row:
        raise KernelError('scheme export does not accept ground-level requests')
    cap = (1 << word_bits) - 1
    limits = Limits(
        expressions=cap,
        levels=cap,
        vector_cells=cap,
        declarations=cap,
        symbols=cap,
        locals=min(cap, 4096),
        stack=min(cap, 8192),
        fuel=2_000_000,
        word_bits=word_bits,
    )
    return SyntaxCodec(limits).document(row)


def measure_transport(row, word_bits=16):
    """Arena size of one closure. A resource error is reported, not clipped."""
    missing = missing_const_references(row)
    if missing:
        raise KernelError('exported const reference has no declaration')
    declared = declaration_names(row)
    base = dict(
        name=row['name'],
        target_kind=row['target']['kind'],
        declaration_records=len(row['declarations']),
        declared_constants=len(declared),
        const_references=len(const_references(row)),
        missing_const_references=0,
        dependencies_dropped=False,
        proof_checked=False,
        admission=None,
    )
    try:
        doc = transport_exported(row, word_bits=word_bits)
    except ResourceError as exc:
        base.update(transported=False, word_bits=word_bits, error=f'{type(exc).__name__}: {exc}')
        return base
    base.update(
        transported=True,
        word_bits=word_bits,
        expression_rows=len(doc.arena.rows) - 1,
        level_rows=len(doc.arena.levels) - 1,
        vector_refs=len(doc.arena.vectors) - 1,
        vector_cells=doc.arena._cells,
        symbols=len(doc.symbols.names) - 1,
        target_has_value=doc.target.value is not None,
    )
    return base
