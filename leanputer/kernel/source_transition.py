"""Syntax-only original-source loader for the weighted declaration controller.

No inference/checking/reduction/spec admission routines are imported or called.
The target is the last RAW bank row, not an assumed checked signature. Missing
kernel services are reported by the model as GAP, not patched with host answers.
"""
from .arena import KernelError, ResourceError, Tag
from .syntax import SyntaxCodec, RawDeclaration
from .native_cells import CellCapacities, pack_source
from .traversal_machine import (BANK_FIELDS, REGISTERS, MachineConfig, Mode, Task,
    Outcome, Reason, StateLayout, RegisterLayout)
from .level_transition import boot_length
from .traversal_transition import (RuleCompiler, compile_addresses, constant_fields,
    first_banks, second_banks)


def parse_document(document):
    source = SyntaxCodec().document(document)
    return source, None, source.declarations


def prepare(config, source, _unused=None, _declarations=()):
    packed = pack_source(source, CellCapacities(heap=config.heap, constants=config.constants, word_bits=config.word_bits))
    raw = packed.constants+(packed.target,)
    if len(raw) > config.constants:
        raise ResourceError('raw dependency+target declaration bank')
    state = {'regs': dict.fromkeys(REGISTERS, 0)}
    for bank, width in BANK_FIELDS.items(): state[bank] = [[0]*width for _ in range(getattr(config, bank))]
    state['heap'][:packed.initial_free] = [list(row) for row in packed.heap]
    state['constants'][:len(raw)] = [list(row) for row in raw]
    state['regs'].update(mode=int(Mode.WALK), task=int(Task.CHECK_SOURCE), free=packed.initial_free,
        decl_count=len(raw), target_index=len(source.declarations), symbols_root=packed.symbols,
        fuel=config.fuel, open_tag=int(Tag.PI), fold_tag=int(Tag.PI))
    return state


def assumptions(declarations):
    # Candidate syntax only. The native runner's state-aware hook below is used
    # to report the actually committed source prefix on both success and failure.
    return [d.symbol for d in declarations if isinstance(d, RawDeclaration) and d.kind == 'axiom']


def assumptions_from_state(declarations, registers):
    prefix = declarations[:registers['raw_index']]
    return assumptions(prefix)


program_name = 'kernel.source-transactions.v1'
primitive_basis = ()
