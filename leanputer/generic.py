"""Generic declaration-as-data checker CLI; no reference checker at inference."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from collections import Counter
import torch
from .generic_spec import MachineConfig,Outcome,Reason,prepare
from .generic_syntax import parse_document,assumptions,Unsupported,Exhausted
from . import generic_transition as program


def check_documents(model,documents,backend='native',batch_size=16):
    records=[];pending=[];positions=[];batches=[];started=time.perf_counter()
    for i,document in enumerate(documents):
        name=document.get('name',str(i))if isinstance(document,dict)else str(i)
        record=dict(name=name)
        if isinstance(document,dict) and 'provenance' in document:
            record['provenance']=document['provenance']
        if isinstance(document,dict) and document.get('format')=='leanputer.generic.v1' and document.get('status')=='UNSUPPORTED':
            record.update(status='UNSUPPORTED',reason=document.get('reason','unsupported source syntax'),
                          environment_declarations=None,assumptions=None,input_heap_nodes=None)
            records.append(record);continue
        try:
            term,claim,ds=parse_document(document);state=prepare(model.config,term,claim,ds)
            record.update(environment_declarations=len(ds),assumptions=assumptions(ds),input_heap_nodes=state['regs']['free']-1)
        except Unsupported as e:record.update(status='UNSUPPORTED',reason=str(e))
        except Exhausted as e:record.update(status='RESOURCE',reason=str(e))
        except (ValueError,TypeError,KeyError,RecursionError)as e:record.update(status='MALFORMED',reason=str(e))
        else:pending.append(document);positions.append(i)
        records.append(record)
    syntax_seconds=time.perf_counter()-started
    for start in range(0,len(pending),batch_size):
        rows=pending[start:start+batch_size]
        if backend=='native':
            result=model.check(rows);result.pop('registers');results=result.pop('results')
        else:
            states=[prepare(model.config,*parse_document(d))for d in rows]
            bits=torch.cat([model.layout.encode(s)for s in states]);bits=bits.to(next(model.buffers()).device)
            began=time.perf_counter()
            with torch.inference_mode():
                bits=model.initializer(bits)
                for _ in range(model.config.fuel+1):bits=model(bits)
            if bits.device.type=='cuda':torch.cuda.synchronize()
            result=dict(forward_seconds=time.perf_counter()-began,applied_steps=model.config.fuel+1)
            results=[]
            for document,bitsrow in zip(rows,bits.cpu()):
                r=model.layout.decode(bitsrow.tolist())['regs']
                status='UNSUPPORTED'if r['reason']==Reason.UNSUPPORTED_DECLARATION else Outcome(r['status']).name
                results.append(dict(name=document.get('name','unnamed'),status=status,reason=Reason(r['reason']).name,
                                    semantic_steps=model.config.fuel-r['fuel']+int(r['reason']==Reason.FUEL),allocated_heap_nodes=r['free']-1))
        indices=positions[start:start+batch_size]
        for i,r in zip(indices,results):records[i].update(r)
        batches.append(dict(input_positions=indices,**result))
    return dict(format='leanputer.generic-report.v1',semantic_program=program.program_name,primitive_basis=[],
                config=asdict(model.config),results=records,counts=dict(Counter(r['status']for r in records)),
                syntax_seconds=syntax_seconds,batches=batches,total_check_seconds=time.perf_counter()-started,
                validation_scope='Restricted uniform type-parameter family/constructor admission, zero-parameter direct recursion/projections, and nullary Prop; no full Lean/general inductive soundness claim')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--config',type=Path)
    p.add_argument('--report',type=Path);p.add_argument('--device',choices=('cpu','cuda'),default='cpu')
    p.add_argument('--backend',choices=('native','circuit'),default='native')
    p.add_argument('--batch-size',type=int,default=16)
    args=p.parse_args(argv);torch.set_num_threads(1)
    if args.batch_size<1:p.error('positive batch size required')
    cfg=MachineConfig(**json.loads(args.config.read_text()))if args.config else MachineConfig()
    content=args.input.read_text()
    try:
        docs=json.loads(content);docs=docs if isinstance(docs,list)else[docs]
    except json.JSONDecodeError:docs=[json.loads(line)for line in content.splitlines()if line.strip()]
    began=time.perf_counter()
    if args.backend=='native':
        from .native_machine import compile_native_machine
        model=compile_native_machine(cfg,device=args.device,program=program)
    else:model=program.compile_machine(cfg).to(args.device)
    compile_seconds=time.perf_counter()-began
    result=check_documents(model,docs,args.backend,args.batch_size)
    result.update(backend=args.backend,device=args.device,compile_seconds=compile_seconds,
                  cold_compile_and_check_seconds=time.perf_counter()-began)
    text=json.dumps(result,indent=2)+'\n'
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(text)
    else:print(text,end='')
    return 1 if result['counts'].get('REJECT')else 2 if set(result['counts'])-{'ACCEPT'}else 0


if __name__=='__main__':raise SystemExit(main())
