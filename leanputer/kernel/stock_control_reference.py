"""OFFLINE encoding correspondence only; never imported by inference.

This reference evaluates compiler records to find lowering bugs before model
allocation. It does not produce inference inputs, cache values or answers.
"""
from copy import deepcopy
from collections import Counter
from .stock_control import main_address
from .stock_datapath import CoreRecord,FieldRecord,WordAction as O
from .stock_guard import GuardRecord


class NativeControlReference:
    def __init__(self,program,state):
        self.program=program;self.names=[n for n,w in program.store.compiler.layout.fields]
        self.rf=[[0]*7 for _ in range(512)];self.dirty=[[False]*7 for _ in range(136)]
        self.banks={name:deepcopy(state[name])for name in('heap','stack','context','constants')}
        self.queue=[];self.pc=0;self.status=self.reason=self.result=0;self.records=self.forwards=self.semantic_steps=0
        self.forward_costs=Counter()
        self.region_forward_costs=Counter()
        self.return_pc=None
        for i,name in enumerate(self.names):self.write(main_address(i),int(state['regs'][name]))

    def read(self,address):return self.rf[address>>3][address&7]if address&7<7 else 0
    def write(self,address,value):
        if address&7>=7:raise AssertionError('native compiler selected invalid RF slot')
        self.rf[address>>3][address&7]=value&65535

    def state(self):
        return dict(regs={name:self.read(main_address(i))for i,name in enumerate(self.names)},**deepcopy(self.banks))

    def step(self):
        r=self.program.records[self.pc];self.records+=1;following=r.yes;forwards=1;committed=False
        if isinstance(r,GuardRecord):
            values=[]
            for address,value,op in r.items:
                word=self.read(address);values.append((word==value,word!=value,word<value,word>=value)[op])
            passed=any(values)if r.any_of else all(values);following=r.yes if passed else r.no
            if r.return_yes if passed else r.return_no:
                if self.return_pc is None:raise AssertionError('bundled guard return without handler call')
                following=self.return_pc;self.return_pc=None
        elif isinstance(r,FieldRecord):
            forwards=0
            for dest,value,literal in r.items:
                value=value if literal else self.read(value);logical=dest>>4;slot=dest&7;shadow=dest|8
                if self.dirty[logical][slot]:self.write(shadow,self.read(shadow)|value);forwards+=1
                else:
                    self.write(shadow,value);self.dirty[logical][slot]=True
                    field=(dest&7)|((dest>>4)<<3);row,qs=divmod(len(self.queue),7)
                    self.write(((272+row)<<3)|qs,field);self.queue.append(dest);forwards+=2
        else:
            a=r.immediate if r.literal_a else self.read(r.a);b=r.immediate if r.literal_b else self.read(r.b);op=r.action
            if r.capture_return:
                if self.return_pc is not None:raise AssertionError('nested fused native handler call')
                self.return_pc=r.auxiliary
            if op==O.MOVE:self.write(r.dest,a)
            elif op==O.ADD:self.write(r.dest,a+b)
            elif op==O.SUB:self.write(r.dest,a-b)
            elif op==O.AND:self.write(r.dest,a&b)
            elif op==O.OR:self.write(r.dest,a|b)
            elif op==O.XOR:self.write(r.dest,a^b)
            elif op==O.SHR:self.write(r.dest,a>>1)
            elif op==O.SHL:self.write(r.dest,a<<1)
            elif op in(O.SHR_LOOP,O.SHL_LOOP):
                count=r.auxiliary&15
                if not count:raise AssertionError('zero bounded shift count')
                self.write(r.dest,a>>count if op==O.SHR_LOOP else a<<count);forwards=count
            elif op==O.EQ_BRANCH:following=r.yes if a==b else r.no
            elif op==O.LT_BRANCH:following=r.yes if a<b else r.no
            elif op==O.NONZERO_BRANCH:following=r.yes if a else r.no
            elif op in(O.SWITCH4,O.SWITCH8):
                size=16 if op==O.SWITCH4 else 256;offset=(a-b)&65535
                following=r.auxiliary+offset if offset<size else r.yes
            elif op==O.INVALID_BRANCH:
                from .stock_bounds import evaluate
                invalid=any(evaluate(tree,self.read(main_address(index)))for index,tree in self.program.bounds_schema)
                following=r.yes if invalid else r.no
            elif op==O.JUMP:pass
            elif op==O.CLEAR_RF_ROW:
                row=r.dest>>3;self.rf[row]=[0]*7
                if row<272 and row&1:self.dirty[row>>1]=[False]*7
            elif op in(O.HEAP_ROW_READ,O.FRAME_ROW_READ,O.CONTEXT_ROW_READ,O.DECLARATION_ROW_READ):
                if r.dest&7:raise AssertionError('source row load must have aligned destination')
                bank={O.HEAP_ROW_READ:'heap',O.FRAME_ROW_READ:'stack',O.CONTEXT_ROW_READ:'context',O.DECLARATION_ROW_READ:'constants'}[op]
                rows=self.banks[bank]
                for field,value in enumerate(rows[a&(len(rows)-1)]):self.write(r.dest+field,value)
                forwards=2
            elif op==O.CALL_HANDLER:
                if self.return_pc is not None:raise AssertionError('nested native handler call')
                self.return_pc=r.no
            elif op==O.RETURN_HANDLER:
                if self.return_pc is None:raise AssertionError('unpaired native handler return')
                following=self.return_pc;self.return_pc=None
            elif op==O.COMMIT_FIELDS:
                forwards=2*len(self.queue)+1
                for dest in self.queue:
                    self.write(dest,self.read(dest|8));self.dirty[dest>>4][dest&7]=False
                self.queue.clear();committed=True;self.semantic_steps+=1
            elif op==O.PUBLISH_RESULT:
                self.status=a;self.reason=b;self.result=self.read(r.dest)
            elif op==O.STOP_OK:self.status=1
            elif op==O.STOP_INVALID:self.status=2;self.reason=1
            elif op in(O.HEAP_READ,O.HEAP_WRITE,O.FRAME_READ,O.FRAME_WRITE,O.CONTEXT_READ,O.CONTEXT_WRITE,O.DECLARATION_READ):
                bank={O.HEAP_READ:'heap',O.HEAP_WRITE:'heap',O.FRAME_READ:'stack',O.FRAME_WRITE:'stack',O.CONTEXT_READ:'context',O.CONTEXT_WRITE:'context',O.DECLARATION_READ:'constants'}[op]
                rows=self.banks[bank];row=rows[a&(len(rows)-1)];field=r.auxiliary&7
                if field>=len(row):raise AssertionError('invalid compiler arena field')
                if op in(O.HEAP_WRITE,O.FRAME_WRITE,O.CONTEXT_WRITE):row[field]=b
                else:self.write(r.dest,row[field]);forwards=2
            else:raise ValueError('unmapped native compiler reference '+op.name)
        if isinstance(r,CoreRecord)and(r.return_yes or r.return_no):
            false=(op==O.EQ_BRANCH and a!=b)or(op==O.LT_BRANCH and a>=b)or(op==O.NONZERO_BRANCH and not a)
            if r.return_no if false else r.return_yes:
                if self.return_pc is None:raise AssertionError('fused handler edge without call')
                following=self.return_pc;self.return_pc=None
        self.region_forward_costs[self.program.record_regions[self.pc]]+=forwards
        self.pc=following;self.forwards+=forwards
        self.forward_costs['MERGE_FIELDS3'if isinstance(r,FieldRecord)else r.action.name]+=forwards
        return committed
