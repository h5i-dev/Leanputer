"""Exhaustive compiler partitioning of kernel INTERNAL control states.

Only task/mode/continuation/private-PC fields are partitioned. All16bit values
(including invalid ones) are covered by disjoint intervals. AST tags, names,
constructor shapes, counts and proof inputs are never specialization keys.
"""
from dataclasses import replace
from collections import Counter
from .control_ir import Bit


class PhasePartition:
    def __init__(self,compiler,max_states=50000,contract_only=False):
        self.compiler=compiler;self.g=compiler.g;self.nodes=self.g.nodes
        self.variables={i:n.data for i,n in enumerate(self.nodes)if n.op=='input'and(n.data in('mode','task','read/frame/task','read/frame/phase')or n.data.endswith('_pc'))}
        self.indices={i:j for j,i in enumerate(self.variables)}
        self.dep_cache={};self.test_cache={};self.cofactors={};self.memo={};self.leaves=[];self.dispatch=[];self.max_states=max_states;self.visited=0;self.region_aliases={}
        self.contract=compiler.preflight_active;self.contract_cache={}
        self.contract_domains={i:(0,(1<<self.nodes[i].width)-1)for i in self.variables}
        def require(index,truth):
            n=self.nodes[index]
            if n.op=='not':require(n.args[0],not truth)
            elif n.op=='all'and truth:
                for arg in n.args:require(arg,True)
            elif n.op=='any'and not truth:
                for arg in n.args:require(arg,False)
            elif n.op in('eq','ult'):
                a,b=n.args
                if a in self.variables and self.nodes[b].op=='const':
                    lo,hi=self.contract_domains[a];value=self.nodes[b].data
                    if n.op=='eq'and truth:lo=max(lo,value);hi=min(hi,value)
                    elif n.op=='ult':
                        if truth:hi=min(hi,value-1)
                        else:lo=max(lo,value)
                    self.contract_domains[a]=(lo,hi)
                elif b in self.variables and self.nodes[a].op=='const':
                    lo,hi=self.contract_domains[b];value=self.nodes[a].data
                    if n.op=='eq'and truth:lo=max(lo,value);hi=min(hi,value)
                    elif n.op=='ult':
                        if truth:lo=max(lo,value+1)
                        else:hi=min(hi,value)
                    self.contract_domains[b]=(lo,hi)
        require(self.contract,True)
        self.prefix=tuple((i,e)for i,e in enumerate(compiler.effects)if i<compiler.preflight_effect_count)
        required_cache={}
        def required(index):
            if index not in required_cache:
                n=self.nodes[index]
                if n.op=='all':result=set.union(set(),*(required(i)for i in n.args))
                elif n.op=='any':result=set.intersection(*(required(i)for i in n.args))if n.args else set()
                else:result=set()
                result.add(index);required_cache[index]=result
            return required_cache[index]
        dominated=[];fallback=[]
        for i,e in enumerate(compiler.effects):
            if i<compiler.preflight_effect_count:continue
            if self.contract not in required(e.guard):fallback.append((i,e));continue
            if e.kind=='merge_fields':values=tuple((n,self.under_contract(w))for n,w in e.values)
            else:values=tuple(self.under_contract(w)for w in e.values)
            dominated.append((i,replace(e,guard=self.under_contract(e.guard),values=values,address=self.under_contract(e.address)if e.address>=0 else-1)))
        self.fallback=tuple(fallback);self.body=tuple(dominated)
        self.root=None if contract_only else self.partition(self.body)

    def under_contract(self,index):
        if index==self.contract:return self.g.one.word
        if index not in self.contract_cache:
            n=self.nodes[index];args=tuple(self.under_contract(i)for i in n.args)
            if n.op=='all':result=self.g.AND(*(Bit(i,0)for i in args)).word
            elif n.op=='any':result=self.g.OR(*(Bit(i,0)for i in args)).word
            elif n.op=='not':result=self.g.NOT(Bit(args[0],0)).word
            elif n.op=='choose'and self.nodes[args[0]].op=='const':result=args[1]if self.nodes[args[0]].data else args[2]
            elif args==n.args:result=index
            else:result=self.g.node(n.op,n.width,args,n.data).node
            self.contract_cache[index]=result
        return self.contract_cache[index]

    def dependencies(self,index):
        if index not in self.dep_cache:
            n=self.nodes[index];mask=1<<self.indices[index]if index in self.indices else 0
            for arg in n.args:mask|=self.dependencies(arg)
            self.dep_cache[index]=mask
        return self.dep_cache[index]

    def tests(self,index,opaque=frozenset()):
        if index in opaque:return {}
        key=(index,opaque)
        if key in self.test_cache:return self.test_cache[key]
        n=self.nodes[index];result={}
        if n.op in('eq','ult'):
            for a,b in(n.args,n.args[::-1]):
                if a in self.variables and self.nodes[b].op=='const':result[a]={self.nodes[b].data}
        for arg in n.args:
            for variable,values in self.tests(arg,opaque).items():result.setdefault(variable,set()).update(values)
        self.test_cache[key]={k:frozenset(v)for k,v in result.items()};return self.test_cache[key]

    def cofactor(self,index,variable,low,high,opaque=frozenset()):
        if index in opaque:return index
        if not self.dependencies(index)&(1<<self.indices[variable]):return index
        key=index,variable,low,high,opaque
        if key in self.cofactors:return self.cofactors[key]
        n=self.nodes[index];args=tuple(self.cofactor(i,variable,low,high,opaque)for i in n.args)
        def bounds(i):
            child=self.nodes[i]
            if i==variable:return low,high
            if child.op=='const':return child.data,child.data
            return 0,(1<<child.width)-1
        out=None
        if n.op in('eq','ult'):
            alo,ahi=bounds(args[0]);blo,bhi=bounds(args[1])
            if n.op=='eq':
                if ahi<blo or bhi<alo:out=self.g.zero.word
                elif alo==ahi==blo==bhi:out=self.g.one.word
            else:
                if ahi<blo:out=self.g.one.word
                elif alo>=bhi:out=self.g.zero.word
        if out is None:
            if n.op=='all':out=self.g.AND(*(Bit(i,0)for i in args)).word
            elif n.op=='any':out=self.g.OR(*(Bit(i,0)for i in args)).word
            elif n.op=='not':out=self.g.NOT(Bit(args[0],0)).word
            elif n.op=='choose'and self.nodes[args[0]].op=='const':out=args[1]if self.nodes[args[0]].data else args[2]
            elif n.op=='choose'and args[1]==args[2]:out=args[1]
            elif args==n.args:out=index
            else:out=self.g.node(n.op,n.width,args,n.data).node
        self.cofactors[key]=out;return out

    def signature(self,effects):
        # Every effect reads the immutable old state and OR-merges its output.
        # Ordering is immaterial and exact duplicate effects are idempotent.
        return tuple(sorted(set((e.kind,e.guard,tuple(sorted(e.values))if e.kind=='merge_fields'else e.values,e.address)for i,e in effects)))

    def partition(self,effects):
        signature=self.signature(effects)
        if signature in self.memo:
            result=self.memo[signature]
            if result[0]=='leaf':self.leaves[result[1]]['aliases'].update(i for i,e in effects)
            self.region_aliases.setdefault(result,set()).update(i for i,e in effects)
            return result
        self.visited+=1
        if self.visited>self.max_states:raise ValueError('kernel control partition exceeds50000 compiler states')
        tests={}
        for i,e in effects:
            for variable,values in self.tests(e.guard).items():tests.setdefault(variable,set()).update(values)
        if not tests:
            result=('leaf',len(self.leaves));self.leaves.append(dict(effects=effects,aliases=set(i for i,e in effects)));self.memo[signature]=result;return result
        # RETURN dispatches on caller before current task; ordinary phases use
        # current task. Mode is always resolved first, then task/private PC.
        def priority(variable):
            name=self.variables[variable]
            if getattr(self,'control_order',None)=='task_first':
                return (0 if name=='task'else 1 if name=='mode'else 2 if name=='read/frame/task'else 3 if name=='read/frame/phase'else 4,-len(tests[variable]),name)
            if getattr(self,'control_order',None)=='caller_first':
                return (0 if name=='read/frame/task'else 1 if name=='read/frame/phase'else 2 if name=='task'else 3 if name=='mode'else 4,-len(tests[variable]),name)
            return (0 if name=='mode'else 1 if name=='read/frame/task'else 2 if name=='task'else 3 if name=='read/frame/phase'else 4,-len(tests[variable]),name)
        variable=min(tests,key=priority);minimum,limit=self.contract_domains[variable]
        breaks={minimum,limit+1}
        for value in tests[variable]:
            if minimum<=value<=limit:breaks.add(value);breaks.add(value+1)
        breaks=sorted(breaks);cases=[]
        for low,end in zip(breaks,breaks[1:]):
            high=end-1;specialized=[]
            for i,e in effects:
                guard=self.cofactor(e.guard,variable,low,high)
                if self.nodes[guard].op=='const'and not self.nodes[guard].data:continue
                if e.kind=='merge_fields':values=tuple((name,self.cofactor(word,variable,low,high))for name,word in e.values)
                else:values=tuple(self.cofactor(word,variable,low,high)for word in e.values)
                address=self.cofactor(e.address,variable,low,high)if e.address>=0 else-1
                specialized.append((i,replace(e,guard=guard,values=values,address=address)))
            child=self.partition(tuple(specialized))
            if cases and cases[-1][2]==child:cases[-1]=(cases[-1][0],high,child)
            else:cases.append((low,high,child))
        if len(cases)==1:result=cases[0][2]
        else:
            result=('switch',len(self.dispatch));self.dispatch.append(dict(variable=variable,name=self.variables[variable],cases=cases))
        self.memo[signature]=result;return result

    def report(self):
        covered=set().union(*(leaf['aliases']for leaf in self.leaves),*self.region_aliases.values())|{i for i,e in self.prefix+self.fallback}
        return dict(compiler_states=self.visited,distinct_handlers=len(self.leaves),dispatch_nodes=len(self.dispatch),source_effects_represented_in_control_regions=len(covered),source_effects_control_dead=sorted(set(range(len(self.compiler.effects)))-covered),control_variables=list(self.variables.values()),all_control_values_covered=True,entry_implied_domains={self.variables[i]:bounds for i,bounds in self.contract_domains.items()if bounds!=(0,(1<<self.nodes[i].width)-1)},invalid_control_path='Original preflight effects retained; dispatch only runs under its proven true predicate.',preflight_effects=len(self.prefix),non_dominated_fallback_effects=len(self.fallback),max_handler_effects=max(len(x['effects'])for x in self.leaves),max_handler_candidate_fields=max(len({name for i,e in x['effects']if e.kind=='merge_fields'for name,word in e.values})for x in self.leaves),cofactor_nodes=len(self.nodes),cofactor_cache=len(self.cofactors),provenance_scope='Exact duplicate semantic regions share code; source effects alias the shared region, not a claimed per-input executed leaf.')
