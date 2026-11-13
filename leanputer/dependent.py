"""Ground-universe dependent syntax and independent recursive checking oracle.

This module is preparation/testing code. Its infer/convert/reduction functions
are never used by the compiled transition engine's runtime checking path.
"""
from dataclasses import dataclass
from functools import reduce
from enum import IntEnum


class Unsupported(ValueError):
    pass


class Rejected(ValueError):
    pass


class Exhausted(ValueError):
    pass


class Tag(IntEnum):
    EMPTY = 0
    VAR = 1
    SORT = 2
    PI = 3
    LAM = 4
    APP = 5
    CONST = 6
    BUILTIN = 7
    PROJ = 8
    LET = 9


TAGS = {'var': Tag.VAR, 'sort': Tag.SORT, 'pi': Tag.PI, 'lam': Tag.LAM, 'app': Tag.APP, 'const': Tag.CONST, 'builtin':Tag.BUILTIN, 'proj':Tag.PROJ, 'let':Tag.LET}


def parse_expr(value):
    if not isinstance(value, (tuple, list)) or not value or not isinstance(value[0], str):
        raise ValueError('dependent expressions must be tagged arrays')
    tag = value[0]
    if tag not in TAGS:
        raise Unsupported(f'unsupported expression: {tag}')
    if tag in ('var', 'sort') and len(value) == 2 and type(value[1]) is int and value[1] >= 0:
        return (tag, value[1])
    if tag == 'const' and len(value) == 2 and isinstance(value[1], str) and value[1]:
        return (tag, value[1])
    if tag == 'builtin':
        from .primitives import PRIMITIVE_CODES,PRIMITIVE_UNIVERSES
        if len(value)>=2 and isinstance(value[1],str) and value[1] in PRIMITIVE_CODES:
            count=PRIMITIVE_UNIVERSES.get(value[1],0)
            if len(value)==2+count and all(type(u)is int and u>=0 for u in value[2:]):
                return tuple(value)
        raise Unsupported('unsupported logical primitive or universe arity')
    if tag == 'proj':
        if len(value)==4 and value[1] in ('Iff','And') and type(value[2]) is int and 0<=value[2]<2:
            return (tag,value[1],value[2],parse_expr(value[3]))
        raise Unsupported('unsupported structure projection')
    if tag in ('pi', 'lam', 'app') and len(value) == 3:
        return (tag, parse_expr(value[1]), parse_expr(value[2]))
    if tag == 'let' and len(value) == 4:
        return (tag, *(parse_expr(child) for child in value[1:]))
    raise ValueError(f'malformed dependent {tag} expression')


@dataclass(frozen=True)
class Declaration:
    name: str
    type: tuple
    value: object = None
    opaque: bool = False

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError('declaration name required')
        object.__setattr__(self, 'type', parse_expr(self.type))
        if self.value is not None:
            object.__setattr__(self, 'value', parse_expr(self.value))
        if type(self.opaque) is not bool or (self.opaque and self.value is None):
            raise ValueError('opaque declarations require a value')


