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
    def __init__(self,compiler):
        self.compiler=compiler;self.nodes=compiler.g.nodes;self.blocks=[];self.peak_temporaries=17
        uses=Counter(i for n in self.nodes for i in n.args)
        chosen=sorted(sorted((i for i,n in enumerate(self.nodes)if n.op in('all','any','not')and uses[i]>=4),key=lambda i:-uses[i])[:32])
        self.frozen={i:Operand('temporary',17+j,1)for j,i in enumerate(chosen)}
        self.temporary_base=17+len(chosen)
        self.condition_entries={}
        self.inputs={name:Operand('current',i,width)for i,(name,width)in enumerate(compiler.layout.fields)}
        port=0
        for name,index in compiler.g.input_words.items():
            if name.startswith('read/'):
                self.inputs[name]=Operand('temporary',port,self.nodes[index].width);port+=1
        if port!=17:raise ValueError('kernel read-port word ABI')
        self.covered=set();self.constant_dead=set()
        self.terminal=self.block();self.terminal.emit('COMMIT_STEP')
        grouped=defaultdict(list)
        for i,effect in enumerate(compiler.effects):grouped[effect.guard].append(i)
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
        self.entry=self.trie(trie,self.terminal.label)
        for predicate in reversed(chosen):
            dest=self.frozen.pop(predicate);yes,no=self.block(),self.block()
            self.condition_entries={}
            yes.emit('MOVE_WORD',dest=dest,a=Operand('literal',1,1),yes=self.entry,width=1)
            no.emit('MOVE_WORD',dest=dest,a=Operand('literal',0,1),yes=self.entry,width=1)
            self.entry=self.condition(predicate,yes.label,no.label)
            self.frozen[predicate]=dest
        self.records,self.entry_pc=self.flatten()
        if self.covered|self.constant_dead!=set(range(len(compiler.effects))):raise ValueError('missing kernel effects in control store')

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
        return -self.condition_frequency[index],rank,name,index

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

    def actions(self,ids,following):
        block=self.block();code=WordCode(self,block)
        pending=[];provenance=[]
        def flush():
            if pending:
                code.block.emit('MERGE_CHECKER_FIELDS3',items=tuple(pending),effects=tuple(provenance),forwards=2*len(pending))
                pending.clear();provenance.clear()
        for index in ids:
            effect=self.compiler.effects[index];self.covered.add(index)
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
        flush();code.block.emit('JUMP',yes=following);return block.label

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
        return result,starts[self.entry]

    def report(self):
        opcounts=dict(Counter(r['op']for r in self.records));effects=self.compiler.effects
        return dict(format='leanputer.typed-kernel-control-store.v1',input_independent=True,
            rule_families=self.compiler.families,rule_family_count=len(self.compiler.families),
            captured_effects=len(effects),mapped_effects=len(self.covered),constant_dead_effects=len(self.constant_dead),
            unmapped_effects=sorted(set(range(len(effects)))-self.covered-self.constant_dead),
            typed_nodes=self.compiler.g.statistics(),control_records=len(self.records),entry_pc=self.entry_pc,operations=opcounts,
            temporary_words_including_ports=self.peak_temporaries,proposed_available_temporary_words=175,
            record_budget=16384,record_budget_met=len(self.records)<=16384,scratch_budget_met=self.peak_temporaries<=175,
            pc16_encoding_met=len(self.records)<=65536,frozen_guard_words=len(self.frozen),
            commit_accounting=dict(algorithm='model-owned dirty-field queue; OR shadow merges and queued commit',max_unique_fields=len(self.compiler.layout.fields),queue_address_bits=11,queue_entries_per_row=11,queue_rows=87,current_rows=136,shadow_rows=136,temporary_rows=25,rf_rows_total=384,rf_read_ports=3,rf_heads_total=9,field_merge_max_forwards=2,commit_steady_forwards_per_dirty_field=2),
            full_rule_capture=True,native_lowering_complete=False,original_source_stock_admission=False,
            native_unmapped_actions=sorted(opcounts),
            note='All source rule effects are mapped to typed WORD/control records. This does not establish112bit encoding, a native operator schedule, complete semantic coverage, latency or source stock admission.')

    def serializable(self):
        return dict(report=self.report(),records=self.records,
            effects=[asdict(e)for e in self.compiler.effects])
