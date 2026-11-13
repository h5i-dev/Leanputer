"""Bounded explicit small-step dependent checker specification.

The separate recursive Oracle is a differential reference. This specification
has no dependency on torch, Boolean gates, or the weighted implementation.
"""
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum

from .dependent import Declaration, Exhausted, TAGS, Tag, parse_expr
from .primitives import PRIMITIVE_SCHEMAS, PRIMITIVE_UNIVERSES, PRIMITIVE_CODES, PROJECTION_FAMILIES, primitive_code, REC_ARITIES, REC_CONSTRUCTORS, REC_MAJOR_ARITIES, ONE_FIELD_RECORDS, TWO_FIELD_RECORDS, LAW_RECORDS, PROJECTION_COUNT


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
    EXPECT_STRUCTURE = 13
    NATURAL = 14


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
    BUILTIN_TYPE = 49
    I_PROJ = 50
    I_PROJ_TYPE = 51
    I_PROJ_FAMILY = 52
    I_PROJ_HEAD = 53
    I_PROJ_ARROW = 54
    W_PROJ = 55
    PROJ_FIELDS = 56
    PROJ_HEAD = 57
    PROJ_SELECT = 58
    TREE_PROJ = 59
    EQ_REC = 60
    EQ_MINOR = 61
    EQ_ANCHOR = 62
    EQ_INDEX = 63
    EQ_SELECT = 64
    EQ_RESULT = 65
    LET_VALUE = 66
    LET_CHECK = 67
    LET_INFER = 68
    SHIFT_LET_A = 69
    SUBST_LET_A = 70
    SHIFT_LET_B = 71
    SUBST_LET_B = 72
    LET_END = 73
    REC_SPINE = 74
    REC_SCAN = 75
    REC_SELECT = 76
    REC_FIELDS = 77
    REC_PICK = 78
    REC_APPLY = 79
    REC_MAJOR = 80
    I_SUBTYPE_PROPERTY = 81
    S_REC_LEFT = 82
    S_REC_RIGHT = 83
    S_REC_APPLY = 84
    S_TYPE = 85
    S_FN = 86
    S_HEAD = 87
    S_RIGHT_TYPE = 88
    S_SAME_TYPE = 89
    S_RIGHT_VAL = 90
    H_REC = 91
    H_CARRIER = 92
    H_MINOR = 93
    H_MOTIVE = 94
    H_ANCHOR = 95
    H_ALPHA = 96
    H_VALUE = 97
    B_PICK = 98
    O_SPINE = 99
    I_ONE_CTOR = 100
    I_ONE_FIELD = 101
    ONE_REC = 102
    N_SUCC = 103
    N_SUCC_VALUE = 104
    N_REC_PRED = 105
    N_REC_CALL = 106
    N_REC_STEP = 107
    N_CTOR = 108
    I_RECORD_PARAMS = 109
    P_UNIT_UNIVERSE = 110
    P_UNIT_MAJOR = 111
    S_PAIR_FIELD = 112
    S_PAIR_NEXT = 113
    LAW_FIELD_TYPE = 114
    LAW_SECOND = 115


@dataclass(frozen=True)
class MachineConfig:
    heap: int = 128
    stack: int = 32
    context: int = 32
    constants: int = 16
    universe: int = 4
    fuel: int = 1024
    atom_pool: bool = False

    def __post_init__(self):
        if type(self.atom_pool)is not bool:raise ValueError('atom_pool must be Boolean')
        for name in ('heap', 'stack', 'context', 'constants'):
            value = getattr(self, name)
            if type(value) is not int or value < 2 or value & (value-1):
                raise ValueError(f'{name} capacity must be a power of two >= 2')
        if self.heap < 16 or type(self.universe) is not int or not 0 <= self.universe < self.heap-1:
            raise ValueError('heap >= 16 and universe below heap-1 required')
        if type(self.fuel) is not int or self.fuel < 1:
            raise ValueError('positive fuel required')

        if self.atom_pool_size>=self.heap:raise ValueError('atom pool must fit the heap')

    @property
    def atom_variables(self):return min(8,self.context)if self.atom_pool else 0

    @property
    def atom_pool_size(self):return self.atom_variables+self.universe+1 if self.atom_pool else 0

    @property
    def universe_bits(self):
        return max(1,self.universe.bit_length())

    @property
    def primitive_bits(self):
        return max(PRIMITIVE_CODES.values()).bit_length()

    @property
    def word_bits(self):
        return max(7,int(max(Op)).bit_length(),max(PRIMITIVE_CODES.values()).bit_length(),
                   min(3,max(PRIMITIVE_UNIVERSES.values(),default=0))*self.universe_bits,
                   self.primitive_bits+max(0,max(PRIMITIVE_UNIVERSES.values(),default=0)-3)*self.universe_bits,
                   max(self.heap,self.stack,self.context,self.constants).bit_length())


REGISTERS = ('mode', 'x', 'y', 'z', 'w', 'r', 'ctx', 'sp', 'free', 'scan',
             'decl', 'decl_count', 'term', 'claim', 'fuel', 'status', 'reason', 'head', 'arity')
HEAP_FIELDS = ('tag', 'a', 'b', 'v')
FRAME_FIELDS = ('mode', 'x', 'y', 'z', 'w', 'ctx')


