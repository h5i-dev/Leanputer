"""Lossless two-bit residual packing; inference unpacking is emitted stock FFNs.

Host encode/decode methods are serialization only. Model feedback stays an
identity wire. No checker result, normalization or semantic state update occurs
in these methods.
"""
from dataclasses import dataclass
import torch


@dataclass(frozen=True)
class PackedBit:
    feature: object
    high: bool

    def realize(self,builder,memo):
        dimension=next(iter(self.feature.terms))
        if dimension not in memo:
            g=builder.graph;one=g.one
            memo[dimension]=g.ffn([(1,one,self.feature-one),(-1,one,self.feature-2*one)],
                name='unpack/'+str(dimension),min_level=builder.barrier)
        bit=memo[dimension]
        return bit if self.high else self.feature-2*bit


class ControlPacking:
    def __init__(self,registers):
        self.logical_width=registers.width;self.pairs=[];self.slices={};offset=0
        for name,width in registers.fields:
            start=len(self.pairs)
            self.pairs.extend((offset+i,offset+i+1 if i+1<width else None)for i in range(0,width,2))
            self.slices[name]=slice(start,len(self.pairs));offset+=width
        self.width=len(self.pairs)
        self.low=torch.tensor([a for a,b in self.pairs],dtype=torch.long)
        self.high=torch.tensor([b if b is not None else a for a,b in self.pairs],dtype=torch.long)
        self.high_mask=torch.tensor([b is not None for a,b in self.pairs])

    def encode(self,bits):
        return bits.index_select(-1,self.low.to(bits.device))+2*bits.index_select(-1,self.high.to(bits.device))*self.high_mask.to(bits.device)

    def decode(self,digits):
        if not torch.all((digits>=0)&(digits<=3)&(digits==digits.floor())):raise ValueError('native packed control left exact digit domain')
        bits=digits.new_zeros((*digits.shape[:-1],self.logical_width))
        for i,(a,b)in enumerate(self.pairs):
            bits[...,a]=digits[...,i]%2
            if b is not None:bits[...,b]=torch.floor_divide(digits[...,i],2)
        return bits

    def features(self,builder):
        physical=[builder.feature('packed-control/'+str(i))for i in range(self.width)]
        logical=[None]*self.logical_width
        for feature,(a,b)in zip(physical,self.pairs):
            logical[a]=PackedBit(feature,False)
            if b is not None:logical[b]=PackedBit(feature,True)
        return physical,logical


def packed_update_outputs(builder,plan,inputs,physical_features,logical_width):
    """Compile keep*old_digit + updated_bits, preserving overlapping updates."""
    from .native_vendor.qwenputer.expr import Expr
    circuit,logical_outputs=plan;graph=builder.graph
    if not hasattr(circuit,'native_packed_fields'):raise ValueError('program does not expose packed update metadata')
    roots=[]
    for name,keep,updated in circuit.native_packed_fields:roots.append(keep);roots.extend(updated)
    roots.extend(logical_outputs[logical_width:])
    values=builder.circuit((circuit,roots),inputs,'transition');cursor=0;outputs=[];physical=0
    for name,keep,updated in circuit.native_packed_fields:
        condition=values[cursor];cursor+=1;bits=values[cursor:cursor+len(updated)];cursor+=len(updated)
        for i in range(0,len(bits),2):
            old=physical_features[physical];physical+=1
            if condition.terms==graph.one.terms:retained=old
            elif not condition.terms:retained=Expr()
            else:retained=graph.ffn([(1,old,condition)],name='packed-keep/'+str(physical),min_level=builder.barrier)
            outputs.append(retained+bits[i]+(2*bits[i+1]if i+1<len(bits)else Expr()))
    outputs.extend(values[cursor:]);return coalesce_packed_outputs(graph,outputs,physical)


def coalesce_packed_outputs(graph,outputs,packed_count):
    """Accumulate private final components into one residual slot per digit."""
    from .native_vendor.qwenputer.ir import FFN
    from .native_vendor.qwenputer.emit import reads
    from .native_vendor.qwenputer.expr import Expr
    consumers={};writers={};output_uses={}
    for index,node in enumerate(graph.nodes):
        for d in reads(node):consumers[d]=consumers.get(d,0)+1
        if isinstance(node,FFN):writers.setdefault(node.out,[]).append((index,node))
    for value in outputs:
        for d in value.terms:output_uses[d]=output_uses.get(d,0)+1
    result=list(outputs)
    for i,value in enumerate(outputs[:packed_count]):
        eligible=[d for d in value.terms if d in writers and len(writers[d])==1 and not consumers.get(d,0)and output_uses[d]==1]
        if len(eligible)<2:continue
        eligible.sort(key=lambda d:(writers[d][0][1].level,writers[d][0][0]));target=eligible[0];last_level=0
        for d in eligible:
            _,node=writers[d][0];coefficient=value.terms[d]
            node.terms=[(coefficient*c,a,b)for c,a,b in node.terms]
            node.out=target;node.into=d!=target;last_level=max(last_level,node.level)
        graph.dims[target].level=last_level
        result[i]=Expr({d:c for d,c in value.terms.items()if d not in eligible})+Expr({target:1})
    return result
