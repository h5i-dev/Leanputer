"""Bounded explicit small-step dependent checker specification.

This specification has no dependency on torch, Boolean gates, declaration
names, or the weighted implementation. The calculus core originates at4da2515.
"""
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum

from .generic_syntax import Declaration, Exhausted, TAGS, Tag, parse_expr


class Outcome(IntEnum):
    RUNNING = 0
    ACCEPT = 1
    REJECT = 2
    RESOURCE = 3


class Reason(IntEnum):
    NONE = 0
    SYNTAX = 1
    UNBOUND = 2
    EXPECT_SORT = 3
    EXPECT_PI = 4
    CONVERSION = 5
    HEAP = 6
    STACK = 7
    CONTEXT = 8
    UNIVERSE = 9
    FUEL = 10
    INDEX = 11
    INTERNAL = 12
    UNSUPPORTED_DECLARATION = 13
    DECLARATION = 14


class Op(IntEnum):
    VALIDATE = 0
    ENV = 1
    TYPE = 2
    VALUE = 3
    COMMIT = 4
    ROOT_TYPE = 5
    ROOT_TERM = 6
    ROOT_EQ = 7
    FINISH = 8
    INFER = 9
    I_DOM = 10
    I_BIND = 11
    I_LAM = 12
    I_PI = 13
    I_SORT = 14
    I_APP = 15
    I_FUN = 16
    I_ARG = 17
    I_CHECK = 18
    WHNF = 19
    W_APP = 20
    W_BETA = 21
    SHIFT = 22
    SUBST = 23
    TREE_LEFT = 24
    TREE_RIGHT = 25
    CONV = 26
    C_LEFT = 27
    C_RIGHT = 28
    C_CHILD = 29
    RET = 30
    ENV_EQ = 31
    FALLBACK = 32
    C_AFTER_CHILD = 33
    F_TYPE = 34
    F_TYPE_WHNF = 35
    F_SORT = 36
    F_SORT_WHNF = 37
    F_Y = 38
    F_PROOF_RESULT = 39
    ETA = 40
    E_TYPE = 41
    E_TYPE_WHNF = 42
    E_DOMAIN = 43
    E_SHIFT = 44
    E_VAR = 45
    E_BUILD = 46
    E_MAKE_APP = 47
    E_COMPARE = 48
    G_FAMILY = 49
    G_CTOR = 50
    G_REC = 51
    G_R0 = 52
    G_R1 = 53
    G_R2 = 54
    G_R3 = 55
    G_R4 = 56
    G_R5 = 57
    G_R6 = 58
    G_RLOOP = 59
    G_RC1 = 60
    G_RC2 = 61
    G_RC3 = 62
    G_RDONE = 63
    G_MAJOR = 64
    G_CHOOSE = 65
    G_PICK = 66
    G_AFTER = 67
    G_RNEXT = 68
    G_CTOR_TYPE = 69
    G_FIELD_DOMAIN = 70
    G_FIELD_SORT = 71
    G_FIELD_RESULT = 72
    G_RCTYPE = 73
    G_RF0 = 74
    G_RF1 = 75
    G_RF2 = 76
    G_CHEAD = 77
    G_CCHECK = 78
    G_APPLY = 79
    G_ELIM = 80
    G_MTYPE = 81
    P_TYPE = 82
    P_FAMILY = 83
    P_DOMAIN = 84
    P_VALUE = 85
    P_HEAD = 86
    P_CHECK = 87
    P_DONE = 88
    P_REBUILD = 89
    P_CONV_DONE = 90


@dataclass(frozen=True)
class MachineConfig:
    heap: int = 128
    stack: int = 32
    context: int = 32
    constants: int = 16
    universe: int = 4
    fuel: int = 1024

    def __post_init__(self):
        for name in ('heap', 'stack', 'context', 'constants'):
            value = getattr(self, name)
            if type(value) is not int or value < 2 or value & (value-1):
                raise ValueError(f'{name} capacity must be a power of two >= 2')
        if self.heap < 16 or type(self.universe) is not int or not 0 <= self.universe < self.heap-1:
            raise ValueError('heap >= 16 and universe below heap-1 required')
        if type(self.fuel) is not int or self.fuel < 1:
            raise ValueError('positive fuel required')

    @property
    def word_bits(self):
        return max(7, max(self.heap, self.stack, self.context, self.constants).bit_length())


REGISTERS = ('mode', 'x', 'y', 'z', 'w', 'r', 'ctx', 'sp', 'free', 'scan',
             'decl', 'decl_count', 'term', 'claim', 'fuel', 'status', 'reason', 'head', 'arity', 'gi', 'gf', 'gm', 'gt', 'gc', 'ga', 'gb')
