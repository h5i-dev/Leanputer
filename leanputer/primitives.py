"""Fixed kernel families; never unchecked user-environment axioms.

Only the named families/constructors below are intrinsic. Their closed
schemas are checker rules compiled into weights. General datatype declarations
and recursors outside this catalog remain unsupported.
"""

from functools import reduce

PRIMITIVE_CODES = {'False':0,'False.rec':1,'Iff':2,'Iff.intro':3,'And':4,'And.intro':5,'Eq':6,'Eq.refl':7,'Eq.rec':8,'True':9,'True.intro':10,
                   'True.rec':11,'And.rec':12,'Iff.rec':13,'Nonempty':14,'Nonempty.intro':15,'Nonempty.rec':16,
                   'Exists':17,'Exists.intro':18,'Exists.rec':19,'Or':20,'Or.inl':21,'Or.inr':22,'Or.rec':23,
                   'Quot':24,'Quot.mk':25,'Quot.ind':26,'Quot.lift':27,
                   'Decidable':28,'Decidable.isFalse':29,'Decidable.isTrue':30,'Decidable.rec':31,
                   'Subtype':32,'Subtype.mk':33,'Subtype.rec':34,'HEq':35,'HEq.refl':36,'HEq.rec':37,
                   'Bool':38,'Bool.false':39,'Bool.true':40,'Bool.rec':41,
                   'Option':42,'Option.none':43,'Option.some':44,'Option.rec':45}
PRIMITIVE_UNIVERSES = {'False.rec':1,'Eq':1,'Eq.refl':1,'Eq.rec':2,'True.rec':1,'And.rec':1,'Iff.rec':1,
                       'Nonempty':1,'Nonempty.intro':1,'Nonempty.rec':1,'Exists':1,'Exists.intro':1,'Exists.rec':1,
                       'Quot':1,'Quot.mk':1,'Quot.ind':1,'Quot.lift':2,'Decidable.rec':1,
                       'Subtype':1,'Subtype.mk':1,'Subtype.rec':2,'HEq':1,'HEq.refl':1,'HEq.rec':2,'Bool.rec':1,
                       'Option':1,'Option.none':1,'Option.some':1,'Option.rec':2}
PROJECTION_FAMILIES = {'Iff':0,'And':2,'Subtype':4}
REC_ARITIES = {8:6,11:3,12:5,13:5,16:4,19:5,23:6,26:5,27:6,31:5,34:5,37:7,41:4,45:5}
REC_CONSTRUCTORS = {12:(5,),13:(3,),16:(15,),19:(18,),23:(21,22),26:(25,),27:(25,),31:(29,30)}
REC_MAJOR_ARITIES = {12:4,13:4,16:2,19:4,23:3,26:3,27:3,31:2}

# Fixed nonrecursive records, not admission of arbitrary input declarations.
ONE_FIELD_RECORDS = {
    'Inhabited':dict(code=46, projection=6, constructor='mk', field='value', data=True, type_carrier=False),
    'Mul':dict(code=49, projection=7, constructor='mk', field='binary', data=True, type_carrier=True),
    'Add':dict(code=52, projection=8, constructor='mk', field='binary', data=True, type_carrier=True),
    'Subsingleton':dict(code=55, projection=9, constructor='intro', field='equality', data=False, type_carrier=False),
    'Zero':dict(code=58, projection=10, constructor='mk', field='value', data=True, type_carrier=True),
    'One':dict(code=61, projection=11, constructor='mk', field='value', data=True, type_carrier=True),
    'OfNat':dict(code=68, projection=12, constructor='mk', field='value', data=True, type_carrier=True, parameters=2),
    'LT':dict(code=74, projection=13, constructor='mk', field='relation', data=True, type_carrier=True),
    'LE':dict(code=77, projection=14, constructor='mk', field='relation', data=True, type_carrier=True),
}
for _family, _record in ONE_FIELD_RECORDS.items():
    for _offset, _name in enumerate((_family, _family+'.'+_record['constructor'], _family+'.rec')):
        PRIMITIVE_CODES[_name]=_record['code']+_offset
        PRIMITIVE_UNIVERSES[_name]=2 if _offset==2 else 1
    PROJECTION_FAMILIES[_family]=_record['projection']
    REC_ARITIES[_record['code']+2]=_record.get('parameters',1)+3
    if not _record['data']:
        REC_CONSTRUCTORS[_record['code']+2]=(_record['code']+1,)
        REC_MAJOR_ARITIES[_record['code']+2]=2
