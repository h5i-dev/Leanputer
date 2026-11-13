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
            (fields,'UNSUPPORTED'),(indexed,'UNSUPPORTED'),(prop,'UNSUPPORTED')]
