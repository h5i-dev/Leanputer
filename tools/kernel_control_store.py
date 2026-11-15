"""Compile the whole typed kernel program; no proof input or model inference."""
import argparse,json,time
from pathlib import Path
from leanputer.kernel.control_capture import capture
from leanputer.kernel.control_store import ControlStore
from leanputer.kernel.traversal_machine import MachineConfig


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--store',type=Path);p.add_argument('--offline-verify',type=Path);a=p.parse_args();start=time.perf_counter()
    compiler,addresses=capture(MachineConfig(**json.loads(a.config.read_text())))
    store=ControlStore(compiler);report=store.report();report['compile_seconds']=time.perf_counter()-start
    report['address_programs']=[b.statistics()for b,w in addresses]
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    if a.store:a.store.write_text(json.dumps(store.serializable(),separators=(',',':'))+'\n')
    if a.offline_verify:
        # Development correspondence only, after the input-independent program
        # already exists. No production model imports this reference.
        from leanputer.kernel import source_transition as source,traversal_machine as spec
        from leanputer.kernel.control_store_reference import StoreReference
        checker=StoreReference(store,addresses);examples=[]
        for line in a.offline_verify.read_text().splitlines():
            doc=json.loads(line);state=source.prepare(compiler.cfg,*source.parse_document(doc));reference=spec.SpecMachine(compiler.cfg,state);steps=records=forwards=peak=0
            for steps in range(1,compiler.cfg.fuel+3):
                state=checker.step(state);expected=reference.step()
                if state!=expected:raise AssertionError(('typed store differs from SPEC',doc.get('name'),steps))
                records+=checker.last_records;forwards+=checker.last_forwards;peak=max(peak,checker.last_forwards)
                if state['regs']['status']:break
            examples.append(dict(name=doc.get('name'),semantic_steps=steps,status=spec.Outcome(state['regs']['status']).name,reason=spec.Reason(state['regs']['reason']).name,typed_records_executed=records,estimated_model_forwards=forwards,forward_max_per_semantic_step=peak,exact_all_registers_and_banks=True,evidence='OFFLINE compiled typed control reference, not stock inference'))
        report['offline_examples']=examples;report['total_seconds']=time.perf_counter()-start
        a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in('rule_family_count','captured_effects','mapped_effects','control_records','temporary_words_including_ports','record_budget_met','scratch_budget_met','compile_seconds')}),flush=True)


if __name__=='__main__':main()
