"""Typed word/guard capture of the general kernel rule generators.

Compile-time only. These objects are not an inference interpreter. Scalar
values retain their widths; guards are structured control predicates rather
than an expansion into a generic Boolean gate tape.
"""
from dataclasses import dataclass
from collections import Counter


@dataclass(frozen=True)
class Bit:
    word: int
    index: int


@dataclass(frozen=True)
class Node:
    op: str
    width: int
    args: tuple = ()
    data: object = None


class Word:
    def __init__(self, builder, node):
        self.builder, self.node = builder, node

    def __len__(self): return self.builder.nodes[self.node].width
    def __iter__(self): return (Bit(self.node, i) for i in range(len(self)))
    def __getitem__(self, key): return tuple(self)[key]
    def __add__(self, other): return tuple(self)+tuple(other)
    def __radd__(self, other): return tuple(other)+tuple(self)


class TypedBuilder:
    def __init__(self, names, optimized=True):
        self.nodes=[]; self.cache={}; self.optimized=optimized; self.inputs=[]
        self.input_words={}
        groups={}
        for name in names:
            word,index=name.rsplit('/',1);groups.setdefault(word,[]).append(int(index))
        for name,indices in groups.items():
            if indices!=list(range(len(indices))):raise ValueError('noncontiguous typed input word')
            word=self.node('input',len(indices),data=name)
            self.input_words[name]=word.node;self.inputs.extend(word)
        self.zero=next(iter(self.const(0,1))); self.one=next(iter(self.const(1,1)))

    def node(self,op,width,args=(),data=None):
        key=Node(op,width,tuple(args),data)
        if key not in self.cache:
            self.cache[key]=len(self.nodes);self.nodes.append(key)
        return Word(self,self.cache[key])

    def const(self,value,width):
        value=int(value)
        if width<0 or not 0<=value<1<<width:raise ValueError('typed constant outside word')
        return self.node('const',width,data=value)

    def word(self,value):
        if isinstance(value,Word):return value
        if isinstance(value,Bit):value=(value,)
        bits=tuple(value)
        if not bits:return self.const(0,0)
        if any(not isinstance(b,Bit) for b in bits):raise TypeError('expected typed bit sequence')
        constants=[]
        for b in bits:
            n=self.nodes[b.word];constants.append((n.data>>b.index)&1 if n.op=='const'else None)
        if all(v is not None for v in constants):return self.const(sum(v<<i for i,v in enumerate(constants)),len(bits))
        # Canonical contiguous spans and zero extension stay word operations.
        first=bits[0];length=0
        while length<len(bits) and bits[length]==Bit(first.word,first.index+length):length+=1
        if length==len(bits):
            base=Word(self,first.word)
            if first.index==0 and length==len(base):return base
            return self.node('slice',length,(first.word,),first.index)
        if length and first.index==0 and all(v==0 for v in constants[length:]):
            return self.fit(Word(self,first.word),len(bits)) if length==self.nodes[first.word].width else self.node('splice',len(bits),tuple(b.word for b in bits),tuple(b.index for b in bits))
        return self.node('splice',len(bits),tuple(b.word for b in bits),tuple(b.index for b in bits))

    def fit(self,value,width):
        value=self.word(value);n=self.nodes[value.node]
        if n.width==width:return value
        if n.op=='const':return self.const(n.data&((1<<width)-1),width)
        if width<n.width:return self.node('slice',width,(value.node,),0)
        return self.node('extend',width,(value.node,))

    def pred(self,value):
        value=self.word((value,))if isinstance(value,Bit)else self.word(value)
        if len(value)!=1:raise ValueError('predicate must be one bit')
        return value.node

    def truth(self,node):
        n=self.nodes[node];return n.data if n.op=='const'else None

    def boolean(self,op,args):
        operands=[]
        for arg in args:
            i=self.pred(arg);n=self.nodes[i];v=self.truth(i)
            if v is not None:
                if v==(0 if op=='all'else 1):return self.zero if v==0 else self.one
                continue
            # Retain named validity/phase guard structure. Flattening destroys
            # sharing and duplicates a whole preflight in every phase path.
            operands.append(i)
        operands=tuple(sorted(set(operands)))
        if not operands:return self.one if op=='all'else self.zero
        if len(operands)==1:return Bit(operands[0],0)
        return Bit(self.node(op,1,operands).node,0)

    def AND(self,*args):return self.boolean('all',args)
    def OR(self,*args):return self.boolean('any',args)
    def NOT(self,arg):
        i=self.pred(arg);v=self.truth(i)
        if v is not None:return self.one if v==0 else self.zero
        n=self.nodes[i]
        return Bit(n.args[0],0)if n.op=='not'else Bit(self.node('not',1,(i,)).node,0)

    def binary(self,op,a,b):
        a,b=self.word(a),self.word(b);width=max(len(a),len(b));a,b=self.fit(a,width),self.fit(b,width)
        if op=='eq'and a.node>b.node:a,b=b,a
        x,y=self.nodes[a.node],self.nodes[b.node]
        if x.op==y.op=='const':
            v={'add':lambda:x.data+y.data,'sub':lambda:x.data-y.data,'eq':lambda:int(x.data==y.data),'ult':lambda:int(x.data<y.data)}[op]()
            return self.const(v&((1<<(1 if op in('eq','ult')else width))-1),1 if op in('eq','ult')else width)
        if a.node==b.node and op in('sub','eq','ult'):return self.const(int(op=='eq'),1 if op in('eq','ult')else width)
        return self.node(op,1 if op in('eq','ult')else width,(a.node,b.node))

    def eq(self,a,b):return Bit(self.binary('eq',a,b).node,0)
    def lt(self,a,b):return Bit(self.binary('ult',a,b).node,0)
    def add(self,a,b):return self.binary('add',a,b)
    def sub(self,a,b,borrow_in=False):
        if borrow_in:b=self.add(b,self.const(1,len(self.word(b))))
        return self.binary('sub',a,b),self.lt(a,b)
    def mux(self,condition,yes,no):
        p=self.pred(condition);yes,no=self.word(yes),self.word(no);width=max(len(yes),len(no));yes,no=self.fit(yes,width),self.fit(no,width)
        v=self.truth(p)
        if v is not None:return yes if v else no
        if yes.node==no.node:return yes
        return self.node('choose',width,(p,yes.node,no.node))

    def compile(self,outputs,target=None):
        # Address programs retain typed packed outputs, not Boolean gates.
        output=self.word(outputs)
        return self,output

    def statistics(self):return dict(nodes=len(self.nodes),operators=dict(Counter(n.op for n in self.nodes)))
