"""Name-independent generic kernel lowered to Boolean IR and shared layers."""
import torch
from torch import nn
from .bitvec import Builder
from .generic_spec import FRAME_FIELDS,HEAP_FIELDS,CONST_FIELDS,MachineConfig,Op,Outcome,Reason
from .generic_syntax import Tag
from .generic_layout import StateLayout,RegisterLayout
from .memory import AddressedRead,AddressedWrite

PORTS=[('hx',HEAP_FIELDS),('hy',HEAP_FIELDS),('hr',HEAP_FIELDS),('hs',HEAP_FIELDS),
       ('back',FRAME_FIELDS),('declrow',CONST_FIELDS),('lookup',('type',)),
       ('constant',CONST_FIELDS),('owner',CONST_FIELDS),('nextctor',CONST_FIELDS),
       ('headrow',CONST_FIELDS)]
SECOND_BANKS=('context','constants','constants','constants','constants')

def port_names(width,ports):
    return[f'read/{p}/{f}/{i}'for p,fs in ports for f in fs for i in range(width)]
def state_words(builder,layout):
    return{name:tuple(builder.inputs[layout.slices[name]])for name,_ in layout.fields}

def compile_addresses(layout,optimized=True,target=None):
    cfg=layout.config;width=cfg.word_bits;g=Builder(layout.names,optimized);r=state_words(g,layout);out=[]
    for name in('x','y','r','scan'):out.extend(r[name][:cfg.heap.bit_length()-1])
    out.extend(g.sub(r['sp'],g.const(1,width))[0][:cfg.stack.bit_length()-1]);out.extend(r['decl'][:cfg.constants.bit_length()-1])
    first=g.compile(out,target=target)
    g=Builder(layout.names+port_names(width,PORTS[:6]),optimized);r=state_words(g,layout)
    offset=len(layout.names);node_v=tuple(g.inputs[offset+3*width:offset+4*width])
    # Four heap ports plus the stack frame precede the declaration row.
    decl_offset=offset+22*width
    owner=tuple(g.inputs[decl_offset+3*width:decl_offset+4*width])
    out=list(g.sub(r['ctx'],node_v,borrow_in=True)[0][:cfg.context.bit_length()-1])
    cwidth=cfg.constants.bit_length()-1
    ctor_address=g.mux(g.eq(r['mode'],g.const(Op.G_CTOR,width)),g.add(g.add(r['decl'],g.const(1,width)),r['gi']),g.add(owner,r['gi']))
    for address in(node_v,owner,ctor_address,g.sub(r['head'],g.const(1,width))[0]):out.extend(address[:cwidth])
    return first,g.compile(out,target=target)

def compile_initializer(layout, optimized=True):
    """Seal proof inputs against forged control, fuel, and mutable memory."""
    g = Builder(layout.names, optimized)
    words = state_words(g, layout)
    outputs = []
    for name, width in layout.fields:
        if name.startswith(('heap/', 'constants/')) or name in ('free', 'decl_count', 'term', 'claim'):
            outputs.extend(words[name])
        else:
            value = layout.config.fuel if name == 'fuel' else 1 if name == 'scan' else 0
            outputs.extend(g.const(value, width))
    return g.compile(outputs)


