"""Typed checker control store, generated independently of input declarations.

Guards become short-circuit branches over WORD comparisons. There is no
Boolean-gate opcode, RV ISA, proof-supplied instruction tape or host dispatch.
This is the compiler representation; stock emission coverage is separate.
"""
from dataclasses import dataclass,asdict
from collections import Counter,defaultdict
import hashlib
import json


@dataclass(frozen=True)
class Operand:
    space: str
    index: int = 0
    width: int = 16
    source_width: int = 0


@dataclass
class Record:
    op: str
    dest: object = None
    a: object = None
    b: object = None
    immediate: int = 0
    yes: object = None
    no: object = None
    width: int = 16
    forwards: int = 1
    effects: tuple = ()
    items: tuple = ()
    callee: object = None
    region: str = 'body'
    cases: tuple = ()


class Block:
    def __init__(self,label,region='body'):self.label=label;self.records=[];self.region=region
    def emit(self,op,**kwargs):
        row=Record(op,region=self.region,**kwargs);self.records.append(row);return row


class WordCode:
    def __init__(self,store,block,memo=None,start=None):
        self.store,self.block=store,block;self.memo=dict(memo or {});self.next_temp=store.temporary_base if start is None else start

    def temp(self,width):
        out=Operand('temporary',self.next_temp,width);self.next_temp+=(width+15)//16
        self.store.peak_temporaries=max(self.store.peak_temporaries,self.next_temp)
        return out

    def get(self,index):
        if index in self.memo:return self.memo[index]
        s=self.store;n=s.nodes[index];op=n.op
        if index in s.frozen:out=s.frozen[index]
        elif op=='input':out=s.inputs[n.data]
        elif op=='const':out=Operand('literal',n.data,n.width)
        elif op=='extend':
            base=self.get(n.args[0]);out=Operand(base.space,base.index,n.width,base.source_width or base.width)
        elif op in('eq','ult','not','all','any'):
            out=self.temp(1);yes,no,join=s.block(),s.block(),s.block()
            entry=s.condition(index,yes.label,no.label,self.memo,self.next_temp)
            self.block.emit('JUMP',yes=entry)
            yes.emit('MOVE_WORD',dest=out,a=Operand('literal',1,1),yes=join.label,width=1)
            no.emit('MOVE_WORD',dest=out,a=Operand('literal',0,1),yes=join.label,width=1)
            self.block=join
        elif op=='choose':
            # A chain testing one word against constants is one dispatch, not
            # eager computation of every alternative at every use.
            def finite_test(index):
                test=s.nodes[index]
                if test.op=='eq':
                    for a,b in(test.args,test.args[::-1]):
                        if s.nodes[b].op=='const':return a,(s.nodes[b].data,)
                if test.op=='any':
                    pieces=[finite_test(i)for i in test.args]
                    if pieces and all(p and p[0]==pieces[0][0]for p in pieces):return pieces[0][0],tuple(sorted({v for p in pieces for v in p[1]}))
                return None
            chain=[];cursor=index;variable=None
            while self.store.nodes[cursor].op=='choose':
                selected=self.store.nodes[cursor];pair=finite_test(selected.args[0])
                if pair is None or(variable is not None and variable!=pair[0]):break
                variable=pair[0];chain.extend((v,selected.args[1])for v in pair[1]);cursor=selected.args[2]
            if len(chain)>=3 and self.store.nodes[variable].op=='input':
                out=self.temp(n.width);join=s.block();cases={};alternatives={}
                for value,alternative in chain+[(None,cursor)]:
                    if value in cases:continue
                    if alternative not in alternatives:
                        block=s.block();branch=WordCode(s,block,self.memo,self.next_temp);operand=branch.get(alternative)
                        branch.block.emit('MOVE_WORD',dest=out,a=operand,yes=join.label,width=n.width,forwards=(n.width+15)//16)
                        alternatives[alternative]=block.label
                    cases[value]=alternatives[alternative]
                self.block.emit('JUMP',yes=s.switch(variable,sorted((v,target)for v,target in cases.items()if v is not None),cases[None]))
                self.block=join;self.memo[index]=out;return out
            if getattr(s,'lazy_choices',False):
                out=self.temp(n.width);yes,no,join=s.block(),s.block(),s.block()
                entry=s.condition(n.args[0],yes.label,no.label,self.memo,self.next_temp)
                self.block.emit('JUMP',yes=entry)
                for block,alternative in zip((yes,no),n.args[1:]):
                    branch=WordCode(s,block,self.memo,self.next_temp);operand=branch.get(alternative)
                    branch.block.emit('MOVE_WORD',dest=out,a=operand,yes=join.label,width=n.width,forwards=(n.width+15)//16)
                self.block=join;self.memo[index]=out;return out
            # Pure word operands dominate the branch. Computing their common
            # DAG once avoids exponentially duplicating nested decimal/select
            # expressions into both control continuations.
            alternatives=[self.get(i)for i in n.args[1:]]
            out=self.temp(n.width);yes,no,join=s.block(),s.block(),s.block()
            entry=s.condition(n.args[0],yes.label,no.label,self.memo,self.next_temp)
            self.block.emit('JUMP',yes=entry)
            for block,value in zip((yes,no),alternatives):
                block.emit('MOVE_WORD',dest=out,a=value,yes=join.label,width=n.width,forwards=(n.width+15)//16)
            self.block=join
        elif op in('add','sub'):
            a,b=(self.get(i)for i in n.args);out=self.temp(n.width)
            self.block.emit('WORD_'+op.upper(),dest=out,a=a,b=b,width=n.width,forwards=(n.width+15)//16)
        elif op=='slice':
            a=self.get(n.args[0])
            if n.data==0:out=Operand(a.space,a.index,n.width)
            else:
                out=self.temp(n.width);self.block.emit('EXTRACT_WORD',dest=out,a=a,immediate=n.data,width=n.width,forwards=1+n.data)
        elif op=='splice':
            out=self.temp(n.width);self.block.emit('MOVE_WORD',dest=out,a=Operand('literal',0,n.width),width=n.width)
            cursor=0
            while cursor<n.width:
                source,low=n.args[cursor],n.data[cursor];end=cursor+1
                while end<n.width and n.args[end]==source and n.data[end]==low+end-cursor:end+=1
                a=self.get(source)
                # Bitfield movement is a bounded WORD operation. It expands
                # through the shared one-bit shifter, not Boolean instructions.
                descriptor=low|((end-cursor)<<5)|(cursor<<10)
                self.block.emit('MERGE_WORD_SLICE',dest=out,a=a,b=out,immediate=descriptor,width=n.width,forwards=2+low+cursor)
                cursor=end
        else:raise ValueError('unmapped typed word operator '+op)
        self.memo[index]=out;return out


class ControlStore:
    def __init__(self,compiler,phase_dispatch=False,contract_dispatch=False,family_dispatch=False,role_dispatch=False,mode_dispatch=False,indexed_phases=False,incremental_bounds=False,fast_default_dispatch=False,continuation_dispatch=False,dispatch_table_budget=None,direct_preflight=False):
        role_dispatch=role_dispatch or mode_dispatch
        family_dispatch=family_dispatch or role_dispatch
        self.mode_dispatch=mode_dispatch
        self.direct_preflight=direct_preflight
        if direct_preflight and not(incremental_bounds and role_dispatch):raise ValueError('direct source preflight requires checked role dispatch and invalid latch')
        self.indexed_phases=indexed_phases
        self.incremental_bounds=incremental_bounds
        self.fast_default_dispatch=fast_default_dispatch
        self.continuation_dispatch=continuation_dispatch
        limits=dispatch_table_budget.values()if isinstance(dispatch_table_budget,dict)else([dispatch_table_budget]if dispatch_table_budget is not None else[])
        if any(value<0 for value in limits):raise ValueError('negative dispatch table budget')
        self.dispatch_table_budget=dispatch_table_budget;self.dispatch_entries_allocated=0;self.dispatch_entries_by_region=Counter()
        self.role_dispatch=role_dispatch
        self.capture_statistics=compiler.g.statistics()
        self.phase_plan=None;self.contract_plan=None;self.control_priority=contract_dispatch;self.family_dispatch=family_dispatch
        if phase_dispatch or contract_dispatch or family_dispatch:
            from .control_phases import PhasePartition
            plan=PhasePartition(compiler,contract_only=contract_dispatch or family_dispatch,implied_contract=direct_preflight)
            if contract_dispatch or family_dispatch:self.contract_plan=plan
            else:self.phase_plan=plan
        self.compiler=compiler;self.nodes=compiler.g.nodes;self.blocks=[];self.peak_temporaries=17
        uses=Counter(i for n in self.nodes for i in n.args)
        chosen=sorted(set(i for i in compiler.active_nodes if i<=compiler.preflight_active))if phase_dispatch or contract_dispatch or family_dispatch else sorted(sorted((i for i,n in enumerate(self.nodes)if n.op in('all','any','not')and uses[i]>=4),key=lambda i:-uses[i])[:32])
        if contract_dispatch:
            # Cache shared residual source guards too. The checked contract is
            # removed only from the body, so its large ownership/continuation
            # predicates otherwise get recomputed at hundreds of guard sites.
            reachable=set();body_uses=Counter()
            def visit(i):
                if i in reachable:return
                reachable.add(i)
                for child in self.nodes[i].args:body_uses[child]+=1;visit(child)
            for _,effect in self.contract_plan.body:
                body_uses[effect.guard]+=1;visit(effect.guard)
                for value in effect.values:visit(value[1]if effect.kind=='merge_fields'else value)
                if effect.address>=0:visit(effect.address)
            extra=sorted((i for i in reachable if i not in chosen and self.nodes[i].op in('all','any','not')and body_uses[i]>=4),key=lambda i:(-body_uses[i],i))[:32-len(chosen)]
            chosen=sorted(chosen+extra)
        if direct_preflight:chosen=[]
        self.frozen={i:Operand('temporary',17+j,1)for j,i in enumerate(chosen)}
        # The source's validity chain is A' = A AND NOT bad. Once A' is
        # cached, its rejection A AND bad is exactly A AND NOT A'. Reusing
        # that result avoids evaluating the whole node/tag policy twice.
        self.rejected_guards={}
        from .control_ir import Bit
        for index in self.frozen:
            n=self.nodes[index]
            if n.op!='all':continue
            for arg in n.args:
                child=self.nodes[arg]
                if child.op!='not':continue
                base=[Bit(i,0)for i in n.args if i!=arg]
                rejected=compiler.g.AND(*base,Bit(child.args[0],0)).word
                replacement=compiler.g.AND(*base,compiler.g.NOT(Bit(index,0))).word
                self.rejected_guards[rejected]=replacement
        self.temporary_base=17+len(chosen)
        self.condition_entries={}
        self.preflight_entries={}
        self.action_entries={};self.source_action_regions={};self.phase_entries={};self.effect_lookup={}
        self.inputs={name:Operand('current',i,width)for i,(name,width)in enumerate(compiler.layout.fields)}
        port=0
        for name,index in compiler.g.input_words.items():
            if name.startswith('read/'):
                self.inputs[name]=Operand('temporary',port,self.nodes[index].width);port+=1
        if port!=17:raise ValueError('kernel read-port word ABI')
        self.covered=set();self.constant_dead=set()
        self.terminal=self.block();self.terminal.emit('COMMIT_STEP')
        self.handler_return=self.block();self.handler_return.emit('RETURN_HANDLER')
        if self.contract_plan:
            if family_dispatch:
                # Independent source modules merge into the same shadow state.
                # Factor their control separately instead of taking the
                # Cartesian product of unrelated private continuation states.
                if role_dispatch:
                    from .traversal_machine import Mode
                    mode=next(i for i,name in self.contract_plan.variables.items()if name=='mode')
                    minimum,maximum=self.contract_plan.contract_domains[mode];parts=[]
                    intervals=[(minimum,int(Mode.RETURN)-1),(int(Mode.RETURN),int(Mode.RETURN)),(int(Mode.RETURN)+1,maximum)]
                    if mode_dispatch:
                        # One global partition of INTERNAL mode, before owner
                        # and family handlers. Every guard interval is retained;
                        # declarations/proof inputs are not partition keys.
                        values=set()
                        for _,effect in self.contract_plan.body:values.update(self.contract_plan.tests(effect.guard).get(mode,()))
                        breaks={minimum,maximum+1,int(Mode.RETURN),int(Mode.RETURN)+1}
                        for value in values:
                            if minimum<=value<=maximum:breaks.update((value,value+1))
                        breaks=sorted(breaks);intervals=[(a,b-1)for a,b in zip(breaks,breaks[1:])]
                    for low,high in intervals:
                        order,owner=('caller_first','read/frame/task')if low==high==int(Mode.RETURN)else('task_first','task')
                        if low>high:continue
                        self.contract_plan.control_order=order
                        effects=self.specialized_effects(self.contract_plan.body,mode,low,high)
                        variable=next(i for i,name in self.contract_plan.variables.items()if name==owner)
                        if continuation_dispatch and low==high==int(Mode.RETURN):
                            phase=next(i for i,name in self.contract_plan.variables.items()if name=='read/frame/phase')
                            target=self.route_effects(effects,phase,self.terminal.label,lambda group,tail:self.route_effects(group,variable,tail))
                        else:target=self.route_effects(effects,variable,self.terminal.label)
                        if mode_dispatch and parts and parts[-1][2]==target:parts[-1]=(parts[-1][0],high,target)
                        else:parts.append((low,high,target))
                    body=self.control_cases(mode,parts)
                else:body=self.family_effects(self.contract_plan.body,self.terminal.label)
                for region,aliases in self.contract_plan.region_aliases.items():
                    if any(node==region for node,following in self.phase_entries):self.covered.update(aliases)
            else:body=self.effect_set(self.contract_plan.body,self.terminal.label)
            if direct_preflight:
                if self.contract_plan.fallback:raise ValueError('preflight macro cannot omit non-dominated fallback effects')
                self.entry=body;self.covered.update(i for i,e in self.contract_plan.prefix)
            else:
                self.region='preflight';entry=self.condition(compiler.preflight_active,body,self.terminal.label)
                from dataclasses import replace
                prefix=tuple((i,replace(e,guard=self.rejected_guards.get(e.guard,e.guard)))for i,e in self.contract_plan.prefix)
                self.entry=self.effect_set(prefix+self.contract_plan.fallback,entry)
        elif self.phase_plan:
            body=self.phase(self.phase_plan.root)
            entry=self.condition(compiler.preflight_active,body,self.terminal.label)
            self.entry=self.effect_set(self.phase_plan.prefix+self.phase_plan.fallback,entry)
            for region,aliases in self.phase_plan.region_aliases.items():
                if any(node==region for node,following in self.phase_entries):self.covered.update(aliases)
            self.constant_dead.update(self.phase_plan.report()['source_effects_control_dead'])
        else:self.entry=self.effect_set(tuple(enumerate(compiler.effects)),self.terminal.label)
        self.region='guard-initialization'
        for predicate in reversed(chosen):
            dest=self.frozen.pop(predicate);yes,no=self.block(),self.block()
            self.condition_entries={}
            yes.emit('MOVE_WORD',dest=dest,a=Operand('literal',1,1),yes=self.entry,width=1)
            no.emit('MOVE_WORD',dest=dest,a=Operand('literal',0,1),yes=self.entry,width=1)
            self.entry=self.condition(predicate,yes.label,no.label)
            self.frozen[predicate]=dest
        self.records,self.entry_pc=self.flatten()
        if self.covered|self.constant_dead!=set(range(len(compiler.effects))):raise ValueError('missing kernel effects in control store')

    def specialized_effects(self,effects,variable,low,high):
        from dataclasses import replace
        plan=self.contract_plan;result=[]
        for index,e in effects:
            guard=plan.cofactor(e.guard,variable,low,high)
            if self.nodes[guard].op=='const'and not self.nodes[guard].data:continue
            values=tuple((name,plan.cofactor(w,variable,low,high))for name,w in e.values)if e.kind=='merge_fields'else tuple(plan.cofactor(w,variable,low,high)for w in e.values)
            address=plan.cofactor(e.address,variable,low,high)if e.address>=0 else-1
            result.append((index,replace(e,guard=guard,values=values,address=address)))
        return tuple(result)

    def family_effects(self,effects,following):
        groups={}
        for index,effect in effects:groups.setdefault(effect.family,[]).append((index,effect))
        for group in reversed(list(groups.values())):
            root=self.contract_plan.partition(tuple(group));entry=self.phase(root,self.handler_return.label)
            if entry!=self.handler_return.label:
                caller=self.block();caller.emit('CALL_HANDLER',callee=entry,yes=following);following=caller.label
        return following

    def route_effects(self,effects,variable,following,lower=None):
        # Resolve the internal owner once; common effects share a continuation.
        # Main state is immutable until commit, so OR-shadow writes commute.
        common=[];private=[];values=set();plan=self.contract_plan
        for item in effects:
            tests=plan.tests(item[1].guard).get(variable)
            if tests:private.append(item);values.update(tests)
            else:common.append(item)
        lower=lower or self.family_effects
        tail=lower(common,following)
        if not private:return tail
        minimum,maximum=plan.contract_domains[variable];breaks={minimum,maximum+1}
        for value in values:
            if minimum<=value<=maximum:breaks.update((value,value+1))
        breaks=sorted(breaks);parts=[]
        for low,end in zip(breaks,breaks[1:]):
            body=lower(self.specialized_effects(private,variable,low,end-1),tail)
            if parts and parts[-1][2]==body:parts[-1]=(parts[-1][0],end-1,body)
            else:parts.append((low,end-1,body))
        return self.control_cases(variable,parts)

    def reserve_dispatch_table(self,size):
        region=getattr(self,'region','body');budget=getattr(self,'dispatch_table_budget',None)
        by_region=getattr(self,'dispatch_entries_by_region',None)
        used=getattr(self,'dispatch_entries_allocated',0)
        if isinstance(budget,dict):
            limit=budget.get(region,budget.get('default',0));consumed=by_region[region]if by_region is not None else 0
        else:limit=budget;consumed=used
        if limit is not None and consumed+size>limit:return False
        self.dispatch_entries_allocated=used+size
        if by_region is not None:by_region[region]+=size
        return True

    def control_cases(self,variable,parts):
        if len(parts)==1:return parts[0][2]
        if len(parts)>=4:
            default=parts[-1][2]
            interesting=[(low,high,target)for low,high,target in parts if target!=default]
            if interesting:
                high=max(end for low,end,target in interesting)
                size=16 if high<16 else 256 if high<256 else None
                if size and size<=16*len(parts)and self.reserve_dispatch_table(size):
                    block=self.block();block.emit('SWITCH_WORD',a=self.inputs[self.contract_plan.variables[variable]],yes=default,cases=tuple(interesting),immediate=size,forwards=2)
                    return block.label
        split=len(parts)//2;left=self.control_cases(variable,parts[:split]);right=self.control_cases(variable,parts[split:])
        block=self.block();block.emit('TEST_WORD_LT',a=self.inputs[self.contract_plan.variables[variable]],b=Operand('literal',parts[split][0],self.nodes[variable].width),yes=left,no=right,width=self.nodes[variable].width)
        return block.label

    def effect_set(self,effects,following):
        previous=self.effect_lookup;self.effect_lookup=dict(effects)
        grouped=defaultdict(list)
        for i,effect in effects:grouped[effect.guard].append(i)
        trie={'effects':[],'children':{}}
        self.condition_frequency=Counter()
        for guard in grouped:self.condition_frequency.update(self.guard_literals(guard))
        for guard,ids in grouped.items():
            node=self.nodes[guard]
            if node.op=='const'and not node.data:self.constant_dead.update(ids);continue
            conditions=self.guard_literals(guard)
            here=trie
            for condition in sorted(conditions,key=self.priority):here=here['children'].setdefault(condition,{'effects':[],'children':{}})
            here['effects'].extend(ids)
        result=self.trie(trie,following);self.effect_lookup=previous;return result

    def phase(self,node,following=None):
        if following is None:following=self.terminal.label
        key=node,following
        if key in self.phase_entries:return self.phase_entries[key]
        plan=self.contract_plan if self.family_dispatch else self.phase_plan
        kind,index=node
        if kind=='leaf':
            leaf=plan.leaves[index]
            entry=self.effect_set(leaf['effects'],following)
            self.covered.update(leaf['aliases'])
        else:
            case=plan.dispatch[index];ranges=[]
            for low,high,child in case['cases']:
                target=self.phase(child,following)
                if ranges and ranges[-1][2]==target:ranges[-1]=(ranges[-1][0],high,target)
                else:ranges.append((low,high,target))
            def select(parts):
                if len(parts)==1:return parts[0][2]
                if self.fast_default_dispatch and parts[0][2]==following:
                    left=parts[0][2];right=select(parts[1:]);split=1
                else:
                    split=len(parts)//2;left=select(parts[:split]);right=select(parts[split:])
                block=self.block();code=WordCode(self,block);a=code.get(case['variable'])
                code.block.emit('TEST_WORD_LT',a=a,b=Operand('literal',parts[split][0],a.width),yes=left,no=right,width=a.width)
                return block.label
            entry=self.control_cases(case['variable'],ranges)if self.indexed_phases else select(ranges)
        self.phase_entries[key]=entry;return entry

    def block(self):
        if len(self.blocks)>=200000:
            raise ValueError('typed control store exceeds200000 compiler blocks; no model emission authorized')
        block=Block(len(self.blocks),getattr(self,'region','body'));self.blocks.append(block);return block

    def guard_literals(self,index):
        n=self.nodes[index]
        if n.op=='const':return ()if n.data else(index,)
        if index in self.frozen or n.op!='all':return(index,)
        return tuple(sorted(set(i for arg in n.args for i in self.guard_literals(arg))))

    def equality(self,index):
        n=self.nodes[index]
        if n.op!='eq':return None
        for a,b in(n.args,n.args[::-1]):
            if self.nodes[b].op=='const':return a,self.nodes[b].data
        return None

    def priority(self,index):
        eq=self.equality(index);name=''
        if eq and self.nodes[eq[0]].op=='input':name=self.nodes[eq[0]].data
        rank=0 if name=='status'else 1 if name=='task'else 2 if name=='mode'else 3 if name=='read/frame/task'else 4 if name.endswith('_pc')or name=='read/frame/phase'else 5
        # Global validity/ownership prefixes must precede task-specific tests.
        # Otherwise the same large prefix is copied into every phase branch.
        if self.control_priority and rank in(1,2,3,4):return 0,rank,name,index
        return (1 if self.control_priority else 0),-self.condition_frequency[index],rank,name,index

    def condition(self,index,yes,no,memo=None,start=None):
        if start is None:start=self.temporary_base
        key=(index,yes,no,tuple(sorted((memo or {}).items())),start)
        if key not in self.condition_entries:self.condition_entries[key]=self.condition_body(index,yes,no,memo,start)
        return self.condition_entries[key]

    def condition_body(self,index,yes,no,memo,start):
        if getattr(self,'incremental_bounds',False) and index==self.compiler.g.pred(self.compiler.invalid_syntax):
            block=self.block();block.emit('TEST_INVALID_LATCH',yes=yes,no=no,width=1)
            return block.label
        if index in self.frozen:
            block=self.block();block.emit('TEST_WORD_NONZERO',a=self.frozen[index],yes=yes,no=no,width=1)
            return block.label
        n=self.nodes[index]
        if self.contract_plan and index==self.compiler.preflight_active:
            return self.preflight_condition(index,yes,no,memo,start)
        if n.op=='const':return yes if n.data else no
        if n.op=='not':return self.condition(n.args[0],no,yes,memo,start)
        if n.op in('all','any'):
            # Source enum/tag membership is a word dispatch, not a linear
            # scan of every equality. This applies to any fixed comparison
            # set; runtime words and all unknown16bit values remain data.
            candidates=defaultdict(list);ordinary=[]
            def flatten(i):
                child=self.nodes[i]
                return tuple(j for a in child.args for j in flatten(a))if child.op==n.op else(i,)
            for arg in tuple(i for a in n.args for i in flatten(a)):
                child=self.nodes[arg];positive=arg
                if n.op=='all':
                    if child.op!='not':ordinary.append(arg);continue
                    positive=child.args[0]
                equality=self.equality(positive)
                if equality:candidates[equality[0]].append((equality[1],arg))
                else:ordinary.append(arg)
            groups=[]
            for word,items in candidates.items():
                if len(items)>=3:groups.append((word,sorted(set(v for v,a in items))))
                else:ordinary.extend(a for v,a in items)
            if groups:
                following=yes if n.op=='all'else no
                for arg in reversed(ordinary):following=self.condition(arg,following,no,memo,start)if n.op=='all'else self.condition(arg,yes,following,memo,start)
                for word,values in reversed(groups):
                    following=self.switch(word,[(value,no if n.op=='all'else yes)for value in values],following,memo,start)
                return following
            following=yes if n.op=='all'else no
            for arg in reversed(n.args):following=self.condition(arg,following,no,memo,start)if n.op=='all'else self.condition(arg,yes,following,memo,start)
            return following
        block=self.block();code=WordCode(self,block,memo,start)
        if n.op in('eq','ult'):
            a,b=(code.get(i)for i in n.args)
            code.block.emit('TEST_WORD_'+('EQ'if n.op=='eq'else'LT'),a=a,b=b,yes=yes,no=no,width=max(a.width,b.width),forwards=(max(a.width,b.width)+15)//16)
        else:
            a=code.get(index)
            code.block.emit('TEST_WORD_NONZERO',a=a,yes=yes,no=no,width=n.width,forwards=(n.width+15)//16)
        return block.label

    def preflight_condition(self,index,yes,no,memo,start):
        """Factor the source preflight predicate by INTERNAL control only.

        This partitions every16bit task/mode value before checking data. It
        replaces a long source expression of nested task overrides, preserving
        invalid task/mode paths and all tag/pointer checks verbatim.
        """
        opaque=frozenset(self.frozen)
        key=index,yes,no,tuple(sorted((memo or {}).items())),start,opaque
        if key in self.preflight_entries:return self.preflight_entries[key]
        plan=self.contract_plan
        tests={v:values for v,values in plan.tests(index,opaque).items()if plan.variables[v]in('task','mode')}
        if not tests:
            # Avoid re-entering this transform if no control test remains.
            saved=self.contract_plan;self.contract_plan=None
            try:entry=self.condition(index,yes,no,memo,start)
            finally:self.contract_plan=saved
        else:
            variable=min(tests,key=lambda v:(plan.variables[v]!='task',-len(tests[v])))
            limit=1<<self.nodes[variable].width;breaks={0,limit}
            for value in tests[variable]:
                if 0<=value<limit:breaks.update((value,value+1))
            breaks=sorted(breaks);parts=[]
            for low,end in zip(breaks,breaks[1:]):
                cofactored=plan.cofactor(index,variable,low,end-1,opaque)
                if cofactored==index:raise ValueError('preflight control partition did not remove a test')
                target=self.preflight_condition(cofactored,yes,no,memo,start)
                if parts and parts[-1][2]==target:parts[-1]=(parts[-1][0],end,target)
                else:parts.append((low,end,target))
            entry=self.control_cases(variable,[(low,end-1,target)for low,end,target in parts])
        self.preflight_entries[key]=entry;return entry

    def actions(self,ids,following):
        effects=[self.effect_lookup.get(i,self.compiler.effects[i])for i in ids]
        key=(tuple((e.kind,e.values,e.address)for e in effects),following)
        if key in self.action_entries:
            entry=self.action_entries[key];self.covered.update(ids)
            for i in ids:self.source_action_regions.setdefault(i,set()).add(entry)
            return entry
        block=self.block();code=WordCode(self,block)
        pending=[];provenance=[]
        def flush():
            if pending:
                code.block.emit('MERGE_CHECKER_FIELDS3',items=tuple(pending),effects=tuple(provenance),forwards=2*len(pending))
                pending.clear();provenance.clear()
        for index,effect in zip(ids,effects):
            self.covered.add(index)
            if effect.kind=='merge_fields':
                for name,word in effect.values:
                    value=code.get(word);dest=self.inputs[name]
                    pending.append((dest,value));provenance.append(index)
                    if len(pending)==3:flush()
            else:
                flush()
                address=code.get(effect.address);bank=effect.kind.removeprefix('write_')
                for first in range(0,len(effect.values),3):
                    values=tuple(code.get(word)for word in effect.values[first:first+3])
                    code.block.emit('MERGE_ARENA_FIELDS3',a=address,items=values,immediate=16*{'heap':0,'stack':1,'context':2}[bank]+first,effects=(index,),forwards=1+len(values))
        flush();code.block.emit('JUMP',yes=following);self.action_entries[key]=block.label
        for i in ids:self.source_action_regions.setdefault(i,set()).add(block.label)
        return block.label

    def switch(self,word,cases,following,memo=None,start=None):
        if not cases:return following
        if len(cases)>=4:
            maximum=max(value for value,target in cases);minimum=min(value for value,target in cases)
            size=16 if maximum<16 else 256 if maximum<256 else None
            if minimum>=0 and size and size<=16*len(cases)and self.reserve_dispatch_table(size):
                block=self.block();code=WordCode(self,block,memo,start);a=code.get(word)
                code.block.emit('SWITCH_WORD',a=a,yes=following,cases=tuple((value,value,target)for value,target in cases),immediate=size,width=a.width,forwards=2)
                return block.label
        mid=len(cases)//2;value,entry=cases[mid]
        left=self.switch(word,cases[:mid],following,memo,start);right=self.switch(word,cases[mid+1:],following,memo,start)
        comparison=self.block();code=WordCode(self,comparison,memo,start);a=code.get(word)
        less=self.block();less.emit('TEST_WORD_LT',a=a,b=Operand('literal',value,a.width),yes=left,no=right,width=a.width)
        code.block.emit('TEST_WORD_EQ',a=a,b=Operand('literal',value,a.width),yes=entry,no=less.label,width=a.width)
        return comparison.label

    def trie(self,node,following):
        equalities=defaultdict(list);ordinary=[];pairs=defaultdict(dict)
        for predicate,child in node['children'].items():
            eq=self.equality(predicate)
            if eq:equalities[eq[0]].append((eq[1],child))
            else:
                n=self.nodes[predicate];pairs[n.args[0]if n.op=='not'else predicate][n.op!='not']=child
        entry=following
        for predicate,branches in pairs.items():
            if len(branches)==2:
                yes=self.trie(branches[True],entry);no=self.trie(branches[False],entry)
                entry=self.condition(predicate,yes,no)
            else:
                polarity,child=next(iter(branches.items()))
                yes=self.trie(child,entry)
                entry=self.condition(predicate,yes,entry)if polarity else self.condition(predicate,entry,yes)
        for word,cases in reversed(list(equalities.items())):
            lowered=[(value,self.trie(child,entry))for value,child in sorted(cases,key=lambda row:row[0])]
            entry=self.switch(word,lowered,entry)
        return self.actions(node['effects'],entry)if node['effects']else entry

    def flatten(self):
        # Fold an unconditional tail transfer into the preceding descriptor's
        # next-PC field. This changes no checks and is not input specialization.
        for block in self.blocks:
            if len(block.records)>=2 and block.records[-1].op=='JUMP'and block.records[-2].yes is None:
                block.records[-2].yes=block.records[-1].yes;block.records.pop()
        starts={};rows=[]
        for block in self.blocks:
            if not block.records:continue
            starts[block.label]=len(rows);rows.extend(block.records)
        result=[]
        for row in rows:
            item=asdict(row)
            for k in('yes','no','callee'):
                if item[k]is not None:item[k]=starts[item[k]]
            item['cases']=[(low,high,starts[target])for low,high,target in item['cases']]
            result.append(item)
        # Remove compiler blocks that no branch of this FIXED checker can
        # reach. Both outcomes of every data comparison remain traversed; no
        # declaration or proof input is inspected here.
        entry=starts[self.entry];reachable=set();pending=[entry]
        while pending:
            pc=pending.pop()
            if pc in reachable:continue
            reachable.add(pc);record=result[pc]
            if record['op']in('COMMIT_STEP','RETURN_HANDLER'):continue
            following=record['yes']if record['yes']is not None else pc+1
            pending.append(following)
            if record['no']is not None:pending.append(record['no'])
            if record['callee']is not None:pending.append(record['callee'])
            pending.extend(target for low,high,target in record['cases'])
        order=sorted(reachable);positions={old:new for new,old in enumerate(order)}
        self.unreachable_records=len(result)-len(order)
        compact=[]
        for old in order:
            row=result[old]
            for field in('yes','no','callee'):
                if row[field]is not None:row[field]=positions[row[field]]
            row['cases']=[(low,high,positions[target])for low,high,target in row['cases']]
            compact.append(row)
        return compact,positions[entry]

    def report(self):
        opcounts=dict(Counter(r['op']for r in self.records));effects=self.compiler.effects
        return dict(format='leanputer.typed-kernel-control-store.v1',input_independent=True,
            rule_families=self.compiler.families,rule_family_count=len(self.compiler.families),
            captured_effects=len(effects),mapped_effects=len(self.covered),constant_dead_effects=len(self.constant_dead),
            unmapped_effects=sorted(set(range(len(effects)))-self.covered-self.constant_dead),
            typed_nodes=self.capture_statistics,control_records=len(self.records),entry_pc=self.entry_pc,operations=opcounts,
            temporary_words_including_ports=self.peak_temporaries,proposed_available_temporary_words=707,
            record_budget=65536,record_budget_met=len(self.records)<=65536,scratch_budget_met=self.peak_temporaries<=707,
            record_budget_basis='16bit control PC with paged weight-ROM; final native count and dense architecture are accounted separately',
            pc16_encoding_met=len(self.records)<=65536,frozen_guard_words=len(self.frozen),
            input_independent_unreachable_records_removed=self.unreachable_records,
            commit_accounting=dict(algorithm='model-owned dirty-field queue; OR shadow merges and queued commit',max_unique_fields=len(self.compiler.layout.fields),queue_address_bits=11,queue_entry_storage_bits=16,queue_entries_per_row=7,queue_rows=136,current_rows=136,shadow_rows=136,main_shadow_interleaved=True,temporary_rows=101,reserved_arena_rows=3,rf_rows_total=512,rf_read_ports=3,rf_heads_total=12,field_merge_max_forwards=2,commit_steady_forwards_per_dirty_field=2),
            full_rule_capture=True,native_lowering_complete=False,original_source_stock_admission=False,
            native_unmapped_actions=sorted(opcounts),
            phase_dispatch=self.phase_plan.report()if self.phase_plan else None,
            checked_contract_dispatch=bool(self.contract_plan),
            source_family_control_dispatch=self.contract_plan.report()if self.family_dispatch else None,
            source_control_role_dispatch=self.role_dispatch,source_global_mode_dispatch=self.mode_dispatch,indexed_phase_dispatch=self.indexed_phases,incremental_bounds=self.incremental_bounds,fast_default_dispatch=self.fast_default_dispatch,direct_source_preflight=self.direct_preflight,global_continuation_dispatch=self.continuation_dispatch,dispatch_table_budget=self.dispatch_table_budget,dispatch_entries_allocated=self.dispatch_entries_allocated,dispatch_entries_by_region=dict(self.dispatch_entries_by_region),
            note='All source rule effects are mapped to typed WORD/control records. This does not establish112bit encoding, a native operator schedule, complete semantic coverage, latency or source stock admission.')

    def serializable(self):
        return dict(report=self.report(),records=self.records,
            effects=[asdict(e)for e in self.compiler.effects])