PROJECTION_ARITIES={family:1 if family in ONE_FIELD_RECORDS else 2 for family in PROJECTION_FAMILIES}
PROJECTION_COUNT=max(PROJECTION_FAMILIES[family]+count for family,count in PROJECTION_ARITIES.items())
PRIMITIVE_CODES.update({'Nat':64,'Nat.zero':65,'Nat.succ':66,'Nat.rec':67})
PRIMITIVE_UNIVERSES['Nat.rec']=1
PRIMITIVE_CODES.update({'PUnit':71,'PUnit.unit':72,'PUnit.rec':73})
PRIMITIVE_UNIVERSES.update({'PUnit':1,'PUnit.unit':1,'PUnit.rec':2})
# Nat.succ is also a reducible head on literal arguments.
REC_ARITIES.update({66:1,67:4,73:3})


def primitive_code(expression): return PRIMITIVE_CODES[expression[1]]


def _close_schema(term,names=()):
    # Resolve names only in fixed compiler-authored kernel rule schemas.
    if term[0]=='named': return ('var',len(names)-1-names.index(term[1]))
    if term[0]=='bind': return ('pi',_close_schema(term[2],names),_close_schema(term[3],names+(term[1],)))
    if term[0]=='app': return ('app',_close_schema(term[1],names),_close_schema(term[2],names))
    return term


def primitive_type(expression):
    name = expression[1]
    sort = ('sort',0)
    var = lambda i:('var',i)
    app = lambda f,a:('app',f,a)
    pi = lambda a,b:('pi',a,b)
    if name.startswith('PUnit'):return _unit_type(expression)
    if name in ('Nat','Nat.zero','Nat.succ','Nat.rec'):return _natural_type(expression)
    if name.split('.')[0] in ONE_FIELD_RECORDS:return _one_record_type(expression)
    if name.startswith('Option'):return _option_type(expression)
    if name.startswith('Bool'):return _bool_type(expression)
    if name.startswith('HEq'):return _heq_type(expression)
    if name.startswith('Subtype'):return _subtype_type(expression)
    if name.startswith('Decidable'):return _decidable_type(expression)
    if name in ('Quot','Quot.mk','Quot.ind','Quot.lift'):return _quotient_type(expression)
    if name in ('True.rec','And.rec','Iff.rec','Nonempty','Nonempty.intro','Nonempty.rec','Exists','Exists.intro','Exists.rec','Or','Or.inl','Or.inr','Or.rec'):
        return _positive_type(expression)
    if name in ('Eq','Eq.refl','Eq.rec'):
        variable=lambda n:('named',n)
        binder=lambda n,t,b:('bind',n,t,b)
        apps=lambda f,*xs: reduce(lambda a,b:('app',a,b),xs,f)
        result_level=expression[2]
        alpha_level=expression[3] if name=='Eq.rec' else expression[2]
        alpha,anchor,end,motive,proof=map(variable,('alpha','anchor','end','motive','proof'))
        eq=lambda a,b:apps(('builtin','Eq',alpha_level),alpha,a,b)
        refl=apps(('builtin','Eq.refl',alpha_level),alpha,anchor)
        if name=='Eq': tree=binder('alpha',('sort',alpha_level),binder('anchor',alpha,binder('end',alpha,sort)))
        elif name=='Eq.refl': tree=binder('alpha',('sort',alpha_level),binder('anchor',alpha,eq(anchor,anchor)))
        else:
            motive_type=binder('motive_end',alpha,binder('motive_proof',eq(anchor,variable('motive_end')),('sort',result_level)))
            minor_type=apps(motive,anchor,refl)
            tree=binder('alpha',('sort',alpha_level),binder('anchor',alpha,binder('motive',motive_type,
                 binder('minor',minor_type,binder('end',alpha,binder('proof',eq(anchor,end),apps(motive,end,proof)))))))
        return _close_schema(tree)
    if name=='False': return sort
    if name=='True': return sort
    if name=='True.intro': return ('builtin','True')
    if name=='False.rec':
        false = ('builtin','False')
        return pi(pi(false,('sort',expression[2])),pi(false,app(var(1),var(0))))
    if name in ('Iff','And'): return pi(sort,pi(sort,sort))
    family = ('builtin',name.split('.')[0])
    result = app(app(family,var(3)),var(2))
    if name=='And.intro': return pi(sort,pi(sort,pi(var(1),pi(var(1),result))))
    if name=='Iff.intro': return pi(sort,pi(sort,pi(pi(var(1),var(1)),pi(pi(var(1),var(3)),result))))
    raise ValueError('unknown intrinsic typing rule')


