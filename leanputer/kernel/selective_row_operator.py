"""Shared checker RF gather: select one word per page with stock GDN gating.

Three independently addressed replicas read twelve words in one forward.
Rows, word lanes and payloads are DATA. There is no host-side read or dispatch.
This module is a hardware primitive, not a whole-source checker.
"""
import torch
from ..native_machine import NativeBuilder
from ..native_vendor.qwenputer.expr import Expr
from ..native_vendor.qwenputer.ir import K,A_REF,A_BIT
from .stock_datapath import FixedSlots
from .operator_emitter import emit_operator


def emit_selective_reads(builder,payload,key,write_enable,queries,outputs,write_page=None):
    """Emit identical writes and independent model-owned read selectors.

    Each query is (row7, page_lanes4x3, enabled). Every value head stores seven
    whole words; its gated norm selects one of those lanes before the fixed
    output projection sums matching bit columns. Lane7 has no match (zero).
    """
    graph=builder.graph;one=graph.one;layers=[]
    def matches(bits,value):return[bit if value>>i&1 else one-bit for i,bit in enumerate(bits)]
    def form(values):return K*(2*(sum(values,Expr())-(len(values)-1)*one)-one)
    keys={i:form(matches(key,i))for i in range(128)}
    page_enables=[write_enable if write_page is None else builder.gate('and',[write_enable]+matches(write_page,page),'rf-write-page')for page in range(4)]
    for port,((address,selectors,enabled),destination)in enumerate(zip(queries,outputs)):
        q={i:form(matches(address,i)+[enabled])for i in range(128)}
        heads=[]
        for page in range(4):
            values={0:A_REF*one,1:A_REF*one}
            values.update({2+i:A_BIT*payload[(page*112 if write_page is None else 0)+i]for i in range(112)})
            z={2+16*lane+bit:K*(sum(matches(selectors[page],lane),Expr())-2*one)
               for lane in range(7)for bit in range(16)}
            into=[destination[page*16+bit]for lane in range(7)for bit in range(16)]
            heads.append(dict(v=values,a=0,z=z,outs=[(2+i,128.)for i in range(112)],
                              beta=page_enables[page],into=into))
        head=heads[0]
        graph.head(f'checker.rf.selective.{port}',q,keys,head['v'],0,head['z'],head['outs'],
                   beta=head['beta'],into=head['into'],vx=heads[1:],min_level=builder.barrier)
        layers.append(graph.nodes[-1].level//2)
    return tuple(layers)


def build_selective_probe(device='cpu',plan_only=False,paged_writes=False,ports=3):
    if ports not in(3,4):raise ValueError('bounded selective RF port count')
    hidden,intermediate=(1024 if paged_writes else 1536),128;torch.set_num_threads(1)
    builder=NativeBuilder(intermediate=intermediate,reset_layers=0)
    builder.graph.target.value_heads=4;builder.graph.target.intermediate=intermediate-24
    slots=FixedSlots(hidden//64+1);physical={}
    def feature(name,width):
        positions=slots.add(name,width);values=[builder.feature(f'{name}/{i}')for i in range(width)]
        physical.update((next(iter(value.terms)),position)for value,position in zip(values,positions))
        return values
    payload=feature('pending',112 if paged_writes else 448);key=feature('pending_row',7);enabled=feature('pending_enable',1)[0]
    write_page=feature('pending_page',2)if paged_writes else None
    queries=[];outputs=[]
    for port in range(ports):
        address=feature(f'row/{port}',7);lanes=feature(f'lanes/{port}',12)
        query_enabled=feature(f'enabled/{port}',1)[0];output=feature(f'output/{port}',64)
        queries.append((address,[lanes[3*i:3*i+3]for i in range(4)],query_enabled));outputs.append(output)
    # Identity feedback may contain the preceding read; clear it before heads.
    for output in outputs:
        for target in output:builder.graph.ffn([(-1,target,builder.graph.one)],name='readout-clear',into=target)
    builder.barrier=2*builder.graph.n_layers()
    layers=emit_selective_reads(builder,payload,key,enabled,queries,outputs,write_page=write_page)
    report=dict(format='leanputer.selective-rf-operator.v1',stock_operator_probe=True,
                row_capacity=128,row_words=28,replicas=ports,selected_words_per_forward=4*ports,
                memory_layers=layers,one_forward_per_gather=True,stock_speed_measured=False)
    report.update(paged_writes=paged_writes,pending_payload_bits=len(payload),
                  independent_write_page_beta=paged_writes)
    return emit_operator(builder,slots,physical,outputs[0],hidden=hidden,intermediate=intermediate,
                         report=report,device=device,plan_only=plan_only)
