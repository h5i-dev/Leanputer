"""Compile original source-address DAGs to bounded word/address operations.

All names and expression shapes remain inference data. These compiler records
implement the fixed source controller's address algorithms, including every
16-bit internal-mode value. No source document is inspected here.
"""
from dataclasses import dataclass,replace
from .stock_datapath import CoreRecord,WordAction as O


@dataclass(frozen=True)
class AffineAddressRecord:
    dest: int
    sources: tuple
    constant: int
    yes: int
    @property
    def action(self):return O.CONTEXT_AFFINE3
    def bits(self):
        if len(self.sources)!=3 or self.sources[2][0]!=self.dest:raise ValueError('affine accumulator must be destination word')
        fields=[(int(self.action),6),(self.dest,12)]
        fields.extend((address,12)for address,coefficient in self.sources)
        if any(coefficient not in(-1,0,1)for address,coefficient in self.sources):raise ValueError('affine coefficient bound')
        fields.extend(((int(coefficient==1)|2*int(coefficient==-1)),2)for address,coefficient in self.sources)
        fields.extend(((self.constant,3),(self.yes,16),(0,33)))
        bits=[]
        for value,width in fields:
            if not 0<=value<1<<width:raise ValueError('affine address encoding bound')
            bits.extend(value>>i&1 for i in range(width))
        return bits


@dataclass(frozen=True)
class SparseSwitchRecord:
    a: int
    cases: tuple
    yes: int
    table_id: int = 0
    @property
    def action(self):return O.SPARSE_SWITCH
    def bits(self):
        if len(dict(self.cases))!=len(self.cases)or any(not 0<=key<65536 for key,pc in self.cases):raise ValueError('sparse word dispatch keys')
        return CoreRecord(self.action,a=self.a,yes=self.yes,auxiliary=self.table_id).bits()


def map_cases(record,convert):
    return replace(record,cases=tuple((value,convert(pc))for value,pc in record.cases))if isinstance(record,SparseSwitchRecord)else record


def affine_tree(graph,index,width,choices=None):
    """Exact modular affine extraction; reject unsupported DAGs, never assume."""
    n=graph.nodes[index]
    if n.width<width:raise ValueError('affine source narrower than address')
    if n.op=='choose'and choices is not None and n.args[0]in choices:
        return affine_tree(graph,n.args[1]if choices[n.args[0]]else n.args[2],width,choices)
    if n.op=='input':return {n.data:1},0
    if n.op=='const':return {},n.data%2**width
    if n.op in('extend','slice'):
        if n.op=='slice'and n.data!=0:raise ValueError('shifted address slice')
        return affine_tree(graph,n.args[0],width,choices)
    if n.op in('add','sub'):
        left,c=affine_tree(graph,n.args[0],width,choices);right,d=affine_tree(graph,n.args[1],width,choices);sign=1 if n.op=='add'else-1
        result=dict(left)
        for key,value in right.items():result[key]=result.get(key,0)+sign*value
        result={key:value for key,value in result.items()if value}
        if any(abs(value)>1 for value in result.values()):raise ValueError('affine coefficient exceeds shared address operator')
        return result,(c+sign*d)%2**width
    raise ValueError('non-affine source address '+n.op)


def context_choices(graph,index):
    def strip(i):
        n=graph.nodes[i]
        if n.op in('slice','extend'):
            if n.op=='slice'and n.data!=0:raise ValueError('shifted context selector')
            return strip(n.args[0])
        return i
    def finite(i):
        n=graph.nodes[i]
        if n.op=='eq':
            for a,b in(n.args,n.args[::-1]):
                if graph.nodes[a].op=='input'and graph.nodes[b].op=='const':return a,(graph.nodes[b].data,)
        if n.op=='any':
            pieces=[finite(a)for a in n.args]
            if pieces and all(p and p[0]==pieces[0][0]for p in pieces):return pieces[0][0],tuple(sorted({v for p in pieces for v in p[1]}))
        return None
    tests={};seen=set()
    def collect(i):
        if i in seen:return
        seen.add(i);n=graph.nodes[i]
        if n.op=='choose':
            test=finite(n.args[0])
            if test is None:raise ValueError('context choice is not a finite word test')
            tests[n.args[0]]=test
            for child in n.args[1:]:collect(child)
        else:
            for child in n.args:collect(child)
    collect(index)
    variables={variable for variable,values in tests.values()}
    if len(variables)!=1:raise ValueError('context choices must share one source-defined word selector')
    variable=next(iter(variables));keys=sorted({value for variable,values in tests.values()for value in values})
    if any(not 0<=value<65536 for value in keys):raise ValueError('context selector must retain full16bit keys')
    default_value=next(value for value in range(65536)if value not in keys)
    def scheme(value):
        choices={i:value in values for i,(variable,values)in tests.items()}
        values,constant=affine_tree(graph,index,3,choices)
        return tuple(sorted(values.items())),constant
    return graph.nodes[variable].data,{value:scheme(value)for value in keys},scheme(default_value)


