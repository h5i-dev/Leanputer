"""OFFLINE old-control row-access account; never new native or stock speed."""
import argparse
from collections import Counter
import json
from pathlib import Path
import pickle
from leanputer.kernel.transition_contracts import validate_sources, compile_contracts
from leanputer.kernel.transition_layout import pack_register_rows
from leanputer.kernel.stock_control_reference import NativeControlReference
from leanputer.kernel.stock_datapath import CoreRecord, WordAction as O
from leanputer.kernel import source_transition as source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trusted-compiler-cache',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--global-policy',choices=['boundary','frequency'],default='boundary')
    args=parser.parse_args()
    program=pickle.loads(args.trusted_compiler_cache.read_bytes())
    compiler=program.store.compiler;validate_sources(compiler)
    contracts=compile_contracts(compiler,program.store.contract_plan)
    layout=pack_register_rows(compiler,contracts,global_policy=args.global_policy)
    # Layout is complete BEFORE either input is opened; no trace selects or
    # prunes any rule, register, parameter, domain bound or circuit.
    class AccessReference(NativeControlReference):
        def __init__(self,*args):
            self.accessed=set()
            super().__init__(*args)
        def read(self,address):
            row,slot=divmod(address,8)
            if row<272 and not row&1 and slot<7:
                index=(row//2)*7+slot
                if index<len(self.names):self.accessed.add(self.names[index])
            return super().read(address)
    rows=[]
    for line in Path('benchmarks/kernel-full-source-stock/source.jsonl').read_text().splitlines():
        document=json.loads(line);machine=AccessReference(program,source.prepare(compiler.cfg,*source.parse_document(document)))
        histogram=Counter();forwards=steps=conflicts=0
        banks=set()
        while not machine.status:
            record=program.records[machine.pc]
            operation=record.action if isinstance(record,CoreRecord)else None
            if operation in(O.HEAP_WRITE,O.FRAME_WRITE,O.CONTEXT_WRITE):
                banks.add({O.HEAP_WRITE:'heap',O.FRAME_WRITE:'stack',O.CONTEXT_WRITE:'context'}[operation])
            if operation==O.COMMIT_FIELDS:
                fields={machine.names[(address>>4)*7+(address&7)]for address in machine.queue}
            # The reference computes a bounds latch from state to validate its
            # old encoding; the model-owned latch is maintained on writes.
            # PREFLIGHT_CHECK's development oracle eagerly constructs a
            # dictionary of all registers. Actual weighted inputs are only
            # the preceding nine-word gathers, already charged here.
            prior=set(machine.accessed)if operation in(O.INVALID_BRANCH,O.PREFLIGHT_CHECK)else None
            committed=machine.step()
            if prior is not None:machine.accessed=prior
            if not committed:continue
            steps+=1
            touched=layout.touched_rows(machine.accessed|fields)
            updated=layout.touched_rows(fields)
            # Optimistic read/compute on the last row, then read/merge each
            # other changed row. Pipeline pending writes across forwards.
            cost=max(1,len(touched))+max(0,len(updated)-1)
            forwards+=cost;histogram[f'{len(touched)}/{len(updated)}']+=1
            conflicts+=int('context'in banks and'stack'in banks)
            machine.accessed.clear();banks.clear()
            if steps>compiler.cfg.fuel+1:raise AssertionError('reference failed to stop within semantic fuel')
        rows.append(dict(name=document['name'],semantic_steps=steps,status=machine.status,
                         reason=machine.reason,result=machine.result,
                         touched_updated_row_histogram=dict(sorted(histogram.items())),
                         conditional_row_access_forwards=forwards,small_bank_conflicts=conflicts,
                         optimistic_combined_forwards=forwards+conflicts+22+5+2,
                         actual_native_forwards=None,native_schedule_verified=False))
    report=dict(format='leanputer.checker-row-access-accounting.v1',logical_words=951,rf_rows=len(layout.rows),
                global_policy=args.global_policy,globals=layout.globals,
                layout_input_independent=True,all_logical_state_retained=True,source_rows=rows,
                assumptions=['Bounds latch updated on every write','Lazy operands fetched without scalar dispatch',
                             'One full transition circuit fits shared operator layers','Pending write forwarding and atomic bulk commit'],
                evidence_scope='OFFLINE old-encoding register-access accounting, not implemented new native upper bounds or stock timing',
                joint_delivery_gate=False)
    args.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
