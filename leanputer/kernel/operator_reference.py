"""DEVELOPMENT ONLY source-operator correspondence; NEVER imported at inference.

Interpreting compiler IR here supplies no syntax packets, model state, cache,
control dispatch or answers to stock inference. It is an independent diagnostic
against the preserved complete word-backend reference after semantic steps.
"""
from copy import deepcopy
from collections import Counter
from .control_reference import evaluate


class OperatorReference:
    def __init__(self,program):
        self.program=program;self.metadata=[0]*program.compiler.cfg.stack
        self.stack_sites={site.effect:site.identity for site in program.continuations}
        self.steps=0;self.uninitialized_returns=0;self.multiple_stack_writers=0
        self.max_candidate_effects=0;self.max_active_groups=0
        self.selectors=None;self.selector_actions=Counter();self.selector_reload_steps=0

    def step(self,state):
        address_fields=set()
        class AddressInputs(dict):
            def __getitem__(self,name):address_fields.add(name);return super().__getitem__(name)
        p=self.program;cfg=p.compiler.cfg;inputs=AddressInputs(state['regs'])
        a1,word1=p.addresses[0];packed=evaluate(a1,[word1.node],inputs)[0];offset=0
        for bank,port,fields in(('heap','node',('tag','a','b','c')),('stack','frame',('phase','original','depth','task','first','second')),('constants','declaration',('kind','symbol','parameters','type','value','extra'))):
            width=getattr(cfg,bank).bit_length()-1;address=(packed>>offset)&((1<<width)-1);offset+=width
            inputs.update((f'read/{port}/{name}',int(value))for name,value in zip(fields,state[bank][address]))
        a2,word2=p.addresses[1];address=evaluate(a2,[word2.node],inputs)[0]
        inputs['read/operand/value']=int(state['context'][address][0])
        inputs=dict(inputs)
        get=evaluate(p.compiler.g,None,inputs);merged={};writes={};stack_writers=[]
        if inputs['mode']==p.control.return_mode and inputs['sp']:
            self.uninitialized_returns+=int(not self.metadata[(inputs['sp']-1)&(cfg.stack-1)])
        cache=[None]*len(p.control_nodes);cache[0]=False;cache[1]=True
        if p.aliases:
            expected=p.aliases.reference_values(inputs)
            if self.selectors is None:self.selectors=expected
            if expected!=self.selectors:raise AssertionError('incremental control-selector correspondence failed')
            aliases=self.selectors
        else:aliases={}
        def selected(index):
            if cache[index]is not None:return cache[index]
            value=p.control_nodes[index]
            if value[0]=='range':
                _,variable,low,high=value
                operand=aliases[variable]if variable<0 else int(inputs['sp']==0)if variable==p.control.stack_empty else inputs[p.control.variables[variable]]
                answer=low<=operand<=high
            elif value[0]=='and':answer=all(selected(v)for v in value[1])
            else:answer=any(selected(v)for v in value[1])
            cache[index]=answer;return answer
        effects=list(p.contract.prefix);active_groups=0
        operands=set(address_fields)
        if get(p.compiler.preflight_active):
            for control,group in p.groups:
                if selected(control):
                    effects.extend(group);active_groups+=1
                    for index,effect in group:operands.update(p.operand_fields[index])
        self.max_active_groups=max(self.max_active_groups,active_groups)
        self.max_candidate_effects=max(self.max_candidate_effects,len(effects))
        for index,effect in effects:
            if not get(effect.guard):continue
            if effect.kind=='merge_fields':
                for name,node in effect.values:merged[name]=merged.get(name,0)|get(node)
            else:
                bank=effect.kind.removeprefix('write_');address=get(effect.address)&(getattr(cfg,bank)-1)
                values=[get(node)for node in effect.values]
                if bank in writes:
                    old_address,old_values=writes[bank];address|=old_address
                    values=[a|b for a,b in zip(values,old_values)]
                writes[bank]=(address,values)
                if bank=='stack':stack_writers.append((address,self.stack_sites[index]))
        result=deepcopy(state);result['regs'].update(merged)
        for bank,(address,values)in writes.items():result[bank][address]=values
        if len(stack_writers)>1:self.multiple_stack_writers+=1
        for address,identity in stack_writers:self.metadata[address]=identity
        if p.aliases:
            self.selectors,actions=p.aliases.reference_update(inputs,merged,self.selectors,result['regs'].__getitem__)
            self.selector_actions.update(action for action,name in actions.values())
            self.selector_reload_steps+=int(any(action=='reload'for action,name in actions.values()))
            # Proven current-owner words use the shared selector operand.
            bit=1<<(inputs['task']-p.aliases.low)
            operands.difference_update(p.control.variables[v]for v,mask in p.aliases.owners.items()if mask&bit)
        self.last_access=dict(reads={name for name in operands if not name.startswith('read/')},
                              updates=set(merged),writes=set(writes))
        self.steps+=1
        return result