def emit_source_program(native,addresses):
    """Connect all original address expressions through one fixed controller."""
    from .control_ir import Bit
    from .stock_control import temporary_address
    graph,output=addresses[0]
    def bit(index,offset):
        n=graph.nodes[index]
        if n.op=='splice':return bit(n.args[offset],n.data[offset])
        if n.op=='slice':return bit(n.args[0],n.data+offset)
        if n.op=='extend'and offset<graph.nodes[n.args[0]].width:return bit(n.args[0],offset)
        return Bit(index,offset)
    loads=[];cursor=port=0
    for action,cells,words in((O.HEAP_ROW_READ,512,4),(O.FRAME_ROW_READ,32,6),(O.DECLARATION_ROW_READ,4,6)):
        width=cells.bit_length()-1
        word=graph.word(tuple(bit(output.node,cursor+i)for i in range(width)));cursor+=width
        terms,constant=affine_tree(graph,word.node,width)
        if len(terms)!=1 or next(iter(terms.values()))!=1 or constant not in(0,cells-1):raise ValueError('unsupported first source address expression')
        name=next(iter(terms));operand=native.value(native.store.inputs[name])
        if operand.literal:raise ValueError('source bank address must remain register data')
        loads.append((action,temporary_address(port),operand,32768 if constant else 0));port+=words
    g,word=addresses[1];selector,cases,default=context_choices(g,word.node)
    schemes=set(cases.values())|{default}
    if any(len(terms)>4 for terms,constant in schemes):raise ValueError('context address exceeds two shared affine operations')
    labels={scheme:native.label()for scheme in sorted(schemes)}
    native.mark(('source',))
    for action,dest,operand,auxiliary in loads:native.emit(action,dest=dest,a=operand,auxiliary=auxiliary)
    selector_word=native.value(native.store.inputs[selector])
    native.pending.append((SparseSwitchRecord(selector_word.value,tuple((value,labels[scheme])for value,scheme in sorted(cases.items())),0),labels[default],None));native.pending_regions.append(native.region)
    for scheme,label in labels.items():
        native.mark(label);terms,constant=scheme;remaining=list(terms);accumulated=False
        while True:
            piece=remaining[:2];remaining=remaining[2:];dest=temporary_address(670)
            sources=[(native.value(native.store.inputs[name]).value,coefficient)for name,coefficient in piece]
            sources += [(0,0)]*(2-len(sources));sources.append((dest,1 if accumulated else 0))
            following=native.label()if remaining else('load-context',)
            native.pending.append((AffineAddressRecord(dest,tuple(sources),constant if not accumulated else 0,0),following,None));native.pending_regions.append(native.region)
            if not remaining:break
            native.mark(following);accumulated=True
    native.mark(('load-context',));native.emit(O.CONTEXT_ROW_READ,dest=temporary_address(16),a=type(operand)(temporary_address(670)))
    native.emit(O.JUMP,yes=('typed',native.store.entry_pc))
    return dict(derived_from_original_addresses=True,all_selector_values_covered=True,selector_cases=len(cases),distinct_affine_schemes=len(schemes),max_affine_forwards=max(max(1,(len(terms)+1)//2)for terms,constant in schemes),source_bank_read_forwards=8)