def prepare(config, term, claim, declarations=()):
    """Syntax-only postorder DAG encoding, including all environment assumptions."""
    declarations = tuple(d if isinstance(d, Declaration) else Declaration(**d) for d in declarations)
    if len(declarations) > config.constants:
        raise Exhausted('constant table capacity')
    names = {d.name: i for i, d in enumerate(declarations)}
    if len(names) != len(declarations):
        raise ValueError('duplicate declaration names')
    heap, cache = [[0, 0, 0, 0]], {}
    if config.atom_pool:
        for tag,limit in ((Tag.VAR,config.atom_variables),(Tag.SORT,config.universe+1)):
            for value in range(limit):
                cache[('var'if tag==Tag.VAR else 'sort',value)]=len(heap)
                heap.append([int(tag),0,0,value])
    def visit(expr):
        expr = parse_expr(expr)
        if expr in cache:
            return cache[expr]
        tag = expr[0]
        a = b = v = 0
        if tag in ('pi', 'lam', 'app'):
            a, b = visit(expr[1]), visit(expr[2])
        elif tag=='let':
            a,b,v=(visit(child)for child in expr[1:])
        elif tag == 'const':
            if expr[1] not in names:
                raise ValueError(f'undeclared constant: {expr[1]}')
            v = names[expr[1]]
        elif tag == 'proj':
            a=visit(expr[3]);v=PROJECTION_FAMILIES[expr[1]]+expr[2]
        elif tag == 'builtin':
            v = primitive_code(expr)
            if any(level >= 1<<config.universe_bits for level in expr[2:]):
                raise Exhausted('universe lane encoding capacity')
            a=sum(level<<(index*config.universe_bits)for index,level in enumerate(expr[2:5]))
            b=sum(level<<(index*config.universe_bits)for index,level in enumerate(expr[5:]))
        else:
            v = expr[1]
        if max(a,b,v) >= 1 << config.word_bits:
            raise Exhausted('natural scalar encoding capacity' if tag=='nat' else 'syntax scalar encoding capacity')
        if len(heap) >= config.heap:
            raise Exhausted('input heap capacity')
        idx = len(heap)
        heap.append([int(TAGS[tag]), a, b, v]); cache[expr] = idx
        return idx
    constants = []
    for d in declarations:
        ty = visit(d.type)
        value = visit(d.value) if d.value is not None else 0
        constants.append([2 if d.opaque else int(d.value is not None), ty, value])
    term_id, claim_id = visit(term), visit(claim)
    regs = {name: 0 for name in REGISTERS}
    regs.update(free=len(heap), scan=1, decl_count=len(constants), term=term_id,
                claim=claim_id, fuel=config.fuel)
    heap.extend([[0]*4 for _ in range(config.heap-len(heap))])
    constants.extend([[0]*3 for _ in range(config.constants-len(constants))])
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
        self.state['regs'].update(mode=int(Op.RET),r=result,head=head,arity=arity)

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
        if resume is not None:
            self.tail(*resume)

    def allocate_atom(self,tag,v):
        # Only standalone leaves use this path. Fixed schema rows must stay
        # contiguous for their relative-pointer relocation.
        if self.config.atom_pool:
            if v>=1<<self.config.word_bits:
                self.stop(Outcome.RESOURCE,Reason.INDEX);return
            if tag==Tag.VAR and v<self.config.atom_variables:
                self.ret(1+v);return
            if tag==Tag.SORT and v<=self.config.universe:
                self.ret(1+self.config.atom_variables+v);return
        self.allocate(tag,v=v)

    def neutral_projection(self,original,base):
        _,child,_,projection=self.node(original)
        if child==base: self.ret(original)
        else: self.allocate(Tag.PROJ,base,v=projection)

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
        if (not cfg.atom_pool_size+1 <= r['free'] <= cfg.heap or r['sp'] > cfg.stack or r['ctx'] > cfg.context
                or not r['decl'] <= r['decl_count'] <= cfg.constants or (r['head']!=0 and r['head']not in REC_ARITIES) or r['arity']>=REC_ARITIES.get(r['head'],1)):
            self.stop(Outcome.REJECT, Reason.SYNTAX); return s
        pointers = []
        if op in (Op.INFER, Op.I_BIND, Op.WHNF, Op.W_APP, Op.SHIFT, Op.SUBST,
                  Op.TREE_LEFT, Op.TREE_RIGHT, Op.CONV, Op.C_RIGHT, Op.C_CHILD,
                  Op.FALLBACK, Op.ETA, Op.E_TYPE_WHNF, Op.E_COMPARE, Op.I_PROJ, Op.I_PROJ_TYPE,
                  Op.I_PROJ_FAMILY, Op.I_PROJ_HEAD, Op.I_PROJ_ARROW, Op.W_PROJ, Op.PROJ_FIELDS, Op.PROJ_HEAD, Op.PROJ_SELECT, Op.TREE_PROJ, Op.EQ_REC, Op.EQ_MINOR, Op.EQ_ANCHOR, Op.EQ_INDEX, Op.EQ_RESULT,
                  Op.LET_VALUE, Op.LET_CHECK, Op.SHIFT_LET_A, Op.SUBST_LET_A, Op.SHIFT_LET_B, Op.SUBST_LET_B, Op.LET_END,
                  Op.REC_SPINE, Op.REC_SCAN, Op.REC_SELECT, Op.REC_FIELDS, Op.REC_PICK, Op.REC_APPLY, Op.REC_MAJOR,
                  Op.I_SUBTYPE_PROPERTY, Op.S_REC_LEFT, Op.S_REC_RIGHT, Op.S_REC_APPLY, Op.S_TYPE, Op.S_FN, Op.S_HEAD, Op.S_RIGHT_TYPE, Op.S_SAME_TYPE, Op.S_RIGHT_VAL,
                  Op.H_REC, Op.H_CARRIER, Op.H_MINOR, Op.H_MOTIVE, Op.H_ANCHOR, Op.H_ALPHA, Op.H_VALUE, Op.B_PICK, Op.O_SPINE, Op.I_ONE_CTOR, Op.ONE_REC,
                  Op.N_SUCC, Op.N_REC_PRED, Op.N_REC_CALL, Op.N_REC_STEP, Op.N_CTOR, Op.I_RECORD_PARAMS, Op.P_UNIT_UNIVERSE, Op.P_UNIT_MAJOR):
            pointers.append(x)
        if op in (Op.VALUE, Op.ROOT_TERM, Op.I_BIND, Op.I_SORT, Op.I_FUN, Op.W_APP,
                  Op.C_RIGHT, Op.F_TYPE_WHNF, Op.F_SORT_WHNF, Op.E_TYPE_WHNF, Op.I_PROJ_TYPE, Op.W_PROJ, Op.TREE_PROJ, Op.LET_VALUE, Op.LET_INFER, Op.SHIFT_LET_A, Op.SUBST_LET_A, Op.SHIFT_LET_B, Op.SUBST_LET_B, Op.LET_END):
            pointers.append(result)
        if op in (Op.REC_SPINE,Op.I_SUBTYPE_PROPERTY,Op.S_RIGHT_TYPE,Op.I_ONE_CTOR,Op.I_ONE_FIELD,Op.N_SUCC_VALUE,Op.P_UNIT_UNIVERSE,Op.P_UNIT_MAJOR):pointers.append(result)
        if op in (Op.CONV, Op.FALLBACK, Op.ETA, Op.I_PROJ_FAMILY, Op.I_PROJ_HEAD, Op.PROJ_FIELDS, Op.PROJ_SELECT, Op.EQ_MINOR, Op.EQ_ANCHOR, Op.EQ_INDEX, Op.EQ_RESULT, Op.REC_MAJOR, Op.REC_APPLY, Op.REC_FIELDS, Op.REC_PICK,
                  Op.S_REC_LEFT, Op.S_REC_RIGHT, Op.S_REC_APPLY, Op.S_TYPE, Op.S_FN, Op.S_HEAD, Op.S_RIGHT_TYPE, Op.S_SAME_TYPE, Op.S_RIGHT_VAL,
                  Op.H_CARRIER, Op.H_MINOR, Op.H_MOTIVE, Op.H_ANCHOR, Op.H_ALPHA, Op.H_VALUE, Op.O_SPINE, Op.ONE_REC, Op.N_REC_CALL, Op.N_REC_STEP, Op.N_CTOR, Op.I_RECORD_PARAMS, Op.P_UNIT_UNIVERSE):
            pointers.append(y)
        if op in (Op.S_REC_RIGHT,Op.S_REC_APPLY,Op.S_TYPE,Op.S_FN,Op.S_HEAD,Op.S_RIGHT_TYPE,Op.N_REC_STEP,Op.N_CTOR) or (op==Op.ETA and z):pointers.append(z)
        if op in (Op.S_PAIR_FIELD,Op.S_PAIR_NEXT):pointers.extend((x,y))
        if op in (Op.LAW_FIELD_TYPE,Op.LAW_SECOND):pointers.append(x)
        if op==Op.LAW_FIELD_TYPE:pointers.append(result)
        if op==Op.LAW_SECOND:pointers.append(y)
        if any(not 0 < pointer < r['free'] for pointer in pointers):
            self.stop(Outcome.REJECT, Reason.SYNTAX); return s
        if op == Op.VALIDATE:
            if r['scan'] >= r['free']:
                self.tail(Op.ENV)
            else:
                i = r['scan']; tag, a, b, v = s['heap'][i]
                valid = 1 <= tag <= int(Tag.NAT)
                if cfg.atom_pool and i<=cfg.atom_pool_size:
                    expected=(int(Tag.VAR),0,0,i-1)if i<=cfg.atom_variables else (int(Tag.SORT),0,0,i-cfg.atom_variables-1)
                    valid &= (tag,a,b,v)==expected
                if tag in (Tag.PI, Tag.LAM, Tag.APP):
                    valid &= 0 < a < i and 0 < b < i and v == 0
                elif tag == Tag.PROJ:
                    valid &= 0<a<i and b==0 and v<PROJECTION_COUNT
                elif tag == Tag.LET:
                    valid &= all(0<child<i for child in (a,b,v))
                elif tag == Tag.BUILTIN:
                    counts={PRIMITIVE_CODES[name]:count for name,count in PRIMITIVE_UNIVERSES.items()}
                    count=counts.get(v,0)
                    valid &= v in PRIMITIVE_SCHEMAS and a < 1<<(min(count,3)*cfg.universe_bits) and b < 1<<(max(0,count-3)*cfg.universe_bits)
                else:
                    valid &= a == b == 0
                if tag == Tag.CONST:
                    valid &= v < r['decl_count']
                if not valid:
                    self.stop(Outcome.REJECT, Reason.SYNTAX)
                elif (tag==Tag.SORT and v>cfg.universe) or (tag==Tag.BUILTIN and any((((a|(b<<(3*cfg.universe_bits)))>>(index*cfg.universe_bits))&((1<<cfg.universe_bits)-1))>=cfg.universe for index in range(count))):
                    self.stop(Outcome.RESOURCE, Reason.UNIVERSE)
                else:
                    r['scan'] += 1
        elif op == Op.BUILTIN_TYPE:
            code=x&((1<<cfg.primitive_bits)-1)
            schema=PRIMITIVE_SCHEMAS.get(code,())
            count=next((count for name,count in PRIMITIVE_UNIVERSES.items()if PRIMITIVE_CODES[name]==code),0)
            if x >= 1<<(cfg.primitive_bits+max(0,count-3)*cfg.universe_bits):schema=()
            if not 0 <= y < len(schema) or z<=0 or z+y!=r['free']:
                self.stop(Outcome.REJECT,Reason.SYNTAX)
            else:
                tag,a,b,v=schema[y]
                binary=tag in (Tag.PI,Tag.APP)
                resume=(Op.BUILTIN_TYPE,x,y+1,z,w) if y+1<len(schema) else None
                u=w&((1<<cfg.universe_bits)-1); second=(w>>cfg.universe_bits)&((1<<cfg.universe_bits)-1)
                def resolve(value):
                    if isinstance(value,tuple):
                        if value[0]=='succ':return resolve(value[1])+1
                        if value[0]=='max':return max(resolve(part)for part in value[1:])
                        raise ValueError('unknown fixed universe expression')
                    return u if value==-1 else second if value==-2 else max(1,u) if value==-3 else u+1 if value==-4 else second+1 if value==-5 else (w>>(2*cfg.universe_bits))&((1<<cfg.universe_bits)-1) if value==-6 else (x>>cfg.primitive_bits)&((1<<cfg.universe_bits)-1) if value==-8 else value
                encoded_a=sum(resolve(level)<<(index*cfg.universe_bits)for index,level in enumerate(a[:3])) if tag==Tag.BUILTIN else z+a if binary or tag==Tag.PROJ else resolve(a)
                encoded_b=sum(resolve(level)<<(index*cfg.universe_bits)for index,level in enumerate(a[3:])) if tag==Tag.BUILTIN else z+b if binary else resolve(b)
                self.allocate(tag,encoded_a,encoded_b,resolve(v),resume)
        elif op == Op.ENV:
            if r['decl'] == r['decl_count']:
                self.call(Op.INFER, r['claim'], continuation=(Op.ROOT_TYPE,))
            else:
                kind, ty, value = s['constants'][r['decl']]
                if kind not in (0, 1, 2) or not 0 < ty < r['free'] or (kind and not 0 < value < r['free']):
                    self.stop(Outcome.REJECT, Reason.SYNTAX)
                else:
                    self.call(Op.INFER, ty, continuation=(Op.TYPE, ty, value, kind))
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
            elif tag==Tag.NAT:self.allocate(Tag.BUILTIN,v=64)
            elif tag == Tag.SORT:
                if v >= cfg.universe:
                    self.stop(Outcome.RESOURCE, Reason.UNIVERSE)
                else:
                    self.allocate_atom(Tag.SORT, v=v+1)
            elif tag == Tag.BUILTIN:
                if v==0:
                    self.allocate_atom(Tag.SORT,v=0)
                else:
                    self.tail(Op.BUILTIN_TYPE,v|(b<<cfg.primitive_bits),0,r['free'],a)
            elif tag==Tag.PROJ:
                self.call(Op.INFER,a,continuation=(Op.I_PROJ,x))
            elif tag in (Tag.LAM, Tag.PI, Tag.LET):
                self.call(Op.INFER, a, continuation=(Op.I_DOM, x))
            elif tag == Tag.APP:
                self.call(Op.INFER, a, continuation=(Op.I_APP, b))
            elif tag == Tag.CONST and v < r['decl']:
                self.ret(s['constants'][v][1])
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op==Op.I_PROJ:
            self.call(Op.WHNF,result,continuation=(Op.I_PROJ_TYPE,x))
        elif op==Op.I_PROJ_TYPE:
            tag,a,b,_=self.node(result)
            projection=self.node(x)[3]
            record=next((record for record in ONE_FIELD_RECORDS.values()if record['projection']==projection),None)
            law=next((record for record in LAW_RECORDS.values()if record['projection']<=projection<record['projection']+2),None)
            if law:self.call(Op.I_RECORD_PARAMS,result,x,1,continuation=(Op.LAW_FIELD_TYPE,x))
            elif record:self.call(Op.I_RECORD_PARAMS,result,x,record.get('parameters',1),continuation=(Op.I_ONE_FIELD,))
            elif tag!=Tag.APP: self.stop(Outcome.REJECT,Reason.EXPECT_STRUCTURE)
            else: self.tail(Op.I_PROJ_FAMILY,a,x,b)
        elif op==Op.I_RECORD_PARAMS:
            tag,a,b,v=self.node(x)
            projection=self.node(y)[3]
            record=next((record for record in ONE_FIELD_RECORDS.values()if record['projection']==projection),None)
            if record is None:record=next(record for record in LAW_RECORDS.values()if record['projection']<=projection<record['projection']+2)
            if z:
                if tag!=Tag.APP:self.stop(Outcome.REJECT,Reason.EXPECT_STRUCTURE)
                else:self.call(Op.I_RECORD_PARAMS,a,y,z-1,continuation=(Op.I_ONE_CTOR,b))
            elif tag!=Tag.BUILTIN or v!=record['code']:self.stop(Outcome.REJECT,Reason.EXPECT_STRUCTURE)
            else:self.tail(Op.BUILTIN_TYPE,record['code']+1,0,r['free'],a)
        elif op==Op.I_PROJ_FAMILY:
            tag,a,b,_=self.node(x)
            if tag!=Tag.APP: self.stop(Outcome.REJECT,Reason.EXPECT_STRUCTURE)
            else: self.tail(Op.I_PROJ_HEAD,a,y,b,z)
        elif op==Op.I_ONE_CTOR:
            if self.node(result)[0]!=Tag.PI:self.stop(Outcome.REJECT,Reason.SYNTAX)
            else:self.tail(Op.SUBST,self.node(result)[2],x)
        elif op==Op.I_ONE_FIELD:
            if self.node(result)[0]!=Tag.PI:self.stop(Outcome.REJECT,Reason.SYNTAX)
            else:self.ret(self.node(result)[1])
        elif op==Op.LAW_FIELD_TYPE:
            projection=self.node(x)[3];record=next(record for record in LAW_RECORDS.values()if record['projection']<=projection<record['projection']+2)
            if self.node(result)[0]!=Tag.PI:self.stop(Outcome.REJECT,Reason.SYNTAX)
            elif projection==record['projection']:self.ret(self.node(result)[1])
            else:self.allocate(Tag.PROJ,self.node(x)[1],v=record['projection'],resume=(Op.LAW_SECOND,result,r['free']))
        elif op==Op.LAW_SECOND:
            if self.node(x)[0]!=Tag.PI:self.stop(Outcome.REJECT,Reason.SYNTAX)
            else:self.call(Op.SUBST,self.node(x)[2],y,continuation=(Op.I_ONE_FIELD,))
        elif op==Op.I_PROJ_HEAD:
            tag,a,_,v=self.node(x); projection=self.node(y)[3]
            pair=next((record for record in TWO_FIELD_RECORDS.values()if record['projection']<=projection<record['projection']+2),None)
            expected=pair['code']if pair else 2 if projection<2 else 4 if projection<4 else 32
            if tag!=Tag.BUILTIN or (not pair and expected!=32 and a) or v!=expected:
                self.stop(Outcome.REJECT,Reason.EXPECT_STRUCTURE)
            elif pair:self.ret(w if projection==pair['projection']+1 else z)
            elif projection==4:self.ret(z)
            elif projection==5:self.allocate(Tag.PROJ,self.node(y)[1],v=4,resume=(Op.I_SUBTYPE_PROPERTY,w))
            elif projection>=2: self.ret(w if projection%2 else z)
            else:
                domain,codomain=(z,w) if projection==0 else (w,z)
                self.call(Op.SHIFT,codomain,0,1,continuation=(Op.I_PROJ_ARROW,domain))
        elif op==Op.I_PROJ_ARROW:
            self.allocate(Tag.PI,x,result)
        elif op==Op.I_SUBTYPE_PROPERTY:
            self.allocate(Tag.APP,x,result)
        elif op == Op.I_DOM:
            self.call(Op.WHNF, result, continuation=(Op.I_BIND, x))
        elif op == Op.I_BIND:
            if self.node(result)[0] != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            elif self.node(x)[0]==Tag.LET:
                self.call(Op.INFER,self.node(x)[2],continuation=(Op.LET_VALUE,x))
            elif r['ctx'] >= cfg.context:
                self.stop(Outcome.RESOURCE, Reason.CONTEXT)
            else:
                tag, a, b, _ = self.node(x)
                s['context'][r['ctx']][0] = a
                cont = (Op.I_LAM, a) if tag == Tag.LAM else (Op.I_PI, self.node(result)[3])
                self.call(Op.INFER, b, continuation=cont, context=r['ctx']+1)
        elif op==Op.LET_VALUE:
            self.call(Op.CONV,self.node(x)[1],result,continuation=(Op.LET_CHECK,x))
        elif op==Op.LET_CHECK:
            if not result: self.stop(Outcome.REJECT,Reason.CONVERSION)
            else: self.call(Op.SUBST,self.node(x)[3],self.node(x)[2],continuation=(Op.LET_INFER,))
        elif op==Op.LET_INFER:
            self.tail(Op.INFER,result)
        elif op == Op.I_LAM:
            self.allocate(Tag.PI, x, result)
        elif op == Op.I_PI:
            self.call(Op.WHNF, result, continuation=(Op.I_SORT, x))
        elif op == Op.I_SORT:
            tag, _, _, v = self.node(result)
            if tag != Tag.SORT:
                self.stop(Outcome.REJECT, Reason.EXPECT_SORT)
            else:
                self.allocate_atom(Tag.SORT, v=0 if v == 0 else max(x, v))
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
            if tag==Tag.PROJ:
                self.call(Op.WHNF,a,continuation=(Op.W_PROJ,x))
            elif tag == Tag.APP:
                self.call(Op.WHNF, a, continuation=(Op.W_APP, x, b))
            elif tag==Tag.LET:
                self.call(Op.SUBST,v,b,continuation=(Op.W_BETA,))
            elif tag == Tag.CONST:
                if v >= r['decl']:
                    self.stop(Outcome.REJECT, Reason.SYNTAX)
                elif s['constants'][v][0] == 1:
                    self.tail(Op.WHNF, s['constants'][v][2])
                else:
                    self.ret(x)
            elif tag==Tag.BUILTIN and v==65:self.allocate(Tag.NAT,v=0)
            elif tag in (Tag.VAR, Tag.SORT, Tag.PI, Tag.LAM, Tag.BUILTIN, Tag.NAT):
                self.ret(x,v if tag==Tag.BUILTIN and v in REC_ARITIES else 0)
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op==Op.W_PROJ:
            tag,a,b,_=self.node(result)
            if tag==Tag.APP: self.tail(Op.PROJ_FIELDS,a,x,result,b)
            else: self.neutral_projection(x,result)
        elif op==Op.PROJ_FIELDS:
            tag,a,b,_=self.node(x)
            if tag==Tag.APP:
                projection=self.node(y)[3]
                record=next((record for record in ONE_FIELD_RECORDS.values() if record['projection']==projection),None)
                pair=next((record for record in TWO_FIELD_RECORDS.values()if record['projection']<=projection<record['projection']+2),None)
                law=next((record for record in LAW_RECORDS.values()if record['projection']<=projection<record['projection']+2),None)
                ctor=record['code']+1 if record else (pair or law)['code']+1 if pair or law else 3 if projection<2 else 5 if projection<4 else 33
                self.call(Op.PROJ_HEAD,a,record.get('parameters',1)-1 if record else 1 if law else 2,ctor,continuation=(Op.PROJ_SELECT,y,z,b,w))
            else: self.neutral_projection(y,z)
        elif op==Op.PROJ_HEAD:
            tag,a,_,v=self.node(x)
            if y:
                if tag==Tag.APP: self.tail(Op.PROJ_HEAD,a,y-1,z)
                else: self.ret(0)
            else: self.ret(int(tag==Tag.BUILTIN and (a==0 or z==33 or z in {record['code']+1 for record in list(ONE_FIELD_RECORDS.values())+list(TWO_FIELD_RECORDS.values())+list(LAW_RECORDS.values())}) and v==z))
        elif op==Op.PROJ_SELECT:
            if result:
                projection=self.node(x)[3]
                pair=next((record for record in list(TWO_FIELD_RECORDS.values())+list(LAW_RECORDS.values())if record['projection']<=projection<record['projection']+2),None)
                second=projection==pair['projection']+1 if pair else projection>=6 or projection%2
                self.tail(Op.WHNF,w if second else z)
            else: self.neutral_projection(x,y)
        elif op == Op.W_APP:
            tag, _, body, _ = self.node(result)
            if tag == Tag.LAM:
                self.call(Op.SUBST, body, y, continuation=(Op.W_BETA,))
            elif r['head'] in REC_ARITIES:
                head=r['head']
                if r['arity']<REC_ARITIES[head]-1:
                    if result==self.node(x)[1]:self.ret(x,head,r['arity']+1)
                    else:self.allocate(Tag.APP,result,y,head=head,arity=r['arity']+1)
                elif head==8:self.call(Op.EQ_REC,result,continuation=(Op.EQ_RESULT,x,result,y))
                elif head==11:self.tail(Op.WHNF,self.node(result)[2])
                elif head==34:self.tail(Op.S_REC_LEFT,self.node(result)[2],y)
                elif head in {record['code']+2 for record in list(TWO_FIELD_RECORDS.values())+list(LAW_RECORDS.values())}:
                    projection=next(record['projection']for record in list(TWO_FIELD_RECORDS.values())+list(LAW_RECORDS.values())if record['code']+2==head)
                    self.tail(Op.S_REC_LEFT,self.node(result)[2],y,projection)
                elif head==37:self.call(Op.H_REC,result,continuation=(Op.EQ_RESULT,x,result,y))
                elif head==66:self.call(Op.N_SUCC,y,continuation=(Op.EQ_RESULT,x,result,y))
                elif head in {record['code']+2 for record in ONE_FIELD_RECORDS.values() if record['data']}:
                    projection=next(record['projection'] for record in ONE_FIELD_RECORDS.values() if record['code']+2==head)
                    self.tail(Op.ONE_REC,self.node(result)[2],y,projection)
                else:
                    self.call(Op.REC_MAJOR,result,y,head,continuation=(Op.EQ_RESULT,x,result,y))
            elif result == self.node(x)[1]:
                self.ret(x)
            else:
                self.allocate(Tag.APP, result, y)
        elif op in (Op.EQ_REC,Op.EQ_MINOR,Op.EQ_ANCHOR,Op.EQ_INDEX):
            tag,a,b,_=self.node(x)
            if tag!=Tag.APP: self.stop(Outcome.REJECT,Reason.SYNTAX)
            elif op==Op.EQ_REC: self.tail(Op.EQ_MINOR,a,b)
            elif op==Op.EQ_MINOR: self.call(Op.EQ_ANCHOR,a,y,continuation=(Op.EQ_SELECT,b))
            elif op==Op.EQ_ANCHOR: self.tail(Op.EQ_INDEX,a,y)
            else: self.tail(Op.CONV,b,y)
        elif op==Op.EQ_SELECT:
            self.ret(x if result else 0)
        elif op==Op.EQ_RESULT:
            if result: self.tail(Op.WHNF,result)
            elif self.node(x)[1]==y: self.ret(x)
            else: self.allocate(Tag.APP,y,z)
        elif op in (Op.H_REC,Op.H_CARRIER,Op.H_MINOR,Op.H_MOTIVE,Op.H_ANCHOR,Op.H_ALPHA):
            tag,a,b,_=self.node(x)
            if tag!=Tag.APP:self.stop(Outcome.REJECT,Reason.SYNTAX)
            elif op==Op.H_REC:self.tail(Op.H_CARRIER,a,b)
            elif op==Op.H_CARRIER:self.tail(Op.H_MINOR,a,b,y)
            elif op==Op.H_MINOR:self.call(Op.H_MOTIVE,a,y,z,continuation=(Op.EQ_SELECT,b))
            elif op==Op.H_MOTIVE:self.tail(Op.H_ANCHOR,a,y,z)
            elif op==Op.H_ANCHOR:self.tail(Op.H_ALPHA,a,y,b,z)
            else:self.call(Op.CONV,b,y,continuation=(Op.H_VALUE,z,w))
        elif op==Op.H_VALUE:
            if result:self.tail(Op.CONV,x,y)
            else:self.ret(0)
        elif op==Op.N_SUCC:
            self.call(Op.WHNF,x,continuation=(Op.N_SUCC_VALUE,))
        elif op==Op.P_UNIT_UNIVERSE:
            tag,levels,_,code=self.node(result)
            carrier=levels>>cfg.universe_bits
            if tag!=Tag.BUILTIN or code!=73:self.stop(Outcome.REJECT,Reason.SYNTAX)
            elif carrier:self.ret(self.node(x)[2])
            else:self.call(Op.WHNF,y,continuation=(Op.P_UNIT_MAJOR,self.node(x)[2]))
        elif op==Op.P_UNIT_MAJOR:
            tag,carrier,_,code=self.node(result)
            self.ret(x if tag==Tag.BUILTIN and code==72 and carrier==0 else 0)
        elif op==Op.N_SUCC_VALUE:
            tag,_,_,value=self.node(result)
            if tag!=Tag.NAT:self.ret(0)
            elif value==(1<<cfg.word_bits)-1:self.stop(Outcome.RESOURCE,Reason.NATURAL)
            else:self.allocate(Tag.NAT,v=value+1)
        elif op==Op.REC_MAJOR:
            if z==73:self.call(Op.REC_SCAN,x,2,continuation=(Op.P_UNIT_UNIVERSE,x,y))
            else:self.call(Op.WHNF,y,continuation=(Op.REC_SPINE,x,z))
        elif op==Op.REC_SPINE:
            # Entered with normalized major in r, saved partial fn/head in x/y.
            tag,a,b,_=self.node(result)
            if y==41:
                ctor=self.node(result)[3] if tag==Tag.BUILTIN else -1
                if ctor==40:self.ret(self.node(x)[2])
                elif ctor==39:self.tail(Op.B_PICK,self.node(x)[1])
                else:self.ret(0)
            elif y==67:
                if tag==Tag.APP:self.tail(Op.N_CTOR,a,x,b)
                elif tag!=Tag.NAT:self.ret(0)
                elif self.node(result)[3]==0:self.tail(Op.B_PICK,self.node(x)[1])
                else:self.tail(Op.N_REC_PRED,x,self.node(result)[3]-1)
            elif tag!=Tag.APP:self.ret(0)
            elif y==45:self.tail(Op.O_SPINE,a,x,b)
            else:self.call(Op.REC_SCAN,a,REC_MAJOR_ARITIES[y]-1,continuation=(Op.REC_SELECT,x,y,b,a))
        elif op==Op.B_PICK:
            self.ret(self.node(x)[2])
        elif op==Op.N_REC_PRED:
            self.allocate(Tag.NAT,v=y,resume=(Op.N_REC_CALL,x,r['free']))
        elif op==Op.N_REC_CALL:
            self.allocate(Tag.APP,x,y,resume=(Op.N_REC_STEP,x,y,r['free']))
        elif op==Op.N_REC_STEP:
            self.allocate(Tag.APP,self.node(x)[2],y,resume=(Op.REC_APPLY,r['free'],z))
        elif op==Op.N_CTOR:
            if self.node(x)[0]==Tag.BUILTIN and self.node(x)[3]==66:self.tail(Op.N_REC_CALL,y,z)
            else:self.ret(0)
        elif op==Op.O_SPINE:
            tag,a,_,v=self.node(x)
            if tag==Tag.BUILTIN and v==43:self.tail(Op.B_PICK,self.node(y)[1])
            elif tag==Tag.APP:self.call(Op.REC_SCAN,a,0,continuation=(Op.REC_SELECT,y,45,z))
            else:self.ret(0)
        elif op==Op.REC_SCAN:
            if y==0:self.ret(x)
            elif self.node(x)[0]!=Tag.APP:self.ret(0)
            else:self.tail(Op.REC_SCAN,self.node(x)[1],y-1)
        elif op==Op.REC_SELECT:
            ctor=self.node(result)[3] if result and self.node(result)[0]==Tag.BUILTIN else -1
            if y==45:
                if ctor==44:self.tail(Op.REC_APPLY,self.node(x)[2],z)
                else:self.ret(0)
            elif ctor not in REC_CONSTRUCTORS[y]:self.ret(0)
            elif y in (16,26) or y in {record['code']+2 for record in ONE_FIELD_RECORDS.values()}:
                self.tail(Op.REC_APPLY,self.node(x)[2],z)
            elif y in (12,13,19):self.tail(Op.REC_FIELDS,w,self.node(x)[2],z)
            elif y==27:self.tail(Op.REC_PICK,self.node(x)[1],z)
            elif ctor==22 or (y==31 and ctor==30):self.tail(Op.REC_APPLY,self.node(x)[2],z)
            else:self.tail(Op.REC_PICK,self.node(x)[1],z)
        elif op==Op.REC_FIELDS:
            self.allocate(Tag.APP,y,self.node(x)[2],resume=(Op.REC_APPLY,r['free'],z))
        elif op==Op.REC_PICK:
            self.tail(Op.REC_APPLY,self.node(x)[2],y)
        elif op==Op.REC_APPLY:
            self.allocate(Tag.APP,x,y,resume=(Op.W_BETA,))
        elif op==Op.S_REC_LEFT:
            self.allocate(Tag.PROJ,y,v=z or 4,resume=(Op.S_REC_RIGHT,x,y,r['free'],(z or 4)+1))
        elif op==Op.ONE_REC:
            self.allocate(Tag.PROJ,y,v=z,resume=(Op.REC_APPLY,x,r['free']))
        elif op==Op.S_REC_RIGHT:
            self.allocate(Tag.PROJ,y,v=w,resume=(Op.S_REC_APPLY,x,z,r['free']))
        elif op==Op.S_REC_APPLY:
            self.allocate(Tag.APP,x,y,resume=(Op.REC_APPLY,r['free'],z))
        elif op == Op.W_BETA:
            self.tail(Op.WHNF, result)
        elif op in (Op.SHIFT, Op.SUBST):
            tag, a, b, v = self.node(x)
            if tag in (Tag.SORT, Tag.CONST,Tag.BUILTIN,Tag.NAT) or (op == Op.SHIFT and z == 0):
                self.ret(x)
            elif tag == Tag.VAR:
                if op == Op.SHIFT:
                    if v < y:
                        self.ret(x)
                    else:
                        self.allocate_atom(Tag.VAR, v=v+z)
                elif v < z:
                    self.ret(x)
                elif v == z:
                    self.tail(Op.SHIFT, y, 0, z)
                else:
                    self.allocate_atom(Tag.VAR, v=v-1)
            elif tag==Tag.PROJ:
                self.call(op,a,y,z,continuation=(Op.TREE_PROJ,x))
            elif tag==Tag.LET:
                self.call(op,a,y,z,continuation=(Op.SHIFT_LET_A if op==Op.SHIFT else Op.SUBST_LET_A,x,y,z))
            elif tag in (Tag.PI, Tag.LAM, Tag.APP):
                self.call(op, a, y, z, continuation=(Op.TREE_LEFT, x, y, z, op))
            else:
                self.stop(Outcome.REJECT, Reason.SYNTAX)
        elif op==Op.TREE_PROJ:
            _,a,_,v=self.node(x)
            if a==result: self.ret(x)
            else: self.allocate(Tag.PROJ,result,v=v)
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
        elif op in (Op.SHIFT_LET_A,Op.SUBST_LET_A):
            operation=Op.SHIFT if op==Op.SHIFT_LET_A else Op.SUBST
            continuation=Op.SHIFT_LET_B if op==Op.SHIFT_LET_A else Op.SUBST_LET_B
            self.call(operation,self.node(x)[2],y,z,continuation=(continuation,x,result,y,z))
        elif op in (Op.SHIFT_LET_B,Op.SUBST_LET_B):
            operation=Op.SHIFT if op==Op.SHIFT_LET_B else Op.SUBST
            next_y=z+int(operation==Op.SHIFT);next_z=w+int(operation==Op.SUBST)
            if max(next_y,next_z)>=1<<cfg.word_bits: self.stop(Outcome.RESOURCE,Reason.INDEX)
            else: self.call(operation,self.node(x)[3],next_y,next_z,continuation=(Op.LET_END,x,y,result))
        elif op==Op.LET_END:
            _,a,b,body=self.node(x)
            if (a,b,body)==(y,z,result): self.ret(x)
            else: self.allocate(Tag.LET,y,z,result)
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
                if vx==vy: self.call(Op.CONV,ax,ay,continuation=(Op.C_AFTER_CHILD,x,result))
                else: self.tail(Op.FALLBACK,x,result)
            elif tx in (Tag.VAR, Tag.SORT, Tag.CONST,Tag.BUILTIN,Tag.NAT):
                if vx == vy and (tx != Tag.BUILTIN or (ax==ay and bx==by)):
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
                self.tail(Op.ETA, x, y,z)
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
                if z:self.tail(Op.S_TYPE,z,x,y,z)
                else:self.ret(0)
            elif left_lam:
                self.call(Op.INFER, y, continuation=(Op.E_TYPE, x, y))
            else:
                self.call(Op.INFER, x, continuation=(Op.E_TYPE, y, x))
        elif op==Op.S_TYPE:
            tag,carrier,_,code=self.node(x)
            if tag==Tag.BUILTIN and code==71 and carrier>0:
                self.call(Op.INFER,z,continuation=(Op.S_RIGHT_TYPE,y,z,w,PROJECTION_COUNT))
            elif tag!=Tag.APP:self.ret(0)
            else:self.tail(Op.S_FN,self.node(x)[1],y,z,w)
        elif op==Op.S_FN:
            if self.node(x)[0]==Tag.APP:self.tail(Op.S_FN,self.node(x)[1],y,z,w)
            else:self.tail(Op.S_HEAD,x,y,z,w)
        elif op==Op.S_HEAD:
            record=next((record for record in ONE_FIELD_RECORDS.values() if record['code']==self.node(x)[3] and record['data']),None)
            pair=next((record for record in list(TWO_FIELD_RECORDS.values())+list(LAW_RECORDS.values())if record['code']==self.node(x)[3]),None)
            if self.node(x)[0]!=Tag.BUILTIN or (not record and not pair and self.node(x)[3]!=32):self.ret(0)
            else:self.call(Op.INFER,z,continuation=(Op.S_RIGHT_TYPE,y,z,w,(record or pair)['projection']if record or pair else 4))
        elif op==Op.S_RIGHT_TYPE:
            self.call(Op.CONV,z,result,continuation=(Op.S_SAME_TYPE,x,y,w))
        elif op==Op.S_SAME_TYPE:
            if not result:self.ret(0)
            elif z==PROJECTION_COUNT:self.ret(1)
            elif z in {record['projection']for record in TWO_FIELD_RECORDS.values()}:
                self.call(Op.S_PAIR_FIELD,x,y,z,continuation=(Op.S_PAIR_NEXT,x,y,z+1))
            else:self.allocate(Tag.PROJ,x,v=z,resume=(Op.S_RIGHT_VAL,y,r['free'],z))
        elif op==Op.S_PAIR_FIELD:
            self.allocate(Tag.PROJ,x,v=z,resume=(Op.S_RIGHT_VAL,y,r['free'],z))
        elif op==Op.S_PAIR_NEXT:
            if not result:self.ret(0)
            else:self.tail(Op.S_PAIR_FIELD,x,y,z)
        elif op==Op.S_RIGHT_VAL:
            self.allocate(Tag.PROJ,x,v=z,resume=(Op.CONV,y,r['free']))
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
            self.allocate_atom(Tag.VAR, v=0)
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
