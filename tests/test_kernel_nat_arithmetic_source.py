"""Original source exercises the pinned finite Nat primitive interface.

Function bindings are ordinary checked definitions with simple bodies. Pinned
C++ reduce_nat uses its finite names before delta on numeric operands, so the
weighted algorithm must do so too; neutral applications must reach delta.
This is synthetic original source, not exported Std body/coverage evidence.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from tests.test_kernel_nat_literal_source import document as nat_document
from tests.test_kernel_source_nested_transaction import canonical,assert_public_matches_independent
from tests.test_kernel_quotient_source import name,const,pi,lam,app,raw,document as quotient_document
from tests.test_kernel_traversal_machine import CircuitHarness


def arithmetic_document():
    one=['succ',['zero']];prop=('sort',['zero']);type0=('sort',one);nt=const('Nat');bt=const('Bool')
    eq=json.loads(Path('tests/fixtures/kernel-source-smoke.jsonl').read_text().splitlines()[2])['declarations'][0]
    boolean=dict(kind='inductive_block',level_params=[],parameters=0,recursor_claims=[],families=[dict(
        name=name('Bool'),recursor_name=name('Bool.rec'),type=raw(type0),constructors=[
            dict(name=name('Bool.false'),type=raw(bt)),dict(name=name('Bool.true'),type=raw(bt))])])
    declarations=[nat_document('0')['declarations'][0],eq,boolean]
    for operation in ('add','sub','mul','pow','gcd','mod','div','beq','ble','land','lor','xor','shiftLeft','shiftRight'):
        result=bt if operation in ('beq','ble') else nt
        value=const('Bool.false') if operation in ('beq','ble') else const('Nat.zero')
        declarations.append(dict(kind='definition',name=name('Nat.'+operation),level_params=[],
            type=raw(pi('x',nt,pi('y',nt,result))),value=raw(lam('x',nt,lam('y',nt,value)))))
    number=lambda n:('nat',str(n))
    def calc(op,*args):return app(const('Nat.'+op),*(number(a) if isinstance(a,int) else a for a in args))
    base=calc('add',calc('gcd',calc('mul',13,7),calc('add',9,5)),calc('add',calc('div',calc('pow',3,5),7),calc('mod',calc('shiftLeft',5,3),calc('succ',6))))
    sixty=calc('xor',calc('sub',calc('add',base,calc('land',29,22)),calc('lor',2,1)),calc('shiftRight',24,3))
    mixed=app(const('Bool.rec',one),lam('b',bt,nt),number(0),number(1),calc('ble',5,6))
    expression=calc('beq',calc('add',sixty,mixed),61)
    # A Quot reducer wraps the first numeric operand, so recursive WHNF crosses
    # Nat -> Quot -> Nat -> inductive Bool -> Nat owned continuations.
    relation=lam('x',nt,lam('y',nt,app(const('Eq',one),nt,'x','y')))
    sanity=lam('x',nt,lam('y',nt,lam('h',app(const('Eq',one),nt,'x','y'),'h')))
    quotient=app(const('Quot.mk',one),nt,relation,sixty)
    lifted=app(const('Quot.lift',one,one),nt,relation,nt,lam('x',nt,'x'),sanity,quotient)
    expression=calc('beq',calc('add',lifted,mixed),61)
    declarations[3:3]=deepcopy(quotient_document()['declarations'][1:])
    ty=app(const('Eq',one),bt,expression,const('Bool.true'))
    value=app(const('Eq.refl',one),bt,const('Bool.true'))
    return dict(format='leanputer.kernel-source.v1',status='EXPORTED',name='source-composed-kernel-Nat-primitives',
        declarations=declarations,target=dict(kind='theorem',name=name('arbitraryArithmeticProofName'),level_params=[],type=raw(ty),value=raw(value)))


def false_arithmetic_document():
    doc=arithmetic_document();doc['name']='source-composed-Nat-false-predicates'
    def transform(node):
        # Flip the ordinary Boolean recursor major to false. Then its Nat result
        # is0, so the surrounding61comparison is false too.
        if node==raw(app(const('Nat.ble'),('nat','5'),('nat','6'))):
            return raw(app(const('Nat.ble'),('nat','6'),('nat','5')))
        if isinstance(node,list):return [transform(x)for x in node]
        return node
    doc['target']['type']=transform(doc['target']['type'])
    doc['target']['type'][2]=raw(const('Bool.false'))
    doc['target']['value'][2]=raw(const('Bool.false'))
    return doc


def big_limb_document():
    doc=arithmetic_document();doc['name']='source-Nat-multiple-limb-multiply-divide'
    one=['succ',['zero']];nt=const('Nat');number=lambda n:('nat',str(n))
    a=4294967297;b=4294967299
    expr=app(const('Nat.div'),app(const('Nat.mul'),number(a),number(b)),number(b))
    doc['target'].update(type=raw(app(const('Eq',one),nt,expr,number(a))),
        value=raw(app(const('Eq.refl',one),nt,number(a))))
    return doc


def cap_document():
    doc=arithmetic_document();doc['name']='source-Nat-pow-cap-delta-fallback'
    one=['succ',['zero']];nt=const('Nat');number=lambda n:('nat',str(n))
    for declaration in doc['declarations']:
        if declaration.get('name')==name('Nat.pow'):
            declaration['value']=raw(lam('x',nt,lam('y',nt,number(7))))
    expr=app(const('Nat.pow'),number(2),number((1<<24)+1))
    doc['target'].update(type=raw(app(const('Eq',one),nt,expr,number(7))),
        value=raw(app(const('Eq.refl',one),nt,number(7))))
    return doc


def zero_offset_document():
    doc=arithmetic_document();doc['name']='source-Nat-zero-literal-conversion'
    one=['succ',['zero']];nt=const('Nat')
    doc['target'].update(type=raw(app(const('Eq',one),nt,const('Nat.zero'),('nat','0'))),
        value=raw(app(const('Eq.refl',one),nt,('nat','0'))))
    return doc


def ordinary_name_document():
    prop=('sort',['zero']);truth=pi('P',prop,pi('h','P','P'))
    ty=pi('P',prop,pi('Q',prop,prop));val=lam('P',prop,lam('Q',prop,'P'))
    declaration=dict(kind='definition',name=name('Nat.add'),level_params=[],type=raw(ty),value=raw(val))
    return dict(format='leanputer.kernel-source.v1',status='EXPORTED',name='neutral-primitive-name-still-ordinary-data',
        declarations=[declaration],target=dict(kind='theorem',name=name('ordinaryNameProof'),level_params=[],
            type=raw(app(const('Nat.add'),truth,truth)),value=raw(lam('P',prop,lam('h','P','h')))))


class NatArithmeticSourceTest(unittest.TestCase):
    def test_negative_offsets_and_large_shift_bounds(self):
        cfg=spec.MachineConfig(heap=32768,stack=256,context=128,constants=32,fuel=1000000,word_bits=16)
        circuit=CircuitHarness(cfg)
        for kind in ('negative-offset','large-right','large-left-zero','large-left-resource'):
            doc=arithmetic_document();one=['succ',['zero']];nt=const('Nat');number=lambda n:('nat',str(n))
            if kind=='negative-offset':
                ty=pi('n',nt,app(const('Eq',one),nt,app(const('Nat.succ'),'n'),number(1)))
                value=lam('n',nt,app(const('Eq.refl',one),nt,number(1)))
            else:
                operation='shiftRight' if kind=='large-right' else 'shiftLeft'
                left=0 if kind=='large-left-zero' else 1
                expr=app(const('Nat.'+operation),number(left),number(1<<80))
                ty=app(const('Eq',one),nt,expr,number(0));value=app(const('Eq.refl',one),nt,number(0))
            doc['name']=kind;doc['target'].update(type=raw(ty),value=raw(value))
            if kind!='large-left-resource':
                source,args,decls=program.parse_document(doc);oracle=EnvironmentDriver(source).check()
                self.assertEqual(oracle.status,'REJECT' if kind=='negative-offset' else 'ACCEPT',(kind,oracle))
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs'];prior={k:int(v)for k,v in r.items()};machine.step()
                if r['status']:
                    before=canonical(state);before['regs']=prior;self.assertEqual(circuit.step(before),canonical(state),kind);break
            expected=spec.Outcome.INVALID if kind=='negative-offset' else spec.Outcome.RESOURCE if kind=='large-left-resource' else spec.Outcome.DONE
            self.assertEqual(r['status'],expected,(kind,r['reason']))
            self.assertEqual(r['published_declarations'],29)
            print('Nat offset/shift boundary',kind,spec.Outcome(r['status']).name,spec.Reason(r['reason']).name,step+1,'steps',flush=True)

    def test_whole_source_composition_and_ordinary_delta_fallback(self):
        cfg=spec.MachineConfig(heap=32768,stack=256,context=128,constants=32,fuel=1000000,word_bits=16)
        # Selected Boolean checks are enabled once the complete source controller
        # reaches its first semantic checkpoint, not supplied as inference answers.
        checks=0;seen=set();circuit=CircuitHarness(cfg)
        for doc in (ordinary_name_document(),arithmetic_document(),false_arithmetic_document(),big_limb_document(),cap_document(),zero_offset_document()):
            source,args,decls=program.parse_document(doc);driver=EnvironmentDriver(source);oracle=driver.check()
            self.assertEqual(oracle.status,'ACCEPT',(doc['name'],oracle));self.assertEqual(oracle.assumptions,())
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
            owners={spec.Task.NAT_CLASSIFY,spec.Task.NAT_BRIDGE,spec.Task.NAT_REDUCE,spec.Task.NAT_BITS,spec.Task.NAT_HIGH,spec.Task.BOOL_BINDINGS,spec.Task.NAT_OFFSET}
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1] if r['sp'] else [0]*6;key=None
                node=state['heap'][r['x']] if r['x']<cfg.heap else [0]*4
                if r['mode']==spec.Mode.RETURN and frame[3] in owners:key=('return',int(frame[3]),frame[0],frame[1] if frame[3]==spec.Task.NAT_BITS else 0,bool(r['r']))
                elif r['task']==spec.Task.NAT_OFFSET:key=('offset',r['offset_pc'],r['offset_is_zero'],node[0],bool(node[1]))
                elif r['task']==spec.Task.NAT_CLASSIFY:
                    key=('name',r['nat_name_pc'],r['nat_name_state'] if r['nat_name_pc']==10 else 0,node[1] if r['nat_name_pc'] in (6,10) else 0,r['nat_name_remaining']==1)
                elif r['task']==spec.Task.NAT_BRIDGE:key=('bridge',r['nat_bridge_pc'],r['nat_operation'])
                elif r['task']==spec.Task.NAT_REDUCE:
                    branch=frame[2] if r['nat_reduce_pc'] in (5,7,12,13,26,60,80,81,90,91,104) else 0
                    key=('reduce',r['nat_reduce_pc'],branch,node[0],bool(r['x']))
                elif r['task']==spec.Task.BOOL_BINDINGS:key=('bool',r['bool_pc'],r['bool_validated'])
                elif r['task']==spec.Task.NAT_BITS:
                    branch=r['bits_operation'] if r['bits_pc'] in (0,41,42,46,58) else 0
                    key=('bits',r['bits_pc'],branch,r['bits_carry'],bool(r['bits_left_count']),bool(r['bits_right_count']),node[1] if r['bits_pc'] in(43,45,46) else 0,r['bits_position']==15)
                elif r['task']==spec.Task.NAT_HIGH:key=('high',r['high_pc'],frame[4] if r['high_pc']==1 else 0,bool(node[1]),bool(node[2]))
                elif r['mode']==spec.Mode.RETURN and frame[3] in owners:key=('return',int(frame[3]),frame[0],bool(r['r']))
                before=canonical(state) if key is not None and key not in seen else None
                state=machine.step();r=state['regs']
                if before is not None:
                    actual=circuit.step(before);seen.add(key);checks+=1
                    if actual!=state:
                        diff={k:(actual['regs'][k],int(r[k])) for k in spec.REGISTERS if actual['regs'][k]!=r[k]}
                        self.fail(str((doc['name'],step,key,diff)))
                if r['status']:break
            self.assertEqual((r['status'],r['reason']),(spec.Outcome.DONE,0),
                (doc['name'],step,{k:int(r[k]) for k in ('status','reason','task','mode','nat_reduce_pc','nat_bridge_pc','bits_pc','high_pc','x','free','raw_index','sp')}))
            assert_public_matches_independent(self,state,driver)
            if doc['name']=='neutral-primitive-name-still-ordinary-data':self.assertEqual(r['nat_validated'],0)
            print('Nat arithmetic whole source',doc['name'],'DONE',step+1,'steps',r['free'],'heap',r['published_declarations'],'signatures; no assumptions',flush=True)
        print('Nat arithmetic selected Boolean transitions',checks,flush=True)


if __name__=='__main__':unittest.main()