def _positive_type(expression):
    """Closed schemas for this fixed nonrecursive positive primitive catalog."""
    name=expression[1];sort=('sort',0)
    v=lambda n:('named',n)
    bind=lambda n,t,b:('bind',n,t,b)
    apps=lambda f,*xs:reduce(lambda a,b:('app',a,b),xs,f)
    builtin=lambda n:('builtin',n)+tuple(expression[2:]) if n.startswith(('Nonempty','Exists')) else ('builtin',n)
    alpha,p,q,motive,major=map(v,('alpha','p','q','motive','major'))
    if name=='True.rec':
        return _close_schema(bind('motive',bind('motive_arg',('builtin','True'),('sort',expression[2])),
            bind('minor',apps(motive,('builtin','True.intro')),bind('major',('builtin','True'),apps(motive,major)))))
    family=name.split('.')[0]
    if family in ('And','Iff','Or'):
        ty=apps(('builtin',family),p,q)
        if name=='Or':return ('pi',sort,('pi',sort,sort))
        if name in ('Or.inl','Or.inr'):
            field=p if name=='Or.inl' else q
            return _close_schema(bind('p',sort,bind('q',sort,bind('field',field,ty))))
        result_sort=('sort',expression[2]) if family!='Or' else sort
        motive_type=bind('motive_arg',ty,result_sort)
        if family=='Or':
            left=bind('left',p,apps(motive,apps(('builtin','Or.inl'),p,q,v('left'))))
            right=bind('right',q,apps(motive,apps(('builtin','Or.inr'),p,q,v('right'))))
            tail=bind('minor_left',left,bind('minor_right',right,bind('major',ty,apps(motive,major))))
        else:
            left=p if family=='And' else bind('left_arg',p,q)
            right=q if family=='And' else bind('right_arg',q,p)
            minor=bind('left',left,bind('right',right,apps(motive,apps(('builtin',family+'.intro'),p,q,v('left'),v('right')))))
            tail=bind('minor',minor,bind('major',ty,apps(motive,major)))
        return _close_schema(bind('p',sort,bind('q',sort,bind('motive',motive_type,tail))))
    carrier_sort=('sort',expression[2])
    ty=apps(builtin(family),alpha,*([p]if family=='Exists' else []))
    pred=bind('pred_arg',alpha,sort)
    wrap=lambda tail:bind('alpha',carrier_sort,bind('p',pred,tail) if family=='Exists' else tail)
    if name==family:return _close_schema(wrap(sort))
    ctor=apps(builtin(family+'.intro'),alpha,*([p]if family=='Exists' else []),v('witness'),*([v('evidence')]if family=='Exists' else []))
    fields=lambda tail:bind('witness',alpha,bind('evidence',apps(p,v('witness')),tail) if family=='Exists' else tail)
    if name==family+'.intro':return _close_schema(wrap(fields(ty)))
    minor=fields(apps(motive,ctor))
    return _close_schema(wrap(bind('motive',bind('motive_arg',ty,sort),bind('minor',minor,bind('major',ty,apps(motive,major))))))


