"""Fixed syntax of the four genuine quot.cpp interfaces, for weighted building.

This describes the kernel's finite primitive interface, never ordinary library
constants. Eq's scheme and constructor identity are validated from checked data.
No input expression is inferred, specialized or evaluated by this compiler helper.
"""
from dataclasses import dataclass
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V


@dataclass(frozen=True)
class Ref:
    index:int


class Syntax:
    def __init__(self):self.rows=[]
    def cell(self,tag,a=0,b=0,c=0):
        ref=Ref(len(self.rows));self.rows.append((tag,a,b,c));return ref
    def vector(self,items,role):
        tail=0
        for item in reversed(tuple(items)):tail=self.cell(C.VECTOR_CELL,item,tail)
        return self.cell(C.VECTOR,len(items),tail,role)
    def expression(self,expr,scope=()):
        if isinstance(expr,str):return self.cell(Tag.BVAR,scope.index(expr))
        tag,*args=expr
        if tag==Tag.SORT:return self.cell(tag,args[0])
        if tag==Tag.CONST:return self.cell(tag,*args)
        if tag==Tag.PI:
            name,domain,body,bi=args
            return self.cell(tag,self.expression(domain,scope),self.expression(body,(name,)+scope),bi)
        if tag==Tag.APP:return self.cell(tag,self.expression(args[0],scope),self.expression(args[1],scope))
        raise AssertionError(tag)


def name_syntax(parts):
    s=Syntax();components=[]
    for part in parts:components.append(s.cell(C.NAME_STRING,s.vector(part.encode('utf8'),V.BYTES)))
    path=s.vector(components,V.REFERENCES)
    return s,path


def interface_syntax():
    s=Syntax()
    levels={name:s.cell(C.LEVEL_PARAM,reg) for name,reg in (
        ('u','quot_symbol_u'),('v','quot_symbol_v'),('e','quot_eq_u'),('r','quot_refl_u'))}
    vectors={name:s.vector([ref],V.LEVELS) for name,ref in levels.items()}
    parameters=s.vector(['quot_symbol_u'],V.SYMBOLS)
    lift_parameters=s.vector(['quot_symbol_u','quot_symbol_v'],V.SYMBOLS)
    prop=(Tag.SORT,'kernel_zero')
    sort=lambda level:(Tag.SORT,levels[level])
    const=lambda name,level:(Tag.CONST,'quot_symbol_'+name,vectors[level])
    def app(fn,*args):
        for arg in args:fn=(Tag.APP,fn,arg)
        return fn
    pi=lambda x,ty,body,bi=0:(Tag.PI,x,ty,body,bi)
    arrow=lambda x,ty,body:pi(x,ty,body)
    relation=lambda:pi('x','a',pi('y','a',prop))
    eq=pi('a',sort('e'),pi('x','a',pi('y','a',prop)),1)
    refl=pi('a',sort('r'),pi('x','a',app(const('eq','r'),'a','x','x')),1)
    q=app(const('quot','u'),'a','r')
    ty=pi('a',sort('u'),pi('r',relation(),sort('u')),1)
    mk=pi('a',sort('u'),pi('r',relation(),pi('x','a',q)),1)
    sanity=pi('x','a',pi('y','a',arrow('h',app('r','x','y'),app(const('eq','v'),'b',app('f','x'),app('f','y')))))
    lift=pi('a',sort('u'),pi('r',relation(),pi('b',sort('v'),pi('f',arrow('x','a','b'),
        arrow('h',sanity,arrow('q',q,'b'))),1),1),1)
    minor=pi('x','a',app('b',app(const('mk','u'),'a','r','x')))
    ind=pi('a',sort('u'),pi('r',relation(),pi('b',arrow('q',q,prop),pi('m',minor,pi('q',q,app('b','q'))),1),1),1)
    refs={key:s.expression(expr) for key,expr in [('eq',eq),('refl',refl),('type',ty),('ctor',mk),('lift',lift),('ind',ind)]}
    return s,refs,parameters,lift_parameters
