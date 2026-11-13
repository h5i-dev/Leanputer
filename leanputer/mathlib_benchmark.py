"""Pinned, denominator-preserving mathlib declaration sampling and evaluation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import time

from .preparation import lean_tool


DEFAULT_MODULES = ['Mathlib.Logic.Basic', 'Mathlib.Logic.Function.Basic',
                   'Mathlib.Algebra.Group.Defs', 'Mathlib.Data.Nat.Basic']


def run_lake(checkout, command, log, timeout=300):
    started = time.perf_counter()
    result = subprocess.run(['lake', 'env']+command, cwd=checkout, capture_output=True, text=True, timeout=timeout)
    Path(log).write_text(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(f'mathlib command failed ({result.returncode}): {result.stdout}{result.stderr}')
    return time.perf_counter()-started


def select_population(population, count, seed):
    if type(count) is not int or count < 0:
        raise ValueError('nonnegative selection count required')
    public = [entry for entry in population['declarations'] if not entry['internal'] and not entry['private']]
    rank = lambda entry: hashlib.sha256(f'{seed}/{entry["module"]}/{entry["name"]}'.encode()).hexdigest()
    return sorted(public, key=rank)[:count]


def prepare_mathlib(checkout, directory, count=200, seed=814732, modules=DEFAULT_MODULES):
    checkout, directory = Path(checkout).resolve(), Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    def git(*args):
        result = subprocess.run(['git', '-C', str(checkout), *args], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    commit = git('rev-parse', 'HEAD')
    enumeration_config, population_file = directory/'enumeration.json', directory/'population.json'
    enumeration_config.write_text(json.dumps(dict(modules=modules, output=str(population_file))))
    enumeration_seconds = run_lake(checkout, ['lean', '--run', str(lean_tool('Enumerate.lean')), str(enumeration_config)], directory/'enumeration.log')
    population = json.loads(population_file.read_text())
    selected = select_population(population, count, seed)
    targets = [dict(name=entry['name'], name_parts=entry.get('name_parts'), levels=[1]*len(entry['universe_parameters'])) for entry in selected]
    selection = dict(format='leanputer.mathlib-selection.v1', mathlib_commit=commit,
                     lean_toolchain=(checkout/'lean-toolchain').read_text().strip(),
                     lake_manifest_sha256=hashlib.sha256((checkout/'lake-manifest.json').read_bytes()).hexdigest(),
                     modules=modules, original_theorem_declarations=len(population['declarations']),
                     public_theorem_population=sum(not e['internal'] and not e['private'] for e in population['declarations']),
                     public_by_module=dict(Counter(e['module'] for e in population['declarations'] if not e['internal'] and not e['private'])),
                     selected=len(selected), seed=seed,
                     protocol='Public original-theorem declarations in four fixed owner modules; lowest SHA256(seed/module/name), before any body/feature filtering; one all-ones ground universe instantiation per theorem.',
                     trust_mode='dependency-closed; genuine axioms explicit; opaque bodies required and checked',
                     declarations=selected, targets=targets, enumeration_seconds=enumeration_seconds,
                     scope='Budgeted module population/sample, not a full-mathlib denominator.')
    (directory/'selection.json').write_text(json.dumps(selection, indent=2)+'\n')
    export_config, corpus = directory/'export.json', directory/'corpus.jsonl'
    export_config.write_text(json.dumps(dict(modules=modules, targets=targets, output=str(corpus))))
    export_seconds = run_lake(checkout, ['lean', '--run', str(lean_tool('Export.lean')), str(export_config)], directory/'export.log', timeout=600)
    documents = [json.loads(line) for line in corpus.read_text().splitlines() if line.strip()]
    if len(documents) != len(selected):
        raise RuntimeError('export denominator changed')
    statuses = Counter('EXPORTED' if 'term' in d else d.get('status', 'EXPORT_FAILURE') for d in documents)
    reasons = Counter(d.get('reason', '') for d in documents if 'term' not in d)
    summary = dict(selection=selection, export_seconds=export_seconds, export_counts=dict(statuses), unsupported_reasons=dict(reasons),
                   exported_corpus_sha256=hashlib.sha256(corpus.read_bytes()).hexdigest(),
                   throughput_scope='Export/screening throughput is not successful proof-checking throughput.')
    (directory/'preparation.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary


def write_syntax_report(preparation, directory, feature_boundary):
    """Retain every selected row, without assigning proof-checking verdicts."""
    from .dependent import parse_expr
    directory = Path(directory)
    selection = preparation['selection']
    corpus = directory/'corpus.jsonl'
    documents = [json.loads(line) for line in corpus.read_text().splitlines() if line.strip()]
    if len(documents) != selection['selected']:
        raise ValueError('syntax report denominator changed')
    outcomes = []
    for declaration, document in zip(selection['declarations'], documents):
        provenance = document['provenance']
        if declaration['name'] != provenance['source_constant']:
            raise ValueError('syntax report declaration order changed')
        exported = 'term' in document
        nodes = set()
        environment = document.get('environment', [])
        if exported:
            pending = [parse_expr(document['term']), parse_expr(document['claim'])]
            for entry in environment:
                pending.append(parse_expr(entry['type']))
                if entry.get('value') is not None:
                    pending.append(parse_expr(entry['value']))
            while pending:
                expression = pending.pop()
                if expression in nodes:
                    continue
                nodes.add(expression)
                if expression[0] in ('pi', 'lam', 'app', 'let'):
                    pending.extend(expression[1:])
                elif expression[0] == 'proj':
                    pending.append(expression[3])
        outcomes.append(dict(module=declaration['module'], source=declaration['name'],
            source_name_parts=provenance.get('source_name_parts'), ground_levels=provenance['ground_levels'],
            status='EXPORTED' if exported else document.get('status', 'EXPORT_FAILURE'),
            reason=None if exported else document.get('reason'), checking_status='NOT_RUN_IN_THIS_REFRESH',
            environment_declarations=len(environment) if exported else None,
            assumptions=[e['name'] for e in environment if e.get('value') is None] if exported else None,
            input_dag_nodes=len(nodes) if exported else None,
            dependency_closure='complete_syntax_export' if exported else 'not_exported'))
    outcome_file = directory/'syntax-outcomes.jsonl'
    outcome_file.write_text(''.join(json.dumps(row)+'\n' for row in outcomes))
    summary = {key: selection[key] for key in ('mathlib_commit', 'lean_toolchain', 'modules',
        'original_theorem_declarations', 'selected', 'protocol')}
    summary.update(format='leanputer.mathlib-syntax-refresh.v1',
        public_population=selection['public_theorem_population'], ground_instances_per_source=1,
        counts=dict(Counter(row['status'] for row in outcomes)), export_seconds=preparation['export_seconds'],
        enumeration_seconds=selection['enumeration_seconds'], unsupported_reasons=preparation['unsupported_reasons'],
        exporter_sha256=hashlib.sha256(lean_tool('Export.lean').read_bytes()).hexdigest(),
        corpus_sha256=hashlib.sha256(corpus.read_bytes()).hexdigest(),
        all_outcomes_sha256=hashlib.sha256(outcome_file.read_bytes()).hexdigest(),
        leanputer_feature_boundary=feature_boundary,
        scope='Syntax-only export refresh. EXPORTED is not proof acceptance. No full-population native/differential run in this refresh.')
    (directory/'syntax-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mathlib', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=200)
    parser.add_argument('--seed', type=int, default=814732)
    parser.add_argument('--syntax-report', metavar='FEATURE_BOUNDARY',
                        help='also write complete syntax-only outcomes labeled with this feature boundary')
    args = parser.parse_args(argv)
    summary = prepare_mathlib(args.mathlib, args.output, args.count, args.seed)
    if args.syntax_report:
        write_syntax_report(summary, args.output, args.syntax_report)
    print(json.dumps(dict(selected=summary['selection']['selected'], public_population=summary['selection']['public_theorem_population'],
                         counts=summary['export_counts'], export_seconds=summary['export_seconds'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
