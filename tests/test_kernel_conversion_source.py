"""General typed conversion exercised through raw source transactions."""
from copy import deepcopy
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.arena import Tag
from tests.test_kernel_source_nested_transaction import canonical
from tests.test_kernel_traversal_machine import CircuitHarness


def cases():
    name=lambda s:[{'str':s}]
    const=lambda s:['const',name(s),[]]
    prop=['sort',['zero']];type0=['sort',['succ',['zero']]]
    def ax(s,ty):return dict(kind='axiom',name=name(s),level_params=[],type=ty,value=None)
    def doc(label,ds,ty,val):return dict(format='leanputer.kernel-source.v1',status='EXPORTED',name=label,declarations=ds,
        target=dict(kind='definition',name=name(label),level_params=[],type=ty,value=val))
    app=lambda fn,arg:['app',fn,arg]
    proof=[ax('P',prop),ax('h1',const('P')),ax('h2',const('P')),ax('F',['pi',0,const('P'),type0]),ax('v',app(const('F'),const('h1')))]
    irrelevant=doc('proof-irrelevance',proof,app(const('F'),const('h2')),const('v'))
    arrow=['pi',0,const('A'),const('A')]
    function=[ax('A',type0),ax('f',arrow),ax('G',['pi',0,arrow,type0]),ax('v',app(const('G'),const('f')))]
    expanded=['lam',0,const('A'),app(const('f'),['var',0])]
    eta=doc('function-eta',function,app(const('G'),expanded),const('v'))
    binder_ty=['pi',0,type0,['pi',0,['var',0],['var',1]]]
    beta=['app',['lam',0,type0,['var',0]],['var',0]]
    alternate=['pi',0,type0,['pi',0,beta,['var',1]]]
    binders=doc('binder-congruence',[],alternate,['lam',0,type0,['lam',0,['var',0],['var',0]]])
    def record(s,fields):
        ty=const(s)
        for field in reversed(fields):ty=['pi',0,field,ty]
        return dict(kind='inductive_block',level_params=[],parameters=0,recursor_claims=[],families=[dict(
            name=name(s),recursor_name=name(s)+[{'str':'rec'}],type=type0,constructors=[dict(name=name(s)+[{'str':'mk'}],type=ty)])])
    # A single data field, with its type supplied by an explicitly checked axiom.
    pair=record('Record',[const('A')]);r=const('r')
    structure=doc('structure-eta',[ax('A',type0),pair,ax('r',const('Record')),ax('G',['pi',0,const('Record'),type0]),
        ax('v',app(const('G'),r))],app(const('G'),app(['const',name('Record')+[{'str':'mk'}],[]],['proj',name('Record'),0,r])),const('v'))
    unit=record('Unitish',[])
    unitlike=doc('unit-like',[unit,ax('x',const('Unitish')),ax('y',const('Unitish')),ax('G',['pi',0,const('Unitish'),type0]),
        ax('v',app(const('G'),const('x')))],app(const('G'),const('y')),const('v'))
    u,v=name('u'),name('universe_v');pu,pv=['param',u],['param',v]
    type_scheme=dict(kind='axiom',name=name('UniverseType'),level_params=[u,v],type=['sort',['succ',['max',pu,pv]]],value=None)
    ordinary_type=['const',name('UniverseType'),[pu,pv]]
    element=dict(kind='axiom',name=name('element'),level_params=[u,v],type=ordinary_type,value=None)
    levels=doc('equivalent-level-vector',[type_scheme,element],['const',name('UniverseType'),[['max',pu,['zero']],['max',pv,pv]]],['const',name('element'),[pu,pv]])
    levels['target']['level_params']=[u,v]
    return [irrelevant,eta,binders,structure,unitlike,levels]


class ConversionSourceTest(unittest.TestCase):
    def test_general_typed_rules_from_original_source(self):
        cfg=spec.MachineConfig(heap=16384,stack=128,context=64,constants=8,fuel=200000,word_bits=15)
        circuit=CircuitHarness(cfg);seen=set();checked=0
        tasks={spec.Task.CONVERT:'convert_pc',spec.Task.LEVELS_EQUIVALENT:'levels_eq_pc',spec.Task.STRUCTURE_INFO:'structure_pc'}
        for doc in cases():
            with self.subTest(doc=doc['name']):
                source,args,decls=program.parse_document(doc);oracle=EnvironmentDriver(source).check();self.assertEqual(oracle.status,'ACCEPT',(doc['name'],oracle))
                source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
                for step in range(cfg.fuel+2):
                    state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1] if r['sp'] else [0]*6;key=None
                    if r['task'] in tasks and r['mode']==spec.Mode.WALK:
                        node=state['heap'][r['x']] if 0<=r['x']<cfg.heap else [0]*4
                        key=(int(r['task']),r[tasks[r['task']]],node[0],bool(node[1]),bool(node[2]),bool(node[3]),bool(r['r']))
                    elif r['mode']==spec.Mode.RETURN and frame[3] in tasks:key=('return',int(frame[3]),frame[0],bool(r['r']))
                    before=canonical(state) if key is not None and key not in seen else None
                    expected=machine.step()
                    if before is not None:
                        actual=circuit.step(before);checked+=1;seen.add(key)
                        if actual!=expected:
                            differences={k:(actual['regs'][k],int(expected['regs'][k])) for k in spec.REGISTERS if actual['regs'][k]!=expected['regs'][k]}
                            self.fail(str((doc['name'],step,key,differences)))
                    if expected['regs']['status']:break
                r=machine.state['regs']
                self.assertEqual((r['status'],r['reason']),(spec.Outcome.DONE,0),
                    (doc['name'],step,{k:int(r[k]) for k in ('status','reason','task','convert_pc','structure_pc','x','ctx','free')}))
                self.assertEqual((r['ctx'],r['sp'],r['typing_active']),(len(doc['target']['level_params']),0,0))
                self.assertEqual(len(program.assumptions_from_state(decls,r)),len([d for d in doc['declarations'] if d['kind']=='axiom']))
                print('conversion source',doc['name'],'DONE',step+1,'steps',flush=True)
        print('conversion selected Boolean transitions',checked,flush=True)


if __name__=='__main__':unittest.main()
