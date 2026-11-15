"""Compile physical memory pages into stock shared-key GDN value heads.

This changes memory layout only. All logical rows, read/write values and bank
permissions are retained. No inference host reads or dispatch are involved.
"""
from ..native_vendor.qwenputer.expr import Expr
from ..native_vendor.qwenputer.ir import K,A_REF,A_BIT


def grouped_rf(builder,port,query,outputs,write_flags,address,payload,run,literal,suppress,layer,metadata,packed=None):
    g=builder.graph;one=g.one
    def matches(bits,value):return[b if value>>i&1 else one-b for i,b in enumerate(bits)]
    def form(values):return K*(2*(sum(values,Expr())-(len(values)-1)*one)-one)
    q={r:form(matches(query[3:10],r)+[run,one-literal]+([one-suppress]if port==2 else[]))for r in range(128)}
    k={r:form(matches(address[:7],r))for r in range(128)}
    values={0:A_REF*one,1:A_REF*one};values.update({i+2:A_BIT*v for i,v in enumerate(payload)})
    pages=[]
    for page in range(4):
        z={};outs=[];into=[]
        if port<2:
            for slot in range(7):
                if packed is None:
                    gate=K*(sum(matches(query[:3],slot)+matches(query[10:12],page),Expr())-4*one);weight=128.
                else:
                    normal=builder.gate('and',matches(query[:3],slot)+matches(query[10:12],page)+[one-packed],'rf-word-read')
                    vector=builder.gate('and',matches(query[10:12],page)+[packed],'rf-triplet-read')if slot<3 else Expr()
                    gate=(K*64//2**slot)*normal+(K*64)*vector;weight=2.**(slot+1)
                for bit in range(16):
                    column=2+16*slot+bit;z[column]=gate;outs.append((column,weight));into.append(outputs[bit])
        else:
            gate=K*(sum(matches(query[10:12],page),Expr())-one)
            z={i+2:gate for i in range(126)};outs=[(i+2,128.)for i in range(126)];into=list(outputs)
        pages.append(dict(v=values,a=0,z=z,outs=outs,beta=write_flags[page],into=into))
    first=pages[0]
    g.head(f'rf.group.{port}',q,k,first['v'],0,first['z'],first['outs'],beta=first['beta'],into=first['into'],min_level=2*layer,vx=pages[1:])
    actual=g.nodes[-1].level//2
    for page in range(4):metadata.append(dict(port=port,page=page,layer=actual,value_head=page))


def grouped_arenas(builder,a,address,payload,enable,kind,boot,run,stage,flags,D,start,metadata,O):
    g=builder.graph;one=g.one
    def matches(bits,value):return[b if value>>i&1 else one-b for i,b in enumerate(bits)]
    def form(values):return K*(2*(sum(values,Expr())-(len(values)-1)*one)-one)
    def query(read,row,write):
        return builder.gate('and',[flags[read]+flags[row],one-stage[0]],'bank-load')+(flags[write]if write is not None else Expr())
    specs=[('heap',512,4,1,O.HEAP_READ,O.HEAP_ROW_READ,O.HEAP_WRITE),('stack',32,6,2,O.FRAME_READ,O.FRAME_ROW_READ,O.FRAME_WRITE),('constants',4,6,4,O.DECLARATION_READ,O.DECLARATION_ROW_READ,None),('context',8,1,3,O.CONTEXT_READ,O.CONTEXT_ROW_READ,O.CONTEXT_WRITE)]
    name,cells,words,bank,reading,row,writing=specs[0];reading_now=query(reading,row,writing)
    q={r:form(matches(a[:7],r)+[run,reading_now])for r in range(128)}
    k={r:form(matches(address[:7],r))for r in range(128)}
    values={0:A_REF*one,1:A_REF*one};values.update({i+2:A_BIT*payload[i]for i in range(64)})
    pages=[]
    for page in range(4):
        beta=builder.gate('and',[enable]+matches(kind,bank)+matches(address[7:9],page),'heap-page-write')
        selected=builder.gate('and',matches(a[7:9],page),'heap-page-read')
        pages.append(dict(v=values,a=0,z={i+2:K*selected for i in range(64)},outs=[(i+2,128.)for i in range(64)],beta=beta,into=D[:64]))
    first=pages[0];g.head('arena.heap.group',q,k,first['v'],0,first['z'],first['outs'],beta=first['beta'],into=first['into'],min_level=2*start,vx=pages[1:])
    actual=g.nodes[-1].level//2
    for page in range(4):metadata.append(dict(bank='heap',page=page,words=4,layer=actual,value_head=page,row_offset=0))
    # Disjoint key coordinates let the small banks share one key head. Every
    # ordinary instruction reads one bank; write-beta remains bank-specific.
    q={};k={};heads=[];offset=0
    for name,cells,words,bank,reading,row,writing in specs[1:]:
        width=cells.bit_length()-1;reading_now=query(reading,row,writing)
        bank_write=builder.gate('and',matches(kind,bank),'small-bank-kind')
        for r in range(cells):
            q[offset+r]=form(matches(a[:width],r)+[run,reading_now])
            k[offset+r]=form(matches(address[:width],r)+[bank_write])
        beta=builder.gate('and',[enable,bank_write]+([boot]if name=='constants'else[]),'small-bank-write')
        values={0:A_REF*one,1:A_REF*one};values.update({i+2:A_BIT*payload[i]for i in range(16*words)})
        heads.append(dict(v=values,a=0,z={i+2:K*reading_now for i in range(16*words)},outs=[(i+2,128.)for i in range(16*words)],beta=beta,into=D[:16*words]))
        metadata.append(dict(bank=name,page=0,words=words,layer=None,value_head=len(heads)-1,row_offset=offset));offset+=cells
    first=heads[0];g.head('arena.small.group',q,k,first['v'],0,first['z'],first['outs'],beta=first['beta'],into=first['into'],min_level=2*(start+1),vx=heads[1:])
    for item in metadata:
        if item['layer']is None:item['layer']=g.nodes[-1].level//2
