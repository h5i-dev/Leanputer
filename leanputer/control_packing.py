"""Lossless bounded-digit packing; inference unpacking is emitted stock FFNs.

Host encode/decode methods are serialization only. Model feedback stays an
identity wire. No checker result, normalization or semantic state update occurs
in these methods.
"""
from dataclasses import dataclass
import torch


@dataclass(frozen=True)
class PackedBit:
    feature: object
    bit: int
    digit_bits: int = 2

    def realize(self,builder,memo):
        dimension=tuple(sorted(self.feature.terms.items()))
        if not self.feature.terms:return builder.graph.one*0
        if set(self.feature.terms)=={0}:
            return builder.graph.one*((int(self.feature.terms[0])>>self.bit)&1)
        g=builder.graph;one=g.one;remainder=self.feature
        for bit in range(self.digit_bits-1,0,-1):
            key=(dimension,bit)
            if key not in memo:
                threshold=1<<bit
                memo[key]=g.ffn([(1,one,remainder-(threshold-1)*one),(-1,one,remainder-threshold*one)],
                    name=f'unpack/{dimension}/{bit}',min_level=builder.barrier)
            if bit==self.bit:return memo[key]
            remainder=remainder-(1<<bit)*memo[key]
        return remainder


class ControlPacking:
    def __init__(self,registers,digit_bits=2):
        if digit_bits not in (2,4,8):raise ValueError('native control digits must contain 2, 4 or 8 bits')
        self.digit_bits=digit_bits;self.logical_width=registers.width;self.chunks=[];self.slices={};offset=0
        for name,width in registers.fields:
            start=len(self.chunks)
            self.chunks.extend(tuple(range(offset+i,offset+min(i+digit_bits,width)))for i in range(0,width,digit_bits))
            self.slices[name]=slice(start,len(self.chunks));offset+=width
        self.width=len(self.chunks)
        self.indices=torch.tensor([list(chunk)+[0]*(digit_bits-len(chunk))for chunk in self.chunks],dtype=torch.long)
        self.weights=torch.tensor([[1<<i if i<len(chunk)else 0 for i in range(digit_bits)]for chunk in self.chunks])
        self.bit_features=torch.tensor([i for i,chunk in enumerate(self.chunks)for _ in chunk],dtype=torch.long)
        self.bit_powers=torch.tensor([1<<bit for chunk in self.chunks for bit in range(len(chunk))])
        self.maxima=torch.tensor([(1<<len(chunk))-1 for chunk in self.chunks])

    def encode(self,bits):
        selected=bits.index_select(-1,self.indices.flatten().to(bits.device)).reshape(*bits.shape[:-1],self.width,self.digit_bits)
        return (selected*self.weights.to(bits.device)).sum(dim=-1)

    def decode(self,digits):
        if not torch.all((digits>=0)&(digits<=self.maxima.to(digits.device))&(digits==digits.floor())):raise ValueError('native packed control left exact digit domain')
        return torch.floor_divide(digits.index_select(-1,self.bit_features.to(digits.device)),self.bit_powers.to(digits.device))%2

    def features(self,builder):
        physical=[builder.feature('packed-control/'+str(i))for i in range(self.width)]
        logical=[None]*self.logical_width
        for feature,chunk in zip(physical,self.chunks):
            for bit,index in enumerate(chunk):logical[index]=PackedBit(feature,bit,len(chunk))
        return physical,logical


def packed_update_outputs(builder,plan,inputs,physical_features,logical_width,digit_bits=2):
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
        for i in range(0,len(bits),digit_bits):
            old=physical_features[physical];physical+=1
            if condition.terms==graph.one.terms:retained=old
            elif not condition.terms:retained=Expr()
            else:retained=graph.ffn([(1,old,condition)],name='packed-keep/'+str(physical),min_level=builder.barrier)
            outputs.append(retained+sum(((1<<j)*value for j,value in enumerate(bits[i:i+digit_bits])),Expr()))
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
