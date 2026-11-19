"""Minimal matched-source IR correspondence; never runs or supplies a model."""
import argparse
import json
from pathlib import Path
import pickle
import time
from leanputer.kernel.control_ir import TypedBuilder
from leanputer.kernel.traversal_transition import compile_addresses
from leanputer.kernel.transition_contracts import validate_sources
from leanputer.kernel.operator_program import OperatorProgram
from leanputer.kernel.operator_reference import OperatorReference
from leanputer.kernel.stock_control_reference import NativeControlReference
from leanputer.kernel.continuation_plan import account_continuations
from leanputer.kernel.transition_contracts import compile_contracts
from leanputer.kernel.transition_layout import pack_register_rows
from leanputer.kernel.operator_budget import OperatorBudget
from leanputer.kernel import source_transition as source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trusted-compiler-cache',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--alias-private-controls',action='store_true')
    parser.add_argument('--access-trace',type=Path,help='OFFLINE field-access costs only; never inference inputs')
    args=parser.parse_args();start=time.monotonic()
    legacy=pickle.loads(args.trusted_compiler_cache.read_bytes());compiler=legacy.store.compiler
    validate_sources(compiler)
    addresses=compile_addresses(compiler.layout,builder_factory=TypedBuilder)
    program=OperatorProgram(compiler,legacy.store.contract_plan,addresses,alias_private_controls=args.alias_private_controls)
    layout=pack_register_rows(compiler,compile_contracts(compiler,legacy.store.contract_plan))
    print(json.dumps(program.report()),flush=True)
    # The complete operator set and continuation metadata are fixed BEFORE
    # reading these original sources. No proof selects a reduced program.
    rows=[];traces=[]
    for line in Path('benchmarks/kernel-full-source-stock/source.jsonl').read_text().splitlines():
        document=json.loads(line);initial=source.prepare(compiler.cfg,*source.parse_document(document))
        state=initial;reference=OperatorReference(program);old=NativeControlReference(legacy,initial);budget=OperatorBudget(layout)
        trace=[]
        while not state['regs']['status']:
            state=reference.step(state)
            budget.add(reference.last_access)
            if args.access_trace:trace.append({key:sorted(value)for key,value in reference.last_access.items()})
            while not old.step():
                if old.status:raise AssertionError('old reference stopped before matching commit')
            expected=old.state()
            if state!=expected:
                mismatch={name:(state['regs'][name],expected['regs'][name])for name in state['regs']if state['regs'][name]!=expected['regs'][name]}
                raise AssertionError(('operator/word state divergence',document['name'],reference.steps,mismatch))
            if reference.steps%256==0:print(document['name'],reference.steps,flush=True)
            if reference.steps>compiler.cfg.fuel+1:raise AssertionError('operator exceeded abstract fuel')
        while not old.status:old.step()
        rows.append(dict(name=document['name'],ir_semantic_steps=reference.steps,status=old.status,reason=old.reason,result=old.result,
                         all_951_registers_all_banks_match_each_step=True,
                         max_selected_control_groups=reference.max_active_groups,
                         max_candidate_source_effects=reference.max_candidate_effects,
                         returns_with_uninitialized_control_metadata=reference.uninitialized_returns,
                         steps_with_multiple_stack_write_sites=reference.multiple_stack_writers,
                         control_selector_actions=dict(reference.selector_actions),
                         conditional_selector_reload_forwards=reference.selector_reload_steps,
                         conditional_page_schedule=budget.report(reference.selector_reload_steps),
                         native_forwards=None,stock_executed=False))
        if args.access_trace:traces.append(dict(name=document['name'],access=trace,selector_reloads=reference.selector_reload_steps))
    report=dict(format='leanputer.original-source-operator-correspondence.v1',program=program.report(),
                continuations=account_continuations(program.continuations),source_rows=rows,seconds=time.monotonic()-start,
                evidence_scope='Complete original-source operator IR vs preserved word-control reference; NOT stock speed, lowering or external Lean differential evidence',
                joint_delivery_gate=False)
    args.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
    if args.access_trace:args.access_trace.write_text(json.dumps(dict(evidence_scope='OFFLINE costs only, NEVER inference transport or dispatch',sources=traces))+'\n')


if __name__=='__main__':main()
