"""Check original source declarations in compiler-generated STOCK Transformer weights.

Parsing/packing is syntax only. No Python kernel, Lean or nanoda checker is
called by this inference CLI. Missing implemented services return GAP; every
input row remains in the report, including unavailable/malformed/over-limit rows.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import time
import torch
from .kernel.arena import KernelError, ResourceError
from .kernel.syntax import SourceUnavailable
from .kernel import source_transition as program
def compile_native_machine(*args,**kwargs):
    import sys
    if sys.version_info < (3,11):
        raise ImportError('native stock backend requires Python3.11+ and leanputer[native]')
    from .native_machine import compile_native_machine as compile_stock
    return compile_stock(*args,**kwargs)



def read_documents(content):
    try:
        value=json.loads(content)
        return value if isinstance(value,list) else [value]
    except json.JSONDecodeError:
        rows=[]
        for number,line in enumerate(content.splitlines(),1):
            if not line.strip():continue
            try:rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                rows.append(dict(format='leanputer.invalid-json-line',name='line '+str(number),error=str(error)))
        return rows


def check_sources(documents, config, *, device='cuda', batch_size=1, intermediate=512, early_stop=True, weight_storage='sparse_csr', pack_control=True, compiled_machine=None, save_model=None):
    if batch_size<1:raise ValueError('positive batch size required')
    results=[];pending=[];positions=[];judgments=[];batches=[]
    for index,document in enumerate(documents):
        result=dict(index=index,name=document.get('name',str(index)) if isinstance(document,dict) else str(index),
                    native_attempted=False,target_checked=False,assumptions=[],input_axiom_candidates=None,raw_dependency_items=None)
        results.append(result)
        try:
            if not isinstance(document,dict):raise KernelError('source document must be an object')
            if document.get('format')=='leanputer.invalid-json-line':raise KernelError(document['error'])
            judgment=program.parse_document(document)
            initial=program.prepare(config,*judgment)
        except SourceUnavailable as error:result.update(status='SOURCE_UNAVAILABLE',reason=str(error),stage='source_preparation')
        except ResourceError as error:result.update(status='RESOURCE',reason=str(error),stage='syntax_transport')
        except (KernelError,ValueError,TypeError,KeyError,RecursionError) as error:
            result.update(status='MALFORMED_INPUT',reason=str(error),stage='syntax_transport')
        else:
            source=judgment[0]
            result.update(target_kind=source.target.kind,raw_dependency_items=len(judgment[2]),
                input_heap_nodes=initial['regs']['free']-1,input_axiom_candidates=program.assumptions(judgment[2]))
            pending.append(document);positions.append(index);judgments.append(judgment)
    compilation=0.;machine=None
    if pending:
        started=time.perf_counter()
        try:machine=compiled_machine if compiled_machine is not None else compile_native_machine(config,intermediate=intermediate,device=device,program=program,weight_storage=weight_storage,pack_control=pack_control)
        except (RuntimeError,ImportError,ValueError) as error:
            for position in positions:results[position].update(status='INFERENCE_UNAVAILABLE',reason=str(error),stage='stock_compilation')
        if machine is not None and save_model is not None:
            from .source_model import save_source_machine
            save_source_machine(machine,save_model)
        compilation=time.perf_counter()-started
        for start in range(0,len(pending) if machine is not None else 0,batch_size):
            try:report=machine.check(pending[start:start+batch_size],early_stop=early_stop)
            except (RuntimeError,ValueError) as error:
                for position in positions[start:start+batch_size]:
                    results[position].update(status='INFERENCE_FAILURE',reason=str(error),stage='stock_transformer',native_attempted=True)
                batches.append(dict(input_positions=positions[start:start+batch_size],error=str(error)))
                continue
            regs=report.pop('registers')
            for offset,(entry,registers) in enumerate(zip(report.pop('results'),regs)):
                position=positions[start+offset];source=judgments[start+offset][0]
                status='ACCEPT' if entry['status']=='DONE' else 'REJECT' if entry['status']=='INVALID' else entry['status']
                results[position].update(entry,status=status,stage='stock_transformer',native_attempted=True,
                    target_checked=status=='ACCEPT',checked_input_prefix=registers['raw_index'])
                results[position]['assumption_names']=[
                    [{'str':v} if k=='str' else {'num':v} for k,v in source.symbols.names[symbol]]
                    for symbol in entry['assumptions']]
            report['input_positions']=positions[start:start+batch_size];batches.append(report)
    report=dict(format='leanputer.kernel-native-source-report.v1',denominator=len(documents),results=results,
        counts=dict(Counter(row['status'] for row in results)),config=asdict(config),device=device,
        compile_seconds=compilation,batches=batches,syntax_transport_ready=len(pending),
        native_attempted=sum(row['native_attempted'] for row in results),
        full_kernel_native_support=False,small_model_target_met=False,weight_storage=weight_storage,packed_control=pack_control,
        validation_scope='Original-source declaration checking with explicit GAP callbacks; not full Lean or mathlib coverage',
        implementation_gaps=['unavailable/incompatible Nat/Bool/String primitive reduction bindings','nested copying after a prior mutual family member was replaced','unavailable private metadata during source checking','conservative GAP classification for neutral non-Sort/non-Pi mismatches'],
        timing_scope='Cold compilation and forward batches with a fixed fuel cap and optional native completion stopping; syntax/imports excluded from model timings; no steady-state throughput claim')
    if machine is not None:
        from .native_machine import parameter_storage
        report.update(parameter_storage(machine.model))
        report.update(stock_class=type(machine.model).__module__+'.'+type(machine.model).__name__,
            parameters=sum(p.numel() for p in machine.model.parameters()),
            weight_bytes=sum(p.numel()*p.element_size() for p in machine.model.parameters()),
            hidden_size=machine.model.config.hidden_size,native_layers=machine.model.config.num_hidden_layers)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True,help='kernel-source JSON, array or JSONL; all rows retained')
    parser.add_argument('--config',type=Path,help='fixed MachineConfig capacities/fuel')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--device',choices=('cpu','cuda'),default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--batch-size',type=int,default=1)
    parser.add_argument('--weight-storage',choices=('sparse_csr','dense'),default='sparse_csr',help='Stock nn.Linear parameter tensor storage; logical architecture size is reported separately')
    parser.add_argument('--load-model',type=Path,help='Load compiled stock weights without recompiling the kernel')
    parser.add_argument('--save-model',type=Path,help='Save model/ABI tensors for inference reuse')
    parser.add_argument('--unpacked-control',action='store_true',help='Use the historical bit-per-channel control layout')
    parser.add_argument('--fixed-fuel',action='store_true',help='disable native completion stopping for matched diagnostics')
    args=parser.parse_args(argv)
    torch.set_num_threads(1)
    try:
        loaded=None
        if args.load_model:
            from .source_model import load_source_machine
            loaded=load_source_machine(args.load_model,args.device)
        config=loaded.config if loaded is not None else program.MachineConfig(**json.loads(args.config.read_text())) if args.config else program.MachineConfig(
            heap=256,stack=16,context=8,constants=4,fuel=512,word_bits=9)
        if loaded is not None and args.config and program.MachineConfig(**json.loads(args.config.read_text()))!=loaded.config:raise ValueError('config differs from compiled model physical bounds')
        if args.device=='cuda' and not torch.cuda.is_available():raise ValueError('CUDA unavailable')
        documents=read_documents(args.input.read_text())
        if not documents:raise ValueError('input contains no source rows')
        report=check_sources(documents,config,device=args.device,batch_size=args.batch_size,early_stop=not args.fixed_fuel,weight_storage=getattr(loaded.model,'_leanputer_weight_storage','dense')if loaded else args.weight_storage,pack_control=bool(loaded.control_packing)if loaded else not args.unpacked_control,compiled_machine=loaded,save_model=args.save_model)
        text=json.dumps(report,indent=2)+'\n'
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(text)
        else:print(text,end='')
        statuses=set(report['counts'])
        return 1 if 'REJECT' in statuses else 2 if statuses-{'ACCEPT'} else 0
    except (ValueError,TypeError,KeyError,OSError,ImportError) as error:parser.error(str(error))


if __name__=='__main__':raise SystemExit(main())