def _quotient_type(expression):
    """Fixed kernel quotient rules; Quot.sound remains an explicit axiom in Γ."""
    name=expression[1];u=expression[2]
    v=lambda n:('named',n)
    bind=lambda n,t,b:('bind',n,t,b)
    apps=lambda f,*xs:reduce(lambda a,b:('app',a,b),xs,f)
    alpha,relation,beta,fn,motive,major=map(v,('alpha','relation','beta','fn','motive','major'))
    relation_type=bind('rel_left',alpha,bind('rel_right',alpha,('sort',0)))
    quotient=apps(('builtin','Quot',u),alpha,relation)
    mk=lambda witness:apps(('builtin','Quot.mk',u),alpha,relation,witness)
    wrap=lambda tail:bind('alpha',('sort',u),bind('relation',relation_type,tail))
    if name=='Quot':tree=wrap(('sort',u))
    elif name=='Quot.mk':tree=wrap(bind('witness',alpha,quotient))
    elif name=='Quot.ind':
        tree=wrap(bind('motive',bind('motive_arg',quotient,('sort',0)),
             bind('minor',bind('witness',alpha,apps(motive,mk(v('witness')))),bind('major',quotient,apps(motive,major)))))
    else:
        result_level=expression[3]
        equality=apps(('builtin','Eq',result_level),beta,apps(fn,v('left')),apps(fn,v('right')))
        respect=bind('left',alpha,bind('right',alpha,bind('equivalent',apps(relation,v('left'),v('right')),equality)))
        tree=wrap(bind('beta',('sort',result_level),bind('fn',bind('fn_arg',alpha,beta),
                  bind('respect',respect,bind('major',quotient,beta)))))
    return _close_schema(tree)


def _decidable_type(expression):
    name=expression[1];sort=('sort',0)
    v=lambda n:('named',n)
    bind=lambda n,t,b:('bind',n,t,b)
    apps=lambda f,*xs:reduce(lambda a,b:('app',a,b),xs,f)
    p,motive,major=map(v,('p','motive','major'))
    decidable=apps(('builtin','Decidable'),p)
    negative=bind('neg_arg',p,('builtin','False'))
    if name=='Decidable':return ('pi',sort,('sort',1))
    if name in ('Decidable.isFalse','Decidable.isTrue'):
        return _close_schema(bind('p',sort,bind('evidence',negative if name.endswith('isFalse') else p,decidable)))
    false_minor=bind('negative',negative,apps(motive,apps(('builtin','Decidable.isFalse'),p,v('negative'))))
    true_minor=bind('positive',p,apps(motive,apps(('builtin','Decidable.isTrue'),p,v('positive'))))
    tree=bind('p',sort,bind('motive',bind('motive_arg',decidable,('sort',expression[2])),
         bind('minor_false',false_minor,bind('minor_true',true_minor,bind('major',decidable,apps(motive,major))))))
    return _close_schema(tree)


def _subtype_type(expression):
    name=expression[1]
    carrier=expression[3] if name=='Subtype.rec' else expression[2]
    v=lambda n:('named',n)
    bind=lambda n,t,b:('bind',n,t,b)
    apps=lambda f,*xs:reduce(lambda a,b:('app',a,b),xs,f)
    alpha,p,motive,major=map(v,('alpha','p','motive','major'))
    subtype=apps(('builtin','Subtype',carrier),alpha,p)
    pred=bind('pred_arg',alpha,('sort',0))
    wrap=lambda tail:bind('alpha',('sort',carrier),bind('p',pred,tail))
    if name=='Subtype':tree=wrap(('sort',-3 if carrier<0 else max(1,carrier)))
    elif name=='Subtype.mk':tree=wrap(bind('value',alpha,bind('property',apps(p,v('value')),subtype)))
    else:
        ctor=apps(('builtin','Subtype.mk',carrier),alpha,p,v('value'),v('property'))
        minor=bind('value',alpha,bind('property',apps(p,v('value')),apps(motive,ctor)))
        tree=wrap(bind('motive',bind('motive_arg',subtype,('sort',expression[2])),
                  bind('minor',minor,bind('major',subtype,apps(motive,major)))))
    return _close_schema(tree)