class Oracle:
    """Recursive algorithm, independently structured from operational frames."""
    def __init__(self, declarations=(), fuel=100000):
        self.environment = {}
        self.remaining = fuel
        for declaration in declarations:
            if declaration.name in self.environment:
                raise Rejected('duplicate declaration')
            if self.whnf(self.infer(declaration.type))[0] != 'sort':
                raise Rejected('declaration type is not a type')
            if declaration.value is not None and not self.convert(self.infer(declaration.value), declaration.type):
                raise Rejected('declaration value type mismatch')
            self.environment[declaration.name] = declaration

    def tick(self):
        self.remaining -= 1
        if self.remaining < 0:
            raise Exhausted('oracle fuel')

    def shift(self, term, delta, cutoff=0):
        self.tick()
        tag = term[0]
        if tag == 'var':
            return ('var', term[1] + (delta if term[1] >= cutoff else 0))
        if tag in ('sort', 'const', 'builtin'):
            return term
        if tag=='proj': return (tag,term[1],term[2],self.shift(term[3],delta,cutoff))
        if tag=='let':
            return (tag,self.shift(term[1],delta,cutoff),self.shift(term[2],delta,cutoff),
                    self.shift(term[3],delta,cutoff+1))
        return (tag, self.shift(term[1], delta, cutoff),
                self.shift(term[2], delta, cutoff + int(tag in ('pi', 'lam'))))

    def substitute(self, term, replacement, depth=0):
        self.tick()
        tag = term[0]
        if tag == 'var':
            index = term[1]
            if index == depth:
                return self.shift(replacement, depth)
            return ('var', index - int(index > depth))
        if tag in ('sort', 'const', 'builtin'):
            return term
        if tag=='proj': return (tag,term[1],term[2],self.substitute(term[3],replacement,depth))
        if tag=='let':
            return (tag,self.substitute(term[1],replacement,depth),self.substitute(term[2],replacement,depth),
                    self.substitute(term[3],replacement,depth+1))
        return (tag, self.substitute(term[1], replacement, depth),
                self.substitute(term[2], replacement, depth + int(tag in ('pi', 'lam'))))

    def whnf(self, term, context=()):
        self.tick()
        if term[0]=='let':
            return self.whnf(self.substitute(term[3],term[2]),context)
        if term[0] == 'const':
            declaration = self.environment.get(term[1])
            if declaration is None:
                raise Rejected('unknown constant')
            return self.whnf(declaration.value,context) if declaration.value is not None and not declaration.opaque else term
        if term[0]=='proj':
            base=self.whnf(term[3],context); head=base; arguments=[]
            while head[0]=='app': arguments.insert(0,head[2]);head=head[1]
            if head==('builtin',term[1]+'.intro') and len(arguments)==4:
                return self.whnf(arguments[2+term[2]],context)
            return ('proj',term[1],term[2],base)
        if term[0] == 'app':
            fn = self.whnf(term[1],context)
            if fn[0] == 'lam':
                return self.whnf(self.substitute(fn[2], term[2]),context)
            result=('app',fn,term[2]);head=result;arguments=[]
            while head[0]=='app':arguments.insert(0,head[2]);head=head[1]
            if head[0]=='builtin':
                name=head[1]
                apps=lambda f,*xs:reduce(lambda a,b:('app',a,b),xs,f)
                if name=='Eq.rec' and len(arguments)==6 and self.convert(arguments[1],arguments[4],context):
                    return self.whnf(arguments[3],context)
                if name=='True.rec' and len(arguments)==3:return self.whnf(arguments[1],context)
                count={'And.rec':5,'Iff.rec':5,'Nonempty.rec':4,'Exists.rec':5,'Or.rec':6,'Quot.ind':5,'Quot.lift':6,'Decidable.rec':5}.get(name)
                if count and len(arguments)==count:
                    major=self.whnf(arguments[-1],context);ctor=major;fields=[]
                    while ctor[0]=='app':fields.insert(0,ctor[2]);ctor=ctor[1]
                    if ctor[0]=='builtin':
                        if name=='Decidable.rec' and ctor[1] in ('Decidable.isFalse','Decidable.isTrue') and len(fields)==2:
                            return self.whnf(apps(arguments[2 if ctor[1]=='Decidable.isFalse' else 3],fields[1]),context)
                        if name in ('Quot.ind','Quot.lift') and ctor[1]=='Quot.mk' and len(fields)==3:
                            return self.whnf(apps(arguments[3],fields[2]),context)
                        if name in ('And.rec','Iff.rec') and ctor[1]==name.split('.')[0]+'.intro' and len(fields)==4:
                            return self.whnf(apps(arguments[3],*fields[2:]),context)
                        if name=='Nonempty.rec' and ctor[1]=='Nonempty.intro' and len(fields)==2:
                            return self.whnf(apps(arguments[2],fields[1]),context)
                        if name=='Exists.rec' and ctor[1]=='Exists.intro' and len(fields)==4:
                            return self.whnf(apps(arguments[3],*fields[2:]),context)
                        if name=='Or.rec' and ctor[1] in ('Or.inl','Or.inr') and len(fields)==3:
                            return self.whnf(apps(arguments[3 if ctor[1]=='Or.inl' else 4],fields[2]),context)
            return result
        return term

    def convert(self, left, right, context=()):
        self.tick()
        left,right=self.whnf(left,context),self.whnf(right,context)
        if left == right:
            return True
        if left[0] == right[0] and left[0] in ('pi', 'lam', 'app'):
            if self.convert(left[1], right[1], context):
                extended = context + (left[1],) if left[0] in ('pi', 'lam') else context
                if self.convert(left[2], right[2], extended):
                    return True
        if left[0]==right[0]=='proj' and left[1:3]==right[1:3] and self.convert(left[3],right[3],context):
            return True
        # Sort and Pi expressions cannot be proof terms or eta-expanded values.
        if left[0] in ('sort', 'pi') or right[0] in ('sort', 'pi'):
            return False
        left_type = self.whnf(self.infer(left,context),context)
        if left_type[0] != 'sort':
            classifier = self.whnf(self.infer(left_type,context),context)
            if classifier == ('sort', 0) and self.convert(left_type, self.infer(right, context), context):
                return True
        if (left[0] == 'lam') != (right[0] == 'lam'):
            lam, neutral = (left, right) if left[0] == 'lam' else (right, left)
            fn_type = self.whnf(self.infer(neutral,context),context)
            if fn_type[0] == 'pi' and self.convert(lam[1], fn_type[1], context):
                applied = ('app', self.shift(neutral, 1), ('var', 0))
                return self.convert(lam[2], applied, context + (lam[1],))
        return False

    def infer(self, term, context=()):
        self.tick()
        tag = term[0]
        if tag=='let':
            if self.whnf(self.infer(term[1],context),context)[0]!='sort':
                raise Rejected('let annotation is not a type')
            if not self.convert(self.infer(term[2],context),term[1],context):
                raise Rejected('let value type mismatch')
            return self.infer(self.substitute(term[3],term[2]),context)
        if tag == 'builtin':
            from .primitives import primitive_type
            return primitive_type(term)
        if tag=='proj':
            inferred=self.whnf(self.infer(term[3],context),context)
            if inferred[0]!='app' or inferred[1][0]!='app' or inferred[1][1]!=('builtin',term[1]):
                raise Rejected('projection family mismatch')
            left,right=inferred[1][2],inferred[2]
            if term[1]=='And': return (left,right)[term[2]]
            domain,codomain=(left,right) if term[2]==0 else (right,left)
            return ('pi',domain,self.shift(codomain,1))
        if tag == 'sort':
            return ('sort', term[1] + 1)
        if tag == 'var':
            if term[1] >= len(context):
                raise Rejected('unbound de Bruijn variable')
            return self.shift(context[-1-term[1]], term[1]+1)
        if tag == 'const':
            if term[1] not in self.environment:
                raise Rejected('unknown constant')
            return self.environment[term[1]].type
        if tag in ('lam', 'pi'):
            domain_sort=self.whnf(self.infer(term[1],context),context)
            if domain_sort[0] != 'sort':
                raise Rejected('binder domain is not a type')
            body_type = self.infer(term[2], context + (term[1],))
            if tag == 'lam':
                return ('pi', term[1], body_type)
            body_sort=self.whnf(body_type,context+(term[1],))
            if body_sort[0] != 'sort':
                raise Rejected('Pi codomain is not a type')
            # Lean imax on ground numeric levels: impredicative Prop.
            return ('sort', 0 if body_sort[1] == 0 else max(domain_sort[1], body_sort[1]))
        fn_type=self.whnf(self.infer(term[1],context),context)
        if fn_type[0] != 'pi' or not self.convert(self.infer(term[2], context), fn_type[1], context):
            raise Rejected('application type mismatch')
        return self.substitute(fn_type[2], term[2])

    def check(self, term, claim):
        if self.whnf(self.infer(claim))[0] != 'sort':
            raise Rejected('claim is not a type')
        if not self.convert(self.infer(term), claim):
            raise Rejected('claim mismatch')
        return True
