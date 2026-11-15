"""Compile/run the WHOLE shared stock checker, with explicit evidence scope."""
import argparse,json,time
from pathlib import Path
from leanputer.kernel.control_capture import capture
from leanputer.kernel.control_store import ControlStore
from leanputer.kernel.stock_control import NativeControl
from leanputer.kernel.traversal_machine import MachineConfig


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--device',default='cuda');p.add_argument('--max-forwards',type=int,default=512);p.add_argument('--execution',choices=['eager','cuda_graph'],default='cuda_graph');p.add_argument('--offline-check',action='store_true');p.add_argument('--no-compile-stock',action='store_true');p.add_argument('--bundled-controls',action='store_true');p.add_argument('--grouped-memory',action='store_true');p.add_argument('--incremental-bounds',action='store_true');p.add_argument('--compact-rom',action='store_true');p.add_argument('--source-operations',action='store_true');p.add_argument('--fast-default-dispatch',action='store_true');p.add_argument('--reuse-transient-features',action='store_true');p.add_argument('--hidden',type=int,choices=[768,896,960,1024]);p.add_argument('--intermediate',type=int,choices=[256,512,1024],default=256);a=p.parse_args()
    cfg=MachineConfig(**json.loads(a.config.read_text()));compiler,addresses=capture(cfg);store=ControlStore(compiler,role_dispatch=True,mode_dispatch=a.bundled_controls,incremental_bounds=a.incremental_bounds,fast_default_dispatch=a.fast_default_dispatch);program=NativeControl(store,addresses,bundle_guards=a.bundled_controls,compact_rom=a.compact_rom,source_operations=a.source_operations)
    def progress(event):print(json.dumps(event),flush=True)
    progress(dict(event='compiled',control=program.report))
    # Source is parsed only AFTER the immutable full control has been compiled.
    documents=[json.loads(line)for line in a.source.read_text().splitlines()]
    from leanputer.kernel.stock_checker import run,read_main_and_banks
    result=run(program,documents,device=a.device,max_forwards=a.max_forwards,progress=progress,execution=a.execution,compile_stock=not a.no_compile_stock,grouped_memory=a.grouped_memory,model_hidden=a.hidden,intermediate=a.intermediate,reuse_transient_features=a.reuse_transient_features)
    report={k:v for k,v in result.items()if k not in('chip','cache','state')};report['control']=program.report;report['model']=result['chip'].report
    report['full_source_stock_completed']=result['completed'];report['original_source_stock_acceptances']=[doc.get('name')for doc,row in zip(documents,result['outputs'])if result['completed']and row[1]==1];report['source_names']=[doc.get('name')for doc in documents]
    if a.offline_check and result['completed']:
        # Development check runs after inference. No reference state/answer can
        # enter inference inputs, cache, instructions or loop dispatch.
        from leanputer.kernel import source_transition as source,traversal_machine as spec
        checked=[]
        for i,doc in enumerate(documents):
            state=source.prepare(cfg,*source.parse_document(doc));reference=spec.SpecMachine(cfg,state)
            for _ in range(cfg.fuel+2):
                expected=reference.step()
                if expected['regs']['status']:break
            actual=read_main_and_banks(result['chip'],result['cache'],i)
            if actual!=expected:raise AssertionError(('compact stock complete source state differs',doc.get('name')))
            checked.append(dict(name=doc.get('name'),all_registers_and_banks_match=True))
        report['offline_post_inference_checks']=checked
    a.report.write_text(json.dumps(report,indent=2)+'\n');progress(dict(event='result',**report))


if __name__=='__main__':main()
