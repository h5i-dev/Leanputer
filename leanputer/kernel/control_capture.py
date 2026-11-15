"""Input-independent capture of all current source checker rule families."""
from dataclasses import asdict,dataclass
import hashlib
import inspect
from pathlib import Path
from .control_ir import TypedBuilder
from .traversal_transition import RuleCompiler,compile_addresses


@dataclass(frozen=True)
class Effect:
    kind: str
    guard: int
    values: tuple
    source: str
    line: int
    family: str
    address: int = -1


class TypedRuleCompiler(RuleCompiler):
    def __init__(self,layout):
        self.effects=[];self.families=[];self.family='traversal_transition';self.active_nodes=[]
        super().__init__(layout,builder_factory=TypedBuilder)
        self.preflight_effect_count=len(self.effects)
        self.preflight_active=self.g.pred(self.active)

    @property
    def active(self):return self._active

    @active.setter
    def active(self,value):
        self._active=value
        if hasattr(self,'g'):self.active_nodes.append(self.g.pred(value))

    def origin(self):
        frame=inspect.currentframe().f_back;fallback=None
        while frame:
            path=Path(frame.f_code.co_filename)
            if path.parent.name=='kernel' and path.name not in('control_capture.py','traversal_transition.py'):
                return path.name,frame.f_lineno
            if path.name=='traversal_transition.py'and frame.f_code.co_name in('__init__','rules'):
                fallback=(path.name,frame.f_lineno)
            frame=frame.f_back
        return fallback or('traversal_transition.py',0)

    def include_rules(self,module):
        before=len(self.effects);previous=self.family;self.family=module.__name__.rsplit('.',1)[1]
        module.emit_rules(self)
        path=Path(module.__file__)
        self.families.append(dict(module=self.family,source=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),effects=len(self.effects)-before))
        self.family=previous

    def emit(self,guard,**updates):
        source,line=self.origin()
        values=tuple((name,self.g.fit(self.v(value,len(self.r[name])),len(self.r[name])).node)for name,value in updates.items())
        self.effects.append(Effect('merge_fields',self.g.pred(guard),values,source,line,self.family))

    def write(self,bank,guard,address,row):
        source,line=self.origin()
        self.effects.append(Effect('write_'+bank,self.g.pred(guard),tuple(self.g.fit(self.v(v),self.width).node for v in row),source,line,self.family,self.g.word(self.v(address)).node))

    def finish_typed(self):
        self.rules()
        return self


def capture(config):
    from .traversal_machine import StateLayout,RegisterLayout
    layout=RegisterLayout(StateLayout(config));compiler=TypedRuleCompiler(layout).finish_typed()
    addresses=compile_addresses(layout,builder_factory=TypedBuilder)
    return compiler,addresses