class RuleCompiler:
    def __init__(self, layout, optimized=True, factor_choices=False):
        self.layout, self.cfg = layout, layout.config
        self.optimized=optimized;self.factor_choices=factor_choices
        self.width = self.cfg.word_bits
        self.g = Builder(layout.names + port_names(self.width, PORTS), optimized)
        self.c = self.g.c
        self.old = state_words(self.g, layout)
        self.r = {name: self.old[name] for name in self.old if '/' not in name}
        self.choices = {name: [] for name in self.old}
        self.writes = {'heap': [], 'stack': [], 'context': []}
        offset = layout.width
        self.read = {}
        for port, fields in PORTS:
            self.read[port] = {}
            for field in fields:
                self.read[port][field] = tuple(self.g.inputs[offset:offset+self.width])
                offset += self.width
        self.hx, self.hy, self.hr, self.hs = (self.read[p] for p in ('hx', 'hy', 'hr', 'hs'))
        self.running = self.eq(self.r['status'], 0)
        fuel = self.r['fuel']
        self.active = self.AND(self.running, self.NOT(self.eq(fuel, 0)))
        self.emit(self.AND(self.running, self.eq(fuel, 0)), status=Outcome.RESOURCE, reason=Reason.FUEL)
        self.choices['fuel'].append((self.active, self.g.sub(fuel, self.g.const(1, len(fuel)))[0]))
        bad = self.OR(self.eq(self.r['free'], 0), self.lt(self.cfg.heap, self.r['free']),
                      self.lt(self.cfg.stack, self.r['sp']), self.lt(self.cfg.context, self.r['ctx']),
                      self.lt(self.r['decl_count'], self.r['decl']), self.lt(self.cfg.constants, self.r['decl_count']))
        needs_x = (Op.INFER, Op.I_BIND, Op.WHNF, Op.W_APP, Op.SHIFT, Op.SUBST,
                   Op.TREE_LEFT, Op.TREE_RIGHT, Op.CONV, Op.C_RIGHT, Op.C_CHILD,
                   Op.FALLBACK, Op.ETA, Op.E_TYPE_WHNF, Op.E_COMPARE, Op.G_FAMILY,Op.G_PICK,Op.G_MAJOR,Op.G_CTOR_TYPE,Op.G_AFTER,Op.G_FIELD_DOMAIN,Op.G_FIELD_SORT,Op.G_FIELD_RESULT,Op.G_RCTYPE,Op.G_CHEAD,Op.G_CCHECK)
        needs_r = (Op.VALUE, Op.ROOT_TERM, Op.I_BIND, Op.I_SORT, Op.I_FUN, Op.W_APP,
                   Op.C_RIGHT, Op.F_TYPE_WHNF, Op.F_SORT_WHNF, Op.E_TYPE_WHNF,Op.G_R1,Op.G_R2,Op.G_R3,Op.G_R4,Op.G_R5,Op.G_R6,Op.G_RC1,Op.G_RC2,Op.G_RC3,Op.G_RNEXT,Op.G_RDONE,Op.G_REC,Op.G_R0,Op.G_CHOOSE,Op.G_RF0,Op.G_RF1,Op.G_RF2,Op.G_APPLY)
        for value, modes in ((self.r['x'], needs_x), (self.r['r'], needs_r),
                             (self.r['y'], (Op.CONV, Op.FALLBACK, Op.ETA,Op.G_MAJOR,Op.G_AFTER)),(self.r['z'],(Op.G_AFTER,))):
            required = self.OR(*(self.eq(self.r['mode'], op) for op in modes))
            invalid = self.OR(self.eq(value, 0), self.NOT(self.lt(value, self.r['free'])))
            bad = self.OR(bad, self.AND(required, invalid))
        head=self.r['head'];none=self.eq(head,0);row=self.read['headrow']
        good=self.AND(self.lt(head,self.add(self.r['decl'],1)),self.eq(row['kind'],3),self.lt(self.r['arity'],self.add(row['info'],2)))
        bad=self.OR(bad,self.AND(none,self.NOT(self.eq(self.r['arity'],0))),self.AND(self.NOT(none),self.NOT(good)))
        self.stop(self.AND(self.active, bad), Outcome.REJECT, Reason.SYNTAX)
        self.active = self.AND(self.active, self.NOT(bad))

    def vec(self, value, width=None):
        return self.g.const(int(value), width or self.width) if isinstance(value, int) else value

    def AND(self, *bits): return self.g.AND(*bits)
    def OR(self, *bits): return self.g.OR(*bits)
    def NOT(self, bit): return self.g.NOT(bit)
    def eq(self, x, y): return self.g.eq(self.vec(x), self.vec(y))
    def lt(self, x, y): return self.g.lt(self.vec(x), self.vec(y))
    def add(self, x, y): return self.g.add(self.vec(x), self.vec(y))
    def sub(self, x, y): return self.g.sub(self.vec(x), self.vec(y))[0]
    def mux(self, bit, x, y): return self.g.mux(bit, self.vec(x), self.vec(y))
    def mode(self, op): return self.AND(self.active, self.eq(self.r['mode'], op))
    def tag(self, node, *tags): return self.OR(*(self.eq(node['tag'], t) for t in tags))

    def masked_or(self, choices):
        return self.g.masked_or(choices,factor=self.factor_choices)

    def emit(self, condition, **updates):
        for name, value in updates.items():
            value = self.vec(value, len(self.old[name]))
            self.choices[name].append((condition, value))

    def stop(self, condition, status, reason=Reason.NONE):
        self.emit(condition, status=status, reason=reason)

    def tail(self, condition, op, x=0, y=0, z=0, w=0):
        self.emit(condition, mode=op, x=x, y=y, z=z, w=w)

    def ret(self, condition, result, head=0, arity=0):
        self.emit(condition, mode=Op.RET,r=result,head=head,arity=arity)

    def call(self, condition, op, x, y=0, z=0, w=0, continuation=(), context=None):
        available = self.lt(self.r['sp'], self.cfg.stack)
        self.stop(self.AND(condition, self.NOT(available)), Outcome.RESOURCE, Reason.STACK)
        good = self.AND(condition, available)
        frame = [self.vec(v) for v in continuation]
        frame += [self.vec(0)] * (5-len(frame))
        frame.append(self.r['ctx'])
        self.writes['stack'].append((good, self.r['sp'], frame))
        self.emit(good, sp=self.add(self.r['sp'], 1))
        self.tail(good, op, x, y, z, w)
        if context is not None:
            self.emit(good, ctx=context)

    def allocate(self, condition, tag, a=0, b=0, v=0, overflow=None, resume=None, head=0, arity=0):
        available = self.lt(self.r['free'], self.cfg.heap)
        self.stop(self.AND(condition, self.NOT(available)), Outcome.RESOURCE, Reason.HEAP)
        good = self.AND(condition, available)
        if overflow is not None:
            self.stop(self.AND(good, overflow), Outcome.RESOURCE, Reason.INDEX)
            good = self.AND(good, self.NOT(overflow))
        self.writes['heap'].append((good, self.r['free'], [self.vec(t) for t in (tag, a, b, v)]))
        self.emit(good, free=self.add(self.r['free'], 1))
        if resume is None:
            self.ret(good,self.r['free'],head,arity)
        else:
            self.emit(good,r=self.r['free'],head=0,arity=0)
            self.tail(good,*resume)

    def rules(self):
        r, hx, hr, hs = self.r, self.hx, self.hr, self.hs
        x, y, z, w, result = (r[k] for k in ('x', 'y', 'z', 'w', 'r'))
        # Initial syntax and topological validation, before any inference.
        op = self.mode(Op.VALIDATE)
        more = self.lt(r['scan'], r['free'])
        self.tail(self.AND(op, self.NOT(more)), Op.ENV)
        binary = self.tag(hs, Tag.PI, Tag.LAM, Tag.APP)
        atomic = self.tag(hs, Tag.VAR, Tag.SORT, Tag.CONST)
        children = self.AND(self.NOT(self.eq(hs['a'], 0)), self.lt(hs['a'], r['scan']),
                            self.NOT(self.eq(hs['b'], 0)), self.lt(hs['b'], r['scan']), self.eq(hs['v'], 0))
        atom_ok = self.AND(self.eq(hs['a'], 0), self.eq(hs['b'], 0),
                           self.OR(self.NOT(self.tag(hs, Tag.CONST)), self.lt(hs['v'], r['decl_count'])))
        valid = self.OR(self.AND(binary, children), self.AND(atomic, atom_ok))
        check = self.AND(op, more)
        self.stop(self.AND(check, self.NOT(valid)), Outcome.REJECT, Reason.SYNTAX)
        high = self.AND(self.tag(hs, Tag.SORT), self.lt(self.cfg.universe, hs['v']))
        self.stop(self.AND(check, valid, high), Outcome.RESOURCE, Reason.UNIVERSE)
        self.emit(self.AND(check, valid, self.NOT(high)), scan=self.add(r['scan'], 1))
        # Environment and root-check orchestration.
        op = self.mode(Op.ENV)
        done = self.eq(r['decl'], r['decl_count'])
        self.call(self.AND(op, done), Op.INFER, r['claim'], continuation=(Op.ROOT_TYPE,))
        row=self.read['declrow'];owner=self.read['owner'];nxt=self.read['nextctor']
        type_ok=self.AND(self.NOT(self.eq(row['type'],0)),self.lt(row['type'],r['free']))
        normal=self.OR(*(self.eq(row['kind'],i)for i in range(3)))
        metadata_ok=self.AND(self.eq(row['owner'],0),self.eq(row['info'],0),
            self.OR(self.AND(self.eq(row['kind'],0),self.eq(row['value'],0)),self.AND(self.NOT(self.eq(row['kind'],0)),self.NOT(self.eq(row['value'],0)),self.lt(row['value'],r['free']))))
        exists=self.AND(op,self.NOT(done))
        family=self.eq(row['kind'],3);ctor=self.eq(row['kind'],4);rec=self.eq(row['kind'],5)
        legal=self.AND(type_ok,self.OR(self.AND(normal,metadata_ok),family,rec))
        self.stop(self.AND(exists,self.NOT(legal)),Outcome.REJECT,Reason.DECLARATION)
        self.call(self.AND(exists,legal,normal),Op.INFER,row['type'],continuation=(Op.TYPE,row['type'],row['value'],row['kind']))
        self.tail(self.AND(exists,legal,family),Op.G_FAMILY,row['type'])
        rec_ok=self.AND(self.eq(row['value'],0),self.lt(row['owner'],r['decl']),self.eq(owner['kind'],3),self.lt(self.add(row['owner'],owner['info']),r['decl']))
        self.stop(self.AND(exists,legal,rec,self.NOT(rec_ok)),Outcome.REJECT,Reason.DECLARATION)
        level=self.lt(row['info'],self.cfg.universe)
        self.stop(self.AND(exists,legal,rec,rec_ok,self.NOT(level)),Outcome.RESOURCE,Reason.UNIVERSE)
        self.call(self.AND(exists,legal,rec,rec_ok,level),Op.INFER,row['type'],continuation=(Op.G_REC,))
        phase=self.mode(Op.G_FAMILY);shape=self.AND(self.tag(hx,Tag.SORT),self.NOT(self.eq(hx['v'],0)))
        self.stop(self.AND(phase,self.NOT(shape)),Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
        level=self.lt(hx['v'],self.cfg.universe)
        self.stop(self.AND(phase,shape,self.NOT(level)),Outcome.RESOURCE,Reason.UNIVERSE)
        good=self.AND(self.eq(row['value'],0),self.eq(row['owner'],r['decl']),self.lt(row['info'],self.cfg.constants),self.lt(self.add(r['decl'],row['info']),r['decl_count']))
        self.stop(self.AND(phase,shape,level,self.NOT(good)),Outcome.REJECT,Reason.DECLARATION)
        cond=self.AND(phase,shape,level,good);self.emit(cond,gi=0,gm=hx['v']);self.tail(cond,Op.G_CTOR)
        phase=self.mode(Op.G_CTOR);done=self.eq(r['gi'],row['info'])
        self.emit(self.AND(phase,done),decl=self.add(self.add(r['decl'],row['info']),1));self.tail(self.AND(phase,done),Op.ENV)
        good=self.AND(self.eq(nxt['kind'],4),self.eq(nxt['value'],0),self.eq(nxt['owner'],r['decl']),self.eq(nxt['info'],r['gi']),self.NOT(self.eq(nxt['type'],0)),self.lt(nxt['type'],r['free']))
        self.stop(self.AND(phase,self.NOT(done),self.NOT(good)),Outcome.REJECT,Reason.DECLARATION)
        self.tail(self.AND(phase,self.NOT(done),good),Op.G_CTOR_TYPE,nxt['type'])
        phase=self.mode(Op.G_CTOR_TYPE);fields=self.tag(hx,Tag.PI)
        good=self.AND(self.tag(hx,Tag.CONST),self.eq(hx['a'],0),self.eq(hx['b'],0),self.eq(hx['v'],r['decl']))
        self.tail(self.AND(phase,fields),Op.G_FIELD_DOMAIN,hx['a'],hx['b'])
        self.stop(self.AND(phase,self.NOT(fields),self.NOT(good)),Outcome.REJECT,Reason.DECLARATION)
        self.emit(self.AND(phase,good),gi=self.add(r['gi'],1));self.tail(self.AND(phase,good),Op.G_CTOR)
        phase=self.mode(Op.G_FIELD_DOMAIN);good=self.AND(self.tag(hx,Tag.CONST),self.lt(hx['v'],r['decl']))
        self.stop(self.AND(phase,self.NOT(good)),Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
        self.tail(self.AND(phase,good),Op.G_FIELD_SORT,self.read['constant']['type'],y)
        phase=self.mode(Op.G_FIELD_SORT);sort=self.tag(hx,Tag.SORT);level=self.NOT(self.lt(r['gm'],hx['v']))
        self.stop(self.AND(phase,self.NOT(sort)),Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
        self.stop(self.AND(phase,sort,self.NOT(level)),Outcome.REJECT,Reason.DECLARATION)
        self.tail(self.AND(phase,sort,level),Op.G_FIELD_RESULT,y)
        phase=self.mode(Op.G_FIELD_RESULT);fields=self.tag(hx,Tag.PI)
        good=self.AND(self.tag(hx,Tag.CONST),self.eq(hx['a'],0),self.eq(hx['b'],0),self.eq(hx['v'],r['decl']))
        self.stop(self.AND(phase,fields),Outcome.REJECT,Reason.UNSUPPORTED_DECLARATION)
        self.stop(self.AND(phase,self.NOT(fields),self.NOT(good)),Outcome.REJECT,Reason.DECLARATION)
        self.emit(self.AND(phase,good),gi=self.add(r['gi'],1));self.tail(self.AND(phase,good),Op.G_CTOR)
        self.call(self.mode(Op.G_REC),Op.WHNF,result,continuation=(Op.G_R0,))
        phase=self.mode(Op.G_R0);good=self.tag(hr,Tag.SORT)
        self.stop(self.AND(phase,self.NOT(good)),Outcome.REJECT,Reason.EXPECT_SORT)
        self.allocate(self.AND(phase,good),Tag.CONST,v=row['owner'],resume=(Op.G_R1,))
        phase=self.mode(Op.G_R1);self.emit(phase,gf=result);self.allocate(phase,Tag.SORT,v=row['info'],resume=(Op.G_R2,))
        self.allocate(self.mode(Op.G_R2),Tag.PI,r['gf'],result,resume=(Op.G_R3,))
        phase=self.mode(Op.G_R3);self.emit(phase,gm=result);self.allocate(phase,Tag.VAR,v=self.add(owner['info'],1),resume=(Op.G_R4,))
        phase=self.mode(Op.G_R4);self.emit(phase,gc=result);self.allocate(phase,Tag.VAR,v=0,resume=(Op.G_R5,))
        self.allocate(self.mode(Op.G_R5),Tag.APP,r['gc'],result,resume=(Op.G_R6,))
        phase=self.mode(Op.G_R6);self.emit(phase,gi=owner['info']);self.allocate(phase,Tag.PI,r['gf'],result,resume=(Op.G_RLOOP,))
        phase=self.mode(Op.G_RLOOP);done=self.eq(r['gi'],0);self.emit(phase,gt=result)
        self.allocate(self.AND(phase,done),Tag.PI,r['gm'],result,resume=(Op.G_RDONE,))
        self.tail(self.AND(phase,self.NOT(done)),Op.G_RCTYPE,nxt['type'])
        phase=self.mode(Op.G_RCTYPE);self.emit(phase,ga=self.mux(self.tag(hx,Tag.PI),hx['a'],0))
        self.allocate(phase,Tag.CONST,v=self.add(row['owner'],r['gi']),resume=(Op.G_RC1,))
        fields=self.NOT(self.eq(r['ga'],0))
        phase=self.mode(Op.G_RC1);self.emit(phase,gc=result)
        self.allocate(phase,Tag.VAR,v=self.mux(fields,r['gi'],self.sub(r['gi'],1)),resume=(Op.G_RC2,))
        phase=self.mode(Op.G_RC2);self.emit(self.AND(phase,fields),gb=result)
        self.allocate(self.AND(phase,fields),Tag.VAR,v=0,resume=(Op.G_RF0,))
        self.allocate(self.AND(phase,self.NOT(fields)),Tag.APP,result,r['gc'],resume=(Op.G_RC3,))
        self.allocate(self.mode(Op.G_RF0),Tag.APP,r['gc'],result,resume=(Op.G_RF1,))
        self.allocate(self.mode(Op.G_RF1),Tag.APP,r['gb'],result,resume=(Op.G_RF2,))
        self.allocate(self.mode(Op.G_RF2),Tag.PI,r['ga'],result,resume=(Op.G_RC3,))
        self.allocate(self.mode(Op.G_RC3),Tag.PI,result,r['gt'],resume=(Op.G_RNEXT,))
        phase=self.mode(Op.G_RNEXT);self.emit(phase,gi=self.sub(r['gi'],1));self.tail(phase,Op.G_RLOOP)
        self.call(self.mode(Op.G_RDONE),Op.CONV,result,row['type'],continuation=(Op.ENV_EQ,))
        self.call(self.mode(Op.TYPE), Op.WHNF, result, continuation=(Op.VALUE, x, y, z))
        self.call(self.mode(Op.ROOT_TYPE), Op.WHNF, result, continuation=(Op.ROOT_TERM,))
        for operation in (Op.VALUE, Op.ROOT_TERM):
            op = self.mode(operation)
            is_sort = self.tag(hr, Tag.SORT)
            self.stop(self.AND(op, self.NOT(is_sort)), Outcome.REJECT, Reason.EXPECT_SORT)
            if operation == Op.ROOT_TERM:
                self.call(self.AND(op, is_sort), Op.INFER, r['term'], continuation=(Op.ROOT_EQ,))
            else:
                axiom = self.eq(z, 0)
                cond = self.AND(op, is_sort, axiom)
                self.emit(cond, decl=self.add(r['decl'], 1)); self.tail(cond, Op.ENV)
                self.call(self.AND(op, is_sort, self.NOT(axiom)), Op.INFER, y, continuation=(Op.COMMIT, x))
        self.call(self.mode(Op.COMMIT), Op.CONV, result, x, continuation=(Op.ENV_EQ,))
        self.call(self.mode(Op.ROOT_EQ), Op.CONV, result, r['claim'], continuation=(Op.FINISH,))
        for operation in (Op.ENV_EQ, Op.FINISH):
            op, success = self.mode(operation), self.NOT(self.eq(result, 0))
            self.stop(self.AND(op, self.NOT(success)), Outcome.REJECT, Reason.CONVERSION)
            if operation == Op.FINISH:
                self.stop(self.AND(op, success), Outcome.ACCEPT)
            else:
                cond = self.AND(op, success)
                self.emit(cond, decl=self.add(r['decl'], 1)); self.tail(cond, Op.ENV)
        # Return restores the explicit continuation, including context depth.
        op = self.mode(Op.RET)
        empty = self.eq(r['sp'], 0)
        self.stop(self.AND(op, empty), Outcome.REJECT, Reason.INTERNAL)
        cond = self.AND(op, self.NOT(empty))
        self.emit(cond, sp=self.sub(r['sp'], 1), **self.read['back'])
        # Inference.
        op = self.mode(Op.INFER)
        var = self.AND(op, self.tag(hx, Tag.VAR))
        bound = self.lt(hx['v'], r['ctx'])
        self.stop(self.AND(var, self.NOT(bound)), Outcome.REJECT, Reason.UNBOUND)
        self.tail(self.AND(var, bound), Op.SHIFT, self.read['lookup']['type'], 0, self.add(hx['v'], 1))
        sort = self.AND(op, self.tag(hx, Tag.SORT))
        level_ok = self.lt(hx['v'], self.cfg.universe)
        self.stop(self.AND(sort, self.NOT(level_ok)), Outcome.RESOURCE, Reason.UNIVERSE)
        self.allocate(self.AND(sort, level_ok), Tag.SORT, v=self.add(hx['v'], 1))
        self.call(self.AND(op, self.tag(hx, Tag.LAM, Tag.PI)), Op.INFER, hx['a'], continuation=(Op.I_DOM, x))
        self.call(self.AND(op, self.tag(hx, Tag.APP)), Op.INFER, hx['a'], continuation=(Op.I_APP, hx['b']))
        const = self.AND(op, self.tag(hx, Tag.CONST), self.lt(hx['v'], r['decl']))
        self.ret(const, self.read['constant']['type'])
        legal = self.OR(self.tag(hx, Tag.VAR, Tag.SORT, Tag.PI, Tag.LAM, Tag.APP),
                        self.AND(self.tag(hx, Tag.CONST), self.lt(hx['v'], r['decl'])))
        self.stop(self.AND(op, self.NOT(legal)), Outcome.REJECT, Reason.SYNTAX)
        self.call(self.mode(Op.I_DOM), Op.WHNF, result, continuation=(Op.I_BIND, x))
        op, is_sort = self.mode(Op.I_BIND), self.tag(hr, Tag.SORT)
        self.stop(self.AND(op, self.NOT(is_sort)), Outcome.REJECT, Reason.EXPECT_SORT)
        room = self.lt(r['ctx'], self.cfg.context)
        self.stop(self.AND(op, is_sort, self.NOT(room)), Outcome.RESOURCE, Reason.CONTEXT)
        cond = self.AND(op, is_sort, room)
        self.writes['context'].append((cond, r['ctx'], [hx['a']]))
        lam = self.tag(hx, Tag.LAM)
        self.call(self.AND(cond, lam), Op.INFER, hx['b'], continuation=(Op.I_LAM, hx['a']), context=self.add(r['ctx'], 1))
        self.call(self.AND(cond, self.NOT(lam)), Op.INFER, hx['b'], continuation=(Op.I_PI, hr['v']), context=self.add(r['ctx'], 1))
        self.allocate(self.mode(Op.I_LAM), Tag.PI, x, result)
        self.call(self.mode(Op.I_PI), Op.WHNF, result, continuation=(Op.I_SORT, x))
        op, is_sort = self.mode(Op.I_SORT), self.tag(hr, Tag.SORT)
        self.stop(self.AND(op, self.NOT(is_sort)), Outcome.REJECT, Reason.EXPECT_SORT)
        maximum = self.mux(self.lt(x, hr['v']), hr['v'], x)
        universe = self.mux(self.eq(hr['v'], 0), 0, maximum)
        self.allocate(self.AND(op, is_sort), Tag.SORT, v=universe)
        self.call(self.mode(Op.I_APP), Op.WHNF, result, continuation=(Op.I_FUN, x))
        op, is_pi = self.mode(Op.I_FUN), self.tag(hr, Tag.PI)
        self.stop(self.AND(op, self.NOT(is_pi)), Outcome.REJECT, Reason.EXPECT_PI)
        self.call(self.AND(op, is_pi), Op.INFER, x, continuation=(Op.I_ARG, hr['a'], hr['b'], x))
        self.call(self.mode(Op.I_ARG), Op.CONV, x, result, continuation=(Op.I_CHECK, y, z))
        op, good = self.mode(Op.I_CHECK), self.NOT(self.eq(result, 0))
        self.stop(self.AND(op, self.NOT(good)), Outcome.REJECT, Reason.CONVERSION)
        self.tail(self.AND(op, good), Op.SUBST, x, y)
        # WHNF, delta unfolding and beta substitution.
        op = self.mode(Op.WHNF)
        self.call(self.AND(op, self.tag(hx, Tag.APP)), Op.WHNF, hx['a'], continuation=(Op.W_APP, x, hx['b']))
        const = self.AND(op, self.tag(hx, Tag.CONST))
        available = self.lt(hx['v'], r['decl'])
        self.stop(self.AND(const, self.NOT(available)), Outcome.REJECT, Reason.SYNTAX)
        definition = self.eq(self.read['constant']['kind'], 1)
        self.tail(self.AND(const, available, definition), Op.WHNF, self.read['constant']['value'])
        self.ret(self.AND(const,available,self.NOT(definition)),x,head=self.mux(self.eq(self.read['constant']['kind'],5),self.add(self.read['constant']['owner'],1),0))
        self.ret(self.AND(op, self.tag(hx, Tag.VAR, Tag.SORT, Tag.PI, Tag.LAM)), x)
        self.stop(self.AND(op, self.NOT(self.tag(hx, Tag.VAR, Tag.SORT, Tag.PI, Tag.LAM, Tag.APP, Tag.CONST))), Outcome.REJECT, Reason.SYNTAX)
        op,lam=self.mode(Op.W_APP),self.tag(hr,Tag.LAM)
        self.call(self.AND(op,lam),Op.SUBST,hr['b'],y,continuation=(Op.W_BETA,))
        head=r['head'];has=self.NOT(self.eq(head,0));count=self.read['headrow']['info']
        complete=self.AND(has,self.eq(self.add(r['arity'],1),self.add(count,2)))
        self.call(self.AND(op,self.NOT(lam),complete),Op.G_MAJOR,result,y,self.sub(head,1),count,continuation=(Op.G_AFTER,x,result,y))
        partial=self.AND(op,self.NOT(lam),self.NOT(complete));same=self.eq(result,hx['a']);arity=self.mux(has,self.add(r['arity'],1),0)
        self.ret(self.AND(partial,same),x,head=head,arity=arity)
        self.allocate(self.AND(partial,self.NOT(same)),Tag.APP,result,y,head=head,arity=arity)
        self.call(self.mode(Op.G_MAJOR),Op.WHNF,y,continuation=(Op.G_CHOOSE,x,z,w))
        phase=self.mode(Op.G_CHOOSE);app=self.tag(hr,Tag.APP)
        self.emit(phase,ga=self.mux(app,hr['b'],0))
        self.tail(phase,Op.G_CHEAD,self.mux(app,hr['a'],result),x,y,z)
        phase=self.mode(Op.G_CHEAD);row=self.read['constant']
        good=self.AND(self.tag(hx,Tag.CONST),self.lt(hx['v'],r['decl']),self.eq(row['kind'],4),self.eq(row['owner'],z),self.lt(row['info'],w))
        self.tail(self.AND(phase,good),Op.G_CCHECK,row['type'],y,self.sub(self.sub(w,1),row['info']),r['ga'])
        self.ret(self.AND(phase,self.NOT(good)),0)
        phase=self.mode(Op.G_CCHECK);arity=self.eq(self.mux(self.tag(hx,Tag.PI),1,0),self.mux(self.eq(w,0),0,1))
        self.ret(self.AND(phase,self.NOT(arity)),0)
        self.call(self.AND(phase,arity),Op.G_PICK,y,z,continuation=(Op.G_APPLY,w))
        phase=self.mode(Op.G_APPLY);fields=self.NOT(self.eq(x,0))
        self.allocate(self.AND(phase,fields),Tag.APP,result,x)
        self.ret(self.AND(phase,self.NOT(fields)),result)
        phase=self.mode(Op.G_PICK);app=self.tag(hx,Tag.APP);more=self.NOT(self.eq(y,0))
        self.stop(self.AND(phase,self.NOT(app)),Outcome.REJECT,Reason.SYNTAX)
        self.tail(self.AND(phase,app,more),Op.G_PICK,hx['a'],self.sub(y,1))
        self.ret(self.AND(phase,app,self.NOT(more)),hx['b'])
        phase=self.mode(Op.G_AFTER);found=self.NOT(self.eq(result,0));same=self.eq(hx['a'],y)
        self.tail(self.AND(phase,found),Op.WHNF,result)
        self.ret(self.AND(phase,self.NOT(found),same),x)
        self.allocate(self.AND(phase,self.NOT(found),self.NOT(same)),Tag.APP,y,z)
        self.tail(self.mode(Op.W_BETA), Op.WHNF, result)
        # Capture-avoiding structural shift/substitution with explicit frames.
        for operation in (Op.SHIFT, Op.SUBST):
            op = self.mode(operation)
            trivial = self.tag(hx, Tag.SORT, Tag.CONST)
            if operation == Op.SHIFT:
                trivial = self.OR(trivial, self.eq(z, 0))
            self.ret(self.AND(op, trivial), x)
            work = self.AND(op, self.NOT(trivial))
            var = self.AND(work, self.tag(hx, Tag.VAR))
            if operation == Op.SHIFT:
                unchanged = self.lt(hx['v'], y)
                self.ret(self.AND(var, unchanged), x)
                total = self.add(hx['v'], z)
                self.allocate(self.AND(var, self.NOT(unchanged)), Tag.VAR, v=total, overflow=self.lt(total, hx['v']))
            else:
                below, equal = self.lt(hx['v'], z), self.eq(hx['v'], z)
                self.ret(self.AND(var, below), x)
                self.tail(self.AND(var, equal), Op.SHIFT, y, 0, z)
                self.allocate(self.AND(var, self.NOT(below), self.NOT(equal)), Tag.VAR, v=self.sub(hx['v'], 1))
            tree = self.tag(hx, Tag.PI, Tag.LAM, Tag.APP)
            self.call(self.AND(work, tree), operation, hx['a'], y, z,
                      continuation=(Op.TREE_LEFT, x, y, z, operation))
            self.stop(self.AND(work, self.NOT(self.tag(hx, Tag.VAR, Tag.PI, Tag.LAM, Tag.APP))), Outcome.REJECT, Reason.SYNTAX)
        op = self.mode(Op.TREE_LEFT)
        binder = self.tag(hx, Tag.PI, Tag.LAM)
        shift, subst = self.eq(w, Op.SHIFT), self.eq(w, Op.SUBST)
        next_y = self.mux(self.AND(binder, shift), self.add(y, 1), y)
        next_z = self.mux(self.AND(binder, subst), self.add(z, 1), z)
        overflow = self.OR(self.lt(next_y, y), self.lt(next_z, z))
        self.stop(self.AND(op, overflow), Outcome.RESOURCE, Reason.INDEX)
        self.call(self.AND(op, self.NOT(overflow)), w, hx['b'], next_y, next_z,
                  continuation=(Op.TREE_RIGHT, x, result))
        op = self.mode(Op.TREE_RIGHT)
        same = self.AND(self.eq(hx['a'], y), self.eq(hx['b'], result))
        self.ret(self.AND(op, same), x)
        self.allocate(self.AND(op, self.NOT(same)), hx['tag'], y, result)
        # Contextual conversion with beta/delta, proof irrelevance and eta.
        op, same = self.mode(Op.CONV), self.eq(x, y)
        self.ret(self.AND(op, same), 1)
        self.call(self.AND(op, self.NOT(same)), Op.WHNF, x, continuation=(Op.C_LEFT, y))
        self.call(self.mode(Op.C_LEFT), Op.WHNF, x, continuation=(Op.C_RIGHT, result))
        op, same = self.mode(Op.C_RIGHT), self.eq(x, result)
        self.ret(self.AND(op, same), 1)
        work = self.AND(op, self.NOT(same))
        matching = self.eq(hx['tag'], hr['tag'])
        self.tail(self.AND(work, self.NOT(matching)), Op.FALLBACK, x, result)
        atomic = self.AND(work, matching, self.tag(hx, Tag.VAR, Tag.SORT, Tag.CONST))
        equal_value = self.eq(hx['v'], hr['v'])
        self.ret(self.AND(atomic, equal_value), 1)
        self.tail(self.AND(atomic, self.NOT(equal_value)), Op.FALLBACK, x, result)
        self.call(self.AND(work, matching, self.tag(hx, Tag.PI, Tag.LAM, Tag.APP)), Op.CONV,
                  hx['a'], hr['a'], continuation=(Op.C_CHILD, x, result, hx['b'], hr['b']))
        self.stop(self.AND(work, matching, self.NOT(self.tag(hx, Tag.VAR, Tag.SORT, Tag.CONST, Tag.PI, Tag.LAM, Tag.APP))), Outcome.REJECT, Reason.SYNTAX)
        op, good = self.mode(Op.C_CHILD), self.NOT(self.eq(result, 0))
        self.tail(self.AND(op, self.NOT(good)), Op.FALLBACK, x, y)
        binder = self.tag(hx, Tag.PI, Tag.LAM)
        room = self.lt(r['ctx'], self.cfg.context)
        self.stop(self.AND(op, good, binder, self.NOT(room)), Outcome.RESOURCE, Reason.CONTEXT)
        bound_compare = self.AND(op, good, binder, room)
        self.writes['context'].append((bound_compare, r['ctx'], [hx['a']]))
        self.call(bound_compare, Op.CONV, z, w, continuation=(Op.C_AFTER_CHILD, x, y), context=self.add(r['ctx'], 1))
        self.call(self.AND(op, good, self.NOT(binder)), Op.CONV, z, w, continuation=(Op.C_AFTER_CHILD, x, y))
        op, good = self.mode(Op.C_AFTER_CHILD), self.NOT(self.eq(result, 0))
        self.ret(self.AND(op, good), 1)
        self.tail(self.AND(op, self.NOT(good)), Op.FALLBACK, x, y)
        # Definite non-proof/non-function syntax avoids unnecessary inference.
        hy = self.hy
        op = self.mode(Op.FALLBACK)
        impossible = self.OR(self.tag(hx, Tag.SORT, Tag.PI), self.tag(hy, Tag.SORT, Tag.PI))
        self.ret(self.AND(op, impossible), 0)
        self.call(self.AND(op, self.NOT(impossible)), Op.INFER, x, continuation=(Op.F_TYPE, x, y))
        self.call(self.mode(Op.F_TYPE), Op.WHNF, result, continuation=(Op.F_TYPE_WHNF, x, y))
        op, is_sort = self.mode(Op.F_TYPE_WHNF), self.tag(hr, Tag.SORT)
        self.ret(self.AND(op, is_sort), 0)
        self.call(self.AND(op, self.NOT(is_sort)), Op.INFER, result, continuation=(Op.F_SORT, x, y, result))
        self.call(self.mode(Op.F_SORT), Op.WHNF, result, continuation=(Op.F_SORT_WHNF, x, y, z))
        op, is_sort = self.mode(Op.F_SORT_WHNF), self.tag(hr, Tag.SORT)
        self.stop(self.AND(op, self.NOT(is_sort)), Outcome.REJECT, Reason.EXPECT_SORT)
        prop = self.eq(hr['v'], 0)
        self.call(self.AND(op, is_sort, prop), Op.INFER, y, continuation=(Op.F_Y, x, y, z))
        self.tail(self.AND(op, is_sort, self.NOT(prop)), Op.ETA, x, y)
        self.call(self.mode(Op.F_Y), Op.CONV, z, result, continuation=(Op.F_PROOF_RESULT, x, y))
        op, good = self.mode(Op.F_PROOF_RESULT), self.NOT(self.eq(result, 0))
        self.ret(self.AND(op, good), 1)
        self.tail(self.AND(op, self.NOT(good)), Op.ETA, x, y)
        # Eta compares the lambda body against a shifted neutral applied to #0.
        op = self.mode(Op.ETA)
        left_lam, right_lam = self.tag(hx, Tag.LAM), self.tag(hy, Tag.LAM)
        self.ret(self.AND(op, self.NOT(self.g.xor(left_lam, right_lam))), 0)
        self.call(self.AND(op, left_lam, self.NOT(right_lam)), Op.INFER, y, continuation=(Op.E_TYPE, x, y))
        self.call(self.AND(op, right_lam, self.NOT(left_lam)), Op.INFER, x, continuation=(Op.E_TYPE, y, x))
        self.call(self.mode(Op.E_TYPE), Op.WHNF, result, continuation=(Op.E_TYPE_WHNF, x, y))
        op, is_pi = self.mode(Op.E_TYPE_WHNF), self.tag(hr, Tag.PI)
        self.ret(self.AND(op, self.NOT(is_pi)), 0)
        self.call(self.AND(op, is_pi), Op.CONV, hx['a'], hr['a'], continuation=(Op.E_DOMAIN, x, y))
        op, good = self.mode(Op.E_DOMAIN), self.NOT(self.eq(result, 0))
        self.ret(self.AND(op, self.NOT(good)), 0)
        self.call(self.AND(op, good), Op.SHIFT, y, 0, 1, continuation=(Op.E_SHIFT, x))
        self.call(self.mode(Op.E_SHIFT), Op.E_VAR, 0, continuation=(Op.E_BUILD, x, result))
        self.allocate(self.mode(Op.E_VAR), Tag.VAR, v=0)
        self.call(self.mode(Op.E_BUILD), Op.E_MAKE_APP, y, result, continuation=(Op.E_COMPARE, x))
        self.allocate(self.mode(Op.E_MAKE_APP), Tag.APP, x, y)
        op, room = self.mode(Op.E_COMPARE), self.lt(r['ctx'], self.cfg.context)
        self.stop(self.AND(op, self.NOT(room)), Outcome.RESOURCE, Reason.CONTEXT)
        good = self.AND(op, room)
        self.writes['context'].append((good, r['ctx'], [hx['a']]))
        self.tail(good, Op.CONV, hx['b'], result)
        self.emit(good, ctx=self.add(r['ctx'], 1))
        self.stop(self.AND(self.active, self.NOT(self.OR(*(self.eq(r['mode'], op) for op in Op)))), Outcome.REJECT, Reason.INTERNAL)

    def finish(self, memory_update='logic', target=None):
        self.rules()
        if memory_update == 'attention_delta':
            outputs = self.state_outputs()
            for bank, fields, address_name in [('heap', HEAP_FIELDS, 'free'), ('stack', FRAME_FIELDS, 'sp'), ('context', ('type',), 'ctx')]:
                choices = self.writes[bank]
                address = self.r[address_name]
                if any(candidate != address for _, candidate, _ in choices):
                    raise ValueError('attention write requires one address per bank')
                enable = self.OR(*(condition for condition, _, _ in choices))
                outputs.extend(address[:getattr(self.cfg, bank).bit_length()-1]); outputs.append(enable)
                for field in range(len(fields)):
                    outputs.extend(self.masked_or([(condition,payload[field][bit]) for condition, _, payload in choices])
                                   for bit in range(self.width))
            return self.g.compile(outputs, target=target)
        # Masked memory writes are control FFNs, with one write per bank/step.
        for bank, choices in self.writes.items():
            if not choices:
                continue
            fields = {'heap': HEAP_FIELDS, 'stack': FRAME_FIELDS, 'context': ('type',)}[bank]
            if self.optimized:
                address = choices[0][1]
                if any(candidate != address for _, candidate, _ in choices):
                    raise ValueError('write factoring requires one address per bank')
                enabled = self.OR(*(condition for condition, _, _ in choices))
                values = [tuple(self.OR(*(self.AND(condition, payload[field][bit])
                                         for condition, _, payload in choices))
                                for bit in range(self.width)) for field in range(len(fields))]
                choices = [(enabled, address, values)]
            for row in range(getattr(self.cfg, bank)):
                conditions = [self.AND(condition, self.eq(address, row)) for condition, address, _ in choices]
                for field_index, field in enumerate(fields):
                    name = f'{bank}/{row}/{field}'
                    self.choices[name].extend((condition, values[field_index]) for condition, (_, _, values) in zip(conditions, choices))
        return self.g.compile(self.state_outputs(), target=target)

    def state_outputs(self):
        outputs = []
        for name, _ in self.layout.fields:
            choices = self.choices[name]
            if not choices:
                outputs.extend(self.old[name]); continue
            if self.optimized and len(choices) == 1:
                condition, value = choices[0]
                outputs.extend(self.g.mux(condition, value, self.old[name])); continue
            keep = self.NOT(self.OR(*(condition for condition, _ in choices)))
            for i, old in enumerate(self.old[name]):
                outputs.append(self.masked_or([(keep,old)]+[(condition,value[i])for condition,value in choices]))
        return outputs



class SharedChecker(nn.Module):
    def __init__(self, config=MachineConfig(), optimized=True, memory_update='logic'):
        super().__init__()
        self.config = config
        self.optimized = optimized
        if memory_update not in ('logic', 'attention_delta'):
            raise ValueError('unknown memory update implementation')
        self.memory_update = memory_update
        self.layout = StateLayout(config)
        self.control_layout = RegisterLayout(self.layout) if memory_update == 'attention_delta' else self.layout
        self.initializer = compile_initializer(self.layout, optimized)
        self.address1, self.address2 = compile_addresses(self.control_layout, optimized)
        self.heap_read = AddressedRead(config.heap)
        self.stack_read = AddressedRead(config.stack)
        self.context_read = AddressedRead(config.context)
        self.constant_read = AddressedRead(config.constants)
        self.transition = RuleCompiler(self.control_layout, optimized).finish(memory_update)
        if memory_update == 'attention_delta':
            self.heap_write = AddressedWrite(config.heap, 4*config.word_bits)
            self.stack_write = AddressedWrite(config.stack, 6*config.word_bits)
            self.context_write = AddressedWrite(config.context, config.word_bits)
        self.requires_grad_(False)

    def bank(self, state, name):
        start, rows, width = self.layout.banks[name]
        return state[:, start:start+rows*width].reshape(state.shape[0], rows, width)

    def forward(self, state):
        with torch.autocast(device_type=state.device.type, enabled=False):
            control = state[:, :self.control_layout.width]
            query = self.address1(control)
            offset = 0
            reads = []
            for bank, ports, module in [('heap', 4, self.heap_read), ('stack', 1, self.stack_read),
                                        ('constants', 1, self.constant_read)]:
                size = ports*module.bits
                address = query[:, offset:offset+size].reshape(state.shape[0], ports, module.bits)
                reads.append(module(address, self.bank(state, bank)).flatten(1))
                offset += size
            first = torch.cat([control] + reads, dim=1)
            query = self.address2(first)
            offset = self.context_read.bits
            reads.append(self.context_read(query[:, :offset].unsqueeze(1), self.bank(state, 'context')).flatten(1))
            for part in range(len(SECOND_BANKS)-1):
                start=offset+part*self.constant_read.bits
                reads.append(self.constant_read(query[:, start:start+self.constant_read.bits].unsqueeze(1), self.bank(state, 'constants')).flatten(1))
            result = self.transition(torch.cat([control] + reads, dim=1))
            if self.memory_update == 'logic':
                return result
            offset = self.control_layout.width
            updated = [result[:, :offset]]
            for bank, module in [('heap', self.heap_write), ('stack', self.stack_write), ('context', self.context_write)]:
                query_width = module.reader.bits+1
                write_control = result[:, offset:offset+query_width]
                offset += query_width
                payload = result[:, offset:offset+module.width]
                offset += module.width
                updated.append(module(write_control, payload, self.bank(state, bank)).flatten(1))
            updated.append(self.bank(state, 'constants').flatten(1))
            return torch.cat(updated, dim=1)



def compile_machine(config=MachineConfig(),optimized=True,memory_update='attention_delta'):
    return SharedChecker(config,optimized,memory_update).eval()

# Backend program interface: bounds are compilation inputs; declarations are data.
from .generic_spec import prepare
from .generic_syntax import parse_document,assumptions,Unsupported,Exhausted
program_name='generic.nonrecursive-unary-inductives.v1'
constant_fields=5
second_banks=SECOND_BANKS
primitive_basis=()
