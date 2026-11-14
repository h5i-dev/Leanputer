"""Pinned quot.cpp initialization, independent executable development SPEC.

Only the four genuine kernel quotient interfaces have fixed names/types. Eq is
an ordinary checked inductive; its sole constructor name is obtained from data.
This module never supplies native inference answers.
"""
from .arena import KernelError, LevelTag, ResourceError, Tag
from .operations import representation_equal, substitute_levels
from .services import Signature
from .telescope import fold_telescope


def initialize(driver, claim):
    a,c,s = driver.a,driver.c,driver.services
    def symbol(*parts):return driver.symbols.intern_key(tuple(('str',p) for p in parts))
    eq,quot,mk,lift,ind = (symbol(*p) for p in [('Eq',),('Quot',),('Quot','mk'),('Quot','lift'),('Quot','ind')])
    names = (quot,mk,lift,ind)
    interfaces = ('type','ctor','lift','ind')
    if claim.interface not in interfaces or claim.symbol != names[interfaces.index(claim.interface)]:
        raise KernelError('invalid quotient interface binding')
    entries = getattr(s,'quotient_entries',None)
    if entries is None:
        info = s.families.get(eq);signature = s.constants.get(eq)
        if info is None or signature is None or len(signature.universe_parameters)!=1 or len(info.constructors)!=1:
            raise KernelError('Quot initialization requires the checked Eq inductive')
        refl = s.constants[info.constructors[0]]
        if len(refl.universe_parameters)!=1:
            raise KernelError('Eq constructor universe scheme')
        with c.scope():
            def sort(level):return a.mk(Tag.SORT,level)
            def pi(xs,body):return fold_telescope(a,c,tuple(xs),body,Tag.PI)
            def arrow(domain,body):
                v=c.fresh(domain);return pi([v],body)
            u=a.level(LevelTag.PARAM,signature.universe_parameters[0])
            alpha=c.fresh(sort(u),binder_info=1)
            expected=pi([alpha],arrow(alpha,arrow(alpha,sort(a.zero))))
            if not representation_equal(a,expected,signature.type):raise KernelError('unexpected Eq type')
            u=a.level(LevelTag.PARAM,refl.universe_parameters[0])
            alpha=c.fresh(sort(u),binder_info=1);x=c.fresh(alpha)
            expected=pi([alpha,x],a.app(a.const(eq,(u,)),[alpha,x,x]))
            if not representation_equal(a,expected,refl.type):raise KernelError('unexpected Eq constructor type')
        us,vs=symbol('u'),symbol('v')
        u,v=a.level(LevelTag.PARAM,us),a.level(LevelTag.PARAM,vs)
        with c.scope():
            prop=sort(a.zero);su,sv=sort(u),sort(v)
            alpha=c.fresh(su,binder_info=1)
            relation=arrow(alpha,arrow(alpha,prop));r=c.fresh(relation)
            q=a.app(a.const(quot,(u,)),[alpha,r]);x=c.fresh(alpha)
            ty=pi([alpha,r],su);mt=pi([alpha,r,x],q)
            alpha=c.fresh(su,binder_info=1);r=c.fresh(arrow(alpha,arrow(alpha,prop)),binder_info=1)
            q=a.app(a.const(quot,(u,)),[alpha,r]);x=c.fresh(alpha);y=c.fresh(alpha)
            beta=c.fresh(sv,binder_info=1);f=c.fresh(arrow(alpha,beta))
            sanity=pi([x,y],arrow(a.app(r,[x,y]),a.app(a.const(eq,(v,)),[beta,a.app(f,[x]),a.app(f,[y])])))
            lt=pi([alpha,r,beta,f],arrow(sanity,arrow(q,beta)))
            beta=c.fresh(arrow(q,prop),binder_info=1)
            minor=pi([x],a.app(beta,[a.app(a.const(mk,(u,)),[alpha,r,x])]))
            z=c.fresh(q)
            it=pi([alpha,r,beta],arrow(minor,pi([z],a.app(beta,[z]))))
        entries = {quot:Signature((us,),ty),mk:Signature((us,),mt),lift:Signature((us,vs),lt),ind:Signature((us,),it)}
        if len(set(s.constants)|set(entries))>a.limits.declarations:raise ResourceError('quotient environment')
    driver._scheme(claim.universe_parameters,claim.type)
    expected=entries[claim.symbol]
    if len(claim.universe_parameters)!=len(expected.universe_parameters):raise KernelError('quotient universe arity')
    levels={p:a.level(LevelTag.PARAM,q) for p,q in zip(expected.universe_parameters,claim.universe_parameters)}
    expected_type=substitute_levels(a,expected.type,levels)
    # Validate the untrusted interface claim in the canonical private overlay.
    # add_quot itself inserts all four names (including replacement), then sets
    # quotInit. Preserve that behavior without publishing a failed source claim.
    original=s.constants
    metadata=[(table,table.copy()) for table in (s.families,s.constructors,s.recursors)]
    try:
        s.constants={**original,**entries}
        for table,_ in metadata:
            for name in names:table.pop(name,None)
        s.ensure_type(claim.type)
        if not s.convert(claim.type,expected_type):raise KernelError('quotient type claim mismatch')
    finally:
        s.constants=original
        for table,old in metadata:table.clear();table.update(old)
    s.constants.update(entries)
    for table,_ in metadata:
        for name in names:table.pop(name,None)
    s.quotient_entries=entries
    s.quotient_names=(quot,mk,lift,ind)
