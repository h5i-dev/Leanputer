"""DEVELOPMENT ONLY: typed-capture correspondence, never native inference.

The production compact backend must execute weights and stock cache. This
reference supplies no model state, dispatch, checker answer or normalization.
"""
from copy import deepcopy


def evaluate(builder,roots,inputs):
    cache={}
    def value(index):
        if index in cache:return cache[index]
        n=builder.nodes[index];a=n.args
        if n.op=='input':result=int(inputs[n.data])
        elif n.op=='const':result=n.data
        elif n.op=='all':result=int(all(value(i)for i in a))
        elif n.op=='any':result=int(any(value(i)for i in a))
        elif n.op=='not':result=1-value(a[0])
        elif n.op=='choose':result=value(a[1]if value(a[0])else a[2])
        elif n.op=='add':result=value(a[0])+value(a[1])
        elif n.op=='sub':result=value(a[0])-value(a[1])
        elif n.op=='eq':result=int(value(a[0])==value(a[1]))
        elif n.op=='ult':result=int(value(a[0])<value(a[1]))
        elif n.op=='slice':result=value(a[0])>>n.data
        elif n.op=='extend':result=value(a[0])
        elif n.op=='splice':result=sum(((value(i)>>bit)&1)<<j for j,(i,bit)in enumerate(zip(a,n.data)))
        else:raise ValueError('unmapped typed development operator '+n.op)
        result&=(1<<n.width)-1;cache[index]=result;return result
    return value if roots is None else [value(i)for i in roots]


class TypedReference:
    def __init__(self,compiler,addresses):
        self.compiler,self.addresses=compiler,addresses;self.config=compiler.cfg

    def step(self,state):
        cfg=self.config;inputs={n:int(v)for n,v in state['regs'].items()}
        a1,word1=self.addresses[0];packed=evaluate(a1,[word1.node],inputs)[0];offset=0
        for bank,port,fields in (('heap','node',('tag','a','b','c')),('stack','frame',('phase','original','depth','task','first','second')),('constants','declaration',('kind','symbol','parameters','type','value','extra'))):
            width=getattr(cfg,bank).bit_length()-1;address=(packed>>offset)&((1<<width)-1);offset+=width
            inputs.update((f'read/{port}/{name}',int(v))for name,v in zip(fields,state[bank][address]))
        a2,word2=self.addresses[1];address=evaluate(a2,[word2.node],inputs)[0]
        inputs['read/operand/value']=int(state['context'][address][0])
        get=evaluate(self.compiler.g,None,inputs);merged={};writes={}
        for effect in self.compiler.effects:
            if not get(effect.guard):continue
            if effect.kind=='merge_fields':
                for name,word in effect.values:merged[name]=merged.get(name,0)|get(word)
            else:
                bank=effect.kind.removeprefix('write_');address=get(effect.address)&(getattr(cfg,bank)-1)
                values=[get(word)for word in effect.values]
                if bank in writes:
                    old_address,old_row=writes[bank];address|=old_address;values=[a|b for a,b in zip(values,old_row)]
                writes[bank]=(address,values)
        result=deepcopy(state);result['regs'].update(merged)
        for bank,(address,row)in writes.items():result[bank][address]=row
        return result
