"""Post-baseline development accounting, not a checker runtime or inference input."""
import json,statistics,time
from pathlib import Path
from leanputer.kernel import source_transition as p,traversal_machine as spec
from leanputer.control_banking import ownership
root=Path(__file__).resolve().parent;cfg=p.MachineConfig(heap=512,stack=32,context=8,constants=4,fuel=8192,word_bits=16);layout=p.RegisterLayout(p.StateLayout(cfg));compiler=p.RuleCompiler(layout,packed_outputs=True);c,o,groups=ownership(compiler,p.compile_addresses(layout,target=lambda c,o:(c,o)));rows=[]
for doc in [json.loads(line)for line in Path('benchmarks/kernel-full-source-stock/source.jsonl').read_text().splitlines()]:
 m=spec.SpecMachine(cfg,p.prepare(cfg,*p.parse_document(doc)));counts=[];bank_counts=[]
 for step in range(cfg.fuel+2):
  old=dict(m.state['regs']);before={b:[list(row)for row in m.state[b]]for b in('heap','stack','context')};m.step();counts.append(sum(int(m.state['regs'][n])!=int(old[n])for n,w in layout.fields));bank_counts.append(sum(row!=prev for b in before for row,prev in zip(m.state[b],before[b])))
  if m.state['regs']['status']:break
 rows.append(dict(name=doc['name'],semantic_steps=step+1,status=spec.Outcome(m.state['regs']['status']).name,reason=spec.Reason(m.state['regs']['reason']).name,changed_register_words=dict(total=sum(counts),mean=statistics.mean(counts),median=statistics.median(counts),max=max(counts)),changed_bank_rows=dict(total=sum(bank_counts),max=max(bank_counts)),note='Changed-value counts only, not active assignments, microcode length, full-kernel worst case or native timing.'))
report=dict(format='leanputer.kernel-datapath-source-account.v1',semantic_register_words=len(layout.fields),word_bits=cfg.word_bits,source_field_assignments=sum(len(x)for x in compiler.choices.values()),distinct_field_guard_word_choices=sum(len(set((g,tuple(w))for g,w in x))for x in compiler.choices.values()),memory_row_write_choices={b:len(x)for b,x in compiler.writes.items()},boolean_wires=len(c.depth),boolean_gates=len(c.gates),private_register_words=sum(len(x)for x in groups.values()),max_private_owner_words=max(map(len,groups.values())),examples=rows,evidence='Static source compilation and development SPEC accounting after existing stock baseline; no new native admission or microcode compiler.')
(root/'source-account.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
