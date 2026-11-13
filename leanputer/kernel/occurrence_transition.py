"""Syntax-only operation loader; symbol-set membership is checked in weights.

Raw expression and symbol IDs only, no occurrence/positivity/type answers. This
operation is NOT a declaration/proof checker. Source callers derive the family
set in private contexts; this standalone interface transports a raw set.
"""
from .arena import KernelError,ResourceError
from . import traversal_machine as machine
from .traversal_machine import (MachineConfig,Mode,Task,Outcome,Reason,StateLayout,RegisterLayout,boot_length as base_boot)
from .traversal_transition import RuleCompiler,compile_addresses,constant_fields,first_banks,second_banks


def parse_document(document):
    request,unused,decls=machine.parse_document(document)
    if request['task']!=Task.OCCURS:raise KernelError('expected raw occurrence operation')
    prefix=tuple(request['arena'].word(v) for v in document.get('argument_prefix',()))
    return request,prefix,decls


def prepare(config,request,prefix,_decls=()):
    state=machine.prepare(config,request)
    operands=request['operands']
    if len(prefix)+len(operands)>config.context:raise ResourceError('symbol context window')
    if any(v>=1<<config.word_bits for v in prefix):raise ResourceError('prefix word width')
    state['context'][:len(prefix)+len(operands)]=[[v] for v in prefix+operands]
    state['regs'].update(task=int(Task.HAS_CONSTANTS),arg_base=len(prefix),ctx=len(prefix)+len(operands))
    return state


def assumptions(_):return []
def boot_length(bank,state):return state['regs']['ctx'] if bank=='context' else base_boot(bank,state)
program_name='kernel.internal-family-occurrence.v1'
primitive_basis=()
