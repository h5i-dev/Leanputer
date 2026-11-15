"""Compact shared RF/word datapath emitted into UNMODIFIED stock Qwen3.5.

Bring-up module, NOT a full source checker. The immutable ROM is compiler-owned;
inputs carry only operand words/initial rows. No host instruction dispatch or
semantic feedback is used. Full typed-store action coverage is reported apart.
"""
from dataclasses import dataclass
from enum import IntEnum
import math
import torch
from ..native_machine import NativeBuilder
from ..native_vendor.qwenputer.ir import K,A_BIT,A_REF,Head,FFN
from ..native_vendor.qwenputer.expr import Expr
from ..native_vendor.qwenputer.emit import Layout,allocate,emit_layers,row,reads


class WordAction(IntEnum):
    MOVE=0; ADD=1; SUB=2; EQ_BRANCH=3; LT_BRANCH=4; STOP_OK=5; STOP_INVALID=6; JUMP=7
    AND=8; OR=9; XOR=10; SHR=11; SHL=12; NONZERO_BRANCH=13
    SHR_LOOP=14; SHL_LOOP=15; MERGE_FIELDS3=16; COMMIT_FIELDS=48; PUBLISH_RESULT=49
    CALL_HANDLER=50; RETURN_HANDLER=51
    CLEAR_RF_ROW=52
    SWITCH4=53; SWITCH8=54
    HEAP_ROW_READ=56; FRAME_ROW_READ=57; CONTEXT_ROW_READ=58; DECLARATION_ROW_READ=59
    HEAP_READ=40; HEAP_WRITE=41; FRAME_READ=42; FRAME_WRITE=43
    CONTEXT_READ=44; CONTEXT_WRITE=45; DECLARATION_READ=46


@dataclass(frozen=True)
class CoreRecord:
    action: WordAction
    dest: int = 0
    a: int = 0
    b: int = 0
    immediate: int = 0
    yes: int = 0
    no: int = 0
    literal_a: bool = False
    literal_b: bool = False
    auxiliary: int = 0

    def bits(self):
        fields=[(int(self.action),6),(self.dest,12),(self.a,12),(self.b,12),(self.immediate,16),(self.yes,16),(self.no,16),(int(self.literal_a)|2*int(self.literal_b),6),(self.auxiliary,16)]
        result=[]
        for value,width in fields:
            if not 0<=value<1<<width:raise ValueError('core record field overflow')
            result.extend((value>>i)&1 for i in range(width))
        return result


@dataclass(frozen=True)
class FieldRecord:
    """Up to three simultaneous checker shadow assignments, never host effects."""
    items: tuple
    yes: int

    def bits(self):
        if not 1<=len(self.items)<=3:raise ValueError('field descriptor needs1..3 assignments')
        fields=[(int(WordAction.MERGE_FIELDS3),6)]
        for index in range(3):
            dest,value,literal=self.items[index]if index<len(self.items)else(0,0,False)
            if dest&8 or (dest>>4)*7+(dest&7)>=951 or dest&7>=7:raise ValueError('field target must be a main checker row')
            fields.extend(((dest,12),(value,16),(int(literal),1)))
        fields.extend(((len(self.items)-1,2),(self.yes,16),(0,1)))
        result=[]
        for value,width in fields:
            if not 0<=value<1<<width:raise ValueError('field descriptor overflow')
            result.extend(value>>i&1 for i in range(width))
        return result


def rf_address(word):
    """Static compiler register placement, not an inference callback."""
    page_row,slot=divmod(word,7)
    if not 0<=page_row<512:raise ValueError('RF word exceeds four128row pages')
    return (page_row<<3)|slot


class FixedSlots:
    def __init__(self):self.next=13;self.groups={}
    def add(self,name,width):
        value=list(range(self.next,self.next+width));self.groups[name]=value;self.next+=width;return value


@dataclass
class StockDatapath:
    model: object
    slots: FixedSlots
    layout: Layout
    report: dict

    def embeddings(self,packets):
        """Fixed syntax/data transport only. No micro-op is decoded here."""
        parameter=next(self.model.parameters());out=torch.zeros((*packets.shape[:-1],self.layout.hidden),dtype=parameter.dtype,device=parameter.device)
        out[...,:self.layout.m]=self.layout.ballast;out[...,13:self.slots.next]=packets.to(out.device,out.dtype)
        return out

    def packet(self,**groups):
        result=torch.zeros(self.slots.next-13)
        for name,values in groups.items():
            indices=self.slots.groups[name]
            if len(values)!=len(indices):raise ValueError('syntax packet group width')
            result[[i-13 for i in indices]]=torch.tensor(values,dtype=result.dtype)
        return result

    def new_cache(self):
        if not self.report.get('compact_inactive_attention'):return None
        from copy import deepcopy
        from transformers import StaticCache
        # Only zero-output attention blocks use a one-token window. Active
        # checker memories retain the unmodified stock GDN cache layers.
        config=deepcopy(self.model.config)
        config.layer_types=['linear_attention'if kind=='linear_attention'else'sliding_attention'for kind in config.layer_types]
        config.sliding_window=1
        return StaticCache(config=config,max_cache_len=1)