def _heq_type(expression):
    name=expression[1];carrier=expression[3] if name=='HEq.rec' else expression[2]
    v=lambda n:('named',n)
    bind=lambda n,t,b:('bind',n,t,b)
    apps=lambda f,*xs:reduce(lambda a,b:('app',a,b),xs,f)
    alpha,anchor,beta,end,motive,proof=map(v,('alpha','anchor','beta','end','motive','proof'))
    heq=lambda b,e:apps(('builtin','HEq',carrier),alpha,anchor,b,e)
    refl=apps(('builtin','HEq.refl',carrier),alpha,anchor)
    if name=='HEq':tail=bind('beta',('sort',carrier),bind('end',beta,('sort',0)))
    elif name=='HEq.refl':tail=heq(alpha,anchor)
    else:
        motive_type=bind('motive_beta',('sort',carrier),bind('motive_end',v('motive_beta'),
            bind('motive_proof',heq(v('motive_beta'),v('motive_end')),('sort',expression[2]))))
        tail=bind('motive',motive_type,bind('minor',apps(motive,alpha,anchor,refl),
             bind('beta',('sort',carrier),bind('end',beta,bind('proof',heq(beta,end),apps(motive,beta,end,proof))))))
    return _close_schema(bind('alpha',('sort',carrier),bind('anchor',alpha,tail)))


def _bool_type(expression):
    name=expression[1]
    if name=='Bool':return ('sort',1)
    if name in ('Bool.false','Bool.true'):return ('builtin','Bool')
    v=lambda n:('named',n)
    bind=lambda n,t,b:('bind',n,t,b)
    app=lambda f,a:('app',f,a)
    boolean=('builtin','Bool');motive=v('motive')
    return _close_schema(bind('motive',bind('motive_arg',boolean,('sort',expression[2])),
        bind('minor_false',app(motive,('builtin','Bool.false')),bind('minor_true',app(motive,('builtin','Bool.true')),
        bind('major',boolean,app(motive,v('major')))))))


def _option_type(expression):
    name=expression[1]
    carrier=expression[3] if name=='Option.rec' else expression[2]
    # Private compiled-schema markers for successor of either ground level.
    carrier_sort=carrier+1 if carrier>=0 else -4 if carrier==-1 else -5
    v=lambda n:('named',n)
    bind=lambda n,t,b:('bind',n,t,b)
    apps=lambda f,*xs:reduce(lambda a,b:('app',a,b),xs,f)
    alpha,motive,major=map(v,('alpha','motive','major'))
    option=apps(('builtin','Option',carrier),alpha)
    none=apps(('builtin','Option.none',carrier),alpha)
    some=lambda value:apps(('builtin','Option.some',carrier),alpha,value)
    if name=='Option':tail=('sort',carrier_sort)
    elif name=='Option.none':tail=option
    elif name=='Option.some':tail=bind('value',alpha,option)
    else:
        minor_some=bind('value',alpha,apps(motive,some(v('value'))))
        tail=bind('motive',bind('motive_arg',option,('sort',expression[2])),
             bind('minor_none',apps(motive,none),bind('minor_some',minor_some,
             bind('major',option,apps(motive,major)))))
    return _close_schema(bind('alpha',('sort',carrier_sort),tail))


