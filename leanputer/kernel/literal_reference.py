"""Genuine Nat primitive algorithms, independent DEVELOPMENT SPEC ONLY.

Pinned type_checker.cpp:reduce_nat/reduce_pow, inductive.cpp:nat_lit_to_constructor,
Lean/Expr.lean:Literal.type. Never loaded by a native inference runner. Ordinary
Nat formation remains the general source transaction. Only literal uses validate
these finite kernel bindings; this is not an ordinary declaration catalog.
"""
from math import gcd
from .arena import KernelError,LevelTag,ResourceError,Tag
from .operations import representation_equal,spine
from .services import MissingOperation


# Exactly the genuine finite reduce_nat interface in the pinned C++ source.
NAT_OPERATIONS=('succ','add','sub','mul','pow','gcd','mod','div','beq','ble',
                'land','lor','xor','shiftLeft','shiftRight')


class NatPrimitives:
    def __init__(self,services,symbols):self.s,self.a,self.symbols=services,services.a,symbols

    def name(self,*parts):return self.symbols.intern_key(tuple(('str',part) for part in parts))

    def signature(self,symbol,expected):
        signature=self.s.constants.get(symbol)
        if signature is None:raise MissingOperation('required Nat primitive binding unavailable')
        if signature.universe_parameters or not self.s.convert(signature.type,expected):
            raise MissingOperation('incorrect Nat primitive binding type')
        return signature

    def validate_nat(self):
        a=self.a;nat,zero,succ=(self.name(*parts) for parts in [('Nat',),('Nat','zero'),('Nat','succ')])
        type0=a.mk(Tag.SORT,a.level(LevelTag.SUCC,a.zero));nt=a.const(nat)
        self.signature(nat,type0);self.signature(zero,nt);self.signature(succ,a.mk(Tag.PI,nt,nt))
        family=self.s.families.get(nat)
        if family is None or family.parameters or family.indices or len(family.constructors)!=2 or set(family.constructors)!={zero,succ}:
            raise MissingOperation('Nat literal bindings require the checked natural inductive')
        for symbol,fields in [(zero,0),(succ,1)]:
            info=self.s.constructors.get(symbol)
            if info is None or info.family!=nat or info.parameters or info.fields!=fields:
                raise MissingOperation('Nat constructor binding metadata')
        return nat,zero,succ

    def validate_bool(self):
        a=self.a;boolean,yes,no=(self.name(*parts) for parts in [('Bool',),('Bool','true'),('Bool','false')])
        bt=a.const(boolean);self.signature(boolean,a.mk(Tag.SORT,a.level(LevelTag.SUCC,a.zero)))
        self.signature(yes,bt);self.signature(no,bt)
        family=self.s.families.get(boolean)
        if family is None or family.parameters or family.indices or len(family.constructors)!=2 or set(family.constructors)!={yes,no}:
            raise MissingOperation('Bool primitive bindings require checked Boolean constructors')
        for symbol in (yes,no):
            info=self.s.constructors.get(symbol)
            if info is None or info.family!=boolean or info.parameters or info.fields:
                raise MissingOperation('Bool constructor binding metadata')
        return boolean,yes,no

    def literal(self,value):
        a=self.a;limbs=[]
        while value:
            a.tick();limbs.append(value&65535);value>>=16
            if len(limbs)+1>a.limits.vector_cells:raise ResourceError('Nat literal limbs')
        return a.mk(Tag.NAT,a.vec(limbs))

    def value(self,expr):
        a=self.a;row=a.expr(expr)
        if row.tag==Tag.CONST and row.a==self.name('Nat','zero') and not a.vector(row.b):return 0
        if row.tag!=Tag.NAT:return None
        limbs=a.vector(row.a)
        if limbs and not limbs[-1]:raise KernelError('noncanonical natural literal')
        value=0
        for limb in reversed(limbs):
            a.tick()
            if limb>=65536:raise KernelError('invalid literal limb')
            value=(value<<16)|limb
        return value

    def infer(self,expr):
        if self.a.expr(expr).tag!=Tag.NAT:raise KernelError('expected natural literal')
        nat,_,_=self.validate_nat();self.value(expr)
        return self.a.const(nat)

    def to_constructor(self,expr):
        _,zero,succ=self.validate_nat();value=self.value(expr)
        if value is None:raise KernelError('expected natural literal')
        return self.a.const(zero) if not value else self.a.app(self.a.const(succ),[self.literal(value-1)])

    def classify(self,head):
        row=self.a.expr(head)
        if row.tag!=Tag.CONST or self.a.vector(row.b):return None
        key=self.symbols.names[row.a]
        if len(key)==2 and key[0]==('str','Nat') and key[1][0]=='str' and key[1][1] in NAT_OPERATIONS:
            return key[1][1]
        return None

    def reduce(self,expr):
        a,s=self.a,self.s;head,args=spine(a,expr);operation=self.classify(head)
        if operation is None or len(args)!=(1 if operation=='succ' else 2):return None
        nat,_,_=self.validate_nat();nt=a.const(nat)
        result_type=nt
        if operation in ('beq','ble'):
            boolean,yes,no=self.validate_bool();result_type=a.const(boolean)
        expected=a.mk(Tag.PI,nt,result_type)
        if operation!='succ':expected=a.mk(Tag.PI,nt,expected)
        self.signature(a.expr(head).a,expected)
        values=[]
        for arg in args:
            value=self.value(s.whnf(arg))
            if value is None:return None
            values.append(value)
        x=values[0];y=values[1] if len(values)>1 else 0
        # The exponent cap is a pinned semantic neutral result, not RESOURCE.
        if operation=='pow' and y>1<<24:return None
        if operation in ('beq','ble'):
            return a.const(yes if (x==y if operation=='beq' else x<=y) else no)
        # Reject impossible physical result sizes before host allocation in this
        # independent SPEC. Weighted arithmetic will detect limb/heap exhaustion.
        max_bits=16*a.limits.vector_cells
        if operation=='shiftLeft' and x and x.bit_length()+y>max_bits:raise ResourceError('Nat result limb bound')
        if operation=='pow' and x>1 and (x.bit_length()-1)*y>max_bits:raise ResourceError('Nat result limb bound')
        if operation=='succ':result=x+1
        elif operation=='add':result=x+y
        elif operation=='sub':result=max(0,x-y)
        elif operation=='mul':result=x*y
        elif operation=='pow':result=pow(x,y)
        elif operation=='gcd':result=gcd(x,y)
        elif operation=='mod':result=x%y if y else x
        elif operation=='div':result=x//y if y else 0
        elif operation=='land':result=x&y
        elif operation=='lor':result=x|y
        elif operation=='xor':result=x^y
        elif operation=='shiftLeft':result=x<<y if x else 0
        elif operation=='shiftRight':result=x>>y if y<x.bit_length() else 0
        else:raise AssertionError(operation)
        return self.literal(result)
