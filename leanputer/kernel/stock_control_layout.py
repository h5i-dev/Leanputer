"""Input-independent control reachability and aligned ROM repacking.

Both data branches, every indexed-dispatch slot, and all handler continuations
are retained. This removes instructions bypassed by compiler fusion, never
instructions selected by a particular source/proof. No evaluator is involved.
"""
from dataclasses import replace
from .stock_datapath import CoreRecord,WordAction as O
from .stock_source_ops import SparseSwitchRecord,map_cases


def compact_control(records,regions):
    branches={O.EQ_BRANCH,O.LT_BRANCH,O.NONZERO_BRANCH,O.INVALID_BRANCH}
    switches={O.SWITCH4:16,O.SWITCH8:256}
    tables={r.auxiliary:switches[r.action]for r in records if isinstance(r,CoreRecord)and r.action in switches}
    entries={pc for base,size in tables.items()for pc in range(base,base+size)}
    if any(pc>=len(records)for pc in entries):raise ValueError('control table outside ROM')
    live=set();pending=[0];used_tables=set()
    def successors(r):
        core=isinstance(r,CoreRecord)
        if isinstance(r,SparseSwitchRecord):yield from(pc for value,pc in r.cases)
        if core and r.capture_return:yield r.auxiliary
        if core and r.action in switches:
            used_tables.add(r.auxiliary)
            yield from range(r.auxiliary,r.auxiliary+switches[r.action])
        if core and r.action in(O.RETURN_HANDLER,O.STOP_OK,O.STOP_INVALID):return
        if not getattr(r,'return_yes',False):yield r.yes
        if core and r.action==O.CALL_HANDLER:yield r.no
        elif(not core and hasattr(r,'no'))or(core and r.action in branches):
            if not getattr(r,'return_no',False):yield r.no
    while pending:
        pc=pending.pop()
        if pc in live:continue
        if not 0<=pc<len(records):raise ValueError('control edge outside ROM')
        live.add(pc);pending.extend(successors(records[pc]))
    order=sorted(live-entries);mapping={pc:i for i,pc in enumerate(order)};new_bases={};padding=0
    for base in sorted(used_tables):
        size=tables[base]
        while len(order)%size:order.append(None);padding+=1
        new_bases[base]=len(order)
        for pc in range(base,base+size):
            if pc not in live:raise AssertionError('live dispatch lost a data slot')
            mapping[pc]=len(order);order.append(pc)
    if set(mapping)!=live:raise AssertionError('control mapping lost reachable instructions')
    def edge(pc,used=True):
        if not used:return 0
        if pc not in mapping:raise AssertionError('control mapping lost reachable edge')
        return mapping[pc]
    output=[];new_regions=[]
    for pc in order:
        if pc is None:
            output.append(CoreRecord(O.JUMP,yes=0));new_regions.append('table-padding');continue
        r=records[pc];core=isinstance(r,CoreRecord)
        terminal=core and r.action in(O.RETURN_HANDLER,O.STOP_OK,O.STOP_INVALID)
        fields=dict(yes=edge(r.yes,not terminal and not getattr(r,'return_yes',False)))
        if core:
            fields['no']=edge(r.no,r.action==O.CALL_HANDLER or(r.action in branches and not r.return_no))
            if r.action in switches:fields['auxiliary']=new_bases[r.auxiliary]
            elif r.capture_return:fields['auxiliary']=edge(r.auxiliary)
        elif hasattr(r,'no'):fields['no']=edge(r.no,not r.return_no)
        output.append(replace(map_cases(r,edge),**fields));new_regions.append(regions[pc])
    report=dict(input_independent=True,both_data_branches_retained=True,records_before=len(records),reachable_instructions=len(live),records_after=len(output),removed_records=len(records)-len(output),aligned_tables=len(used_tables),aligned_table_entries=sum(tables[b]for b in used_tables),new_padding_records=padding)
    return output,new_regions,report