HEAP_FIELDS = ('tag', 'a', 'b', 'v')
FRAME_FIELDS = ('mode', 'x', 'y', 'z', 'w', 'ctx')
CONST_FIELDS=('kind','type','value','owner','info')


def prepare(config, term, claim, declarations=()):
    """Syntax-only postorder DAG encoding, including all environment assumptions."""
    declarations = tuple(d if isinstance(d, Declaration) else Declaration(**d) for d in declarations)
    if len(declarations) > config.constants:
        raise Exhausted('constant table capacity')
    names = {d.name: i for i, d in enumerate(declarations)}
    if len(names) != len(declarations):
        raise ValueError('duplicate declaration names')
    heap, cache = [[0, 0, 0, 0]], {}
    def visit(expr):
        expr = parse_expr(expr)
        if expr in cache:
            return cache[expr]
        tag = expr[0]
        a = b = v = 0
        if tag in ('pi', 'lam', 'app'):
            a, b = visit(expr[1]), visit(expr[2])
        elif tag in ('const','proj'):
            if tag=='proj':
                a,b=visit(expr[3]),expr[2]
                if b>=1<<config.word_bits:raise Exhausted('projection scalar encoding capacity')
            if expr[1] not in names:
                raise ValueError(f'undeclared constant: {expr[1]}')
            v = names[expr[1]]
        else:
            v = expr[1]
        if v >= 1 << config.word_bits:
            raise Exhausted('syntax scalar encoding capacity')
        if len(heap) >= config.heap:
            raise Exhausted('input heap capacity')
        idx = len(heap)
        heap.append([int(TAGS[tag]), a, b, v]); cache[expr] = idx
        return idx
    constants = []
    kinds={'axiom':0,'definition':1,'opaque':2,'inductive':3,'constructor':4,'recursor':5}
    for i,d in enumerate(declarations):
        ty=visit(d.type);value=visit(d.value)if d.value is not None else 0
        owner=i if d.kind=='inductive'else names.get(d.family,0)
        if d.family is not None and d.family not in names:raise ValueError('unknown family name')
        info=d.constructors if d.kind=='inductive'else d.index if d.kind=='constructor'else d.level if d.kind=='recursor'else 0
        if max(owner,info)>=1<<config.word_bits:raise Exhausted('declaration scalar capacity')
        constants.append([kinds[d.kind],ty,value,owner,info])
    term_id,claim_id=visit(term),visit(claim)
    regs = {name: 0 for name in REGISTERS}
    regs.update(free=len(heap), scan=1, decl_count=len(constants), term=term_id,
                claim=claim_id, fuel=config.fuel)
    heap.extend([[0]*4 for _ in range(config.heap-len(heap))])
    constants.extend([[0]*5 for _ in range(config.constants-len(constants))])
    return dict(regs=regs, heap=heap, stack=[[0]*6 for _ in range(config.stack)],
                context=[[0] for _ in range(config.context)], constants=constants)


