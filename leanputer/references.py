"""Evaluation-only adapters for external reference checkers. Never runtime imports."""
import json
from pathlib import Path
import subprocess
import tempfile
import time

from .runner import parse_document
from .preparation import lean_tool


ROOT = Path(__file__).resolve().parents[1]


def lean_replay(documents, directory, lean='lean'):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    source, result = directory/'lean-replay-input.jsonl', directory/'lean-replay-results.json'
    source.write_text(''.join(json.dumps(document)+'\n' for document in documents))
    start = time.perf_counter()
    command = [str(lean), '--run', str(lean_tool('Validate.lean')), str(source), str(result)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
    (directory/'lean-replay.log').write_text(completed.stdout+completed.stderr)
    if completed.returncode:
        raise RuntimeError('Lean replay failed: '+completed.stdout+completed.stderr)
    return json.loads(result.read_text()), time.perf_counter()-start


class NanodaExport:
    """Pure syntax adapter to lean4export NDJSON 3.1, for independent replay."""
    def __init__(self):
        self.records = [dict(meta=dict(exporter=dict(name='leanputer-syntax-adapter', version='1.0.0'),
                                      format=dict(version='3.1.0'),
                                      lean=dict(version='4.31.0', githash='external-json-replay')))]
        self.names, self.levels, self.expressions = {}, {0:0}, {}

    def name(self, value):
        if value not in self.names:
            self.names[value] = len(self.names)+1
            self.records.append({'in': self.names[value], 'str': dict(pre=0, str=value)})
        return self.names[value]

    def level(self, value):
        if value not in self.levels:
            previous = self.level(value-1)
            self.levels[value] = len(self.levels)
            self.records.append({'il': self.levels[value], 'succ': previous})
        return self.levels[value]

    def expression(self, term):
        if term in self.expressions:
            return self.expressions[term]
        tag = term[0]
        if tag == 'var': payload = {'bvar':term[1]}
        elif tag == 'sort': payload = {'sort':self.level(term[1])}
        elif tag == 'const': payload = {'const':dict(name=self.name(term[1]), us=[])}
        elif tag == 'app': payload = {'app':dict(fn=self.expression(term[1]), arg=self.expression(term[2]))}
        else:
            domain, body = self.expression(term[1]), self.expression(term[2])
            payload = {'lam' if tag == 'lam' else 'forallE':
                       dict(name=self.name('_binder'), type=domain, body=body, binderInfo='default')}
        index = len(self.expressions)
        self.expressions[term] = index
        self.records.append(dict(ie=index, **payload))
        return index

    def declaration(self, name, ty, value):
        name_id, type_id = self.name(name), self.expression(ty)
        if value is None:
            self.records.append({'axiom':dict(name=name_id, levelParams=[], type=type_id, isUnsafe=False)})
        else:
            value_id = self.expression(value)
            self.records.append({'def':dict(name=name_id, levelParams=[], type=type_id,
                                           value=value_id, hints='abbrev', safety='safe', all=[name_id])})

    def document(self, document):
        term, claim, declarations = parse_document(document)
        for declaration in declarations:
            self.declaration(declaration.name, declaration.type, declaration.value)
        target = 'leanputer_replay_target'
        while target in {d.name for d in declarations}:
            target += '_'
        self.declaration(target, claim, term)
        return '\n'.join(json.dumps(record) for record in self.records)+'\n'


def nanoda_replay(document, directory, binary):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    export, config = directory/'nanoda.ndjson', directory/'nanoda-config.json'
    export.write_text(NanodaExport().document(document))
    assumptions = [d['name'] for d in document.get('environment', []) if d.get('value') is None]
    config.write_text(json.dumps(dict(export_file_path=str(export), permitted_axioms=assumptions,
                                     print_success_message=True, print_axioms=False)))
    start = time.perf_counter()
    completed = subprocess.run([str(binary), str(config)], capture_output=True, text=True, timeout=120)
    (directory/'nanoda.log').write_text(completed.stdout+completed.stderr)
    return dict(status='ACCEPT' if completed.returncode == 0 else 'REJECT',
                seconds=time.perf_counter()-start, exit_code=completed.returncode,
                stdout=completed.stdout, stderr=completed.stderr)
