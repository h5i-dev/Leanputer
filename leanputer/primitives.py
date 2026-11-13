"""Fixed positive logical primitives; never unchecked user-environment axioms.

Only the named propositions/constructors below are intrinsic. Their closed
schemas are checker rules compiled into weights. General datatype declarations
and general structure recursors remain unsupported.
"""

from functools import reduce

PRIMITIVE_CODES = {'False':0,'False.rec':1,'Iff':2,'Iff.intro':3,'And':4,'And.intro':5,'Eq':6,'Eq.refl':7,'Eq.rec':8,'True':9,'True.intro':10}
PRIMITIVE_UNIVERSES = {'False.rec':1,'Eq':1,'Eq.refl':1,'Eq.rec':2}
PROJECTION_FAMILIES = {'Iff':0,'And':2}


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


def type_schema(expression):
    """Compile a FIXED primitive type into a relative postorder DAG recipe.

    This runs on kernel rule schemas at weight compilation, never on an input
    proof or an inferred type. Negative scalar markers denote the fixed schema
    universe parameters; input universes are always nonnegative.
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
