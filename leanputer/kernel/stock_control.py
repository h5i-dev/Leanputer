"""Compile the complete typed checker to fixed stock datapath records.

All expansion is compiler-time and input independent. There is no instruction
dispatch or semantic evaluator here. The production host repeats stock forward.
"""
from dataclasses import dataclass,replace
from collections import Counter
from .stock_datapath import CoreRecord,FieldRecord,WordAction as O,rf_address
from .control_store import Operand,ControlStore,WordCode


def main_address(index):
    row,slot=divmod(index,7)
    if not 0<=index<951:raise ValueError('checker main field bound')
    return 16*row+slot


def temporary_address(index):
    if not 0<=index<707:raise ValueError('checker temporary word bound')
    return rf_address(408*7+index)


@dataclass(frozen=True)
class Value:
    value: int
    literal: bool = False


class NativeControl:
    """Bounded two-limb lowering, arena shadowing and fixed source controller."""
    def __init__(self,store,addresses):
        self.store=store;self.pending=[];self.labels={};self.serial=0;self.mask_cursor=0
        cfg=store.compiler.cfg
        if (cfg.word_bits,cfg.heap,cfg.stack,cfg.context,cfg.constants)!=(16,512,32,8,4):raise ValueError('native shared layout currently requires word16/heap512/stack32/context8/constants4')
        if store.peak_temporaries>=200:raise ValueError('native compiler needs address scratch above typed temporaries')
        self.emit(O.JUMP,yes=('source',))
        for pc,record in enumerate(store.records):
            self.mark(('typed',pc));self.lower(record,('typed',record['yes']if record['yes']is not None else pc+1),('typed',record['no'])if record['no']is not None else None)
        self.source_prologue(addresses)
        self.commit_tail()
        self.records=[]
        for record,yes,no in self.pending:
            self.records.append(replace(record,yes=self.labels[yes],**({'no':self.labels[no]}if isinstance(record,CoreRecord)and no is not None else{})))
        before=len(self.records)
        def follow(pc):
            seen=set()
            while isinstance(self.records[pc],CoreRecord)and self.records[pc].action==O.JUMP:
                if pc in seen:raise ValueError('fixed control jump-only cycle')
                seen.add(pc);pc=self.records[pc].yes
            return pc
        keep=[i for i,r in enumerate(self.records)if i==0 or not isinstance(r,CoreRecord)or r.action!=O.JUMP]
        positions={pc:i for i,pc in enumerate(keep)}
        compact=[]
        for pc in keep:
            r=self.records[pc];fields=dict(yes=positions[follow(r.yes)])
            if isinstance(r,CoreRecord):fields['no']=positions[follow(r.no)]if r.action in(O.EQ_BRANCH,O.LT_BRANCH,O.NONZERO_BRANCH)else 0
            compact.append(replace(r,**fields))
        self.records=compact
        tails_removed=before-len(compact)
        # Hash-cons equal state updates with equal continuations. This is
        # whole-program compiler sharing, with both data branches retained.
        alias={};removed=0
        def canonical(pc):
            while pc in alias:pc=alias[pc]
            return pc
        changed=True
        while changed:
            changed=False;seen={}
            for pc,r in enumerate(self.records):
                if pc in alias:continue
                fields=dict(yes=canonical(r.yes))
                if isinstance(r,CoreRecord):fields['no']=canonical(r.no)if r.action in(O.EQ_BRANCH,O.LT_BRANCH,O.NONZERO_BRANCH)else 0
                key=replace(r,**fields)
                if key in seen and pc:
                    alias[pc]=seen[key];removed+=1;changed=True
                else:seen[key]=pc
        keep=[pc for pc in range(len(self.records))if pc not in alias];positions={pc:i for i,pc in enumerate(keep)}
        self.records=[replace(self.records[pc],yes=positions[canonical(self.records[pc].yes)],**({'no':positions[canonical(self.records[pc].no)]if self.records[pc].action in(O.EQ_BRANCH,O.LT_BRANCH,O.NONZERO_BRANCH)else 0}if isinstance(self.records[pc],CoreRecord)else{}))for pc in keep]
        self.report=dict(format='leanputer.native-checker-control.v1',input_independent=True,
            typed_records=len(store.records),native_records=len(self.records),pc16_encoding_met=len(self.records)<=65536,
            compiler_tail_transfers_removed=tails_removed,
            compiler_duplicate_records_removed=removed,
            actions=dict(Counter(r.action.name if isinstance(r,CoreRecord)else'MERGE_FIELDS3'for r in self.records)),
            rule_families=len(store.compiler.families),source_effects=len(store.compiler.effects),
            source_effects_mapped=len(store.covered),temporary_words_available=707,
            typed_temporary_peak=store.peak_temporaries,compiler_scratch_first=200,compiler_scratch_last=695,
            original_source_stock_admission=False,native_reference_verified=False,
            note='Complete fixed encoding count; native execution correspondence and stock source admission are separate obligations.')

    def label(self):self.serial+=1;return('local',self.serial)
    def mark(self,label):
        if label in self.labels:raise ValueError('duplicate compiler label')
        self.labels[label]=len(self.pending)

    def emit(self,op,dest=0,a=Value(0,True),b=Value(0,True),yes=None,no=None,auxiliary=0):
        if op not in(O.ADD,O.SUB,O.EQ_BRANCH,O.LT_BRANCH,O.AND,O.OR,O.XOR,O.HEAP_WRITE,O.FRAME_WRITE,O.CONTEXT_WRITE,O.PUBLISH_RESULT):b=Value(0)
        if a.literal and b.literal and a.value!=b.value:
            # One literal lane per core record. Compiler scratch is a real RF
            # word written by the preceding model step, never a host value.
            self.emit(O.MOVE,dest=temporary_address(690),a=a)
            a=Value(temporary_address(690))
        record=CoreRecord(op,dest=dest,a=0 if a.literal else a.value,b=0 if b.literal else b.value,
            literal_a=a.literal,literal_b=b.literal,immediate=a.value if a.literal else b.value if b.literal else 0,auxiliary=auxiliary)
        following=self.label()if yes is None else yes
        self.pending.append((record,following,no))
        if yes is None:self.mark(following)

    def value(self,operand,limb=0):
        if isinstance(operand,Operand):operand=operand.__dict__
        width=operand.get('source_width')or operand['width']
        if 16*limb>=width:return Value(0,True)
        bits=min(16,width-16*limb)
        space,index=operand['space'],operand['index']
        if space=='literal':return Value((index>>(16*limb))&((1<<bits)-1),True)
        if space=='current':
            if limb:raise ValueError('public checker fields must fit16bits')
            result=Value(main_address(index))
        elif space=='temporary':result=Value(temporary_address(index+limb))
        else:raise ValueError('unmapped native operand space '+space)
        if bits<16:
            scratch=temporary_address(681+self.mask_cursor%8);self.mask_cursor+=1
            self.emit(O.AND,dest=scratch,a=result,b=Value((1<<bits)-1,True));result=Value(scratch)
        return result

    def target(self,operand,limb=0):
        if operand['space']!='temporary':raise ValueError('word result must target compiler scratch')
        return temporary_address(operand['index']+limb)

    def mask(self,dest,width):
        if width<16:self.emit(O.AND,dest=dest,a=Value(dest),b=Value((1<<width)-1,True))

    def move(self,dest,a,width):
        if a.literal:self.emit(O.MOVE,dest=dest,a=Value(a.value&((1<<width)-1),True));return
        if a.value==dest and width==16:return
        self.emit(O.MOVE,dest=dest,a=a);self.mask(dest,width)

    def shifted(self,dest,a,count,left=False):
        if a.literal:self.emit(O.MOVE,dest=dest,a=Value(((a.value<<count)if left else(a.value>>count))&65535,True))
        elif not count:self.emit(O.MOVE,dest=dest,a=a)
        else:self.emit(O.SHL_LOOP if left else O.SHR_LOOP,dest=dest,a=a,auxiliary=count)

    def extract(self,dest,operand,low,width):
        if width>16:raise ValueError('extract limb exceeds16bits')
        if operand['space']=='literal':
            value=operand['index']&((1<<(operand.get('source_width')or operand['width']))-1)
            self.emit(O.MOVE,dest=dest,a=Value(value>>low&((1<<width)-1),True));return
        limb,shift=divmod(low,16);a=self.value(operand,limb)
        self.shifted(dest,a,shift)
        source_width=operand.get('source_width')or operand['width']
        if shift and low+width>16*(limb+1)and source_width>16*(limb+1):
            other=temporary_address(691)
            self.shifted(other,self.value(operand,limb+1),16-shift,True)
            self.emit(O.OR,dest=dest,a=Value(dest),b=Value(other))
        self.mask(dest,width)

    def arithmetic(self,r):
        width=r['width'];op=O.ADD if r['op']=='WORD_ADD'else O.SUB
        dest=self.target(r['dest']);a,b=self.value(r['a']),self.value(r['b'])
        # Preserve a source if an in-place result aliases it before carry test.
        if width>16 and not a.literal and a.value==dest:
            self.emit(O.MOVE,dest=temporary_address(692),a=a);a=Value(temporary_address(692))
        if width>16 and op==O.SUB:
            borrow,clear,join=self.label(),self.label(),self.label()
            self.emit(O.LT_BRANCH,a=a,b=b,yes=borrow,no=clear)
            self.mark(borrow);self.emit(O.MOVE,dest=temporary_address(693),a=Value(1,True),yes=join)
            self.mark(clear);self.emit(O.MOVE,dest=temporary_address(693),a=Value(0,True),yes=join)
            self.mark(join)
        self.emit(op,dest=dest,a=a,b=b)
        if width<=16:self.mask(dest,width);return
        if width>32:raise ValueError('native checker word exceeds two limbs')
        if op==O.ADD:
            carry,clear,join=self.label(),self.label(),self.label()
            self.emit(O.LT_BRANCH,a=Value(dest),b=a,yes=carry,no=clear)
            self.mark(carry);self.emit(O.MOVE,dest=temporary_address(693),a=Value(1,True),yes=join)
            self.mark(clear);self.emit(O.MOVE,dest=temporary_address(693),a=Value(0,True),yes=join)
            self.mark(join)
        high=self.target(r['dest'],1)
        self.emit(op,dest=high,a=self.value(r['a'],1),b=self.value(r['b'],1))
        self.emit(op,dest=high,a=Value(high),b=Value(temporary_address(693)))
        self.mask(high,width-16)

    def comparison(self,r,yes,no):
        op=r['op'];width=r['width'];a,b=self.value(r['a']),self.value(r['b'])if r['b']else Value(0,True)
        if width>16:
            ah=self.value(r['a'],1);bh=self.value(r['b'],1)if r['b']else Value(0,True)
            if ah.literal and bh.literal:
                if op=='TEST_WORD_NONZERO'and ah.value:self.emit(O.JUMP,yes=yes);return
                if op=='TEST_WORD_EQ'and ah.value!=bh.value:self.emit(O.JUMP,yes=no);return
                if op=='TEST_WORD_LT'and ah.value!=bh.value:self.emit(O.JUMP,yes=yes if ah.value<bh.value else no);return
            elif op=='TEST_WORD_NONZERO':
                lower=self.label();self.emit(O.NONZERO_BRANCH,a=ah,yes=yes,no=lower);self.mark(lower)
            elif op=='TEST_WORD_EQ':
                lower=self.label();self.emit(O.EQ_BRANCH,a=ah,b=bh,yes=lower,no=no);self.mark(lower)
            else:
                unequal,lower=self.label(),self.label()
                self.emit(O.EQ_BRANCH,a=ah,b=bh,yes=lower,no=unequal)
                self.mark(unequal);self.emit(O.LT_BRANCH,a=ah,b=bh,yes=yes,no=no);self.mark(lower)
        self.emit({'TEST_WORD_EQ':O.EQ_BRANCH,'TEST_WORD_LT':O.LT_BRANCH,'TEST_WORD_NONZERO':O.NONZERO_BRANCH}[op],a=a,b=b,yes=yes,no=no)

    def lower(self,r,yes,no,commit=('commit',)):
        op=r['op'];width=r['width']
        if op=='COMMIT_STEP':self.emit(O.JUMP,yes=commit);return
        if op=='JUMP':self.emit(O.JUMP,yes=yes);return
        if op.startswith('TEST_WORD_'):self.comparison(r,yes,no);return
        if op in('WORD_ADD','WORD_SUB'):self.arithmetic(r)
        elif op=='MOVE_WORD':
            for limb in range((width+15)//16):self.move(self.target(r['dest'],limb),self.value(r['a'],limb),min(16,width-16*limb))
        elif op=='EXTRACT_WORD':
            for limb in range((width+15)//16):self.extract(self.target(r['dest'],limb),r['a'],r['immediate']+16*limb,min(16,width-16*limb))
        elif op=='MERGE_WORD_SLICE':
            low=r['immediate']&31;length=r['immediate']>>5&31;shift=r['immediate']>>10
            if r['a']['space']=='literal'and not(r['a']['index']>>low&((1<<length)-1)):
                for limb in range((width+15)//16):self.move(self.target(r['dest'],limb),self.value(r['b'],limb),min(16,width-16*limb))
                self.emit(O.JUMP,yes=yes);return
            # Extract the entire <=18bit source into two real scratch words,
            # then compose each affected destination limb. Source/dest may alias.
            for limb in range((length+15)//16):self.extract(temporary_address(694+limb),r['a'],low+16*limb,min(16,length-16*limb))
            source=dict(space='temporary',index=694,width=length)
            for limb in range((width+15)//16):
                start=16*limb-shift;dest=self.target(r['dest'],limb)
                if start>=length or start+16<=0:
                    self.move(dest,self.value(r['b'],limb),min(16,width-16*limb));continue
                work=temporary_address(689)
                if start<0:
                    self.extract(work,source,0,min(length,16+start));self.shifted(work,Value(work),-start,True)
                else:self.extract(work,source,start,min(16,length-start))
                self.emit(O.OR,dest=dest,a=self.value(r['b'],limb),b=Value(work));self.mask(dest,min(16,width-16*limb))
        elif op=='MERGE_CHECKER_FIELDS3':
            items=tuple((main_address(dest['index']),value.value,value.literal)for dest,operand in r['items']for value in(self.value(operand),))
            self.pending.append((FieldRecord(items,0),yes,None));return
        elif op=='MERGE_ARENA_FIELDS3':
            bank,first=divmod(r['immediate'],16);base=(510,509,511)[bank]*7
            addr=temporary_address(680)
            self.emit(O.AND,dest=addr,a=self.value(r['a']),b=Value((self.store.compiler.cfg.heap,self.store.compiler.cfg.stack,self.store.compiler.cfg.context)[bank]-1,True))
            self.emit(O.OR,dest=rf_address(base),a=Value(addr),b=Value(rf_address(base)))
            for offset,operand in enumerate(r['items']):
                target=rf_address(base+1+first+offset)
                self.emit(O.OR,dest=target,a=self.value(operand),b=Value(target))
            # Frame row has no eighth slot; its enable is stored separately.
            flag=rf_address(510*7+6)if bank==1 else rf_address(base+(5 if bank==0 else 2))
            self.emit(O.MOVE,dest=flag,a=Value(1,True))
        else:raise ValueError('unmapped native typed action '+op)
        self.emit(O.JUMP,yes=yes)

    def address_records(self,graph,output,namespace,continuation):
        mini=object.__new__(ControlStore);mini.nodes=graph.nodes;mini.inputs=self.store.inputs;mini.blocks=[]
        mini.temporary_base=200;mini.peak_temporaries=200;mini.frozen={};mini.condition_entries={};mini.contract_plan=None
        block=mini.block();mini.entry=block.label;terminal=mini.block();terminal.emit('COMMIT_STEP')
        code=WordCode(mini,block);value=code.get(output.node)
        code.block.emit('MOVE_WORD',dest=Operand('temporary',670,len(output)),a=value,width=len(output),yes=terminal.label)
        rows,entry=mini.flatten();self.emit(O.JUMP,yes=(namespace,entry))
        for pc,r in enumerate(rows):
            self.mark((namespace,pc));self.lower(r,(namespace,r['yes']if r['yes']is not None else pc+1),(namespace,r['no'])if r['no']is not None else None,commit=continuation)
        if mini.peak_temporaries>=670:raise ValueError('address expression scratch collides with compiler operands')

    def source_prologue(self,addresses):
        self.mark(('source',));self.address_records(*addresses[0],'addresses1',('load-first',))
        self.mark(('load-first',));offset=0;port=0;packed=dict(space='temporary',index=670,width=16)
        for action,cells,words in((O.HEAP_READ,512,4),(O.FRAME_READ,32,6),(O.DECLARATION_READ,4,6)):
            width=cells.bit_length()-1;self.extract(temporary_address(671),packed,offset,width);offset+=width
            for field in range(words):
                self.emit(action,dest=temporary_address(port),a=Value(temporary_address(671)),auxiliary=field);port+=1
        self.address_records(*addresses[1],'addresses2',('load-context',))
        self.mark(('load-context',));self.emit(O.CONTEXT_READ,dest=temporary_address(16),a=Value(temporary_address(670)))
        self.emit(O.JUMP,yes=('typed',self.store.entry_pc))

    def commit_tail(self):
        self.mark(('commit',))
        for action,base,words,flag in((O.HEAP_WRITE,510,4,rf_address(510*7+5)),(O.FRAME_WRITE,509,6,rf_address(510*7+6)),(O.CONTEXT_WRITE,511,1,rf_address(511*7+2))):
            skip,write=self.label(),self.label()
            self.emit(O.NONZERO_BRANCH,a=Value(flag),yes=write,no=skip);self.mark(write)
            for field in range(words):self.emit(action,a=Value(rf_address(base*7)),b=Value(rf_address(base*7+1+field)),auxiliary=field)
            self.mark(skip)
        for row in(509,510,511):
            for slot in range(7):self.emit(O.MOVE,dest=rf_address(row*7+slot),a=Value(0,True))
        self.emit(O.COMMIT_FIELDS)
        names=[name for name,width in self.store.compiler.layout.fields]
        status,reason,result=(main_address(names.index(name))for name in('status','reason','r'))
        publish=self.label();self.emit(O.NONZERO_BRANCH,a=Value(status),yes=publish,no=('source',));self.mark(publish)
        self.emit(O.PUBLISH_RESULT,dest=result,a=Value(status),b=Value(reason),auxiliary=result&7,yes=publish)

