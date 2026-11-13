"""Syntax-only structured-name operation loader; never declaration admission.

Only raw names/symbol roots are transported. The model computes the source
recursor-name relation, no host expected-name/validity/type answer is supplied.
"""
from .arena import KernelError
from .syntax import SyntaxCodec
from .native_cells import pack_source,CellCapacities
from .traversal_machine import (BANK_FIELDS,REGISTERS,MachineConfig,Mode,Task,Outcome,Reason,StateLayout,RegisterLayout)
from .traversal_transition import RuleCompiler,compile_addresses,constant_fields,first_banks,second_banks
from .level_transition import boot_length


def parse_document(document):
    if document.get('format')!='leanputer.kernel-name-operation.v1' or document.get('operation')!='recursor_name':
        raise KernelError('expected raw recursor-name operation')
    codec=SyntaxCodec()
    source=codec.document(dict(format='leanputer.kernel-source.v1',status='EXPORTED',declarations=[],
        target=dict(kind='axiom',name=[],level_params=[],type=['sort',['zero']],value=None)))
    parent=codec.symbols.intern(document['parent']);candidate=codec.symbols.intern(document['candidate'])
    return source,(parent,candidate),()


def prepare(config,source,arguments,_decls=()):
    parent,candidate=arguments
    packed=pack_source(source,CellCapacities(heap=config.heap,constants=config.constants,word_bits=config.word_bits),symbol_roots=arguments)
    state={'regs':dict.fromkeys(REGISTERS,0)}
    for bank,width in BANK_FIELDS.items():state[bank]=[[0]*width for _ in range(getattr(config,bank))]
    state['heap'][:packed.initial_free]=[list(row) for row in packed.heap]
    state['regs'].update(mode=int(Mode.WALK),task=int(Task.CHECK_RECURSOR_NAME),free=packed.initial_free,fuel=config.fuel,
        symbols_root=packed.symbols,name_parent_symbol=parent,name_candidate_symbol=candidate,open_tag=6,fold_tag=6)
    return state


def assumptions(_):return []
program_name='kernel.structured-name-operation.v1'
primitive_basis=()
