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


class Block:
    def __init__(self,label):self.label=label;self.records=[]
    def emit(self,op,**kwargs):
        row=Record(op,**kwargs);self.records.append(row);return row


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
    def __init__(self,compiler,phase_dispatch=False,contract_dispatch=False):
        self.capture_statistics=compiler.g.statistics()
        self.phase_plan=None;self.contract_plan=None;self.control_priority=contract_dispatch
        if phase_dispatch or contract_dispatch:
            from .control_phases import PhasePartition
            plan=PhasePartition(compiler,contract_only=contract_dispatch)
            if contract_dispatch:self.contract_plan=plan
            else:self.phase_plan=plan
        self.compiler=compiler;self.nodes=compiler.g.nodes;self.blocks=[];self.peak_temporaries=17
        uses=Counter(i for n in self.nodes for i in n.args)
        chosen=sorted(set(i for i in compiler.active_nodes if i<=compiler.preflight_active))if phase_dispatch or contract_dispatch else sorted(sorted((i for i,n in enumerate(self.nodes)if n.op in('all','any','not')and uses[i]>=4),key=lambda i:-uses[i])[:32])
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
        self.frozen={i:Operand('temporary',17+j,1)for j,i in enumerate(chosen)}
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
        if self.contract_plan:
            body=self.effect_set(self.contract_plan.body,self.terminal.label)
            entry=self.condition(compiler.preflight_active,body,self.terminal.label)
            self.entry=self.effect_set(self.contract_plan.prefix+self.contract_plan.fallback,entry)
        elif self.phase_plan:
            body=self.phase(self.phase_plan.root)
            entry=self.condition(compiler.preflight_active,body,self.terminal.label)
            self.entry=self.effect_set(self.phase_plan.prefix+self.phase_plan.fallback,entry)
            for region,aliases in self.phase_plan.region_aliases.items():
                if region in self.phase_entries:self.covered.update(aliases)
            self.constant_dead.update(self.phase_plan.report()['source_effects_control_dead'])
        else:self.entry=self.effect_set(tuple(enumerate(compiler.effects)),self.terminal.label)
        for predicate in reversed(chosen):
            dest=self.frozen.pop(predicate);yes,no=self.block(),self.block()
            self.condition_entries={}
            yes.emit('MOVE_WORD',dest=dest,a=Operand('literal',1,1),yes=self.entry,width=1)
            no.emit('MOVE_WORD',dest=dest,a=Operand('literal',0,1),yes=self.entry,width=1)
            self.entry=self.condition(predicate,yes.label,no.label)
            self.frozen[predicate]=dest
        self.records,self.entry_pc=self.flatten()
        if self.covered|self.constant_dead!=set(range(len(compiler.effects))):raise ValueError('missing kernel effects in control store')

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

    def phase(self,node):
        if node in self.phase_entries:return self.phase_entries[node]
        kind,index=node
        if kind=='leaf':
            leaf=self.phase_plan.leaves[index]
            entry=self.effect_set(leaf['effects'],self.terminal.label)
            self.covered.update(leaf['aliases'])
        else:
            case=self.phase_plan.dispatch[index];ranges=[]
            for low,high,child in case['cases']:
                target=self.phase(child)
                if ranges and ranges[-1][2]==target:ranges[-1]=(ranges[-1][0],high,target)
                else:ranges.append((low,high,target))
            def select(parts):
                if len(parts)==1:return parts[0][2]
                split=len(parts)//2;left=select(parts[:split]);right=select(parts[split:])
                block=self.block();code=WordCode(self,block);a=code.get(case['variable'])
                code.block.emit('TEST_WORD_LT',a=a,b=Operand('literal',parts[split][0],a.width),yes=left,no=right,width=a.width)
                return block.label
            entry=select(ranges)
        self.phase_entries[node]=entry;return entry

    def block(self):
        if len(self.blocks)>=200000:
            raise ValueError('typed control store exceeds200000 compiler blocks; no model emission authorized')
        block=Block(len(self.blocks));self.blocks.append(block);return block

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
        if index in self.frozen:
            block=self.block();block.emit('TEST_WORD_NONZERO',a=self.frozen[index],yes=yes,no=no,width=1)
            return block.label
        n=self.nodes[index]
        if self.contract_plan and index==self.compiler.preflight_active:
            return self.preflight_condition(index,yes,no,memo,start)
        if n.op=='const':return yes if n.data else no
        if n.op=='not':return self.condition(n.args[0],no,yes,memo,start)
        if n.op in('all','any'):
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
        key=index,yes,no,tuple(sorted((memo or {}).items())),start
        if key in self.preflight_entries:return self.preflight_entries[key]
        plan=self.contract_plan
        tests={v:values for v,values in plan.tests(index).items()if plan.variables[v]in('task','mode')}
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
                cofactored=plan.cofactor(index,variable,low,end-1)
                if cofactored==index:raise ValueError('preflight control partition did not remove a test')
                target=self.preflight_condition(cofactored,yes,no,memo,start)
                if parts and parts[-1][2]==target:parts[-1]=(parts[-1][0],end,target)
                else:parts.append((low,end,target))
            def select(cases):
                if len(cases)==1:return cases[0][2]
                split=len(cases)//2;left=select(cases[:split]);right=select(cases[split:])
                block=self.block();block.emit('TEST_WORD_LT',a=self.inputs[plan.variables[variable]],b=Operand('literal',cases[split][0],self.nodes[variable].width),yes=left,no=right,width=self.nodes[variable].width)
                return block.label
            entry=select(parts)
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

    def switch(self,word,cases,following):
        if not cases:return following
        mid=len(cases)//2;value,entry=cases[mid]
        left=self.switch(word,cases[:mid],following);right=self.switch(word,cases[mid+1:],following)
        comparison=self.block();code=WordCode(self,comparison);a=code.get(word)
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
            for k in('yes','no'):
                if item[k]is not None:item[k]=starts[item[k]]
            result.append(item)
        # Remove compiler blocks that no branch of this FIXED checker can
        # reach. Both outcomes of every data comparison remain traversed; no
        # declaration or proof input is inspected here.
        entry=starts[self.entry];reachable=set();pending=[entry]
        while pending:
            pc=pending.pop()
            if pc in reachable:continue
            reachable.add(pc);record=result[pc]
            if record['op']=='COMMIT_STEP':continue
            following=record['yes']if record['yes']is not None else pc+1
            pending.append(following)
            if record['no']is not None:pending.append(record['no'])
        order=sorted(reachable);positions={old:new for new,old in enumerate(order)}
        self.unreachable_records=len(result)-len(order)
        compact=[]
        for old in order:
            row=result[old]
            for field in('yes','no'):
                if row[field]is not None:row[field]=positions[row[field]]
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
            note='All source rule effects are mapped to typed WORD/control records. This does not establish112bit encoding, a native operator schedule, complete semantic coverage, latency or source stock admission.')

    def serializable(self):
        return dict(report=self.report(),records=self.records,
            effects=[asdict(e)for e in self.compiler.effects])
