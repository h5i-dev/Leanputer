"""Annotated source data for focused generic declaration tests; no certificates."""
from copy import deepcopy
from functools import reduce


def app(f,*xs):return reduce(lambda f,x:['app',f,x],xs,f)
def const(name):return ['const',name]
def var(i):return ['var',i]


def enum_environment(name,constructors,result_level=1):
    """Assemble source declarations, including a claimed recursor signature.

    The weighted checker independently derives and validates that signature.
    """
    family=const(name)
    rows=[dict(kind='inductive',name=name,type=['sort',1],constructors=len(constructors))]
    rows += [dict(kind='constructor',name=c,family=name,index=i,type=family)for i,c in enumerate(constructors)]
    n=len(constructors)
    tail=['pi',family,app(var(n+1),var(0))]
    for i in reversed(range(n)):tail=['pi',app(var(i),const(constructors[i])),tail]
    ty=['pi',['pi',family,['sort',result_level]],tail]
    rows.append(dict(kind='recursor',name=name+'.rec',family=name,level=result_level,type=ty))
    return rows


def enum_proof(name='Bool',constructors=('false','true'),major=0,case_values=None):
    n=len(constructors);case_values=list(range(n))if case_values is None else case_values
    env=enum_environment(name,constructors)
    family=const(name);anchor=const(constructors[0]);predicate=['pi',family,['sort',0]]
    elimination=app(const(name+'.rec'),['lam',family,family],
                    *(const(constructors[i])for i in case_values),const(constructors[major]))
    return dict(format='leanputer.generic.v1',name=name+'-elimination',environment=env,
                term=['lam',predicate,['lam',app(var(0),anchor),var(0)]],
                claim=['pi',predicate,['pi',app(var(0),anchor),app(var(1),elimination)]])


def focused_cases():
    base=enum_proof();renamed=enum_proof('Unrelated.Namespace',('α','ω'))
    three=enum_proof('Traffic',('red','amber','green'),major=2,case_values=(1,2,0))
    wrong_branch=enum_proof(major=1)
    wrong_result=deepcopy(base);wrong_result['environment'][1]['type']=['sort',1]
    wrong_ordinal=deepcopy(base);wrong_ordinal['environment'][2]['index']=0
    wrong_rec=deepcopy(base);wrong_rec['environment'][-1]['type']=['sort',0]
    fields=deepcopy(base);fields['environment'][1]['type']=['pi',['sort',0],const('Bool')]
    indexed=deepcopy(base);indexed['environment'][0]['type']=['pi',['sort',0],['sort',1]]
    prop=deepcopy(base);prop['environment'][0]['type']=['sort',0]
    return [(base,'ACCEPT'),(renamed,'ACCEPT'),(three,'ACCEPT'),(wrong_branch,'REJECT'),
            (wrong_result,'REJECT'),(wrong_ordinal,'REJECT'),(wrong_rec,'REJECT'),
            (fields,'UNSUPPORTED'),(indexed,'UNSUPPORTED'),(prop,'REJECT')]


def unary_environment(name='Parcel', carrier='Carrier', constructors=('empty','wrap'), result_level=1):
    """Mixed nullary/unary constructor source signatures, not checking answers."""
    family=const(name);field=const(carrier)
    rows=enum_environment(carrier,(carrier+'.a',carrier+'.b'))[:-1]
    rows.append(dict(kind='inductive',name=name,type=['sort',1],constructors=len(constructors)))
    rows.append(dict(kind='constructor',name=constructors[0],family=name,index=0,type=family))
    rows.append(dict(kind='constructor',name=constructors[1],family=name,index=1,type=['pi',field,family]))
    # Under motive, nullary minor, field: motive is de Bruijn index2.
    minor=['pi',field,app(var(2),app(const(constructors[1]),var(0)))]
    final=['pi',family,app(var(3),var(0))]
    ty=['pi',['pi',family,['sort',result_level]],['pi',app(var(0),const(constructors[0])),['pi',minor,final]]]
    rows.append(dict(kind='recursor',name=name+'.rec',family=name,level=result_level,type=ty))
    return rows


def unary_proof(name='Parcel',carrier='Carrier',constructors=('empty','wrap'),wrong=False):
    rows=unary_environment(name,carrier,constructors);field=const(carrier);family=const(name)
    anchor=const(carrier+'.a');other=const(carrier+'.b');predicate=['pi',field,['sort',0]]
    major=app(const(constructors[1]),anchor)
    elim=app(const(name+'.rec'),['lam',family,field],anchor,['lam',field,other if wrong else var(0)],major)
    return dict(format='leanputer.generic.v1',name=name+'-field-iota',environment=rows,
                term=['lam',predicate,['lam',app(var(0),anchor),var(0)]],
                claim=['pi',predicate,['pi',app(var(0),anchor),app(var(1),elim)]])


def unary_cases():
    base=unary_proof();renamed=unary_proof('OtherBox','Tint',('absent','present'))
    wrong=unary_proof(wrong=True)
    recursive=deepcopy(base);recursive['environment'][5]['type']=['pi',['pi',const('Parcel'),const('Parcel')],const('Parcel')]
    larger=deepcopy(base);larger['environment'][0]['type']=['sort',2]
    wrong_result=deepcopy(base);wrong_result['environment'][5]['type']=['pi',const('Carrier'),const('Carrier')]
    wrong_minor=deepcopy(base);wrong_minor['environment'][-1]['type']=enum_environment('Parcel',('empty','wrap'))[-1]['type']
    return [(base,'ACCEPT'),(renamed,'ACCEPT'),(wrong,'REJECT'),(recursive,'UNSUPPORTED'),
            (larger,'REJECT'),(wrong_result,'REJECT'),(wrong_minor,'REJECT')]
