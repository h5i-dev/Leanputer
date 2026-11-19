"""Lower every current kernel region to neural expressions before model emission."""
import argparse,json,pickle,time
from pathlib import Path
from leanputer.native_machine import NativeBuilder
from leanputer.kernel.transition_contracts import validate_sources
from leanputer.kernel.operator_circuit import SourceOperatorLibrary
from leanputer.kernel.macro_budget import BASELINE_DENSE


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trusted-compiler-cache',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--parameterize-literals',action='store_true')
    a=p.parse_args();start=time.monotonic()
    saved=pickle.loads(a.trusted_compiler_cache.read_bytes());compiler=saved.store.compiler
    validate_sources(compiler)
    builder=NativeBuilder(intermediate=128,reset_layers=0)
    builder.graph.target.intermediate=104
    words=[[builder.feature(f'operand/{word}/{bit}')for bit in range(16)]for word in range(32)]
    selector=[builder.feature(f'operator/{bit}')for bit in range(12)]
    literals=[[builder.feature(f'literal/{word}/{bit}')for bit in range(16)]for word in range(32)]if a.parameterize_literals else None
    library=SourceOperatorLibrary(builder,compiler,saved.store.contract_plan.leaves,words,selector,literal_words=literals)
    library.selected_outputs(global_fields=('status','reason','fuel','free','mode','task','sp','x','arg_base','count','r','string_name_base','quot_data_base','ctx','quot_build_base','env_head'))
    report=library.report();lower_bound=3*1152*report['neural_ffn_units']
    report.update(seconds=time.monotonic()-start,
                parameter_limit=BASELINE_DENSE,full_model_emitted=False,
                minimum_mlp_dense_parameters_at_hidden_1152=lower_bound,
                candidate_dense_gate=lower_bound<=BASELINE_DENSE,
                model_emission_allowed=False,
                evidence_scope='Actual AOT neural expression lowering of all source regions; no model allocation or inference',joint_delivery_gate=False)
    a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
