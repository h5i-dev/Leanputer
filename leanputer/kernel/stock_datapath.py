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


def rf_address(word):
    """Static compiler register placement, not an inference callback."""
    page_row,slot=divmod(word,7)
    if not 0<=page_row<384:raise ValueError('RF word exceeds three128row pages')
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


def build(records,device='cpu',hidden=768,intermediate=256,rom_layout='flat',datapath_layers=25):
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
    builder=NativeBuilder(intermediate=intermediate,reset_layers=0);g=builder.graph;fixed=FixedSlots();features={};physical={}
    def feature(name,width):
        slots=fixed.add(name,width);values=[builder.feature(f'{name}/{i}')for i in range(width)]
        for value,slot in zip(values,slots):physical[next(iter(value.terms))]=slot
        features[name]=values;return values
    pc=feature('pc',16);status=feature('status',16);reason=feature('reason',16);result=feature('result',16);stage=feature('stage',4);boot=feature('boot',1)[0]
    raw_code=feature('record',112);code=list(raw_code);valid=feature('record_valid',1)[0]
    A=feature('A',16);B=feature('B',16);D=feature('row',126)
    payload=feature('pending_payload',126);address=feature('pending_row',9);enable=feature('pending_enable',1)[0];kind=feature('pending_kind',3)
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
    flags={op:builder.gate('and',[bit if int(op)>>i&1 else one-bit for i,bit in enumerate(code[:6])],f'opcode/{op.name}')for op in WordAction}
    load=builder.gate('or',[flags[o]for o in(WordAction.HEAP_READ,WordAction.FRAME_READ,WordAction.CONTEXT_READ,WordAction.DECLARATION_READ)],'arena-load')
    store=builder.gate('or',[flags[o]for o in(WordAction.HEAP_WRITE,WordAction.FRAME_WRITE,WordAction.CONTEXT_WRITE)],'arena-store')
    load0=builder.gate('and',[load,one-stage[0]],'arena-load0');load1=builder.gate('and',[load,stage[0]],'arena-load1')
    suppress_dest=builder.gate('or',[store,load0],'suppress-rf-destination')
    # Write enables depend only on the previous model packet. Put them in the
    # front protocol layer, before ROM and all three coherent RF read copies.
    write_flags=[builder.gate('and',[enable]+[one-b for b in kind]+[b if page>>i&1 else one-b for i,b in enumerate(address[7:])],f'rf-write/{page}')for page in range(3)]
    def matches(bits,value):return[b if value>>i&1 else one-b for i,b in enumerate(bits)]
    def select_form(literals):
        condition=sum(literals,Expr())-(len(literals)-1)*one
        return K*(2*condition-one)
    def head(port,page,query,outputs):
        layer=module_start+3*port+page
        # The ROM operand encodes (row9,word-slot3). Literal operands do not
        # query a register. Only one page contributes to each read port.
        literal=code[90+port]if port<2 else Expr()
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
    for port,(query,outputs)in enumerate(((code[18:30],A),(code[30:42],B),(code[6:18],D))):
        for page in range(3):head(port,page,query,outputs)
    # Literal and register operands use the SAME word lanes.
    a=[A[i]+builder.gate('and',[code[90],code[42+i]],f'literal-A/{i}')for i in range(16)]
    b=[B[i]+builder.gate('and',[code[91],code[42+i]],f'literal-B/{i}')for i in range(16)]
    bank_metadata=[]
    # The same pending packet writes ONE bank per forward. RF copies consume
    # it first; arena banks consume it later, before any new packet is committed.
    bank_specs=[('heap',512,4,1,WordAction.HEAP_READ,WordAction.HEAP_WRITE,9),('stack',32,6,2,WordAction.FRAME_READ,WordAction.FRAME_WRITE,13),('constants',4,6,4,WordAction.DECLARATION_READ,None,14),('context',8,1,3,WordAction.CONTEXT_READ,WordAction.CONTEXT_WRITE,15)]
    for bank,cells,words,bank_id,reading,storing,start_layer in bank_specs:
        query=builder.gate('or',[builder.gate('and',[flags[reading],one-stage[0]],f'{bank}-load0')]+([flags[storing]]if storing is not None else[]),bank+'-query')
        width=cells.bit_length()-1
        for page in range(max(1,cells//128)):
            writing=builder.gate('and',[enable]+matches(kind,bank_id)+matches(address[7:width],page)+([boot]if bank=='constants'else[]),f'{bank}-write/{page}')
            q={r:select_form(matches(a[:min(7,width)],r)+matches(a[7:width],page)+[run,query])for r in range(min(128,cells))}
            k={r:select_form(matches(address[:min(7,width)],r))for r in range(min(128,cells))}
            data={0:A_REF*one,1:A_REF*one};data.update({i+2:A_BIT*payload[i]for i in range(words*16)})
            layer=module_start+start_layer+page
            g.head(f'arena.{bank}.{page}',q,k,data,0,{i+2:K*one for i in range(words*16)},[(i+2,128.)for i in range(words*16)],beta=writing,min_level=2*layer,into=D[:words*16])
            bank_metadata.append(dict(bank=bank,page=page,layer=layer,words=words))
    submode=builder.gate('or',[flags[WordAction.SUB],flags[WordAction.EQ_BRANCH],flags[WordAction.LT_BRANCH]],'subtract-mode')
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
    writing=builder.gate('or',[flags[o]for o in(WordAction.MOVE,WordAction.ADD,WordAction.SUB)],'word-write')
    arithmetic=builder.gate('or',[flags[WordAction.ADD],flags[WordAction.SUB]],'arithmetic')
    selected=[g.ffn([(1,a[i],flags[WordAction.MOVE]),(1,sum_bits[i],arithmetic)],name=f'word-value/{i}')for i in range(16)]
    active_core=builder.gate('and',[run,valid,writing],'active-core-write')
    active_load0=builder.gate('and',[run,valid,load0],'active-load0');active_load1=builder.gate('and',[run,valid,load1],'active-load1')
    active_store=builder.gate('and',[run,valid,store],'active-store')
    active_write=builder.gate('or',[active_core,active_load1,active_store],'active-write')
    field_flags=[builder.gate('and',matches(code[96:99],field),f'arena-field/{field}')for field in range(6)]
    loaded=[g.ffn([(1,D[16*field+i],field_flags[field])for field in range(6)],name='arena-word')for i in range(16)]
    next_result=[g.ffn([(1,selected[i],active_core),(1,loaded[i],active_load0),(1,result[i],one-active_core-active_load0)],name=f'result/{i}')for i in range(16)]
    rf_active=builder.gate('or',[active_core,active_load1],'active-rf')
    rf_value=[g.ffn([(1,selected[i],active_core),(1,result[i],active_load1)],name='rf-word')for i in range(16)]
    slot_flags=[builder.gate('and',matches(code[6:9],slot)+[rf_active],f'destination-slot/{slot}')for slot in range(7)]
    store_fields=[builder.gate('and',[field_flags[i],active_store],f'store-field/{i}')for i in range(6)]
    pending=[]
    for i,old in enumerate(D):
        if i<112:
            choose=slot_flags[i//16];memory=store_fields[i//16]if i<96 else Expr()
            value=g.ffn([(1,rf_value[i%16],choose),(1,b[i%16],memory),(1,old,one-choose-memory)],name='patched-row')
        else:value=old
        pending.append(value)
    failed_branch=builder.gate('or',[builder.gate('and',[flags[WordAction.EQ_BRANCH],one-equal],'eq-false'),builder.gate('and',[flags[WordAction.LT_BRANCH],one-less],'lt-false')],'branch-false')
    following=[g.ffn([(1,code[58+i],one-failed_branch),(1,code[74+i],failed_branch)],name='next-pc')for i in range(16)]
    known=builder.gate('or',list(flags.values()),'known-opcode')
    internal_fault=builder.gate('and',[run,builder.gate('or',[one-valid,one-known],'bad-control')],'internal-fault')
    ok=builder.gate('and',[run,valid,flags[WordAction.STOP_OK]],'stop-ok');bad=builder.gate('or',[internal_fault,builder.gate('and',[run,valid,flags[WordAction.STOP_INVALID]],'stop-invalid')],'stop-bad')
    stopping=builder.gate('or',[ok,bad],'stopping')
    next_status=[ok,bad]+[Expr()]*14
    status_values=[g.ffn([(1,next_status[i],stopping),(1,status[i],one-stopping)],name='status-next')for i in range(16)]
    reason_values=[g.ffn([(1,bad,stopping),(1,reason[0],one-stopping)],name='reason-next')]+reason[1:]
    advance=builder.gate('and',[run,one-load0],'advance-pc')
    next_pc=[g.ffn([(1,following[i],advance),(1,pc[i],one-advance)],name='pc-next')for i in range(16)]
    next_address=[g.ffn([(1,code[9+i],rf_active),(1,a[i],active_store)],name='write-address')for i in range(9)]
    next_kind=[builder.gate('or',[flags[op]for op in(WordAction.HEAP_WRITE,WordAction.CONTEXT_WRITE)if (1 if op==WordAction.HEAP_WRITE else 3)>>bit&1]+([flags[WordAction.FRAME_WRITE]]if 2>>bit&1 else[]),f'write-kind/{bit}')for bit in range(3)]
    next_stage=[active_load0]+[Expr()]*3
    targets=result+pc+status+reason+payload+address+[enable]+kind+stage
    values=next_result+next_pc+status_values+reason_values+pending+next_address+[active_write]+next_kind+next_stage
    # Bit-only updates have exact [-1,1] deltas. Commit after ALL old reads of
    # that feature, allowing independent columns to finish at different layers.
    last={d:0 for d in physical}
    for node in g.nodes:
        for d in reads(node):
            if d in last:last[d]=max(last[d],node.level)
    target_dims={next(iter(v.terms))for v in targets}
    for target,value in zip(targets,values):
        d=next(iter(target.terms))
        if (set(value.terms)&target_dims)-{d}:raise ValueError('prototype cross-column commit needs snapshot')
        g.ffn([(1,one,value),(-1,one,target)],name='bit-commit',into=target,min_level=max(last[d],2*module_start))
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
    config=Qwen3_5TextConfig(hidden_size=hidden,intermediate_size=intermediate,num_hidden_layers=layers,layer_types=['linear_attention']*layers,vocab_size=64,linear_key_head_dim=128,linear_value_head_dim=128,linear_num_key_heads=1,linear_num_value_heads=1,linear_conv_kernel_dim=4,num_attention_heads=1,num_key_value_heads=1,head_dim=2,hidden_act='silu',tie_word_embeddings=False,rope_parameters=dict(rope_type='default',rope_theta=10000000,partial_rotary_factor=1.,mrope_section=[1,0,0],mrope_interleaved=True))
    prior=torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.bfloat16)
        with torch.device(device),no_init_weights():model=Qwen3_5ForCausalLM(config)
    finally:torch.set_default_dtype(prior)
    with torch.no_grad():
        for p in model.parameters():p.zero_()
        for layer in model.model.layers:
            layer.linear_attn.dt_bias.fill_(-110.);layer.linear_attn.norm.weight.fill_(1.)
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
        persistent=set(sum((fixed.groups[n]for n in('pc','status','reason','result','stage','pending_payload','pending_row','pending_enable','pending_kind')),[]))
        clear=[slot for slot in range(12,hidden)if slot not in persistent]
        for index,slot in enumerate(clear):
            layer=body+index//intermediate;unit=index%intermediate;mlp=model.model.layers[layer].mlp
            row(one,layout,mlp.gate_proj.weight[unit],128.)
            mlp.up_proj.weight[unit,slot]=1/(128*layout.scale);mlp.down_proj.weight[slot,unit]=-1.
        model.model.norm.weight.fill_(-1.)
        for i,slot in enumerate(sum((fixed.groups[n]for n in('pc','status','reason','result')),[])):
            model.model.norm.weight[slot]=1/layout.scale;model.lm_head.weight[i,slot]=1.
    model.requires_grad_(False);model.eval()
    params=sum(p.numel()for p in model.parameters());expected=layers*(3*hidden*intermediate+644*hidden+1666)+129*hidden
    if params!=expected:raise ValueError('stock dense parameter accounting changed')
    report=dict(format='leanputer.stock-shared-module.v1',logical_dense_parameters=params,hidden=hidden,intermediate=intermediate,layers=layers,rom_records=len(records),rom_layers=rom_layers,rom_layout=rom_layout,rom_decode_layers=decode_layers,active_rf_heads=9,arena_heads=bank_metadata,rf_ports=3,rf_rows_per_copy=384,rf_payload_bits=126,allocated_channels=high,features=fixed.next-13,operator_scratch_channels=high-fixed.next,graph_layers=g.n_layers(),module_layer_budget=datapath_layers,parameter_storage='dense',stock_class=type(model).__module__+'.'+type(model).__name__,full_source_checker=False,native_actions=[a.name for a in WordAction])
    return StockDatapath(model,fixed,layout,report)
