"""Original Nat source through literal inference and generic recursor iota.

These are genuine primitive limb operations, not special ordinary formation.
"""
import unittest
from types import SimpleNamespace
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.arena import Tag
from leanputer.kernel.native_cells import VectorKind
from tests.test_kernel_native_cells import vector
from tests.test_kernel_source_nested_transaction import canonical,assert_public_matches_independent
from tests.test_kernel_traversal_machine import CircuitHarness


def document(value):
    name=lambda s:[{'str':part} for part in s.split('.')]
    const=lambda s,us=[]:['const',name(s),us]
    prop=['sort',['zero']];type0=['sort',['succ',['zero']]];two=['succ',['succ',['zero']]]
    nat=const('Nat')
    block=dict(kind='inductive_block',level_params=[],parameters=0,recursor_claims=[],families=[dict(
        name=name('Nat'),recursor_name=name('Nat.rec'),type=type0,constructors=[
            dict(name=name('Nat.zero'),type=nat),dict(name=name('Nat.succ'),type=['pi',0,nat,nat])])])
    def app(fn,*args):
        for arg in args:fn=['app',fn,arg]
        return fn
    rec=app(const('Nat.rec',[two]),['lam',0,nat,type0],prop,['lam',0,nat,['lam',0,type0,prop]],['nat',value])
    truth=['pi',0,prop,['pi',0,['var',0],['var',1]]]
    return dict(format='leanputer.kernel-source.v1',status='EXPORTED',name='source-natural-literal-'+value,
        declarations=[block],target=dict(kind='definition',name=name('literalRecursor'),level_params=[],type=rec,value=truth))


class NatLiteralSourceTest(unittest.TestCase):
    def test_type_only_bindings_and_narrow_borrow_are_explicit(self):
        circuit=None
        for kind in ('missing','empty','two-fields','narrow-borrow'):
            doc=document('65536' if kind=='narrow-borrow' else '0')
            if kind!='narrow-borrow':
                doc['target']['type']=['const',[{'str':'Nat'}],[]]
                doc['target']['value']=['nat','0']
            if kind=='missing':
                doc['declarations']=[];doc['target']['type']=['sort',['succ',['zero']]]
            elif kind=='empty':doc['declarations'][0]['families'][0]['constructors']=[]
            elif kind=='two-fields':
                nat=['const',[{'str':'Nat'}],[]]
                doc['declarations'][0]['families'][0]['constructors'][1]['type']=['pi',0,nat,['pi',0,nat,nat]]
            if kind!='narrow-borrow':
                source,args,decls=program.parse_document(doc);driver=EnvironmentDriver(source);oracle=driver.check()
                self.assertEqual(oracle.status,'GAP'if kind=='missing'else'ACCEPT',(kind,oracle))
            cfg=spec.MachineConfig(heap=2048,stack=64,context=32,constants=2,fuel=100000,word_bits=12)
            if circuit is None:circuit=CircuitHarness(cfg)
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs'];prior_regs={k:int(v) for k,v in r.items()}
                machine.step()
                if r['status']:
                    before=canonical(state);before['regs']=prior_regs;self.assertEqual(circuit.step(before),canonical(state),kind)
                    break
            self.assertEqual(r['status'],spec.Outcome.RESOURCE if kind=='narrow-borrow' else spec.Outcome.GAP if kind=='missing' else spec.Outcome.DONE,(kind,r['reason']))
            if kind=='narrow-borrow':self.assertEqual(r['reason'],spec.Reason.INDEX)
            elif kind!='missing':self.assertEqual((r['nat_type_validated'],r['nat_validated']),(1,0))
            self.assertEqual(r['published_declarations'],0 if kind=='missing' else 2 if kind=='empty' else 4)
            print('Nat literal boundary',kind,spec.Outcome(r['status']).name,spec.Reason(r['reason']).name,flush=True)

    def test_original_nat_arbitrary_limbs_and_recursor_computation(self):
        cfg=spec.MachineConfig(heap=8192,stack=128,context=64,constants=2,fuel=150000,word_bits=16)
        circuit=CircuitHarness(cfg);seen=set();checks=0
        for value in ('0','1','65536','1461501637330902918203684832716283019655932542976','340282366920938463463374607431768211473'):
            doc=document(value);source,args,decls=program.parse_document(doc);driver=EnvironmentDriver(source);oracle=driver.check()
            self.assertEqual(oracle.status,'ACCEPT',(value,oracle))
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls));prepared=False
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1] if r['sp'] else [0]*6;key=None
                if r['task'] in (spec.Task.NAT_BINDINGS,spec.Task.NAT_LITERAL):
                    pc=r['nat_binding_pc'] if r['task']==spec.Task.NAT_BINDINGS else r['nat_literal_pc']
                    key=(int(r['task']),r['mode'],pc,r['nat_literal_operation'],r['nat_borrow'],bool(r['nat_limb_count']),bool(r['r']))
                    if r['task']==spec.Task.NAT_LITERAL and r['mode']==spec.Mode.WALK and pc==15:
                        result=state['heap'][r['nat_literal_result']]
                        if value=='0':self.assertEqual((result[0],result[1]),(Tag.CONST,r['nat_symbol_zero']))
                        else:
                            self.assertEqual(result[0],Tag.APP);literal=state['heap'][result[2]];self.assertEqual(literal[0],Tag.NAT)
                            limbs=vector(SimpleNamespace(heap=state['heap']),literal[1],VectorKind.LIMBS)
                            self.assertEqual(sum(limb<<(16*i) for i,limb in enumerate(limbs)),int(value)-1)
                        prepared=True
                elif r['mode']==spec.Mode.RETURN and frame[3] in (spec.Task.NAT_BINDINGS,spec.Task.NAT_LITERAL):key=('return',int(frame[3]),frame[1])
                before=canonical(state) if key is not None and key not in seen else None
                expected=machine.step()
                if before is not None:
                    actual=circuit.step(before);seen.add(key);checks+=1
                    if actual!=expected:
                        diff={k:(actual['regs'][k],int(expected['regs'][k])) for k in spec.REGISTERS if actual['regs'][k]!=expected['regs'][k]}
                        self.fail(str((value,step,key,diff)))
                if expected['regs']['status']:break
            self.assertEqual((r['status'],r['reason']),(spec.Outcome.DONE,0),
                (value,{k:int(r[k]) for k in ('status','reason','task','mode','nat_binding_pc','nat_literal_pc','x','free','raw_index')}))
            self.assertTrue(prepared);self.assertEqual((r['published_declarations'],r['nat_validated']),(4,1))
            assert_public_matches_independent(self,state,driver)
            print('original Nat literal',value,'source DONE',step+1,'steps',r['free'],'heap',flush=True)
        print('Nat literal selected Boolean transitions',checks,flush=True)


if __name__=='__main__':unittest.main()