class SpecMachine:
    def __init__(self, config, state):
        self.config, self.state = config, deepcopy(state)

    def node(self, pointer):
        if not 0 < pointer < self.state['regs']['free']:
            self.stop(Outcome.REJECT, Reason.SYNTAX)
            return [0]*4
        return self.state['heap'][pointer]

    def stop(self, status, reason=Reason.NONE):
        self.state['regs'].update(status=int(status), reason=int(reason))

    def ret(self, result, head=0, arity=0):
        self.state['regs'].update(mode=int(Op.RET), r=result, head=head, arity=arity)

    def tail(self, op, x=0, y=0, z=0, w=0):
        self.state['regs'].update(mode=int(op), x=x, y=y, z=z, w=w)

    def call(self, op, x, y=0, z=0, w=0, continuation=None, context=None):
        r = self.state['regs']
        if r['sp'] >= self.config.stack:
            self.stop(Outcome.RESOURCE, Reason.STACK); return
        frame = [int(continuation[0])] + list(continuation[1:])
        frame += [0] * (5-len(frame))
        self.state['stack'][r['sp']] = frame + [r['ctx']]
        r['sp'] += 1
        self.tail(op, x, y, z, w)
        if context is not None:
            r['ctx'] = context

    def allocate(self, tag, a=0, b=0, v=0, resume=None, head=0, arity=0):
        r = self.state['regs']
        if r['free'] >= self.config.heap:
            self.stop(Outcome.RESOURCE, Reason.HEAP); return
        if v >= 1 << self.config.word_bits:
            self.stop(Outcome.RESOURCE, Reason.INDEX); return
        pointer = r['free']
        self.state['heap'][pointer] = [int(tag), a, b, v]
        r['free'] += 1
        self.ret(pointer,head,arity)
        if resume is not None:self.tail(*resume)

    def step(self):
        s, cfg = self.state, self.config
        r = s['regs']
        if r['status']:
            return s
        if r['fuel'] == 0:
            self.stop(Outcome.RESOURCE, Reason.FUEL); return s
        r['fuel'] -= 1
        op, x, y, z, w, result = (r[k] for k in ('mode', 'x', 'y', 'z', 'w', 'r'))
        # Check address domains before any semantic read or update. The weighted
        # engine uses the same guards before interpreting an attention result.
        if (not 1 <= r['free'] <= cfg.heap or r['sp'] > cfg.stack or r['ctx'] > cfg.context
                or not r['decl'] <= r['decl_count'] <= cfg.constants or r['head']>r['decl']
                or (r['head']==0 and r['arity']!=0)):
            self.stop(Outcome.REJECT, Reason.SYNTAX); return s
        if r['head']:
            headrow=s['constants'][r['head']-1]
            if headrow[0]!=3 or r['arity']>=headrow[4]+2:
                self.stop(Outcome.REJECT,Reason.SYNTAX);return s
        pointers = []
        if op in (Op.INFER, Op.I_BIND, Op.WHNF, Op.W_APP, Op.SHIFT, Op.SUBST,
                  Op.TREE_LEFT, Op.TREE_RIGHT, Op.CONV, Op.C_RIGHT, Op.C_CHILD,
                  Op.FALLBACK, Op.ETA, Op.E_TYPE_WHNF, Op.E_COMPARE):
            pointers.append(x)
        if op in (Op.VALUE, Op.ROOT_TERM, Op.I_BIND, Op.I_SORT, Op.I_FUN, Op.W_APP,
                  Op.C_RIGHT, Op.F_TYPE_WHNF, Op.F_SORT_WHNF, Op.E_TYPE_WHNF):
            pointers.append(result)
        if op in (Op.CONV, Op.FALLBACK, Op.ETA):
            pointers.append(y)
        if op in (Op.G_FAMILY,Op.G_PICK,Op.G_MAJOR,Op.G_CTOR_TYPE,Op.G_FIELD_DOMAIN,Op.G_FIELD_SORT,Op.G_FIELD_RESULT,Op.G_RCTYPE,Op.G_CHEAD,Op.G_CCHECK,Op.G_ELIM,Op.G_MTYPE,Op.P_FAMILY,Op.P_DOMAIN,Op.P_VALUE,Op.P_HEAD,Op.P_CHECK,Op.P_DONE,Op.P_REBUILD,Op.P_CONV_DONE):pointers.append(x)
        if op==Op.G_AFTER:pointers.extend((x,y,z))
        if op==Op.G_MAJOR:pointers.append(y)
        if op in (Op.G_R1,Op.G_R2,Op.G_R3,Op.G_R4,Op.G_R5,Op.G_R6,Op.G_RC1,Op.G_RC2,Op.G_RC3,Op.G_RNEXT,Op.G_RDONE,Op.G_REC,Op.G_R0,Op.G_CHOOSE,Op.G_RF0,Op.G_RF1,Op.G_RF2,Op.G_APPLY,Op.P_TYPE,Op.P_FAMILY,Op.P_VALUE,Op.P_REBUILD):pointers.append(result)
        if any(not 0 < pointer < r['free'] for pointer in pointers):
            self.stop(Outcome.REJECT, Reason.SYNTAX); return s
        if op == Op.VALIDATE:
            if r['scan'] >= r['free']:
                self.tail(Op.ENV)
            else:
                i = r['scan']; tag, a, b, v = s['heap'][i]
                valid = 1 <= tag <= 7
                if tag in (Tag.PI, Tag.LAM, Tag.APP):
                    valid &= 0 < a < i and 0 < b < i and v == 0
                elif tag==Tag.PROJ:
                    valid &= 0<a<i
                else:
                    valid &= a == b == 0
                if tag in (Tag.CONST,Tag.PROJ):
                    valid &= v < r['decl_count']
                if not valid:
                    self.stop(Outcome.REJECT, Reason.SYNTAX)
                elif tag==Tag.PROJ and b!=0:
                    self.stop(Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
                elif tag == Tag.SORT and v > cfg.universe:
                    self.stop(Outcome.RESOURCE, Reason.UNIVERSE)
                else:
                    r['scan'] += 1
        elif op == Op.ENV:
            if r['decl'] == r['decl_count']:
                self.call(Op.INFER, r['claim'], continuation=(Op.ROOT_TYPE,))
            else:
                kind, ty, value, owner, info = s['constants'][r['decl']]
                if not 0<ty<r['free'] or kind not in range(6):self.stop(Outcome.REJECT,Reason.DECLARATION)
                elif kind==3:self.tail(Op.G_FAMILY,ty)
                elif kind==4:self.stop(Outcome.REJECT,Reason.DECLARATION)
                elif kind==5:
                    if value or owner>=r['decl'] or s['constants'][owner][0]!=3 or owner+s['constants'][owner][4]>=r['decl']:
                        self.stop(Outcome.REJECT,Reason.DECLARATION)
                    elif info>=cfg.universe:self.stop(Outcome.RESOURCE,Reason.UNIVERSE)
                    else:self.call(Op.INFER,ty,continuation=(Op.G_REC,))
                elif owner or info or (kind and not 0<value<r['free']) or (kind==0 and value):self.stop(Outcome.REJECT,Reason.DECLARATION)
                else:self.call(Op.INFER,ty,continuation=(Op.TYPE,ty,value,kind))
        elif op==Op.G_FAMILY:
            kind,ty,value,owner,count=s['constants'][r['decl']];tag,a,b,level=self.node(x)
            if tag!=Tag.SORT:self.stop(Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
            elif level>=cfg.universe:self.stop(Outcome.RESOURCE,Reason.UNIVERSE)
            elif value or owner!=r['decl'] or count>=cfg.constants or r['decl']+count>=r['decl_count']:self.stop(Outcome.REJECT,Reason.DECLARATION)
            else:r['gi']=0;r['gm']=level;self.tail(Op.G_CTOR)
        elif op==Op.G_CTOR:
            count=s['constants'][r['decl']][4]
            if r['gi']==count:r['decl']+=count+1;self.tail(Op.ENV)
            else:
                kind,ty,value,owner,ordinal=s['constants'][r['decl']+1+r['gi']]
                if kind!=4 or value or owner!=r['decl'] or ordinal!=r['gi'] or not 0<ty<r['free']:self.stop(Outcome.REJECT,Reason.DECLARATION)
                else:self.tail(Op.G_CTOR_TYPE,ty)
        elif op==Op.G_CTOR_TYPE:
            if self.node(x)[0]==Tag.PI:
                if r['gm']==0:self.stop(Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
                else:self.tail(Op.G_FIELD_DOMAIN,self.node(x)[1],self.node(x)[2])
            elif tuple(self.node(x))!=(int(Tag.CONST),0,0,r['decl']):self.stop(Outcome.REJECT,Reason.DECLARATION)
            else:r['gi']+=1;self.tail(Op.G_CTOR)
        elif op==Op.G_FIELD_DOMAIN:
            tag,_,_,index=self.node(x)
            if tag!=Tag.CONST or index>=r['decl']:self.stop(Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
            else:self.tail(Op.G_FIELD_SORT,s['constants'][index][1],y)
        elif op==Op.G_FIELD_SORT:
            tag,_,_,level=self.node(x)
            if tag!=Tag.SORT:self.stop(Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
            elif level>r['gm']:self.stop(Outcome.REJECT,Reason.DECLARATION)
            else:self.tail(Op.G_FIELD_RESULT,y)
        elif op==Op.G_FIELD_RESULT:
            if self.node(x)[0]==Tag.PI:self.stop(Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
            elif tuple(self.node(x))!=(int(Tag.CONST),0,0,r['decl']):self.stop(Outcome.REJECT,Reason.DECLARATION)
            else:r['gi']+=1;self.tail(Op.G_CTOR)
        elif op==Op.G_REC:self.call(Op.WHNF,result,continuation=(Op.G_R0,))
        elif op==Op.G_R0:
            if self.node(result)[0]!=Tag.SORT:self.stop(Outcome.REJECT,Reason.EXPECT_SORT)
            else:self.tail(Op.G_ELIM,s['constants'][s['constants'][r['decl']][3]][1])
        elif op==Op.G_ELIM:
            owner=s['constants'][s['constants'][r['decl']][3]]
            if self.node(x)[3]==0 and s['constants'][r['decl']][4]>0 and owner[4]>1:self.stop(Outcome.REJECT,Reason.DECLARATION)
            else:self.allocate(Tag.CONST,v=s['constants'][r['decl']][3],resume=(Op.G_R1,))
        elif op==Op.G_R1:
            r['gf']=result;self.allocate(Tag.SORT,v=s['constants'][r['decl']][4],resume=(Op.G_R2,))
        elif op==Op.G_R2:self.allocate(Tag.PI,r['gf'],result,resume=(Op.G_R3,))
        elif op==Op.G_R3:
            r['gm']=result;owner=s['constants'][r['decl']][3]
            self.allocate(Tag.VAR,v=s['constants'][owner][4]+1,resume=(Op.G_R4,))
        elif op==Op.G_R4:r['gc']=result;self.allocate(Tag.VAR,v=0,resume=(Op.G_R5,))
        elif op==Op.G_R5:self.allocate(Tag.APP,r['gc'],result,resume=(Op.G_R6,))
        elif op==Op.G_R6:
            self.allocate(Tag.PI,r['gf'],result,resume=(Op.G_RLOOP,))
            r['gi']=s['constants'][s['constants'][r['decl']][3]][4]
        elif op==Op.G_RLOOP:
            r['gt']=result
            if r['gi']==0:self.allocate(Tag.PI,r['gm'],result,resume=(Op.G_RDONE,))
            else:self.tail(Op.G_RCTYPE,s['constants'][s['constants'][r['decl']][3]+r['gi']][1])
        elif op==Op.G_RCTYPE:
            r['ga']=self.node(x)[1] if self.node(x)[0]==Tag.PI else 0
            self.allocate(Tag.CONST,v=s['constants'][r['decl']][3]+r['gi'],resume=(Op.G_RC1,))
        elif op==Op.G_RC1:
            r['gc']=result;self.allocate(Tag.VAR,v=r['gi'] if r['ga'] else r['gi']-1,resume=(Op.G_RC2,))
        elif op==Op.G_RC2:
            if r['ga']:r['gb']=result;self.allocate(Tag.VAR,v=0,resume=(Op.G_RF0,))
            else:self.allocate(Tag.APP,result,r['gc'],resume=(Op.G_RC3,))
        elif op==Op.G_RF0:self.allocate(Tag.APP,r['gc'],result,resume=(Op.G_RF1,))
        elif op==Op.G_RF1:self.allocate(Tag.APP,r['gb'],result,resume=(Op.G_RF2,))
        elif op==Op.G_RF2:self.allocate(Tag.PI,r['ga'],result,resume=(Op.G_RC3,))
        elif op==Op.G_RC3:self.allocate(Tag.PI,result,r['gt'],resume=(Op.G_RNEXT,))
        elif op==Op.G_RNEXT:r['gi']-=1;self.tail(Op.G_RLOOP)
        elif op==Op.G_RDONE:self.call(Op.CONV,result,s['constants'][r['decl']][1],continuation=(Op.ENV_EQ,))
        elif op in (Op.TYPE, Op.ROOT_TYPE):
            cont = (Op.VALUE, x, y, z) if op == Op.TYPE else (Op.ROOT_TERM,)
            self.call(Op.WHNF, result, continuation=cont)
        elif op in (Op.VALUE, Op.ROOT_TERM):
            if self.node(result)[0] != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            elif op == Op.ROOT_TERM:
                self.call(Op.INFER, r['term'], continuation=(Op.ROOT_EQ,))
            elif z == 0:
                r['decl'] += 1; self.tail(Op.ENV)
            else:
                self.call(Op.INFER, y, continuation=(Op.COMMIT, x))
        elif op in (Op.COMMIT, Op.ROOT_EQ):
            self.call(Op.CONV, result, x if op == Op.COMMIT else r['claim'],
                      continuation=(Op.ENV_EQ if op == Op.COMMIT else Op.FINISH,))
        elif op in (Op.ENV_EQ, Op.FINISH):
            if not result:
                self.stop(Outcome.REJECT, Reason.CONVERSION)
            elif op == Op.FINISH:
                self.stop(Outcome.ACCEPT)
            else:
                r['decl'] += 1; self.tail(Op.ENV)
        elif op == Op.RET:
            if not r['sp']:
                self.stop(Outcome.REJECT, Reason.INTERNAL)
            else:
                r['sp'] -= 1
                for key, value in zip(FRAME_FIELDS, s['stack'][r['sp']]):
                    r[key] = value
        elif op == Op.INFER:
            tag, a, b, v = self.node(x)
            if tag == Tag.VAR:
                if v >= r['ctx']:
                    self.stop(Outcome.REJECT, Reason.UNBOUND)
                else:
                    self.tail(Op.SHIFT, s['context'][r['ctx']-1-v][0], 0, v+1)
            elif tag == Tag.SORT:
                if v >= cfg.universe:
                    self.stop(Outcome.RESOURCE, Reason.UNIVERSE)
                else:
                    self.allocate(Tag.SORT, v=v+1)
            elif tag in (Tag.LAM, Tag.PI):
                self.call(Op.INFER, a, continuation=(Op.I_DOM, x))
            elif tag == Tag.APP:
                self.call(Op.INFER, a, continuation=(Op.I_APP, b))
            elif tag==Tag.PROJ:
                self.call(Op.INFER,a,continuation=(Op.P_TYPE,x))
            elif tag == Tag.CONST and v < r['decl']:
                self.ret(s['constants'][v][1])
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op==Op.P_TYPE:self.call(Op.WHNF,result,continuation=(Op.P_FAMILY,x))
        elif op==Op.P_FAMILY:
            family=self.node(x)[3];row=s['constants'][family]
            if self.node(result)[0]!=Tag.CONST or self.node(result)[3]!=family:
                self.stop(Outcome.REJECT,Reason.CONVERSION)
            elif family>=r['decl'] or row[0]!=3 or row[4]!=1:
                self.stop(Outcome.REJECT,Reason.DECLARATION)
            else:self.tail(Op.P_DOMAIN,s['constants'][family+1][1])
        elif op==Op.P_DOMAIN:
            if self.node(x)[0]!=Tag.PI:self.stop(Outcome.REJECT,Reason.DECLARATION)
            else:self.ret(self.node(x)[1])
        elif op == Op.I_DOM:
            self.call(Op.WHNF, result, continuation=(Op.I_BIND, x))
        elif op == Op.I_BIND:
            if self.node(result)[0] != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            elif r['ctx'] >= cfg.context:
                self.stop(Outcome.RESOURCE, Reason.CONTEXT)
            else:
                tag, a, b, _ = self.node(x)
                s['context'][r['ctx']][0] = a
                cont = (Op.I_LAM, a) if tag == Tag.LAM else (Op.I_PI, self.node(result)[3])
                self.call(Op.INFER, b, continuation=cont, context=r['ctx']+1)
        elif op == Op.I_LAM:
            self.allocate(Tag.PI, x, result)
        elif op == Op.I_PI:
            self.call(Op.WHNF, result, continuation=(Op.I_SORT, x))
        elif op == Op.I_SORT:
            tag, _, _, v = self.node(result)
            if tag != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            else:
                self.allocate(Tag.SORT, v=0 if v == 0 else max(x, v))
        elif op == Op.I_APP:
            self.call(Op.WHNF, result, continuation=(Op.I_FUN, x))
        elif op == Op.I_FUN:
            tag, a, b, _ = self.node(result)
            if tag != Tag.PI:
                self.stop(Outcome.REJECT, Reason.EXPECT_PI)
            else:
                self.call(Op.INFER, x, continuation=(Op.I_ARG, a, b, x))
        elif op == Op.I_ARG:
            self.call(Op.CONV, x, result, continuation=(Op.I_CHECK, y, z))
        elif op == Op.I_CHECK:
            if not result:
                self.stop(Outcome.REJECT, Reason.CONVERSION)
            else:
                self.tail(Op.SUBST, x, y)
        elif op == Op.WHNF:
            tag, a, b, v = self.node(x)
            if tag == Tag.APP:
                self.call(Op.WHNF, a, continuation=(Op.W_APP, x, b))
            elif tag==Tag.PROJ:
                if v>=r['decl'] or s['constants'][v][0]!=3 or s['constants'][v][4]!=1:self.stop(Outcome.REJECT,Reason.DECLARATION)
                else:self.call(Op.WHNF,a,continuation=(Op.P_VALUE,x))
            elif tag == Tag.CONST:
                if v >= r['decl']:
                    self.stop(Outcome.REJECT, Reason.SYNTAX)
                elif s['constants'][v][0] == 1:
                    self.tail(Op.WHNF, s['constants'][v][2])
                else:
                    row=s['constants'][v]
                    self.ret(x,head=row[3]+1 if row[0]==5 else 0)
            elif tag in (Tag.VAR, Tag.SORT, Tag.PI, Tag.LAM):
                self.ret(x)
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op == Op.W_APP:
            tag,a,b,_=self.node(result)
            if tag==Tag.LAM:self.call(Op.SUBST,b,y,continuation=(Op.W_BETA,))
            elif r['head'] and r['arity']+1==s['constants'][r['head']-1][4]+2:
                self.call(Op.G_MAJOR,result,y,r['head']-1,s['constants'][r['head']-1][4],continuation=(Op.G_AFTER,x,result,y))
            else:
                head=r['head'];arity=r['arity']+1 if head else 0
                if result==self.node(x)[1]:self.ret(x,head,arity)
                else:self.allocate(Tag.APP,result,y,head=head,arity=arity)
        elif op==Op.G_MAJOR:
            r['ga']=z;self.tail(Op.G_MTYPE,s['constants'][z][1],x,y,w)
        elif op==Op.G_MTYPE:
            if self.node(x)[3]==0 and w==1:self.tail(Op.G_PICK,y,0)
            else:self.call(Op.WHNF,z,continuation=(Op.G_CHOOSE,y,r['ga'],w))
        elif op==Op.G_CHOOSE:
            tag,a,b,_=self.node(result);r['ga']=b if tag==Tag.APP else 0
            self.tail(Op.G_CHEAD,a if tag==Tag.APP else result,x,y,z)
        elif op==Op.G_CHEAD:
            tag,_,_,index=self.node(x)
            row=s['constants'][index]if tag==Tag.CONST and index<r['decl']else None
            if row and row[0]==4 and row[3]==z and row[4]<w:
                self.tail(Op.G_CCHECK,row[1],y,w-1-row[4],r['ga'])
            else:self.ret(0)
        elif op==Op.G_CCHECK:
            if (self.node(x)[0]==Tag.PI)!=bool(w):self.ret(0)
            else:self.call(Op.G_PICK,y,z,continuation=(Op.G_APPLY,w))
        elif op==Op.G_APPLY:
            if x:self.allocate(Tag.APP,result,x)
            else:self.ret(result)
        elif op==Op.G_PICK:
            if self.node(x)[0]!=Tag.APP:self.stop(Outcome.REJECT,Reason.SYNTAX)
            elif y:self.tail(Op.G_PICK,self.node(x)[1],y-1)
            else:self.ret(self.node(x)[2])
        elif op==Op.G_AFTER:
            if result:self.tail(Op.WHNF,result)
            elif self.node(x)[1]==y:self.ret(x)
            else:self.allocate(Tag.APP,y,z)
        elif op==Op.P_VALUE:
            tag,a,b,_=self.node(result)
            if tag==Tag.APP:self.call(Op.P_HEAD,a,b,self.node(x)[3],continuation=(Op.P_DONE,x,result))
            elif self.node(x)[1]==result:self.ret(x)
            else:self.allocate(Tag.PROJ,result,v=self.node(x)[3])
        elif op==Op.P_HEAD:
            tag,_,_,index=self.node(x);row=s['constants'][index]if tag==Tag.CONST and index<r['decl']else None
            if row and row[0]==4 and row[3]==z and row[4]==0:self.tail(Op.P_CHECK,row[1],y)
            else:self.ret(0)
        elif op==Op.P_CHECK:self.ret(y if self.node(x)[0]==Tag.PI else 0)
        elif op==Op.P_DONE:
            if result:self.tail(Op.WHNF,result)
            elif self.node(x)[1]==y:self.ret(x)
            else:self.allocate(Tag.PROJ,y,v=self.node(x)[3])
        elif op==Op.P_REBUILD:
            if self.node(x)[1]==result:self.ret(x)
            else:self.allocate(Tag.PROJ,result,v=self.node(x)[3])
        elif op==Op.P_CONV_DONE:
            if result:self.ret(1)
            else:self.tail(Op.FALLBACK,x,y)
        elif op == Op.W_BETA:
            self.tail(Op.WHNF, result)
        elif op in (Op.SHIFT, Op.SUBST):
            tag, a, b, v = self.node(x)
            if tag in (Tag.SORT, Tag.CONST) or (op == Op.SHIFT and z == 0):
                self.ret(x)
            elif tag == Tag.VAR:
                if op == Op.SHIFT:
                    if v < y:
                        self.ret(x)
                    else:
                        self.allocate(Tag.VAR, v=v+z)
                elif v < z:
                    self.ret(x)
                elif v == z:
                    self.tail(Op.SHIFT, y, 0, z)
                else:
                    self.allocate(Tag.VAR, v=v-1)
            elif tag==Tag.PROJ:self.call(op,a,y,z,continuation=(Op.P_REBUILD,x))
            elif tag in (Tag.PI, Tag.LAM, Tag.APP):
                self.call(op, a, y, z, continuation=(Op.TREE_LEFT, x, y, z, op))
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op == Op.TREE_LEFT:
            tag, _, b, _ = self.node(x)
            binder = int(tag in (Tag.PI, Tag.LAM))
            next_y, next_z = y + (binder if w == Op.SHIFT else 0), z + (binder if w == Op.SUBST else 0)
            if max(next_y, next_z) >= 1 << cfg.word_bits:
                self.stop(Outcome.RESOURCE, Reason.INDEX)
            else:
                self.call(w, b, next_y, next_z, continuation=(Op.TREE_RIGHT, x, result))
        elif op == Op.TREE_RIGHT:
            tag, a, b, _ = self.node(x)
            if a == y and b == result:
                self.ret(x)
            else:
                self.allocate(tag, y, result)
        elif op == Op.CONV:
            if x == y:
                self.ret(1)
            else:
                self.call(Op.WHNF, x, continuation=(Op.C_LEFT, y))
        elif op == Op.C_LEFT:
            self.call(Op.WHNF, x, continuation=(Op.C_RIGHT, result))
        elif op == Op.C_RIGHT:
            tx, ax, bx, vx = self.node(x)
            ty, ay, by, vy = self.node(result)
            if x == result:
                self.ret(1)
            elif tx != ty:
                self.tail(Op.FALLBACK, x, result)
            elif tx==Tag.PROJ:
                if vx==vy:self.call(Op.CONV,ax,ay,continuation=(Op.P_CONV_DONE,x,result))
                else:self.tail(Op.FALLBACK,x,result)
            elif tx in (Tag.VAR, Tag.SORT, Tag.CONST):
                if vx == vy:
                    self.ret(1)
                else:
                    self.tail(Op.FALLBACK, x, result)
            elif tx in (Tag.PI, Tag.LAM, Tag.APP):
                self.call(Op.CONV, ax, ay, continuation=(Op.C_CHILD, x, result, bx, by))
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op == Op.C_CHILD:
            if not result:
                self.tail(Op.FALLBACK, x, y)
            else:
                tag, domain, _, _ = self.node(x)
                binder = tag in (Tag.PI, Tag.LAM)
                if binder and r['ctx'] >= cfg.context:
                    self.stop(Outcome.RESOURCE, Reason.CONTEXT)
                else:
                    if binder:
                        s['context'][r['ctx']][0] = domain
                    self.call(Op.CONV, z, w, continuation=(Op.C_AFTER_CHILD, x, y),
                              context=r['ctx']+int(binder))
        elif op == Op.C_AFTER_CHILD:
            if result:
                self.ret(1)
            else:
                self.tail(Op.FALLBACK, x, y)
        elif op == Op.FALLBACK:
            if self.node(x)[0] in (Tag.SORT, Tag.PI) or self.node(y)[0] in (Tag.SORT, Tag.PI):
                self.ret(0)
            else:
                self.call(Op.INFER, x, continuation=(Op.F_TYPE, x, y))
        elif op == Op.F_TYPE:
            self.call(Op.WHNF, result, continuation=(Op.F_TYPE_WHNF, x, y))
        elif op == Op.F_TYPE_WHNF:
            if self.node(result)[0] == Tag.SORT:
                self.ret(0)
            else:
                self.call(Op.INFER, result, continuation=(Op.F_SORT, x, y, result))
        elif op == Op.F_SORT:
            self.call(Op.WHNF, result, continuation=(Op.F_SORT_WHNF, x, y, z))
        elif op == Op.F_SORT_WHNF:
            tag, _, _, v = self.node(result)
            if tag != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            elif v == 0:
                self.call(Op.INFER, y, continuation=(Op.F_Y, x, y, z))
            else:
                self.tail(Op.ETA, x, y)
        elif op == Op.F_Y:
            self.call(Op.CONV, z, result, continuation=(Op.F_PROOF_RESULT, x, y))
        elif op == Op.F_PROOF_RESULT:
            if result:
                self.ret(1)
            else:
                self.tail(Op.ETA, x, y)
        elif op == Op.ETA:
            left_lam, right_lam = self.node(x)[0] == Tag.LAM, self.node(y)[0] == Tag.LAM
            if left_lam == right_lam:
                self.ret(0)
            elif left_lam:
                self.call(Op.INFER, y, continuation=(Op.E_TYPE, x, y))
            else:
                self.call(Op.INFER, x, continuation=(Op.E_TYPE, y, x))
        elif op == Op.E_TYPE:
            self.call(Op.WHNF, result, continuation=(Op.E_TYPE_WHNF, x, y))
        elif op == Op.E_TYPE_WHNF:
            if self.node(result)[0] != Tag.PI:
                self.ret(0)
            else:
                self.call(Op.CONV, self.node(x)[1], self.node(result)[1], continuation=(Op.E_DOMAIN, x, y))
        elif op == Op.E_DOMAIN:
            if not result:
                self.ret(0)
            else:
                self.call(Op.SHIFT, y, 0, 1, continuation=(Op.E_SHIFT, x))
        elif op == Op.E_SHIFT:
            self.call(Op.E_VAR, 0, continuation=(Op.E_BUILD, x, result))
        elif op == Op.E_VAR:
            self.allocate(Tag.VAR, v=0)
        elif op == Op.E_BUILD:
            self.call(Op.E_MAKE_APP, y, result, continuation=(Op.E_COMPARE, x))
        elif op == Op.E_MAKE_APP:
            self.allocate(Tag.APP, x, y)
        elif op == Op.E_COMPARE:
            if r['ctx'] >= cfg.context:
                self.stop(Outcome.RESOURCE, Reason.CONTEXT)
            else:
                _, domain, body, _ = self.node(x)
                s['context'][r['ctx']][0] = domain
                self.tail(Op.CONV, body, result)
                r['ctx'] += 1
        else:
            self.stop(Outcome.REJECT, Reason.INTERNAL)
        return s

    def run(self, trace=False):
        states = [deepcopy(self.state)] if trace else None
        for _ in range(self.config.fuel+1):
            self.step()
            if trace:
                states.append(deepcopy(self.state))
            if self.state['regs']['status']:
                break
        return states if trace else self.state
