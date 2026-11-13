"""Untrusted generic syntax. Names resolve to input IDs; no checking/normalizing."""
from dataclasses import dataclass
from enum import IntEnum

class Unsupported(ValueError): pass
class Exhausted(ValueError): pass

class Tag(IntEnum):
    EMPTY=0; VAR=1; SORT=2; PI=3; LAM=4; APP=5; CONST=6; PROJ=7
TAGS={name.lower():tag for name,tag in Tag.__members__.items()if tag!=Tag.EMPTY}


def parse_expr(value):
    if not isinstance(value,(list,tuple)) or not value:raise ValueError('tagged expression required')
    tag=value[0]
    if tag in ('var','sort') and len(value)==2 and type(value[1])is int and value[1]>=0:return tuple(value)
    if tag=='const' and len(value)==2 and isinstance(value[1],str)and value[1]:return tuple(value)
    if tag=='proj' and len(value)==4 and isinstance(value[1],str) and value[1] and type(value[2])is int and value[2]>=0:
        return(tag,value[1],value[2],parse_expr(value[3]))
    if tag in ('pi','lam','app')and len(value)==3:return(tag,parse_expr(value[1]),parse_expr(value[2]))
    if tag not in TAGS:raise Unsupported('generic expression form: '+str(tag))
    raise ValueError('malformed generic expression')


@dataclass(frozen=True)
class Declaration:
    name: str
    type: object
    value: object=None
    kind: str='axiom'
    family: object=None
    constructors: int=0
    index: int=0
    level: int=0

    def __post_init__(self):
        if not isinstance(self.name,str)or not self.name:raise ValueError('declaration name required')
        if self.kind not in ('axiom','definition','opaque','inductive','constructor','recursor'):raise ValueError('unknown declaration kind')
        object.__setattr__(self,'type',parse_expr(self.type))
        if self.value is not None:object.__setattr__(self,'value',parse_expr(self.value))
        if self.kind in ('definition','opaque')and self.value is None:raise ValueError('definition needs a value')
        for key in ('constructors','index','level'):
            if type(getattr(self,key))is not int or getattr(self,key)<0:raise ValueError('nonnegative declaration scalar required')
        if self.kind in ('constructor','recursor')and(not isinstance(self.family,str)or not self.family):raise ValueError('family reference required')


def parse_document(document):
    if not isinstance(document,dict)or document.get('format')!='leanputer.generic.v1':raise ValueError('expected leanputer.generic.v1')
    if set(document)-{'format','name','term','claim','environment','provenance'}:raise ValueError('unknown document field')
    entries=document.get('environment',[])
    if not isinstance(entries,list):raise ValueError('ordered environment required')
    declarations=tuple(Declaration(**entry)for entry in entries)
    return parse_expr(document['term']),parse_expr(document['claim']),declarations


def assumptions(declarations):return[d.name for d in declarations if d.kind=='axiom']
