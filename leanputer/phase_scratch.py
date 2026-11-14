"""Compiler-only owner-scoped scratch; no inference dispatcher or executor."""
from dataclasses import replace
from copy import copy
from types import SimpleNamespace

from .native_vendor.qwenputer.emit import allocate, Alloc
from .native_vendor.qwenputer.ir import FFN, Head


def operation_map(circuit):
    result={}
    for w,a,b in getattr(circuit,'native_word_comparisons',[]):result.setdefault(w,('lt',None,a,b,False))
    for w,a,b in getattr(circuit,'native_word_equalities',[]):result.setdefault(w,('eq',None,a,b,False))
    for op,outputs,a,b,control in getattr(circuit,'native_word_operations',[]):
        entry=(op,outputs,a,b,control)
        for w in outputs:
            if w>max(a+b+((control,)if op=='mux'else())):result.setdefault(w,entry)
    return result


def domains(circuit,outputs,operations):
    info=circuit.native_phase_context;count=info['count'];ALL=(1<<count)-1
    zero=list(info['zero'])+[0]*(len(circuit.depth)-len(info['zero']))
    one=list(info['one'])+[0]*(len(circuit.depth)-len(info['one']))
    all_cases=(1<<(3*count))-1
    for w,op,args in circuit.gates:
        if op=='not':z,o=one[args[0]],zero[args[0]]
        elif op=='and':
            z=0;o=all_cases
            for a in args:z|=zero[a];o&=one[a]
        else:
            z=all_cases;o=0
            for a in args:z&=zero[a];o|=one[a]
        fz=info['forced_zero'].get(w,0);fo=info['forced_one'].get(w,0)
        zero[w]=(z|fz)&~fo;one[w]=(o|fo)&~fz
    compressed={0:0,all_cases:ALL}
    def compress(mask):
        if mask not in compressed:compressed[mask]=sum(1<<i for i in range(count)if mask&(7<<(3*i)))
        return compressed[mask]
    may1=[compress(mask)for mask in one]
    normalize=lambda mask:ALL if mask&(mask-1)else mask
    needed=[0]*len(circuit.depth);op_domains={}
    for w in outputs:needed[w]|=may1[w]
    for w,op,args in reversed(circuit.gates):
        mask=normalize(needed[w]);needed[w]=mask
        if not mask:continue
        if w in operations:
            entry=operations[w];kind,outs,a,b,control=entry
            mask=normalize(op_domains.get(entry,0)|mask);op_domains[entry]=mask
            args=a+b+((control,)if kind=='mux'else())
        for a in args:needed[a]|=mask&may1[a]
    def owner(mask):
        return None if mask==ALL else mask.bit_length()-1 if mask else -1
    return [owner(normalize(mask))for mask in needed],{entry:owner(mask)for entry,mask in op_domains.items()}


def allocate_scoped(graph,keep,unit_cap):
    """Allocate shared values once and overlap independent owner-local windows.

    Local lifetimes use the ordinary allocator with every read retained. Their
    subtraction units share the same physical layer budget. Local clears are
    conditional on the model owner guard; shared-slot clears stay unconditional.
    """
    dimensions={}
    for node in graph.nodes:
        ds=[node.out]if isinstance(node,FFN)else[d for vh in node.vheads()for _,d,_ in vh.out]
        for d in ds:
            scope=getattr(node,'scope',None)
            if d not in dimensions:dimensions[d]=scope
            elif dimensions[d]!=scope:dimensions[d]=None
    for d in graph.token_fns:dimensions[d]=None
    for d in keep:dimensions[d]=None
    groups={None:{d for d,scope in dimensions.items()if scope is None}}
    for d,scope in dimensions.items():
        if scope is not None:groups.setdefault(scope,set()).add(d)
    units=dict(graph.units);merged=Alloc({},0);base=0;private_width=0;stats={}
    definitions={node.out:node.level for node in reversed(graph.nodes)if isinstance(node,FFN)and not node.into}
    for scope,selected in groups.items():
        nodes=[]
        for n in graph.nodes:
            if isinstance(n,FFN)and n.out not in selected:n=copy(n);n.into=True
            elif isinstance(n,Head)and scope is not None:n=replace(n,into=True,vx=[replace(vh,into=True)for vh in n.vx])
            nodes.append(n)
        proxy=SimpleNamespace(nodes=nodes,dims=graph.dims,token_fns={d:f for d,f in graph.token_fns.items()if d in selected},
            big=graph.big,units=units)
        part=allocate(proxy,None,set(keep)&selected,unit_cap)
        offset=0 if scope is None else base
        merged.slots.update({d:s+offset for d,s in part.slots.items()})
        merged.subtract.update(part.subtract)
        for level,old in part.clears.items():merged.clears.setdefault(level,[]).extend(old)
        for d in part.subtract:units[definitions[d]]=units.get(definitions[d],0)+1
        for level,old in part.clears.items():units[level]=units.get(level,0)+len(old)
        if scope is None:base=part.n_slots
        else:private_width=max(private_width,part.n_slots)
        stats[str(scope)]=part.n_slots
    # No private heads are permitted: each head's cache/outputs are shared.
    if any(isinstance(n,Head)and any(dimensions[d]is not None for vh in n.vheads()for _,d,_ in vh.out)for n in graph.nodes):
        raise ValueError('scoped native heads require a different allocation proof')
    merged.n_slots=base+private_width
    merged.clear_guards={d:graph.scratch_guards[scope]for d,scope in dimensions.items()if scope is not None}
    merged.final=[None]*merged.n_slots
    for d,s in merged.slots.items():merged.final[s]=d
    graph.scratch_statistics=dict(shared_slots=base,private_window=private_width,owner_slots=stats)
    return merged
