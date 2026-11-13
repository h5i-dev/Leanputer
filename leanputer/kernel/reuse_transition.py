"""Syntax-only operation loader for general dependent telescope parameter reuse.

This is NOT declaration acceptance. Raw type/candidate/count are data; the model
scope-checks both, derives fresh parameter Locals, then checks domain reuse. No
Local/type/uniformity answers are packed. Raw dependencies are never admitted.
"""
from .arena import KernelError,ResourceError,Tag
from .syntax import SyntaxCodec
from .native_cells import CellCapacities,pack_source
from .traversal_machine import (BANK_FIELDS,REGISTERS,MachineConfig,Mode,Task,
    Outcome,Reason,StateLayout,RegisterLayout)
from .traversal_transition import RuleCompiler,compile_addresses,constant_fields,first_banks,second_banks
from .level_transition import boot_length


def parse_document(document):
    if document.get('format')!='leanputer.kernel-telescope-reuse.v1':raise KernelError('expected telescope reuse operation')
    source=SyntaxCodec().document(document['source'])
    if source.target.value is None:raise KernelError('candidate telescope syntax required')
    count=source.arena.word(document['parameters'])
    policy=document.get('normalize',True)
    if type(policy)is not bool:raise KernelError('normalization policy must be Boolean')
    return source,(count,policy),source.declarations


def prepare(config,source,arguments,_declarations=()):
    count,policy=arguments
    if count>=1<<config.word_bits:raise ResourceError('parameter prefix word width')
    packed=pack_source(source,CellCapacities(heap=config.heap,constants=config.constants,word_bits=config.word_bits))
    state={'regs':dict.fromkeys(REGISTERS,0)}
    for bank,width in BANK_FIELDS.items():state[bank]=[[0]*width for _ in range(getattr(config,bank))]
    state['heap'][:packed.initial_free]=[list(row) for row in packed.heap]
    state['constants'][:len(packed.constants)]=[list(row) for row in packed.constants]
    state['regs'].update(free=packed.initial_free,fuel=config.fuel,task=int(Task.LOAD_PARAMETERS),mode=int(Mode.WALK),
        x=packed.target[2],root=packed.target[3],reuse_root=packed.target[4],reuse_end=count,reuse_whnf=int(policy),
        pending_reuse=1,decl_count=len(packed.constants),symbols_root=packed.symbols,open_tag=int(Tag.PI),fold_tag=int(Tag.PI))
    return state


def assumptions(_):return []
program_name='kernel.general-dependent-telescope.v1'
primitive_basis=()
