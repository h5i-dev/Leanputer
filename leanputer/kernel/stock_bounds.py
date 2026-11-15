"""Compiler-derived, model-owned invalid-register latch.

The schema is extracted from the original source invalid-syntax predicate. No
name/type catalog is involved. A bad main-row write latches invalidity inside a
stock GDN cache, including raw syntax boot writes. The original next-preflight
stop remains in place. No host supplies this latch or an admission answer.
"""
from collections import defaultdict


def schema_from_compiler(compiler):
    graph=compiler.g;nodes=graph.nodes;root=graph.pred(compiler.invalid_syntax)
    names={name:i for i,(name,width)in enumerate(compiler.layout.fields)}
    def flatten(i):
        n=nodes[i]
        return tuple(x for a in n.args for x in flatten(a))if n.op=='any'else(i,)
    def expression(i,inputs):
        n=nodes[i]
        if n.op=='input':
            if n.data not in names or n.width!=16:raise ValueError('bounds require full main words')
            inputs.add(names[n.data]);return('word',)
        if n.op=='const':return('const',n.data,n.width)
        if n.op not in('eq','ult','not','all','any'):raise ValueError('unsupported original invalid predicate operator '+n.op)
        return(n.op,*(expression(a,inputs)for a in n.args))
    grouped=defaultdict(list)
    for clause in flatten(root):
        inputs=set();tree=expression(clause,inputs)
        if len(inputs)!=1:raise ValueError('incremental invalid predicate must have one main-field dependency per clause')
        grouped[next(iter(inputs))].append(tree)
    return tuple((index,('any',*trees))for index,trees in sorted(grouped.items()))


def evaluate(tree,value):
    """Offline correspondence helper; never used by stock inference."""
    op,*args=tree
    if op=='word':return value
    if op=='const':return args[0]
    values=[evaluate(a,value)for a in args]
    if op=='eq':return values[0]==values[1]
    if op=='ult':return values[0]<values[1]
    if op=='not':return not values[0]
    if op=='all':return all(values)
    if op=='any':return any(values)
    raise ValueError(op)


def emit_invalid_latch(builder,schema,address,payload,enable,kind,layer):
    """Check each whole main-row write, then retain a sticky cache bit.

    Main state is immutable between commits. The first invalid boundary stops
    before any next semantic action; invalidity cannot be repaired after that
    boundary by the fixed source controller. Writes to shadow/scratch/arenas
    do not affect the latch. Predicates inspect the FINAL committed row, so
    intermediate OR-shadow values are never treated as invalid main state.
    """
    from ..native_vendor.qwenputer.ir import K,A_REF,A_BIT
    from ..native_vendor.qwenputer.expr import Expr
    g=builder.graph;one=g.one
    def matches(bits,value):return[b if value>>i&1 else one-b for i,b in enumerate(bits)]
    def logic(tree,word):
        op,*args=tree
        if op in('eq','ult'):
            left,right=args
            if left[0]=='const'and right[0]=='word':
                bound=left[1]
                if op=='eq':return builder.gate('and',matches(word,bound),'bounds-eq')if bound<65536 else Expr()
                # c < word == NOT(word < c+1), including c=65535.
                return one-logic(('ult',('word',),('const',bound+1,17)),word)
            if left[0]!='word'or right[0]!='const':raise ValueError('bounds comparison must be word versus literal')
            bound=right[1]
            if op=='eq':return builder.gate('and',matches(word,bound),'bounds-eq')if bound<65536 else Expr()
            if bound<=0:return Expr()
            if bound>=65536:return one
            terms=[builder.gate('and',[one-word[i]]+matches(word[i+1:],bound>>(i+1)),'bounds-lt-term')for i in range(16)if bound>>i&1]
            return sum(terms,Expr()) # Disjoint highest differing-bit cases.
        if op=='not':return one-logic(args[0],word)
        if op in('all','any'):return builder.gate('and'if op=='all'else'or',[logic(a,word)for a in args],'bounds-'+op)
        if op=='const':return one if args[0]else Expr()
        raise ValueError('nonpredicate bounds node '+op)
    bad=[]
    for index,tree in schema:
        row,slot=divmod(index,7)
        selected=matches(address,2*row)
        bad.append(builder.gate('and',selected+[logic(tree,payload[16*slot:16*(slot+1)])],'bounds-row'))
    changed=builder.gate('and',[enable]+[one-bit for bit in kind]+[builder.gate('or',bad,'bounds-invalid-row')],'bounds-invalid-write')
    out=builder.feature('bounds/invalid')
    g.head('bounds.invalid-latch',{0:K*one},{0:K*one},{0:A_REF*one,1:A_REF*one,2:A_BIT*one},0,{2:K*one},[(2,128.)],beta=changed,into=[out],min_level=2*layer)
    return out
