"""Audit a trusted local complete compiler cache; never runs a source checker."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import pickle
from leanputer.kernel.transition_contracts import validate_sources, compile_contracts, account_contracts
from leanputer.kernel.transition_layout import pack_register_rows, account_layout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trusted-compiler-cache', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--contracts', type=Path)
    parser.add_argument('--layout', type=Path)
    args = parser.parse_args()
    program = pickle.loads(args.trusted_compiler_cache.read_bytes())
    compiler, partition = program.store.compiler, program.store.contract_plan
    validate_sources(compiler)
    contracts = compile_contracts(compiler, partition)
    report = account_contracts(compiler, partition, contracts)
    if args.layout:
        layout = pack_register_rows(compiler, contracts)
        args.layout.write_text(json.dumps(account_layout(compiler, contracts, layout), indent=2) + '\n')
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    if args.contracts:
        args.contracts.write_text(json.dumps([asdict(c) for c in contracts], indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
