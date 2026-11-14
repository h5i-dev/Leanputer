"""Shared dependent IR lowered to stock Qwen3.5 GatedDeltaNet/SwiGLU.

Bring-up implementation; broad differential validation is deliberately pending.
The host supplies syntax-only boot records, then performs fixed stock forwards
with identity hidden-state feedback and the stock cache. No host checker rules.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import time
import resource

import torch

from .bitvec import pack_words
from .dependent import Exhausted, Unsupported
from .machine_spec import MachineConfig, Outcome, Reason, prepare
from .native import emit_stock, plan_stock, ScratchResetCapacity
from .native_vendor.qwenputer.expr import Expr
from .native_vendor.qwenputer.ir import Graph, Target, Head, FFN, K, A_BIT, A_REF
from .native_vendor.qwenputer.emit import reads
from .runner import parse_document
from .primitives import PRIMITIVE_CODES
from .state_layout import StateLayout, RegisterLayout
from .transition import compile_addresses, RuleCompiler


class NativeBuilder:
    def __init__(self, intermediate=1024, reset_layers=4, layout_policy='compact'):
        # A reused residual slot needs an extra SwiGLU subtraction unit. Filling
        # every row with logic prevents handovers and needlessly grows global H.
        gate_units=intermediate if layout_policy=='legacy' else intermediate//2
        self.graph = Graph(Target(key_heads=1, value_heads=1, intermediate=gate_units))
        self.barrier = 2*reset_layers
        self.layout_policy=layout_policy

    def feature(self, name): return self.graph.token_feature(name, lambda token:0)

    def gate(self, operation, values, name):
        total = sum(values, Expr())
        one = self.graph.one
        if not values and operation in('and','or'):return one if operation=='and'else Expr()
        if operation=='not' and self.layout_policy=='compact':return one-total
        if operation=='or' and self.layout_policy=='compact':
            # On Boolean inputs OR = 1 - relu(1 - sum(inputs)). One exact
            # SwiGLU unit suffices; the complement is a free linear form.
            return one-self.graph.ffn([(1,one,one-total)],name=name,min_level=self.barrier)
        if operation == 'not': terms = [(1, one, one-total)]
        elif operation == 'and': terms = [(1, one, total+1-len(values))]
        else: terms = [(1, one, total),(-1, one, total-1)]
        return self.graph.ffn(terms, name=name, min_level=self.barrier)

    def circuit(self, plan, inputs, name):
        circuit, outputs = plan
        from .control_packing import PackedBit
        memo={}
        class Values(dict):
            def __getitem__(self,key):
                value=super().__getitem__(key)
                if isinstance(value,PackedBit):value=value.realize(self_builder,memo);self[key]=value
                return value
        self_builder=self
        values = Values(enumerate(inputs))
        needed = set(outputs); live = []
        for gate in reversed(circuit.gates):
            if gate[0] in needed: needed.update(gate[2]); live.append(gate)
        for wire, operation, operands in reversed(live):
            values[wire] = self.gate(operation, [values[i] for i in operands], f'{name}/{wire}')
        return [values[i] for i in outputs]

    def onehot(self, bits, enabled, cells, name):
        return [self.gate('and', [enabled]+[bit if row >> i & 1 else self.graph.one-bit
                                           for i,bit in enumerate(bits)], f'{name}/{row}') for row in range(cells)]


def banked_native_read(builder, cells, query, address, enable, values, name,
                       bank, head_metadata, bank_layout='separate'):
    """Compile mutually exclusive RAM banks using stock residual projections.

    Accumulated outputs are shared IR dimensions, so allocation retains them
    across all contributing heads. Prefix reset clears them on every token;
    this helper does not introduce a runtime reduction or alter the cache.
    """
    graph=builder.graph;width=len(values)
    select=lambda expression:K*(2*expression-graph.one)
    low=min(7,cells.bit_length()-1)
    parts=[];accumulated=None
    for part in range(max(1,cells//128)):
        named=f'{name}/bank{part}'
        def matches(bits):
            return [bit if part>>i&1 else graph.one-bit for i,bit in enumerate(bits)]
        writing=builder.gate('and',[enable]+matches(address[low:]),named+'/write')
        querying=builder.gate('and',matches(query[low:]),named+'/query-bank')
        keys=builder.onehot(address[:low],writing,min(cells,128),named+'/key')
        queries=builder.onehot(query[:low],querying,min(cells,128),named+'/query')
        data={i+2:A_BIT*value for i,value in enumerate(values)}
        data.update({0:A_REF*writing,1:A_REF*writing})
        outputs=graph.head(named,{i:select(value)for i,value in enumerate(queries)},
            {i:select(value)for i,value in enumerate(keys)},data,0,
            {i+2:K*graph.one for i in range(width)},[(i+2,2.**7)for i in range(width)],
            min_level=builder.barrier,into=accumulated if bank_layout=='accumulate' else None)
        head_metadata.append(dict(name=named,bank=bank,row_bank=part,layer=(graph.nodes[-1].level-1)//2))
        parts.append(outputs);accumulated=outputs
        builder.barrier=graph.nodes[-1].level
    # Exactly one bank query is active. Prefix reset clears these scratch slots
    # before each transition, so residual accumulation computes the same sum.
    if bank_layout=='accumulate':
        return accumulated
    return [sum((part[i]for part in parts),Expr())for i in range(width)]


def commit_native_outputs(builder,features,outputs):
    """Commit a fixed circuit without copying already materialized gate values.

    Only expressions reading a mutable input feature need a snapshot. Other
    expressions read immutable intermediate dimensions computed before this
    barrier. Unchanged features need no write. This is whole-circuit dependency
    analysis, independent of input proofs or the runtime active kernel task.
    """
    graph=builder.graph
    mutable={next(iter(feature.terms))for feature in features}
    unchanged=[value.terms==feature.terms for feature,value in zip(features,outputs)]
    values=list(outputs);snapshots=0
    barrier=max((node.level for node in graph.nodes),default=0)+2
    for index,value in enumerate(outputs):
        if not unchanged[index]and mutable.intersection(value.terms):
            values[index]=graph.ffn([(1,graph.one,value)],name=f'snapshot/{index}',min_level=barrier);snapshots+=1
    last_read={d:0 for d in mutable}
    for node in graph.nodes:
        for d in reads(node):
            if d in last_read:last_read[d]=max(last_read[d],node.level)
    for index,(feature,value)in enumerate(zip(features,values)):
        if not unchanged[index]:
            dimension=next(iter(feature.terms))
            barrier=max(last_read[dimension],graph.level(value))+1
            graph.ffn([(1,graph.one,value),(-1,graph.one,feature)],name=f'commit/{index}',into=feature,min_level=barrier)
    return dict(output_channels=len(outputs),snapshots=snapshots,unchanged=sum(unchanged),direct_commits=len(outputs)-snapshots-sum(unchanged))


def validate_native_schedule(graph):
    """Check read/write dependencies after compiler-only channel scheduling."""
    writers={}
    for index,node in enumerate(graph.nodes):
        dimensions=[node.out] if isinstance(node,FFN) else [d for vh in node.vheads()for _,d,_ in vh.out]
        for dimension in dimensions:writers.setdefault(dimension,[]).append(index)
    for index,node in enumerate(graph.nodes):
        for dimension in reads(node):
            previous=[w for w in writers.get(dimension,[])if w<index]
            following=[w for w in writers.get(dimension,[])if w>index]
            if previous and max(graph.nodes[w].level for w in previous)>=node.level:
                raise ValueError('native schedule reads before a preceding write: '+node.name)
            if following and min(graph.nodes[w].level for w in following)<node.level:
                raise ValueError('native schedule reads after a following overwrite: '+node.name)


@dataclass
class NativeMachine:
    model: object
    layout: object
    state_layout: object
    register_layout: object
    feature_slots: list
    config: MachineConfig
    offsets: dict
    native_heads: list
    layout_policy: str='legacy'
    layout_statistics: object=None
    bank_layout: str='accumulate'
    max_ballast: int=64
    program: object=None
    control_packing: object=None

    def embeddings(self, features):
        parameter = next(self.model.parameters())
        result = torch.zeros((*features.shape[:2],self.layout.hidden), device=parameter.device, dtype=parameter.dtype)
        result[:,:,:self.layout.m] = self.layout.ballast
        result[:,:,self.feature_slots] = features.to(result.device,result.dtype)
        return result

    def check(self, documents, diagnostic_steps=None, diagnostic_cache=False, *, early_stop=False, halt_interval=8):
        if not documents: raise ValueError('nonempty document batch required')
        if type(halt_interval)is not int or halt_interval<1: raise ValueError('positive halt interval required')
        parser=self.program.parse_document if self.program else parse_document
        encoder=self.program.prepare if self.program else prepare
        get_assumptions=self.program.assumptions if self.program else lambda ds:[d.name for d in ds if d.value is None]
        assumptions_from_state=getattr(self.program, 'assumptions_from_state', None) if self.program else None
        admitted_from_state=getattr(self.program,'admitted_declarations_from_state',None) if self.program else None
        outcome_class=self.program.Outcome if self.program else Outcome
        reason_class=self.program.Reason if self.program else Reason
        parsed = [parser(document) for document in documents]
        states = [encoder(self.config,*judgment) for judgment in parsed]
        logical_width=self.register_layout.width
        packing=self.control_packing
        control_width=packing.width if packing else logical_width
        def encoded_control(state):
            bits=self.state_layout.encode(state)[0,:logical_width]
            return packing.encode(bits)if packing else bits
        # Static syntax load. Equal capacities give every item the same boot length.
        boot = []
        boot_length = (self.program.boot_length if self.program and hasattr(self.program, 'boot_length') else
                       lambda bank, state: state['regs']['free'] if bank == 'heap' else
                       state['regs']['decl_count'] if bank == 'constants' else 0)
        for bank in ('heap','stack','context','constants'):
            for row in range(max(boot_length(bank, state) for state in states)):
                packet = torch.zeros(len(states),len(self.feature_slots))
                for index,state in enumerate(states):
                    packet[index,:control_width] = encoded_control(state)
                    packet[index,self.offsets['boot/'+bank]] = float(row < boot_length(bank, state))
                    for bit in range(self.offsets['address_width']):
                        packet[index,self.offsets['boot/address']+bit] = float(bool(row & (1 << bit)))
                    fields = state[bank][row]
                    values = pack_words(fields,[self.config.word_bits]*len(fields))
                    packet[index,self.offsets['boot/payload']:self.offsets['boot/payload']+len(values)] = torch.tensor(values)
                boot.append(packet)
        initial = torch.zeros(len(states),1,len(self.feature_slots))
        for index,state in enumerate(states): initial[index,0,:control_width] = encoded_control(state)
        device = next(self.model.parameters()).device
        if device.type=='cuda': torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction=False
        if device.type=='cuda': torch.cuda.synchronize()
        if device.type=='cuda': torch.cuda.reset_peak_memory_stats(device)
        started = time.perf_counter()
        context=torch.no_grad if getattr(self.model,'_leanputer_weight_storage','dense')=='sparse_csr'else torch.inference_mode
        with context():
            loaded = self.model(inputs_embeds=self.embeddings(torch.stack(boot,dim=1)), use_cache=True)
            state = self.embeddings(initial)
            cache = loaded.past_key_values
            applied_steps=0;flush_after=None
            status_slice=(packing.slices if packing else self.register_layout.slices)['status']
            for step in range(diagnostic_steps or self.config.fuel+2):
                output = self.model(inputs_embeds=state, past_key_values=cache,
                                    use_cache=True,output_hidden_states=True)
                cache = output.past_key_values
                state = output.hidden_states[-2]  # identity wire; no interpretation/update
                applied_steps=step+1
                if flush_after is not None and applied_steps>=flush_after:break
                if early_stop and not diagnostic_steps and flush_after is None and applied_steps%halt_interval==0:
                    # Only observe the MODEL completion signal, not proof syntax
                    # or a host checker. One more stock forward flushes pending writes.
                    status_bits=output.logits[:,0,status_slice]
                    if bool(torch.all(torch.any(status_bits!=0,dim=-1))):flush_after=applied_steps+1
                if diagnostic_steps:
                    raw = state[:,0,self.feature_slots].float().cpu()
                    values = output.logits[:,0,:].float().cpu()
                    values=(packing.decode(values)if packing else values)[0]
                    decoded = {name:sum(int(values[s.start+i]) << i for i in range(s.stop-s.start))
                               for name,s in self.register_layout.slices.items()}
                    memory = cache.layers[self.native_heads[0]['layer']].recurrent_states[0]
                    print(json.dumps(dict(step=step+1, regs=decoded,
                                          pending=raw[0,control_width:control_width+30].tolist(),
                                          heap5=memory[0,0,5,2:26].float().cpu().tolist())),flush=True)
        if device.type=='cuda': torch.cuda.synchronize()
        bits = output.logits[:,0,:].float().cpu()
        if packing:bits=packing.decode(bits)
        if not torch.all((bits==0)|(bits==1)):
            raise ValueError('native control left Boolean domain; no rounding permitted')
        registers = []
        for row in bits.tolist():
            registers.append({name:sum(int(row[s.start+i]) << i for i in range(s.stop-s.start))
                              for name,s in self.register_layout.slices.items()})
        results = [dict(name=document.get('name',str(index)),status=('UNSUPPORTED'if self.program and r['reason']==self.program.Reason.UNSUPPORTED_DECLARATION else outcome_class(r['status']).name),
                        reason=reason_class(r['reason']).name,
                        assumptions=(assumptions_from_state(judgment[2],r) if assumptions_from_state else get_assumptions(judgment[2])),
                        input_axiom_candidates=get_assumptions(judgment[2]),
                        environment_declarations=len(judgment[2]),admitted_declarations=(admitted_from_state(r) if admitted_from_state else r['decl']),input_heap_nodes=initial_state['regs']['free']-1,
                        allocated_heap_nodes=r['free']-1,
                        semantic_steps=self.config.fuel-r['fuel']+int(r['reason']==reason_class.FUEL))
                   for index,(document,judgment,initial_state,r) in enumerate(zip(documents,parsed,states,registers))]
        report = dict(registers=registers,results=results,forward_seconds=time.perf_counter()-started,
                    layout_policy=self.layout_policy,layout_statistics=self.layout_statistics,
                    bank_layout=self.bank_layout,
                    max_ballast=self.max_ballast,ballast_channels=self.layout.m,
                    primitive_basis=list(self.program.primitive_basis)if self.program else list(PRIMITIVE_CODES),
                    semantic_program=self.program.program_name if self.program else 'historical.per-name-catalog',
                    stock_class=type(self.model).__module__+'.'+type(self.model).__name__,
                    parameters=sum(p.numel() for p in self.model.parameters()),
                    weight_bytes=sum(p.numel()*p.element_size() for p in self.model.parameters()),
                    cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(device) if device.type=='cuda' else None,
                    host_process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                    hidden_size=self.layout.hidden,native_layers=self.model.config.num_hidden_layers,
                    boot_tokens=len(boot),applied_steps=applied_steps,early_stop=early_stop and not bool(diagnostic_steps),
                    halt_interval=halt_interval,completion_flush_forwards=1 if flush_after is not None and applied_steps>=flush_after else 0)
        report.update(parameter_storage(self.model),packed_control=bool(self.control_packing),
                      control_digit_bits=self.control_packing.digit_bits if self.control_packing else None)
        if diagnostic_cache:
            # Development evidence only. Never consulted to decide the result
            # or provide a semantic answer to a subsequent inference token.
            report['diagnostic_cache'] = cache
        return report


def compile_native_machine(config=MachineConfig(heap=32,stack=8,context=4,constants=2,fuel=128),
                           intermediate=1024, reset_layers=4, device='cpu', dtype=torch.bfloat16,
                           layout_policy='compact',plan_only=False,bank_layout='accumulate',max_ballast=64,program=None,pack_control=False,weight_storage='dense',control_digit_bits=2):
    if layout_policy not in ('compact','legacy'):raise ValueError('unknown native layout policy')
    if bank_layout not in ('separate','accumulate'):raise ValueError('unknown native bank layout')
    if type(intermediate)is not int or intermediate<4:raise ValueError('native FFN width must be >=4')
    if type(reset_layers)is not int or reset_layers<1:raise ValueError('recurrent native execution requires scratch reset layers')
    if 6*config.word_bits+2>128:
        raise ValueError('native RAM stack payload exceeds the 128-dimensional value head (word width must be <=21)')
    state_layout = (program.StateLayout if program else StateLayout)(config)
    registers = (program.RegisterLayout if program else RegisterLayout)(state_layout)
    address_compiler=program.compile_addresses if program else compile_addresses
    rule_compiler=program.RuleCompiler if program else RuleCompiler
    constants_width=program.constant_fields if program else 3
    builder = NativeBuilder(intermediate,reset_layers,layout_policy); graph = builder.graph
    from .control_packing import ControlPacking
    packing=ControlPacking(registers,control_digit_bits)if pack_control else None
    if packing:features,control=packing.features(builder)
    else:features=[builder.feature(name)for name in registers.names];control=list(features)
    pending = {}
    for bank,fields,reg in [('heap',4,'free'),('stack',6,'sp'),('context',1,'ctx')]:
        address_width = getattr(config,bank).bit_length()-1
        address = [builder.feature(f'pending/{bank}/address/{i}') for i in range(address_width)]
        enable = builder.feature(f'pending/{bank}/enable')
        payload = [builder.feature(f'pending/{bank}/payload/{i}') for i in range(fields*config.word_bits)]
        pending[bank] = (address,enable,payload)
        features.extend(address+[enable]+payload)
    offsets = {}
    boot_banks = {}
    for bank in ('heap','stack','context','constants'):
        offsets['boot/'+bank] = len(features)
        boot_banks[bank] = builder.feature('boot/'+bank); features.append(boot_banks[bank])
    address_width = max(config.heap,config.stack,config.context,config.constants).bit_length()-1
    offsets.update(address_width=address_width, **{'boot/address':len(features)})
    boot_address = [builder.feature(f'boot/address/{i}') for i in range(address_width)]; features.extend(boot_address)
    offsets['boot/payload'] = len(features)
    boot_payload = [builder.feature(f'boot/payload/{i}') for i in range(6*config.word_bits)]; features.extend(boot_payload)
    head_metadata = []

    def read(bank,query,name):
        saved_barrier = builder.barrier
        # Produce one-hot arrays shortly before their consuming native head,
        # rather than keeping every port's arrays live across all read rounds.
        builder.barrier = max(builder.barrier, max((node.level for node in graph.nodes if isinstance(node,Head)),default=0))
        cells = getattr(config,bank); width = {'heap':4,'stack':6,'context':1,'constants':constants_width}[bank]*config.word_bits
        boot = boot_banks[bank]
        paddr,penable,payload = pending.get(bank,([Expr()]*address_width,Expr(),[Expr()]*width))
        addr = [builder.gate('or',[builder.gate('and',[boot,a],name+'/ba'),
                                  builder.gate('and',[penable,b],name+'/pa')],name+'/wa')
                for a,b in zip(boot_address,paddr)]
        enable = builder.gate('or',[boot,penable],name+'/write')
        values = [builder.gate('or',[builder.gate('and',[boot,a],name+'/bv'),
                                    builder.gate('and',[penable,b],name+'/pv')],name+'/wv')
                  for a,b in zip(boot_payload[:width],payload)]
        outputs=banked_native_read(builder,cells,query,addr,enable,values,name,bank,head_metadata,bank_layout)
        builder.barrier = saved_barrier
        return outputs

    collect = lambda circuit,outputs:(circuit,outputs)
    address1,address2 = address_compiler(registers,target=collect)
    addresses = builder.circuit(address1,control,'address1')
    first = []; offset = 0
    first_banks = program.first_banks if program and hasattr(program, 'first_banks') else [('heap',4),('stack',1),('constants',1)]
    for bank,ports in first_banks:
        bits = getattr(config,bank).bit_length()-1
        for port in range(ports):
            first.extend(read(bank,addresses[offset:offset+bits],f'read/{bank}/{port}')); offset += bits
    if offset != len(addresses):
        raise ValueError('program first read address ABI differs')
    second = builder.circuit(address2,control+first,'address2')
    ctxbits = config.context.bit_length()-1
    if program:
        all_reads=list(first);offset=0
        for index,bank in enumerate(program.second_banks):
            bits=getattr(config,bank).bit_length()-1
            all_reads.extend(read(bank,second[offset:offset+bits],f'read/second/{index}/{bank}'));offset+=bits
        if offset!=len(second):raise ValueError('program read address ABI differs')
    else:all_reads = first+read('context',second[:ctxbits],'read/context')+read('constants',second[ctxbits:],'read/constant')
    options=dict(factor_choices=layout_policy=='compact')
    if packing:options['packed_outputs']=True
    plan=rule_compiler(registers,**options).finish('attention_delta',target=collect)
    if packing:
        from .control_packing import packed_update_outputs
        outputs=packed_update_outputs(builder,plan,control+all_reads,features[:packing.width],registers.width,packing.digit_bits)
    else:outputs=builder.circuit(plan,control+all_reads,'transition')
    update_features = features[:packing.width]if packing else control
    update_features = update_features+sum((address+[enable]+payload for address,enable,payload in pending.values()),[])
    if len(outputs)!=len(update_features): raise ValueError('native controller output ABI differs')
    commit_statistics=commit_native_outputs(builder,update_features,outputs)
    validate_native_schedule(graph)
    dimensions = [next(iter(expression.terms))for expression in (features[:packing.width]if packing else control)]
    keep = {next(iter(expression.terms))for expression in features}
    required_reset = None
    try:
        if plan_only:
            layout,allocation,tc,clear=plan_stock(graph,dimensions,intermediate,keep,reset_layers,max_ballast)
            return dict(graph=graph,layout=layout,allocation=allocation,stock_config=tc,reset_layers=reset_layers,
                        persistent_channels=len(keep),clear_channels=len(clear),commit_statistics=commit_statistics,packed_control=bool(packing),control_digit_bits=packing.digit_bits if packing else None,layout_policy=layout_policy,bank_layout=bank_layout,max_ballast=max_ballast)
        model,layout,allocation = emit_stock(graph,dimensions,intermediate,dtype,device,keep,reset_layers,max_ballast,weight_storage)
    except ScratchResetCapacity as error:
        required_reset = error.required
    if required_reset is not None:
        return compile_native_machine(config,intermediate,required_reset,device,dtype,layout_policy,plan_only,bank_layout,max_ballast,program,pack_control,weight_storage,control_digit_bits)
    slots = [layout.dim(next(iter(expression.terms)))for expression in features]
    stats=dict(allocated_slots=allocation.n_slots,persistent_channels=len(keep),
               subtract_handovers=len(allocation.subtract),head_clears=sum(map(len,allocation.clears.values())),
               logic_units_per_layer=graph.target.intermediate,reset_layers=reset_layers,graph=graph.stats(),commit_statistics=commit_statistics)
    return NativeMachine(model,layout,state_layout,registers,slots,config,offsets,head_metadata,layout_policy,stats,bank_layout,max_ballast,program,packing)


def parameter_storage(model):
    """Physical tensor storage accounting, distinct from logical parameter count."""
    logical=stored=nonzero=0
    for parameter in model.parameters():
        logical+=parameter.numel()
        if parameter.layout==torch.sparse_csr:
            nonzero+=parameter.values().numel()
            stored+=sum(t.numel()*t.element_size()for t in(parameter.values(),parameter.crow_indices(),parameter.col_indices()))
        else:stored+=parameter.numel()*parameter.element_size();nonzero+=int(torch.count_nonzero(parameter))
    return dict(logical_parameters=logical,stored_weight_bytes=stored,stored_nonzero_values=nonzero,weight_storage=getattr(model,'_leanputer_weight_storage','dense'),small_model_target_met=False)


def check_documents(machine, documents, batch_size=4):
    """Retain incomplete/malformed rows; only syntax-capable rows enter weights."""
    if batch_size<1: raise ValueError('positive batch size required')
    results=[];pending=[];positions=[];batches=[]
    for index,document in enumerate(documents):
        name=document.get('name',str(index)) if isinstance(document,dict) else str(index)
        result=dict(name=name,environment_declarations=None,assumptions=None,input_heap_nodes=None)
        results.append(result)
        if isinstance(document,dict) and document.get('format')=='leanputer.dependent.v1' and document.get('status')=='UNSUPPORTED':
            result.update(status='UNSUPPORTED',reason=document.get('reason','unsupported preparation input'))
            continue
        try:
            # Encoding only: no type checking or semantic-step planning.
            judgment=parse_document(document)
            result.update(environment_declarations=len(judgment[2]),
                          assumptions=[d.name for d in judgment[2]if d.value is None])
            initial_state=prepare(machine.config,*judgment)
            result['input_heap_nodes']=initial_state['regs']['free']-1
        except Unsupported as error: result.update(status='UNSUPPORTED',reason=str(error))
        except Exhausted as error: result.update(status='RESOURCE',reason=str(error))
        except (ValueError,TypeError,KeyError,RecursionError) as error: result.update(status='MALFORMED',reason=str(error))
        else: pending.append(document);positions.append(index)
    for start in range(0,len(pending),batch_size):
        batch=machine.check(pending[start:start+batch_size])
        for position,result in zip(positions[start:start+batch_size],batch.pop('results')):
            results[position].update(result)
        # Register dumps are development diagnostics, not proof certificates.
        batch.pop('registers');batch['input_positions']=positions[start:start+batch_size]
        batches.append(batch)
    return dict(format='leanputer.native-report.v1',results=results,counts=dict(Counter(r['status']for r in results)),
                config=asdict(machine.config),batches=batches,parameters=sum(p.numel()for p in machine.model.parameters()),
                weight_bytes=sum(p.numel()*p.element_size()for p in machine.model.parameters()),
                primitive_basis=list(PRIMITIVE_CODES),
                validation_scope='Experimental native backend; broad differential validation pending')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True,help='dependent JSON document, array or JSONL corpus')
    parser.add_argument('--config',type=Path,help='fixed MachineConfig capacities and fuel')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--device',choices=('cpu','cuda'),default='cpu')
    parser.add_argument('--batch-size',type=int,default=4)
    parser.add_argument('--intermediate',type=int,default=1024)
    parser.add_argument('--layout',choices=('compact','legacy'),default='compact')
    parser.add_argument('--bank-layout',choices=('separate','accumulate'),default='accumulate')
    parser.add_argument('--max-ballast',type=int,default=64,help='layout search bound; normalizations retain a power-of-four ratio')
    args=parser.parse_args(argv)
    torch.set_num_threads(1)
    try:
        if args.batch_size<1 or args.intermediate<128: raise ValueError('positive batch size and intermediate>=128 required')
        if args.device=='cuda' and not torch.cuda.is_available(): raise ValueError('CUDA unavailable')
        config=MachineConfig(**json.loads(args.config.read_text())) if args.config else MachineConfig()
        content=args.input.read_text()
        try:
            parsed=json.loads(content);documents=parsed if isinstance(parsed,list) else [parsed]
        except json.JSONDecodeError: documents=[json.loads(line)for line in content.splitlines()if line.strip()]
        started=time.perf_counter()
        machine=compile_native_machine(config,intermediate=args.intermediate,device=args.device,layout_policy=args.layout,bank_layout=args.bank_layout,max_ballast=args.max_ballast)
        compilation=time.perf_counter()-started
        report=check_documents(machine,documents,args.batch_size)
        report.update(compile_seconds=compilation,device=args.device,hidden_size=machine.layout.hidden,
                      native_layers=machine.model.config.num_hidden_layers,intermediate_size=args.intermediate)
        output=json.dumps(report,indent=2)+'\n'
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(output)
        else: print(output,end='')
        statuses={r['status']for r in report['results']}
        return 1 if 'REJECT'in statuses else 2 if statuses-{'ACCEPT'} else 0
    except (ValueError,TypeError,KeyError,OSError,RecursionError) as error: parser.error(str(error))


if __name__=='__main__': raise SystemExit(main())
