"""Joint control-dispatch account. No stock emission and no source execution."""
import json
import pickle
from pathlib import Path

from leanputer.kernel.semantic_dispatch import dispatch_account
from leanputer.kernel.transition_contracts import validate_sources


def main():
    program = pickle.loads(Path('/mnt/scratch/leanputer-runs/architecture-budget/direct-preflight-control-offline.pickle').read_bytes())
    compiler = program.store.compiler
    validate_sources(compiler)
    plan = program.store.contract_plan
    effects = [effect for _, effect in plan.body]
    accounted = dispatch_account(compiler, effects)
    print(json.dumps(accounted['report'], indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