def _one_record_type(expression):
    name=expression[1];family=name.split('.')[0];record=ONE_FIELD_RECORDS[family]
    carrier=expression[3] if name.endswith('.rec') else expression[2]
    carrier_sort=(carrier+1 if carrier>=0 else -4 if carrier==-1 else -5) if record['type_carrier'] else carrier
    v=lambda n:('named',n)
    bind=lambda n,t,b:('bind',n,t,b)
    apps=lambda f,*xs:reduce(lambda a,b:('app',a,b),xs,f)
    alpha,motive,major,field=map(v,('alpha','motive','major','field'))
    parameters=[alpha]+([v('index')]if record.get('parameters',1)==2 else [])
    record_type=apps(('builtin',family,carrier),*parameters)
    if record['field']=='value':field_type=alpha
    elif record['field']=='binary':field_type=bind('left',alpha,bind('right',alpha,alpha))
    elif record['field']=='relation':field_type=bind('left',alpha,bind('right',alpha,('sort',0)))
    elif record['field']=='equality':field_type=bind('left',alpha,bind('right',alpha,apps(('builtin','Eq',carrier),alpha,v('left'),v('right'))))
    else:raise ValueError('unknown fixed record field schema')
    if name==family:
        level=carrier_sort if record['type_carrier'] else (max(1,carrier) if carrier>=0 else -3) if record['data'] else 0
        tail=('sort',level)
    elif not name.endswith('.rec'):tail=bind('field',field_type,record_type)
    else:
        ctor=apps(('builtin',family+'.'+record['constructor'],carrier),*parameters,field)
        tail=bind('motive',bind('motive_arg',record_type,('sort',expression[2])),
             bind('minor',bind('field',field_type,apps(motive,ctor)),bind('major',record_type,apps(motive,major))))
    if record.get('parameters',1)==2:tail=bind('index',('builtin','Nat'),tail)
    return _close_schema(bind('alpha',('sort',carrier_sort),tail))


def _natural_type(expression):
    name=expression[1];natural=('builtin','Nat')
    if name=='Nat':return ('sort',1)
    if name=='Nat.zero':return natural
    if name=='Nat.succ':return ('pi',natural,natural)
    v=lambda n:('named',n)
    bind=lambda n,t,b:('bind',n,t,b)
    apps=lambda f,*xs:reduce(lambda a,b:('app',a,b),xs,f)
    motive,number=map(v,('motive','number'))
    step=bind('number',natural,bind('hypothesis',apps(motive,number),apps(motive,apps(('builtin','Nat.succ'),number))))
    return _close_schema(bind('motive',bind('motive_arg',natural,('sort',expression[2])),
        bind('zero',apps(motive,('builtin','Nat.zero')),bind('step',step,bind('major',natural,apps(motive,v('major')))))))


def _unit_type(expression):
    name=expression[1];carrier=expression[3]if name=='PUnit.rec'else expression[2]
    unit=('builtin','PUnit',carrier);constructor=('builtin','PUnit.unit',carrier)
    if name=='PUnit':return ('sort',carrier)
    if name=='PUnit.unit':return unit
    return ('pi',('pi',unit,('sort',expression[2])),
            ('pi',('app',('var',0),constructor),('pi',unit,('app',('var',2),('var',0)))))


def type_schema(expression):
    """Compile a FIXED primitive type into a relative postorder DAG recipe.

    This runs on kernel rule schemas at weight compilation, never on an input
    proof or an inferred type. Negative scalar markers denote the fixed schema
    universe parameters: -1/-2 are the levels, -3 is max(1, first), and
    -4/-5 are their successors. Input universes are always nonnegative.
    """
    rows,cache = [],{}
    def visit(term):
        if term in cache: return cache[term]
        tag=term[0]; a=b=0
        if tag in ('pi','app'):
            a,b=visit(term[1]),visit(term[2]); code={'pi':3,'app':5}[tag]; value=0
        elif tag=='builtin':
            code,value=7,primitive_code(term)
            a=term[2] if len(term)>2 else 0;b=term[3] if len(term)>3 else 0
        else: code,value={'var':1,'sort':2}[tag],term[1]
        pointer=len(rows);rows.append((code,a,b,value));cache[term]=pointer
        return pointer
    visit(expression)
    return tuple(rows)


PRIMITIVE_SCHEMAS = {code:type_schema(primitive_type(('builtin',name)+tuple(-1-i for i in range(PRIMITIVE_UNIVERSES.get(name,0)))))
                     for name,code in PRIMITIVE_CODES.items()}
EMPTY_ELIMINATOR = PRIMITIVE_SCHEMAS[1]
