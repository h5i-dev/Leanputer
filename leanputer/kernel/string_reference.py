"""Pinned String literal helper construction, independent DEVELOPMENT SPEC.

The development services use this independent specification; no native loader
imports it or receives its results.
String/Char/List formation is general source data; only the finite literal hook
has fixed helper names and required specialized signatures.
"""
from .arena import KernelError,LevelTag,Tag
from .operations import substitute_levels
from .services import MissingOperation
from .telescope import fold_telescope


class StringPrimitives:
    def __init__(self,services,symbols):self.s,self.a,self.c,self.symbols=services,services.a,services.c,symbols

    def name(self,*parts):return self.symbols.intern_key(tuple(('str',part)for part in parts))

    def signature(self,symbol,levels,expected):
        signature=self.s.constants.get(symbol)
        if signature is None:raise MissingOperation('String literal helper binding unavailable')
        if len(signature.universe_parameters)!=len(levels):raise MissingOperation('String helper universe arity')
        type_ref=substitute_levels(self.a,signature.type,dict(zip(signature.universe_parameters,levels)))
        if not self.s.convert(type_ref,expected):raise MissingOperation('String literal helper signature mismatch')

    def validate(self):
        from .literal_reference import NatPrimitives
        # These are genuine helpers from inductive.cpp, not a layout catalog.
        a,c=self.a,self.c
        nat,_,_=NatPrimitives(self.s,self.symbols).validate_nat()
        string,char,list_,nil,cons,ofnat,oflist=(self.name(*parts)for parts in [
            ('String',),('Char',),('List',),('List','nil'),('List','cons'),('Char','ofNat'),('String','ofList')])
        type0=a.mk(Tag.SORT,a.level(LevelTag.SUCC,a.zero))
        st,ct,nt=a.const(string),a.const(char),a.const(nat)
        listchar=a.app(a.const(list_,(a.zero,)),[ct])
        self.signature(string,(),type0);self.signature(char,(),type0)
        self.signature(list_,(a.zero,),a.mk(Tag.PI,type0,type0))
        with c.scope():
            alpha=c.fresh(type0)
            la=a.app(a.const(list_,(a.zero,)),[alpha])
            self.signature(nil,(a.zero,),fold_telescope(a,c,[alpha],la))
            hd=c.fresh(alpha);tail=c.fresh(la)
            self.signature(cons,(a.zero,),fold_telescope(a,c,[alpha,hd,tail],la))
        self.signature(ofnat,(),a.mk(Tag.PI,nt,ct))
        self.signature(oflist,(),a.mk(Tag.PI,listchar,st))
        return string,char,list_,nil,cons,ofnat,oflist

    def infer(self,expr):
        if self.a.expr(expr).tag!=Tag.STRING:raise KernelError('expected String literal')
        symbol=self.name('String')
        type0=self.a.mk(Tag.SORT,self.a.level(LevelTag.SUCC,self.a.zero))
        self.signature(symbol,(),type0)
        return self.a.const(symbol)

    def to_constructor(self,expr):
        from .literal_reference import NatPrimitives
        a=self.a;row=a.expr(expr)
        if row.tag!=Tag.STRING:raise KernelError('expected String literal')
        _,char,list_,nil,cons,ofnat,oflist=self.validate()
        # Python decoding is only an independent expected-data operation here.
        # Native code must decode original bytes in weighted transitions.
        try:scalars=bytes(a.vector(row.a)).decode('utf8')
        except UnicodeError as error:raise KernelError('invalid Unicode string transport')from error
        ct=a.const(char);result=a.app(a.const(nil,(a.zero,)),[ct])
        prefix=a.app(a.const(cons,(a.zero,)),[ct]);numbers=NatPrimitives(self.s,self.symbols)
        for scalar in reversed(scalars):
            a.tick();character=a.app(a.const(ofnat),[numbers.literal(ord(scalar))])
            result=a.app(prefix,[character,result])
        return a.app(a.const(oflist),[result])
