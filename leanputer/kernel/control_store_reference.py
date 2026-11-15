"""OFFLINE correspondence for the compiler's checker control store.

Not imported by stock_datapath or a production inference runner. No model
result, input, cache, instruction dispatch or type-checking answer uses this.
"""
from copy import deepcopy
from .control_reference import evaluate


class StoreReference:
    def __init__(self,store,addresses):
        self.store,self.addresses=store,addresses;self.config=store.compiler.cfg
        self.names=[n for n,w in store.compiler.layout.fields];self.last_forwards=0;self.last_records=0

    def step(self,state):
        cfg=self.config;inputs={n:int(v)for n,v in state['regs'].items()}
        a1,w1=self.addresses[0];packed=evaluate(a1,[w1.node],inputs)[0];offset=0
        for bank,port,fields in(('heap','node',('tag','a','b','c')),('stack','frame',('phase','original','depth','task','first','second')),('constants','declaration',('kind','symbol','parameters','type','value','extra'))):
            width=getattr(cfg,bank).bit_length()-1;address=(packed>>offset)&((1<<width)-1);offset+=width
            inputs.update((f'read/{port}/{name}',int(v))for name,v in zip(fields,state[bank][address]))
        a2,w2=self.addresses[1];address=evaluate(a2,[w2.node],inputs)[0];inputs['read/operand/value']=int(state['context'][address][0])
        temporary={}
        for name,operand in self.store.inputs.items():
            if name.startswith('read/'):temporary[operand.index]=inputs[name]
        def get(operand):
            if operand['space']=='literal':value=operand['index']
            elif operand['space']=='current':value=int(state['regs'][self.names[operand['index']]])
            else:value=temporary[operand['index']]
            return value&((1<<(operand.get('source_width')or operand['width']))-1)
        pc=self.store.entry_pc;fields={};banks={};count=forwards=0;return_pc=None
        for _ in range(len(self.store.records)+1):
            r=self.store.records[pc];op=r['op'];count+=1;forwards+=r['forwards'];following=r['yes']if r['yes']is not None else pc+1
            if op=='COMMIT_STEP':break
            elif op=='JUMP':pass
            elif op=='CALL_HANDLER':
                if return_pc is not None:raise AssertionError('checker handler calls must have depth one')
                return_pc=following;following=r['callee']
            elif op=='RETURN_HANDLER':
                if return_pc is None:raise AssertionError('checker handler return without a call')
                following=return_pc;return_pc=None
            elif op=='TEST_WORD_EQ':following=r['yes']if get(r['a'])==get(r['b'])else r['no']
            elif op=='TEST_WORD_LT':following=r['yes']if get(r['a'])<get(r['b'])else r['no']
            elif op=='TEST_WORD_NONZERO':following=r['yes']if get(r['a'])else r['no']
            elif op in('MOVE_WORD','WORD_ADD','WORD_SUB','EXTRACT_WORD','MERGE_WORD_SLICE'):
                a=get(r['a']);b=get(r['b'])if r['b']else 0
                if op=='MOVE_WORD':v=a
                elif op=='WORD_ADD':v=a+b
                elif op=='WORD_SUB':v=a-b
                elif op=='EXTRACT_WORD':v=a>>r['immediate']
                else:
                    lo=r['immediate']&31;length=(r['immediate']>>5)&31;shift=r['immediate']>>10
                    v=b|(((a>>lo)&((1<<length)-1))<<shift)
                temporary[r['dest']['index']]=v&((1<<r['width'])-1)
            elif op=='MERGE_CHECKER_FIELDS3':
                for dest,value in r['items']:
                    key=self.names[dest['index']];fields[key]=fields.get(key,0)|get(value)
            elif op=='MERGE_ARENA_FIELDS3':
                bank=('heap','stack','context')[r['immediate']//16];first=r['immediate']%16
                address=get(r['a'])&(getattr(cfg,bank)-1)
                if bank not in banks:banks[bank]=[0,[0]*{'heap':4,'stack':6,'context':1}[bank]]
                banks[bank][0]|=address
                for i,value in enumerate(r['items']):banks[bank][1][first+i]|=get(value)
            else:raise ValueError('unmapped typed store action '+op)
            pc=following
        else:raise ValueError('control store does not finish a semantic step within its static record count')
        result=deepcopy(state);result['regs'].update(fields)
        for bank,(address,row)in banks.items():result[bank][address]=row
        self.last_forwards=forwards+2*len(fields)+2*len(banks)+2;self.last_records=count
        return result
