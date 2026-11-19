"""Source-derived reuse of private checker control operands.

Owner sets come from guard sensitivity, not a hand-maintained task catalogue.
Logical private words keep their permanent storage. Physical selector operands
may share a slot only when their possible active task sets are disjoint.
Maintaining those selector slots in weights remains a separate compiler gate.
"""
from collections import defaultdict


class ControlAliases:
    def __init__(self,control,effects):
        self.control=control
        self.task=next(v for v,name in control.variables.items()if name=='task')
        self.low,self.high=control.domains[self.task];self.universe=(1<<(self.high-self.low+1))-1
        self.owners=defaultdict(int);self.mask_cache={}
        private={v for v,name in control.variables.items()if name.endswith('_pc')}
        def scan(value,context):
            if isinstance(value,int):return
            if value[0]=='range':
                if value[1]in private:self.owners[value[1]]|=context
            elif value[0]=='and':
                masks=[self.allowed_tasks(child)for child in value[1]]
                for index,child in enumerate(value[1]):
                    possible=context
                    for other,mask in enumerate(masks):
                        if other!=index:possible&=mask
                    if possible:scan(child,possible)
            else:
                for child in value[1]:scan(child,context)
        for index,effect in effects:scan(control.project(effect.guard),self.universe)
        vertices=sorted(self.owners)
        adjacent={v:{w for w in vertices if w!=v and self.owners[v]&self.owners[w]}for v in vertices}
        self.colors={}
        while len(self.colors)<len(vertices):
            pending=set(vertices)-self.colors.keys()
            v=min(pending,key=lambda v:(-len({self.colors[w]for w in adjacent[v]if w in self.colors}),-len(adjacent[v]),control.variables[v]))
            occupied={self.colors[w]for w in adjacent[v]if w in self.colors};color=0
            while color in occupied:color+=1
            self.colors[v]=color
        self.slots=max(self.colors.values(),default=-1)+1

    def allowed_tasks(self,value):
        if value not in self.mask_cache:
            if isinstance(value,int):result=self.universe if value else 0
            elif value[0]=='range':
                _,variable,low,high=value
                result=((1<<(high-low+1))-1)<<(low-self.low)if variable==self.task else self.universe
            else:
                result=self.universe if value[0]=='and'else 0
                for child in value[1]:
                    if value[0]=='and':result&=self.allowed_tasks(child)
                    else:result|=self.allowed_tasks(child)
            self.mask_cache[value]=result
        return self.mask_cache[value]

    def rewrite_atom(self,atom):
        if atom[0]=='range'and atom[1]in self.colors:
            return(atom[0],-1-self.colors[atom[1]],atom[2],atom[3])
        return atom

    def reference_values(self,inputs):
        """OFFLINE only; never supplies a model selector or inference input."""
        values={-1-slot:0 for slot in range(self.slots)};assigned=set()
        bit=1<<(inputs['task']-self.low)
        for variable,color in self.colors.items():
            if self.owners[variable]&bit:
                if color in assigned:raise AssertionError('control alias has overlapping owners')
                assigned.add(color);values[-1-color]=inputs[self.control.variables[variable]]
        return values

    def reference_update(self,inputs,merged,previous,read_logical_word):
        """OFFLINE model of explicit carry/update/reload actions.

        A reload reads permanent RF storage and costs a separate typed gather.
        This method is not imported or called by inference. Native lowering
        must implement these actions in weights before this gate is verified.
        """
        task=merged.get('task',inputs['task']);bit=1<<(task-self.low)
        values={-1-slot:0 for slot in range(self.slots)};actions={}
        for variable,color in self.colors.items():
            if not self.owners[variable]&bit:continue
            slot=-1-color;name=self.control.variables[variable]
            if name in merged:values[slot]=merged[name];actions[slot]=('update',name)
            elif task==inputs['task']:values[slot]=previous[slot];actions[slot]=('carry',name)
            else:values[slot]=read_logical_word(name);actions[slot]=('reload',name)
        for slot in values:
            if slot not in actions:actions[slot]=('zero',None)
        return values,actions

    def report(self):
        return dict(format='leanputer.private-control-aliases.v1',private_control_words=len(self.colors),
                    physical_selector_words=self.slots,selector_bits=16*self.slots,
                    logical_words_erased=0,owner_task_sets_derived_from_all_source_guards=True,
                    owners={self.control.variables[v]:[self.low+i for i in range(self.high-self.low+1)if mask>>i&1]for v,mask in self.owners.items()},
                    native_selector_maintenance_verified=False,joint_delivery_gate=False)