def build(records,device='cpu',hidden=768,intermediate=256,rom_layout='flat',datapath_layers=35,compact_attention=False):
    from transformers import Qwen3_5ForCausalLM,Qwen3_5TextConfig
    from transformers.initialization import no_init_weights
    torch.set_num_threads(1)
    if hidden!=768 or intermediate!=256:raise ValueError('prototype physical domain H768/I256')
    if not records or len(records)>65536:raise ValueError('16bit control PC domain')
    if rom_layout not in('flat','byte_pages'):raise ValueError('unknown weight-ROM layout')
    encoded=[r.bits()for r in records];pages=math.ceil(len(records)/128)
    rom_layers=math.ceil((15*pages if rom_layout=='byte_pages'else len(records))/intermediate)
    decode_layers=7 if rom_layout=='byte_pages'else 0
    module_start=1+rom_layers+decode_layers;layers=rom_layers+decode_layers+datapath_layers+5
    logical_count=layers*(3*hidden*intermediate+644*hidden+1666)+129*hidden
    if logical_count>100000000:raise ValueError('complete dense stock shape exceeds100M before allocation')
    builder=NativeBuilder(intermediate=intermediate,reset_layers=module_start);g=builder.graph;fixed=FixedSlots();features={};physical={}
    def feature(name,width):
        slots=fixed.add(name,width);values=[builder.feature(f'{name}/{i}')for i in range(width)]
        for value,slot in zip(values,slots):physical[next(iter(value.terms))]=slot
        features[name]=values;return values
    # Only the finite kernel outcome/reason enums are narrowed. All semantic
    # RF words and the64bit diagnostic interface remain unchanged.
    from .traversal_machine import Outcome,Reason
    if max(Outcome)>=8 or max(Reason)>=64:raise ValueError('kernel outcome/reason enum exceeds native diagnostic latches')
    pc=feature('pc',16);status=feature('status',3);reason=feature('reason',6);result=feature('result',16);stage=feature('stage',4);boot=feature('boot',1)[0]
    handler_return=feature('handler_return',16)
    raw_code=feature('record',112);code=list(raw_code);valid=feature('record_valid',1)[0]
    A=feature('A',16);B=feature('B',16);D=feature('row',126)
    payload=feature('pending_payload',126);address=feature('pending_row',9);enable=feature('pending_enable',1)[0];kind=feature('pending_kind',3)
    queue_row=feature('queue_row',8);queue_slot=feature('queue_slot',3);dirty_count=feature('dirty_count',10)
    read_row=feature('queue_read_row',8);read_slot=feature('queue_read_slot',3)
    for i,value in enumerate(raw_code):
        level=2*module_start
        if rom_layout=='byte_pages':level=2*(1+rom_layers+(8-i%8 if i%8 else 0))
        g.dims[next(iter(value.terms))].level=level
    g.dims[next(iter(valid.terms))].level=2*(1+rom_layers)
    if rom_layout=='byte_pages':
        # Byte low-bit slots hold the byte itself. Its bit0 is a free linear
        # remainder after the seven high bits have been decoded in weights.
        for byte in range(14):code[8*byte]=raw_code[8*byte]-sum(((1<<bit)*raw_code[8*byte+bit]for bit in range(1,8)),Expr())
    one=g.one;run=builder.gate('and',[one-boot]+[one-bit for bit in status],'run')
    def matches(bits,value):return[b if value>>i&1 else one-b for i,b in enumerate(bits)]
    def select(condition,x,y,name):return[g.ffn([(1,a,condition),(1,b,one-condition)],name=name)for a,b in zip(x,y)]
    def increment(bits,name):
        return[one-bits[0]]+[bits[i]+builder.gate('and',bits[:i],name+'-carry')-2*builder.gate('and',bits[:i+1],name+'-both')for i in range(1,len(bits))]
    def queue_address(bits):
        #272 + bounded queue row, exact Boolean carry; no rounded packed sum.
        carry=[builder.gate('and',bits[4:i],f'queue-address-carry/{i}')for i in range(5,9)]
        return bits[:4]+[one-bits[4]]+[bits[i]+carry[i-5]-2*builder.gate('and',[bits[i],carry[i-5]],f'queue-address-xor/{i}')for i in range(5,8)]+[one-carry[3]]
    queue_write_address=queue_address(queue_row);queue_read_address=queue_address(read_row)
    flags={op:builder.gate('and',[bit if int(op)>>i&1 else one-bit for i,bit in enumerate(code[:6])],f'opcode/{op.name}')for op in WordAction}
    # Opcode flags are mutually exclusive for every binary6bit ROM code.
    # Their union is a free linear sum, not another Boolean circuit.
    def op_any(*ops):return sum((flags[op]for op in ops),Expr())
    shifting=op_any(WordAction.SHR_LOOP,WordAction.SHL_LOOP)
    shift_resume=builder.gate('and',[shifting,builder.gate('or',stage,'shift-resume-stage')],'shift-resume')
    publish=builder.gate('and',[run,valid,flags[WordAction.PUBLISH_RESULT]],'publish-result')
    merging=flags[WordAction.MERGE_FIELDS3];committing=flags[WordAction.COMMIT_FIELDS]
    merge_append=builder.gate('and',[merging,stage[0]],'merge-append')
    merge_value=builder.gate('and',[merging,one-stage[0]],'merge-value')
    has_dirty=builder.gate('or',dirty_count,'has-dirty')
    commit_main=builder.gate('and',[committing,has_dirty,one-stage[0]],'commit-main')
    commit_clear=builder.gate('and',[committing,has_dirty,stage[0]],'commit-clear')
    descriptor_select=[builder.gate('and',matches(stage[1:3],i),f'field-index/{i}')for i in range(3)]
    descriptor=[]
    for bit in range(29):descriptor.append(g.ffn([(1,code[6+29*i+bit],descriptor_select[i])for i in range(3)],name='field-descriptor'))
    field_dest=descriptor[:12];field_source=descriptor[12:28];field_literal=descriptor[28]
    normal_a=select(merging,field_source[:12],select(shift_resume,code[6:18],code[18:30],'shift-source-address'),'source-A-address')
    query_a=select(committing,read_slot+queue_read_address,normal_a,'query-A-address')
    literal_a=g.ffn([(1,field_literal,merging),(1,code[90],one-merging-committing)],name='source-A-literal')
    immediate_a=select(merging,field_source,code[42:58],'source-A-immediate')
    rowing=op_any(WordAction.HEAP_ROW_READ,WordAction.FRAME_ROW_READ,WordAction.CONTEXT_ROW_READ,WordAction.DECLARATION_ROW_READ)
    load=rowing+op_any(WordAction.HEAP_READ,WordAction.FRAME_READ,WordAction.CONTEXT_READ,WordAction.DECLARATION_READ)
    store=op_any(WordAction.HEAP_WRITE,WordAction.FRAME_WRITE,WordAction.CONTEXT_WRITE)
    load0=builder.gate('and',[load,one-stage[0]],'arena-load0');load1=builder.gate('and',[load,stage[0]],'arena-load1')
    suppress_dest=store+load0
    # Write enables depend only on the previous model packet. Graph logic
    # follows reserved ROM stages and precedes all coherent RF copies.
    write_flags=[builder.gate('and',[enable]+[one-b for b in kind]+matches(address[7:],page),f'rf-write/{page}')for page in range(4)]
    def select_form(literals):
        condition=sum(literals,Expr())-(len(literals)-1)*one
        return K*(2*condition-one)
    rf_metadata=[]
    def head(port,page,query,outputs,literal=Expr()):
        layer=module_start+4*port+page
        # The ROM operand encodes (row9,word-slot3). Literal operands do not
        # query a register. Only one page contributes to each read port.
        q={r:select_form(matches(query[3:10],r)+matches(query[10:12],page)+[run,one-literal]+([one-suppress_dest]if port==2 else[]))for r in range(128)}
        k={r:select_form(matches(address[:7],r))for r in range(128)}
        values={0:A_REF*one,1:A_REF*one};values.update({i+2:A_BIT*v for i,v in enumerate(payload)})
        if port<2:
            z={};outs=[];into=[]
            for slot in range(7):
                gate=K*(sum(matches(query[:3],slot),Expr())-2*one)
                for bit in range(16):
                    column=2+16*slot+bit;z[column]=gate;outs.append((column,128.));into.append(outputs[bit])
        else:
            z={i+2:K*one for i in range(126)};outs=[(i+2,128.)for i in range(126)];into=list(outputs)
        g.head(f'rf.{port}.{page}',q,k,values,0,z,outs,beta=write_flags[page],min_level=2*layer,into=into)
        rf_metadata.append(dict(port=port,page=page,layer=g.nodes[-1].level//2))
    for page in range(4):head(0,page,query_a,A,literal_a)
    queued_main=A[:3]+[Expr()]+A[3:11];queued_shadow=A[:3]+[one]+A[3:11]
    shadow_dest=field_dest[:3]+[one]+field_dest[4:]
    query_b=select(committing,queued_shadow,select(merging,shadow_dest,code[30:42],'source-B-field'),'query-B-address')
    for page in range(4):head(1,page,query_b,B,code[91]-g.ffn([(1,code[91],merging+committing)],name='source-B-literal-mask'))
    merge_dest=select(stage[0],[Expr()]*3+queue_write_address,shadow_dest,'merge-destination')
    commit_dest=select(stage[0],queued_shadow,queued_main,'commit-destination')
    query_d=select(committing,commit_dest,select(merging,merge_dest,code[6:18],'destination-field'),'query-D-address')
    for page in range(4):head(2,page,query_d,D)
    # Literal and register operands use the SAME word lanes.
    a=[A[i]+builder.gate('and',[literal_a,immediate_a[i]],f'literal-A/{i}')for i in range(16)]
    b=[B[i]+builder.gate('and',[code[91],code[42+i]],f'literal-B/{i}')for i in range(16)]
    bank_metadata=[]
    # The same pending packet writes ONE bank per forward. RF copies consume
    # it first; arena banks consume it later, before any new packet is committed.
    bank_specs=[('heap',512,4,1,WordAction.HEAP_READ,WordAction.HEAP_WRITE,12),('stack',32,6,2,WordAction.FRAME_READ,WordAction.FRAME_WRITE,16),('constants',4,6,4,WordAction.DECLARATION_READ,None,17),('context',8,1,3,WordAction.CONTEXT_READ,WordAction.CONTEXT_WRITE,18)]
    for bank,cells,words,bank_id,reading,storing,start_layer in bank_specs:
        row_read={WordAction.HEAP_READ:WordAction.HEAP_ROW_READ,WordAction.FRAME_READ:WordAction.FRAME_ROW_READ,WordAction.CONTEXT_READ:WordAction.CONTEXT_ROW_READ,WordAction.DECLARATION_READ:WordAction.DECLARATION_ROW_READ}[reading]
        query=builder.gate('and',[flags[reading]+flags[row_read],one-stage[0]],f'{bank}-load0')+(flags[storing]if storing is not None else Expr())
        width=cells.bit_length()-1
        for page in range(max(1,cells//128)):
            writing=builder.gate('and',[enable]+matches(kind,bank_id)+matches(address[7:width],page)+([boot]if bank=='constants'else[]),f'{bank}-write/{page}')
            q={r:select_form(matches(a[:min(7,width)],r)+matches(a[7:width],page)+[run,query])for r in range(min(128,cells))}
            k={r:select_form(matches(address[:min(7,width)],r))for r in range(min(128,cells))}
            data={0:A_REF*one,1:A_REF*one};data.update({i+2:A_BIT*payload[i]for i in range(words*16)})
            layer=module_start+start_layer+page
            g.head(f'arena.{bank}.{page}',q,k,data,0,{i+2:K*one for i in range(words*16)},[(i+2,128.)for i in range(words*16)],beta=writing,min_level=2*layer,into=D[:words*16])
            bank_metadata.append(dict(bank=bank,page=page,layer=g.nodes[-1].level//2,words=words))
    submode=op_any(WordAction.SUB,WordAction.EQ_BRANCH,WordAction.LT_BRANCH,WordAction.SWITCH4,WordAction.SWITCH8)
    # One shared nibble adder handles add, subtract and order comparison.
    carry=submode;sum_bits=[]
    for offset in range(0,16,4):
        av=sum(((1<<i)*a[offset+i]for i in range(4)),Expr());parts=[]
        for i in range(4):
            both=g.ffn([(1,b[offset+i],submode)],name='invert-product')
            parts.append(b[offset+i]+submode-2*both)
        bv=sum(((1<<i)*parts[i]for i in range(4)),Expr());total=av+bv+carry
        carry=g.ffn([(1,one,total-15*one),(-1,one,total-16*one)],name='word-carry')
        digit=total-16*carry
        from ..control_packing import PackedBit
        memo={};sum_bits.extend(PackedBit(digit,i,4).realize(builder,memo)for i in range(4))
    less=one-carry;equal=builder.gate('not',[builder.gate('or',sum_bits,'difference-nonzero')],'word-equal')
    writing=op_any(WordAction.MOVE,WordAction.ADD,WordAction.SUB,WordAction.AND,WordAction.OR,WordAction.XOR,WordAction.SHR,WordAction.SHL,WordAction.SHR_LOOP,WordAction.SHL_LOOP)
    arithmetic=op_any(WordAction.ADD,WordAction.SUB)
    shift_right=op_any(WordAction.SHR,WordAction.SHR_LOOP)
    shift_left=op_any(WordAction.SHL,WordAction.SHL_LOOP)
    selected=[]
    for i in range(16):
        conjunction=g.ffn([(1,a[i],b[i])],name='word-conjunction')
        disjunction=a[i]+b[i]-conjunction
        exclusive=disjunction-conjunction
        selected.append(g.ffn([(1,a[i],flags[WordAction.MOVE]),(1,sum_bits[i],arithmetic),(1,conjunction,flags[WordAction.AND]),(1,disjunction,flags[WordAction.OR]),(1,exclusive,flags[WordAction.XOR]),(1,a[i+1]if i<15 else Expr(),shift_right),(1,a[i-1]if i else Expr(),shift_left)],name=f'word-value/{i}'))
    active_core=builder.gate('and',[run,valid,writing],'active-core-write')
    active_load0=builder.gate('and',[run,valid,load0],'active-load0');active_load1=builder.gate('and',[run,valid,load1],'active-load1')
    word_load1=builder.gate('and',[active_load1,one-rowing],'word-load1')
    row_copy=[builder.gate('and',[active_load1,condition],'row-copy')for condition in(rowing,op_any(WordAction.HEAP_ROW_READ,WordAction.FRAME_ROW_READ,WordAction.DECLARATION_ROW_READ),op_any(WordAction.FRAME_ROW_READ,WordAction.DECLARATION_ROW_READ))]
    active_store=builder.gate('and',[run,valid,store],'active-store')
    active_merge=builder.gate('and',[run,valid,merge_value],'active-merge')
    active_append=builder.gate('and',[run,valid,merge_append],'active-append')
    active_commit_main=builder.gate('and',[run,valid,commit_main],'active-commit-main')
    active_commit_clear=builder.gate('and',[run,valid,commit_clear],'active-commit-clear')
    active_clear=builder.gate('and',[run,valid,flags[WordAction.CLEAR_RF_ROW]],'active-row-clear')
    active_write=builder.gate('or',[active_core,active_load1,active_store,active_merge,active_append,active_commit_main,active_commit_clear,active_clear],'active-write')
    field_flags=[builder.gate('and',matches(code[96:99],field),f'arena-field/{field}')for field in range(7)]
    loaded=[g.ffn([(1,D[16*field+i],field_flags[field])for field in range(7)],name='arena-word')for i in range(16)]
    result_from_row=builder.gate('or',[active_load0,publish],'result-from-row')
    next_result=[g.ffn([(1,selected[i],active_core),(1,loaded[i],result_from_row),(1,result[i],one-active_core-result_from_row)],name=f'result/{i}')for i in range(16)]
    old_dirty=g.ffn([(1,D[112+slot],builder.gate('and',matches(field_dest[:3],slot),f'dirty-field/{slot}'))for slot in range(7)],name='old-dirty')
    needs_append=builder.gate('and',[active_merge,one-old_dirty],'needs-append')
    merged=[]
    for i in range(16):
        old=g.ffn([(1,B[i],old_dirty)],name='old-shadow-word')
        merged.append(a[i]+old-g.ffn([(1,a[i],old)],name='shadow-or'))
    field_reference=field_dest[:3]+field_dest[4:]+[Expr()]*5
    rf_active=active_core+word_load1+active_merge+active_commit_main
    rf_value=[g.ffn([(1,selected[i],active_core),(1,result[i],word_load1),(1,merged[i],active_merge),(1,B[i],active_commit_main)],name='rf-word')for i in range(16)]
    slot_flags=[builder.gate('and',matches(query_d[:3],slot)+[rf_active],f'destination-slot/{slot}')for slot in range(7)]
    append_slots=[builder.gate('and',matches(queue_slot,slot)+[active_append],f'queue-slot/{slot}')for slot in range(7)]
    dirty_set=[builder.gate('and',matches(query_d[:3],slot)+[active_merge],f'dirty-set/{slot}')for slot in range(7)]
    dirty_clear=[builder.gate('and',matches(query_d[:3],slot)+[active_commit_clear],f'dirty-clear/{slot}')for slot in range(7)]
    store_fields=[builder.gate('and',[field_flags[i],active_store],f'store-field/{i}')for i in range(6)]
    pending=[]
    for i,old in enumerate(D):
        if i<112:
            choose=slot_flags[i//16];memory=store_fields[i//16]if i<96 else Expr()
            append=append_slots[i//16]
            copying=row_copy[0 if i<16 else 1 if i<64 else 2]if i<96 else Expr()
            value=g.ffn([(1,rf_value[i%16],choose),(1,b[i%16],memory),(1,field_reference[i%16],append),(1,payload[i],copying),(1,old,one-choose-memory-append-active_clear-copying)],name='patched-row')
        elif i<119:
            value=g.ffn([(1,one,dirty_set[i-112]),(1,old,one-dirty_set[i-112]-dirty_clear[i-112]-active_clear)],name='patched-dirty')
        else:value=old
        pending.append(value)
    zero=builder.gate('not',[builder.gate('or',a,'operand-nonzero')],'operand-zero')
    failed_branch=builder.gate('or',[builder.gate('and',[flags[WordAction.EQ_BRANCH],one-equal],'eq-false'),builder.gate('and',[flags[WordAction.LT_BRANCH],one-less],'lt-false'),builder.gate('and',[flags[WordAction.NONZERO_BRANCH],zero],'zero-branch')],'branch-false')
    returning=flags[WordAction.RETURN_HANDLER]
    switch4=builder.gate('and',[flags[WordAction.SWITCH4],one-builder.gate('or',sum_bits[4:],'switch4-outside-page')],'switch4-in-page')
    switch8=builder.gate('and',[flags[WordAction.SWITCH8],one-builder.gate('or',sum_bits[8:],'switch8-outside-page')],'switch8-in-page')
    following=[g.ffn([(1,code[58+i],one-failed_branch-returning-switch4-switch8),(1,code[74+i],failed_branch),(1,handler_return[i],returning),(1,sum_bits[i]if i<4 else code[96+i],switch4),(1,sum_bits[i]if i<8 else code[96+i],switch8)],name='next-pc')for i in range(16)]
    following=select(merging,code[95:111],following,'next-field-pc')
    known=sum(flags.values(),Expr())
    internal_fault=builder.gate('and',[run,builder.gate('or',[one-valid,one-known],'bad-control')],'internal-fault')
    ok=builder.gate('and',[run,valid,flags[WordAction.STOP_OK]],'stop-ok');bad=builder.gate('or',[internal_fault,builder.gate('and',[run,valid,flags[WordAction.STOP_INVALID]],'stop-invalid')],'stop-bad')
    stopping=builder.gate('or',[ok,bad,publish],'stopping')
    next_status=[ok,bad]+[Expr()]*14
    status_values=[g.ffn([(1,next_status[i],stopping),(1,A[i],publish),(1,status[i],one-stopping)],name='status-next')for i in range(len(status))]
    reason_values=[g.ffn([(1,bad if i==0 else Expr(),stopping),(1,B[i],publish),(1,reason[i],one-stopping)],name='reason-next')for i in range(len(reason))]
    last_field=builder.gate('and',[builder.gate('not',[builder.gate('or',[builder.gate('and',[stage[1+i],one-code[93+i]],'field-index-diff-a'),builder.gate('and',[one-stage[1+i],code[93+i]],'field-index-diff-b')],'field-index-diff')],'field-index-equal')for i in range(2)],'last-field')
    field_finished=builder.gate('or',[active_append,builder.gate('and',[active_merge,old_dirty],'existing-shadow')],'field-finished')
    next_field=builder.gate('and',[field_finished,one-last_field],'next-field')
    merge_hold=builder.gate('or',[needs_append,next_field],'merge-hold')
    shift_increment=increment(stage,'shift-stage-increment')
    shift_difference=[shift_increment[i]+code[96+i]-2*g.ffn([(1,shift_increment[i],code[96+i])],name='shift-count-both')for i in range(4)]
    shift_hold=builder.gate('and',[run,shifting,builder.gate('or',shift_difference,'shift-not-finished')],'shift-hold')
    advance=builder.gate('and',[run,one-load0,one-merge_hold,one-shift_hold,one-committing+builder.gate('and',[committing,one-has_dirty],'commit-finished')],'advance-pc')
    next_pc=[g.ffn([(1,following[i],advance),(1,pc[i],one-advance)],name='pc-next')for i in range(16)]
    writing_rf=rf_active+active_append+active_commit_clear+active_clear+row_copy[0]
    next_address=[g.ffn([(1,query_d[3+i],writing_rf),(1,a[i],active_store)],name='write-address')for i in range(9)]
    next_kind=[builder.gate('or',[flags[op]for op in(WordAction.HEAP_WRITE,WordAction.CONTEXT_WRITE)if (1 if op==WordAction.HEAP_WRITE else 3)>>bit&1]+([flags[WordAction.FRAME_WRITE]]if 2>>bit&1 else[]),f'write-kind/{bit}')for bit in range(3)]
    index_increment=increment(stage[1:3],'field-index-increment')
    next_stage=[builder.gate('or',[active_load0,needs_append,active_commit_main],'next-substage')]+[g.ffn([(1,index_increment[i],next_field),(1,stage[1+i],needs_append)],name='next-field-index')for i in range(2)]+[Expr()]
    next_stage=[g.ffn([(1,value,one-shifting),(1,shift_increment[i],shift_hold)],name='next-loop-stage')for i,value in enumerate(next_stage)]
    queue_wrap=builder.gate('and',matches(queue_slot,6),'queue-wrap')
    read_wrap=builder.gate('and',matches(read_slot,6),'queue-read-wrap')
    queue_insert_row=select(queue_wrap,increment(queue_row,'queue-row-increment'),queue_row,'next-queue-row')
    queue_insert_slot=[g.ffn([(1,value,one-queue_wrap)],name='next-queue-slot')for value in increment(queue_slot,'queue-slot-increment')]
    queue_remove_row=select(read_wrap,increment(read_row,'read-row-increment'),read_row,'next-read-row')
    queue_remove_slot=[g.ffn([(1,value,one-read_wrap)],name='next-read-slot')for value in increment(read_slot,'read-slot-increment')]
    commit_done=builder.gate('and',[run,committing,one-has_dirty],'commit-done')
    def cursor(old,new,condition,name):
        return[g.ffn([(1,value,condition),(1,previous,one-condition-commit_done)],name=name)for previous,value in zip(old,new)]
    next_queue_row=cursor(queue_row,queue_insert_row,active_append,'queue-row-next')
    next_queue_slot=cursor(queue_slot,queue_insert_slot,active_append,'queue-slot-next')
    next_read_row=cursor(read_row,queue_remove_row,active_commit_clear,'read-row-next')
    next_read_slot=cursor(read_slot,queue_remove_slot,active_commit_clear,'read-slot-next')
    count_up=increment(dirty_count,'dirty-increment')
    count_down=[one-dirty_count[0]]+[dirty_count[i]+builder.gate('and',[one-v for v in dirty_count[:i]],'dirty-borrow')-2*builder.gate('and',[dirty_count[i]]+[one-v for v in dirty_count[:i]],'dirty-both')for i in range(1,10)]
    next_dirty=[g.ffn([(1,count_up[i],active_append),(1,count_down[i],active_commit_clear),(1,dirty_count[i],one-active_append-active_commit_clear)],name='dirty-count-next')for i in range(10)]
    targets=result+pc+status+reason+payload+address+[enable]+kind+stage+queue_row+queue_slot+read_row+read_slot+dirty_count
    values=next_result+next_pc+status_values+reason_values+pending+next_address+[active_write]+next_kind+next_stage+next_queue_row+next_queue_slot+next_read_row+next_read_slot+next_dirty
    # Bit-only updates have exact [-1,1] deltas. Commit after ALL old reads of
    # that feature, allowing independent columns to finish at different layers.
    last={d:0 for d in physical}
    for node in g.nodes:
        for d in reads(node):
            if d in last:last[d]=max(last[d],node.level)
    target_dims={next(iter(v.terms))for v in targets}
    clear_tails={next(iter(v.terms))for v in payload[119:]}
    for target,value in zip(targets,values):
        d=next(iter(target.terms))
        if (set(value.terms)&target_dims)-{d}:raise ValueError('prototype cross-column commit needs snapshot')
        g.ffn([(1,one-active_clear if d in clear_tails else one,value),(-1,one,target)],name='bit-commit',into=target,min_level=max(last[d],2*module_start))
    for bit,target in enumerate(handler_return):
        d=next(iter(target.terms))
        g.ffn([(1,code[74+bit],flags[WordAction.CALL_HANDLER]),(-1,target,flags[WordAction.CALL_HANDLER])],name='handler-return-commit',into=target,min_level=max(last[d],2*module_start))
    allocation=allocate(g,None,set(physical),intermediate)
    scratch=fixed.next;feature_count=len(physical)
    mapping={d:slot-13 for d,slot in physical.items()}
    for d,slot in allocation.slots.items():
        if d not in mapping:mapping[d]=scratch+slot-feature_count-13
    high=max(mapping.values(),default=0)+14
    if high>hidden:raise ValueError(f'compact module exceeds H768: needs{high} channels')
    allocation.slots=mapping;layout=Layout(hidden=hidden,m=12,slots=mapping)
    body=module_start+datapath_layers
    if g.n_layers()>body:raise ValueError(f'datapath exceeds{datapath_layers} layers: graph{g.n_layers()} body{body}')
    active_layers={node.level//2 for node in g.nodes if isinstance(node,Head)}
    layer_types=['linear_attention'if not compact_attention or i in active_layers else'full_attention'for i in range(layers)]
    expected=sum(3*hidden*intermediate+(644*hidden+1666 if kind=='linear_attention'else 12*hidden+4)for kind in layer_types)+129*hidden
    if expected>100000000:raise ValueError('complete dense stock shape exceeds100M before allocation')
    config=Qwen3_5TextConfig(hidden_size=hidden,intermediate_size=intermediate,num_hidden_layers=layers,layer_types=layer_types,vocab_size=64,linear_key_head_dim=128,linear_value_head_dim=128,linear_num_key_heads=1,linear_num_value_heads=1,linear_conv_kernel_dim=4,num_attention_heads=1,num_key_value_heads=1,head_dim=2,hidden_act='silu',tie_word_embeddings=False,rope_parameters=dict(rope_type='default',rope_theta=10000000,partial_rotary_factor=1.,mrope_section=[1,0,0],mrope_interleaved=True))
    prior=torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.bfloat16)
        with torch.device(device),no_init_weights():model=Qwen3_5ForCausalLM(config)
    finally:torch.set_default_dtype(prior)
    with torch.no_grad():
        for p in model.parameters():p.zero_()
        for layer in model.model.layers:
            if hasattr(layer,'linear_attn'):layer.linear_attn.dt_bias.fill_(-110.);layer.linear_attn.norm.weight.fill_(1.)
        tc=config.to_dict()
        for layer in range(g.n_layers()):
            emitted=emit_layers(g,layout,tc,0,'model.',allocation,only_layer=layer)
            _,unexpected=model.load_state_dict(emitted,strict=False)
            if unexpected:raise ValueError('stock module parameter name mismatch')
        def spare(layer,count):
            mlp=model.model.layers[layer].mlp
            occupied=((mlp.gate_proj.weight!=0).any(dim=1)|(mlp.up_proj.weight!=0).any(dim=1)).nonzero().flatten().tolist()
            available=[i for i in range(intermediate)if i not in set(occupied)]
            if len(available)<count:raise ValueError('ROM/decoder stock MLP capacity collision')
            return mlp,available[:count]
        if rom_layout=='flat':
            for index,bits in enumerate(encoded):
                layer=1+index//intermediate;unit=index%intermediate;mlp=model.model.layers[layer].mlp
                if bool(mlp.gate_proj.weight[unit].any() or mlp.up_proj.weight[unit].any() or mlp.down_proj.weight[:,unit].any()):raise ValueError('flat ROM overlaps scheduled graph unit')
                condition=sum(matches(pc,index),Expr())-15*one
                row(condition,layout,mlp.gate_proj.weight[unit],128.)
                row(one,layout,mlp.up_proj.weight[unit],1/128.)
                for bit,value in enumerate(bits):
                    if value:mlp.down_proj.weight[fixed.groups['record'][bit],unit]=1.
                mlp.down_proj.weight[fixed.groups['record_valid'][0],unit]=1.
        else:
            # The low-row decoder temporarily occupies FUTURE RF read lanes.
            # Separate pending-write lanes remain intact for every RF copy.
            low_slots=fixed.groups['A']+fixed.groups['B']+fixed.groups['row'][:96]
            mlp,units=spare(0,128)
            for value,unit in enumerate(units):
                row(sum(matches(pc[:7],value),Expr())-6*one,layout,mlp.gate_proj.weight[unit],128.)
                row(one,layout,mlp.up_proj.weight[unit],1/128.);mlp.down_proj.weight[low_slots[value],unit]=1.
            for page in range(pages):
                for column in range(15):
                    number=15*page+column;layer=1+number//intermediate;unit=number%intermediate;mlp=model.model.layers[layer].mlp
                    if bool(mlp.gate_proj.weight[unit].any() or mlp.up_proj.weight[unit].any() or mlp.down_proj.weight[:,unit].any()):raise ValueError('paged ROM overlaps scheduled graph unit')
                    row(sum(matches(pc[7:],page),Expr())-8*one,layout,mlp.gate_proj.weight[unit],128.)
                    for low,slot in enumerate(low_slots):
                        index=128*page+low
                        value=(1 if column==14 else sum(encoded[index][8*column+bit]<<bit for bit in range(8)))if index<len(encoded)else 0
                        mlp.up_proj.weight[unit,slot]=value/(128*layout.scale)
                    target=fixed.groups['record_valid'][0]if column==14 else fixed.groups['record'][8*column]
                    mlp.down_proj.weight[target,unit]=1.
            for stage_index,bit in enumerate(range(7,0,-1)):
                layer=1+rom_layers+stage_index;mlp,units=spare(layer,28+(128 if stage_index==0 else 0))
                for byte in range(14):
                    remainder=raw_code[8*byte]-sum(((1<<high)*raw_code[8*byte+high]for high in range(bit+1,8)),Expr())
                    for which,threshold in enumerate(((1<<bit)-1,1<<bit)):
                        unit=units[2*byte+which]
                        row(remainder-threshold*one,layout,mlp.gate_proj.weight[unit],128.)
                        row(one,layout,mlp.up_proj.weight[unit],1/128.)
                        mlp.down_proj.weight[fixed.groups['record'][8*byte+bit],unit]=1. if which==0 else-1.
                if stage_index==0:
                    for slot,unit in zip(low_slots,units[28:]):
                        row(one,layout,mlp.gate_proj.weight[unit],128.)
                        mlp.up_proj.weight[unit,slot]=1/(128*layout.scale);mlp.down_proj.weight[slot,unit]=-1.
        persistent=set(sum((fixed.groups[n]for n in('pc','status','reason','result','stage','pending_payload','pending_row','pending_enable','pending_kind','queue_row','queue_slot','queue_read_row','queue_read_slot','dirty_count','handler_return')),[]))
        clear=[slot for slot in range(12,hidden)if slot not in persistent]
        for index,slot in enumerate(clear):
            layer=body+index//intermediate;unit=index%intermediate;mlp=model.model.layers[layer].mlp
            row(one,layout,mlp.gate_proj.weight[unit],128.)
            mlp.up_proj.weight[unit,slot]=1/(128*layout.scale);mlp.down_proj.weight[slot,unit]=-1.
        model.model.norm.weight.fill_(-1.)
        output_slots=sum((fixed.groups[n]+[None]*(16-len(fixed.groups[n]))for n in('pc','status','reason','result')),[])
        for i,slot in enumerate(output_slots):
            if slot is not None:model.model.norm.weight[slot]=1/layout.scale;model.lm_head.weight[i,slot]=1.
    model.requires_grad_(False);model.eval()
    if compact_attention:model.set_attn_implementation('eager')
    params=sum(p.numel()for p in model.parameters())
    if params!=expected:raise ValueError('stock dense parameter accounting changed')
    report=dict(format='leanputer.stock-shared-module.v1',logical_dense_parameters=params,hidden=hidden,intermediate=intermediate,layers=layers,rom_records=len(records),rom_layers=rom_layers,rom_layout=rom_layout,rom_decode_layers=decode_layers,active_rf_heads=12,rf_heads=rf_metadata,arena_heads=bank_metadata,rf_ports=3,rf_rows_per_copy=512,rf_payload_bits=126,allocated_channels=high,features=fixed.next-13,operator_scratch_channels=high-fixed.next,graph_layers=g.n_layers(),module_layer_budget=datapath_layers,parameter_storage='dense',stock_class=type(model).__module__+'.'+type(model).__name__,full_source_checker=False,native_actions=[a.name for a in WordAction],checker_commit_layout=dict(main_rows=136,shadow_rows=136,main_shadow_interleaved=True,dirty_queue_rows=136,queue_first_row=272,queue_entries_per_row=7,max_dirty_fields=951,temporary_first_row=408,temporary_last_row=508,temporary_words=707,reserved_arena_buffer_rows=[509,510,511],reserved_arena_buffers_implemented=False,merge_new_field_forwards=2,merge_existing_field_forwards=1,commit_forwards_per_dirty_field=2,commit_exit_forwards=1))
    report.update(compact_inactive_attention=compact_attention,active_gdn_layers=sum(kind=='linear_attention'for kind in layer_types),inactive_attention_layers=sum(kind=='full_attention'for kind in layer_types),inactive_attention_head_dim=2,inactive_kv_window=1 if compact_attention else None)
    return StockDatapath(model,fixed,layout,report)
