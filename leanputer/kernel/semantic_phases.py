"""Input-independent whole-transition control partition without scalar code.

Data predicates stay in the original kernel operators. Their existential
projection here is conservative: no declaration name, tag, shape or count
becomes a specialization key. Regions hold simultaneous SOURCE effects, not
word instructions. This compiler IR is never executed by the inference host.
"""
from collections import Counter


class SemanticPhases:
    def __init__(self,compiler,contract,max_regions=4096,max_states=50000,build=True):
        self.compiler=compiler;self.contract=contract;self.nodes=compiler.g.nodes
        self.variables=dict(contract.variables);self.domains=dict(contract.contract_domains)
        self.projected={};self.pure_cache={};self.dependencies_cache={};self.cofactors={}
        self.memo={};self.regions=[];self.switches=[];self.visited=0
        self.max_regions=max_regions;self.max_states=max_states
        from .traversal_machine import Mode
        self.return_mode=int(Mode.RETURN)
        self.mode_variable=next(v for v,name in self.variables.items()if name=='mode')
        # Source rules distinguish root returns from caller returns with this
        # exact predicate (traversal_transition.py:owned_return/top_return).
        # It is a single model-computed bit, not a table of stack depths.
        self.stack_empty=next(i for i,n in enumerate(self.nodes)if n.op=='eq'and any(
            self.nodes[a].op=='input'and self.nodes[a].data=='sp'and self.nodes[b].op=='const'and self.nodes[b].data==0
            for a,b in(n.args,n.args[::-1])))
        self.variables[self.stack_empty]='$stack_empty';self.domains[self.stack_empty]=(0,1)
        self.return_data=frozenset(v for v,name in self.variables.items()if name=='task'or name.endswith('_pc'))
        self.ordinary_data=frozenset(v for v,name in self.variables.items()if name.startswith('read/frame/')or name=='$stack_empty')
        self.erase_cache={}
        self.path=[]
        self.root=self.partition(tuple((index,self.project(effect.guard))for index,effect in contract.body))if build else None

    @staticmethod
    def combine(op,values):
        operands=[]
        for value in values:
            if value==(0 if op=='and'else 1):return value
            if value==(1 if op=='and'else 0):continue
            if isinstance(value,tuple)and value[0]==op:operands.extend(value[1])
            else:operands.append(value)
        operands=tuple(sorted(set(operands),key=repr))
        return operands[0]if len(operands)==1 else(op,operands)if operands else(1 if op=='and'else 0)

    def pure(self,index):
        if index not in self.pure_cache:
            node=self.nodes[index]
            self.pure_cache[index]=node.op=='const'or index in self.variables or(bool(node.args)and all(self.pure(a)for a in node.args))
        return self.pure_cache[index]

    def project(self,index,truth=True):
        key=index,truth
        if key in self.projected:return self.projected[key]
        node=self.nodes[index]
        if node.op=='const':result=int(bool(node.data)==truth)
        elif index==self.stack_empty:result=self.interval(index,int(truth),int(truth))
        elif node.op in('all','any'):
            conjunction=(node.op=='all')==truth
            result=self.combine('and'if conjunction else'or',(self.project(a,truth)for a in node.args))
        elif node.op=='not':result=self.project(node.args[0],not truth)
        elif node.op in('eq','ult'):
            result=1
            for a,b in(node.args,node.args[::-1]):
                if a not in self.variables or self.nodes[b].op!='const':continue
                value=self.nodes[b].data;maximum=(1<<self.nodes[a].width)-1
                if node.op=='eq':low,high=value,value
                elif a==node.args[0]:low,high=0,value-1
                else:low,high=value+1,maximum
                result=self.interval(a,low,high)
                if not truth:result=self.negate(result)
                break
        else:result=1
        # Unknown/data predicates project to TRUE. Their exact original guard
        # remains attached to each source effect and must still be checked.
        self.projected[key]=result;return result

    def interval(self,variable,low,high):
        minimum,maximum=self.domains[variable];low=max(low,minimum);high=min(high,maximum)
        return 0 if low>high else 1 if(low,high)==(minimum,maximum)else('range',variable,low,high)

    def negate(self,value):
        if isinstance(value,int):return 1-value
        if value[0]=='range':
            _,v,low,high=value;minimum,maximum=self.domains[v]
            return self.combine('or',(self.interval(v,minimum,low-1),self.interval(v,high+1,maximum)))
        return self.combine('or'if value[0]=='and'else'and',(self.negate(v)for v in value[1]))

    def dependencies(self,value):
        if value not in self.dependencies_cache:
            if isinstance(value,int):result=frozenset()
            elif value[0]=='range':result=frozenset((value[1],))
            else:result=frozenset().union(*(self.dependencies(v)for v in value[1]))
            self.dependencies_cache[value]=result
        return self.dependencies_cache[value]

    def bounds(self,value,variable):
        if isinstance(value,int):return set()
        if value[0]=='range':return {value[2],value[3]+1}if value[1]==variable else set()
        return set().union(*(self.bounds(v,variable)for v in value[1]))

    def cofactor(self,value,variable,low,high):
        if variable not in self.dependencies(value):return value
        key=value,variable,low,high
        if key not in self.cofactors:
            if value[0]=='range':
                _,v,a,b=value
                if low>=a and high<=b:result=1
                elif high<a or low>b:result=0
                else:raise AssertionError('control partition crosses an interval boundary')
            else:result=self.combine(value[0],(self.cofactor(v,variable,low,high)for v in value[1]))
            self.cofactors[key]=result
        return self.cofactors[key]

    def as_operands(self,value,variables):
        """Move selectors into exact operator guards, without deleting effects.

        A return's callee task/private PCs are DATA operands of the caller's
        continuation. Ordinary steps treat caller-frame fields as operands.
        The original typed guard remains unchanged for native lowering.
        """
        key=value,variables
        if key not in self.erase_cache:
            if isinstance(value,int):result=value
            elif value[0]=='range':result=1 if value[1]in variables else value
            else:result=self.combine(value[0],(self.as_operands(v,variables)for v in value[1]))
            self.erase_cache[key]=result
        return self.erase_cache[key]

    def partition(self,effects):
        effects=tuple((i,v)for i,v in effects if v!=0)
        if effects in self.memo:return self.memo[effects]
        self.visited+=1
        if self.visited>self.max_states:raise ValueError('RESOURCE: whole-transition compiler state cap')
        variables=frozenset().union(*(self.dependencies(v)for i,v in effects))
        if not variables:
            if len(self.regions)>=self.max_regions:
                state=', '.join(f'{self.variables[v]}={low}..{high}'for v,low,high in self.path)
                raise ValueError(f'RESOURCE: whole-transition region cap {self.max_regions}; control path {state}')
            result=('region',len(self.regions));self.regions.append(tuple(i for i,v in effects))
        else:
            priority={'mode':0,'$stack_empty':1,'task':2,'read/frame/task':3,'read/frame/phase':4}
            variable=min(variables,key=lambda v:(priority.get(self.variables[v],4),self.variables[v]))
            minimum,maximum=self.domains[variable];breaks={minimum,maximum+1}
            for i,value in effects:breaks.update(self.bounds(value,variable))
            breaks=sorted(v for v in breaks if minimum<=v<=maximum+1);cases=[]
            for low,end in zip(breaks,breaks[1:]):
                specialized=tuple((i,self.cofactor(v,variable,low,end-1))for i,v in effects)
                if variable==self.mode_variable:
                    # Mode intervals are split at every source test. RETURN
                    # has an explicit source-defined equality and is singleton.
                    operands=self.return_data if low==end-1==self.return_mode else self.ordinary_data
                    specialized=tuple((i,self.as_operands(v,operands))for i,v in specialized)
                self.path.append((variable,low,end-1))
                child=self.partition(specialized)
                self.path.pop()
                if cases and cases[-1][2]==child:cases[-1]=(cases[-1][0],end-1,child)
                else:cases.append((low,end-1,child))
            if len(cases)==1:result=cases[0][2]
            else:result=('switch',len(self.switches));self.switches.append((variable,tuple(cases)))
        self.memo[effects]=result;return result

    def report(self):
        covered=set().union(*(set(r)for r in self.regions),{i for i,e in self.contract.prefix+self.contract.fallback})
        dead=set(range(len(self.compiler.effects)))-covered
        families=Counter()
        for region in self.regions:
            families[len({self.compiler.effects[i].family for i in region})]+=1
        return dict(format='leanputer.whole-transition-control-regions.v1',source_effects=len(self.compiler.effects),
                    source_effects_represented=len(covered),control_dead_effects=sorted(dead),
                    whole_control_regions=len(self.regions),switch_nodes=len(self.switches),compiler_states=self.visited,
                    possible_family_count_histogram=dict(sorted(families.items())),
                    max_candidate_effects=max(map(len,self.regions)),data_predicates_preserved=True,
                    declaration_data_partitioned=False,region_cap=self.max_regions,
                    return_callee_controls_are_operands=True,ordinary_caller_controls_are_operands=True,
                    stack_empty_predicate='Exact source sp==0; one runtime bit; all depths retained',
                    native_phase_successors_verified=False,operator_schedule_verified=False,
                    stock_emitted=False,joint_delivery_gate=False)

    def family_support(self):
        """Conservative simultaneous-family bound, no Cartesian region build.

        A bitset exhausts all valid internal task/mode pairs. Other controls and
        data predicates are existential operands; the resulting family count
        is an upper bound, never a proof that the families actually coincide.
        """
        task=next(v for v,name in self.variables.items()if name=='task')
        mode=self.mode_variable;tlo,thi=self.domains[task];mlo,mhi=self.domains[mode]
        width=mhi-mlo+1;size=(thi-tlo+1)*width;universe=(1<<size)-1;cache={}
        def mask(value):
            if value in cache:return cache[value]
            if isinstance(value,int):result=universe if value else 0
            elif value[0]=='range':
                _,v,low,high=value
                if v==task:
                    result=((1<<((high-low+1)*width))-1)<<((low-tlo)*width)
                elif v==mode:
                    row=((1<<(high-low+1))-1)<<(low-mlo)
                    result=sum(row<<(i*width)for i in range(thi-tlo+1))
                else:result=universe
            else:
                result=universe if value[0]=='and'else 0
                for item in value[1]:
                    if value[0]=='and':result&=mask(item)
                    else:result|=mask(item)
            cache[value]=result;return result
        families={}
        for index,effect in self.contract.body:
            families[effect.family]=families.get(effect.family,0)|mask(self.project(effect.guard))
        histogram=Counter();maximum=0;examples=[]
        for index in range(size):
            active=tuple(name for name,value in families.items()if value>>index&1)
            histogram[len(active)]+=1
            if len(active)>maximum:maximum=len(active);examples=[]
            if len(active)==maximum and len(examples)<4:
                examples.append(dict(task=tlo+index//width,mode=mlo+index%width,families=active))
        return dict(format='leanputer.checker-family-composition-bound.v1',
                    task_mode_pairs=size,effect_family_names=len(families),
                    possible_family_count_histogram=dict(sorted(histogram.items())),
                    upper_bound_simultaneous_families=maximum,widest_examples=examples,
                    private_controls_and_data_existential=True,native_composition_verified=False,
                    joint_delivery_gate=False)
