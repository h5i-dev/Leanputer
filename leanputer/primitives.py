"""Fixed positive logical primitives; never unchecked user-environment axioms.

Only the named propositions/constructors below are intrinsic. Their closed
schemas are checker rules compiled into weights. General datatype declarations
and general structure recursors remain unsupported.
"""

PRIMITIVE_CODES = {'False':0,'False.rec':1,'Iff':2,'Iff.intro':3,'And':4,'And.intro':5}
PROJECTION_FAMILIES = {'Iff':0,'And':2}


def primitive_code(expression): return PRIMITIVE_CODES[expression[1]]


def primitive_type(expression):
    name = expression[1]
    sort = ('sort',0)
    var = lambda i:('var',i)
    app = lambda f,a:('app',f,a)
    pi = lambda a,b:('pi',a,b)
    if name=='False': return sort
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
    proof or an inferred type. None in a Sort is the concrete universe parameter.
    """
    rows,cache = [],{}
    def visit(term):
        if term in cache: return cache[term]
        tag=term[0]; a=b=0
        if tag in ('pi','app'):
            a,b=visit(term[1]),visit(term[2]); code={'pi':3,'app':5}[tag]; value=0
        elif tag=='builtin': code,value=7,primitive_code(term)
        else: code,value={'var':1,'sort':2}[tag],term[1]
        pointer=len(rows);rows.append((code,a,b,value));cache[term]=pointer
        return pointer
    visit(expression)
    return tuple(rows)


PRIMITIVE_SCHEMAS = {code:type_schema(primitive_type(('builtin',name,None) if name=='False.rec' else ('builtin',name)))
                     for name,code in PRIMITIVE_CODES.items()}
EMPTY_ELIMINATOR = PRIMITIVE_SCHEMAS[1]
