"""Report the new joint gate without emitting a model or running a host checker."""
import argparse,json
from pathlib import Path
from leanputer.kernel.macro_budget import TransitionArchitecture,source_step_allowance


def main():
    p=argparse.ArgumentParser();p.add_argument('--source-costs',type=Path,default=Path('benchmarks/kernel-macro-budget/source-costs.json'));p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    source=json.loads(a.source_costs.read_text());report=dict(format='leanputer.checker-transition-joint-budget.v1',architecture=TransitionArchitecture().account(),source_allowances=[source_step_allowance(row)for row in source],evidence_scope='Illustrative shape/step allowances, not a feasible complete schedule; both implemented whole-register layouts exceed the forward target',implemented_whole_register_layouts_meet_target=False,joint_delivery_gate=False)
    a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
