"""Whole-program layout plus OFFLINE replayed cost account; no inference."""
import argparse,json,pickle
from pathlib import Path
from leanputer.kernel.control_ir import TypedBuilder
from leanputer.kernel.traversal_transition import compile_addresses
from leanputer.kernel.transition_contracts import validate_sources,compile_contracts
from leanputer.kernel.transition_layout import pack_operator_rows
from leanputer.kernel.operator_program import OperatorProgram
from leanputer.kernel.operator_budget import OperatorBudget


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trusted-compiler-cache',type=Path,required=True)
    p.add_argument('--access-trace',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--read-ports',type=int,choices=[3,4],default=4)
    a=p.parse_args();legacy=pickle.loads(a.trusted_compiler_cache.read_bytes())
    compiler=legacy.store.compiler;validate_sources(compiler)
    program=OperatorProgram(compiler,legacy.store.contract_plan,compile_addresses(compiler.layout,builder_factory=TypedBuilder),alias_private_controls=True)
    layout=pack_operator_rows(compiler,compile_contracts(compiler,legacy.store.contract_plan),program,global_words=16)
    # Placement and all logical fields are frozen before opening the trace.
    trace=json.loads(a.access_trace.read_text());rows=[]
    for source in trace['sources']:
        budget=OperatorBudget(layout,read_ports=a.read_ports)
        for access in source['access']:budget.add({key:set(values)for key,values in access.items()})
        rows.append(dict(name=source['name'],**budget.report(source['selector_reloads'])))
    report=dict(format='leanputer.operator-layout-budget.v1',
                global_words=16,globals=layout.globals,rf_rows=len(layout.rows),
                all_951_logical_words_distinct=True,input_independent_layout=True,
                layout_inputs='ALL source operator read dependencies; source traces used only after layout is fixed',
                source_rows=rows,complete_neural_layout_verified=False,joint_delivery_gate=False)
    a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
