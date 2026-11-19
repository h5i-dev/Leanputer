"""Static operand-to-port routing for the shared selective checker RF.

Routes are generated from ALL source regions before reading input syntax.
They are descriptor IR, not host-side inference memory operations.
"""
from collections import Counter,defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class GatherQuery:
    row: int
    lanes: tuple
    fields: tuple


@dataclass(frozen=True)
class RegionGather:
    region: int
    queries: tuple
    update_rows: tuple

    def read_forwards(self,ports=3):
        return (len(self.queries)+ports-1)//ports


def compile_gathers(contracts,layout):
    locations=layout.locations();result=[]
    for contract in contracts:
        pages=defaultdict(lambda:[[]for _ in range(4)])
        expected=set(contract.inputs)&set(locations)
        for field in sorted(expected,key=locations.__getitem__):
            row,slot=locations[field];page,lane=divmod(slot,7)
            pages[row][page].append((lane,field))
        queries=[]
        for row,values in sorted(pages.items()):
            for index in range(max(map(len,values))):
                lanes=tuple(value[index][0]if index<len(value)else 7 for value in values)
                fields=tuple(value[index][1]if index<len(value)else None for value in values)
                queries.append(GatherQuery(row,lanes,fields))
        actual=[field for query in queries for field in query.fields if field is not None]
        if len(actual)!=len(expected)or set(actual)!=expected:
            raise AssertionError('selective gather loses or aliases a kernel operand')
        updates=defaultdict(list)
        for field in contract.updates:
            if field in locations:
                row,slot=locations[field];updates[row].append((slot,field))
        result.append(RegionGather(contract.index,tuple(queries),tuple((row,tuple(sorted(fields)))for row,fields in sorted(updates.items()))))
    return tuple(result)


def account_gathers(plans):
    reads=Counter(plan.read_forwards()for plan in plans)
    writes=Counter(len(plan.update_rows)for plan in plans)
    return dict(format='leanputer.checker-selective-gather-plans.v1',
                all_family_regions=len(plans),independent_ports=3,selected_words_per_port=4,
                compile_time_operand_coverage_verified=True,
                read_forward_histogram=dict(sorted(reads.items())),
                candidate_update_row_histogram=dict(sorted(writes.items())),
                max_read_forwards=max(reads),max_candidate_update_rows=max(writes),
                whole_transition_composition_verified=False,complete_descriptor_encoding_verified=False,
                bulk_write_schedule_verified=False,source_native_counts=None,
                joint_delivery_gate=False)
