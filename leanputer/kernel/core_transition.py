"""Raw CORE-operation loader; never an original-source proof acceptance API.

No nested-transformation/typing/admission answers are loaded. The model checks
ordinary dependencies and core headers/constructors. Original nested-source
processing is a separate unfinished pipeline. A sentinel AX target ensures
this operation can never accidentally accept a proof by falling through.
"""
from .arena import KernelError
from .syntax import SyntaxCodec
from . import source_transition as source_program
from .source_transition import (MachineConfig,Mode,Task,Outcome,Reason,StateLayout,RegisterLayout,
    RuleCompiler,compile_addresses,constant_fields,first_banks,second_banks,boot_length,
    assumptions,assumptions_from_state)


def parse_document(document):
    if document.get('format')!='leanputer.kernel-core-operation.v1' or document.get('operation')!='analyze_core':
        raise KernelError('expected analyze_core operation')
    dependencies=document.get('dependencies',[])
    if not isinstance(dependencies,list):raise KernelError('expected dependency array')
    block=document.get('block')
    if not isinstance(block,dict) or block.get('kind')!='inductive_block':raise KernelError('expected raw core block')
    raw=dict(format='leanputer.kernel-source.v1',status='EXPORTED',declarations=dependencies+[block],
        target=dict(kind='axiom',name=[],level_params=[],type=['sort',['zero']],value=None))
    source=SyntaxCodec().document(raw)
    return source,len(dependencies),source.declarations


def prepare(config,source,index,declarations=()):
    state=source_program.prepare(config,source,None,declarations)
    state['regs'].update(core_operation=1,core_index=index)
    return state

program_name='kernel.inductive-core-operation.v1'
primitive_basis=()
