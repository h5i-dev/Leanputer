"""Compiler-only bundling of pure kernel word comparisons.

No input declarations are inspected. The byte literal is an instruction encoding
bound; larger literals retain their original general word-comparison records.
"""
from dataclasses import dataclass
from .stock_datapath import CoreRecord,WordAction as O


@dataclass(frozen=True)
class GuardRecord:
    items: tuple
    yes: int
    no: int
    any_of: bool = False
    return_yes: bool = False
    return_no: bool = False

    @property
    def action(self):return O.GUARD3

    def bits(self):
        if not 2<=len(self.items)<=3:raise ValueError('guard bundle needs two or three comparisons')
        fields=[(int(O.GUARD3),6)]
        for i in range(3):
            address,value,op=self.items[i]if i<len(self.items)else(0,0,0)
            if address&7>=7:raise ValueError('guard source must be an RF word')
            fields.extend(((address,12),(value,8),(op,2)))
        fields.extend(((self.yes,16),(self.no,16),(len(self.items)-1,2),(int(self.any_of),1),(int(self.return_yes),1),(int(self.return_no),1),(0,3)))
        result=[]
        for value,width in fields:
            if not 0<=value<1<<width:raise ValueError('guard encoding overflow')
            result.extend(value>>i&1 for i in range(width))
        return result


def comparison(record):
    if not isinstance(record,CoreRecord):return None
    if record.action==O.NONZERO_BRANCH and not record.literal_a:return record.a,0,1
    if record.action not in(O.EQ_BRANCH,O.LT_BRANCH)or record.literal_a==record.literal_b:return None
    value=record.immediate
    if record.action==O.EQ_BRANCH:address=record.b if record.literal_a else record.a;op=0
    elif record.literal_a:address=record.b;value+=1;op=3
    else:address=record.a;op=2
    return(address,value,op)if value<256 else None


def bundle_conditions(records):
    """Replace short-circuit chains with equivalent pure AND/OR records.

    Read operands may have arbitrary16bit values. Extra speculative reads are
    side-effect free; both original continuations remain reachable.
    """
    result=[];folded=elided=0
    for pc,first in enumerate(records):
        if comparison(first)is None:result.append(first);continue
        best=None
        for any_of in(False,True):
            common=first.yes if any_of else first.no;cursor=pc;seen=set();items=[]
            while cursor not in seen and len(items)<3:
                seen.add(cursor);r=records[cursor];item=comparison(r)
                if item is None:break
                address,value,op=item
                if(any_of and r.yes==common)or(not any_of and r.no==common):following=r.no if any_of else r.yes
                elif(any_of and r.no==common)or(not any_of and r.yes==common):following=r.yes if any_of else r.no;op^=1
                else:break
                items.append((address,value,op));cursor=following
            if len(items)>=2 and(best is None or len(items)>len(best.items)):
                best=GuardRecord(tuple(items),common if any_of else cursor,cursor if any_of else common,any_of)
        if best is None:result.append(first)
        else:result.append(best);folded+=1;elided+=len(best.items)-1
    return result,dict(bundled_record_entries=folded,comparison_slots_fused=elided)
