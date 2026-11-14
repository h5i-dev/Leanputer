"""K/structure reduction through original source, including restored arity changes."""
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from tests.test_kernel_source_nested_transaction import canonical
from tests.test_kernel_traversal_machine import CircuitHarness


def cases():
    name=lambda s:[{'str':s}]
    const=lambda s,levels=[]:['const',name(s),levels]
    prop=['sort',['zero']];type0=['sort',['succ',['zero']]];two=['succ',['succ',['zero']]]
    truth=['pi',0,prop,['pi',0,['var',0],['var',1]]]
    def app(fn,*args):
        for arg in args:fn=['app',fn,arg]
        return fn
    def block(s,ty,ctor_ty,params=0):return dict(kind='inductive_block',level_params=[],parameters=params,recursor_claims=[],families=[dict(
        name=name(s),recursor_name=name(s)+[{'str':'rec'}],type=ty,constructors=[dict(name=name(s)+[{'str':'mk'}],type=ctor_ty)])])
    def ax(s,ty):return dict(kind='axiom',name=name(s),level_params=[],type=ty,value=None)
    def doc(label,decls,ty,val):return dict(format='leanputer.kernel-source.v1',status='EXPORTED',name=label,declarations=decls,
        target=dict(kind='definition',name=name(label),level_params=[],type=ty,value=val))
    unit=const('ProofUnit');unitblock=block('ProofUnit',prop,unit)
    k=doc('source-K-major',[unitblock,ax('h',unit)],app(['const',name('ProofUnit')+[{'str':'rec'}],[two]],
        ['lam',0,unit,type0],prop,const('h')),truth)
    a=const('A');box=const('Box');boxblock=block('Box',type0,['pi',0,a,box])
    eta=doc('source-structure-major',[ax('A',type0),boxblock,ax('r',box)],app(['const',name('Box')+[{'str':'rec'}],[two]],
        ['lam',0,box,type0],['lam',0,a,prop],const('r')),truth)
    f=const('Container');w=const('NestedFamily')
    fblock=block('Container',['pi',0,type0,type0],['pi',1,type0,['pi',0,['var',0],app(f,['var',1])]],1)
    # Current block has TWO dependent parameters; its prior owner has ONE.
    wtype=['pi',0,type0,['pi',0,['var',0],type0]]
    wctor=['pi',1,type0,['pi',1,['var',0],['pi',0,app(f,app(w,['var',1],['var',0])),app(w,['var',2],['var',1])]]]
    wblock=block('NestedFamily',wtype,wctor,2)
    wa=app(w,['var',2],['var',1]);fwa=app(f,wa)
    rec=app(['const',name('NestedFamily')+[{'str':'rec_1'}],[two]],['var',2],['var',1],
        ['lam',0,wa,type0],['lam',0,fwa,type0],
        ['lam',0,fwa,['lam',0,type0,prop]],['lam',0,wa,['lam',0,type0,prop]],['var',0])
    ty=['pi',0,type0,['pi',0,['var',0],['pi',0,app(f,app(w,['var',1],['var',0])),rec]]]
    value=['lam',0,type0,['lam',0,['var',0],['lam',0,app(f,app(w,['var',1],['var',0])),truth]]]
    nested=doc('restored-owner-parameter-count',[fblock,wblock],ty,value)
    return [k,eta,nested]


class SourceMajorExpansionTest(unittest.TestCase):
    def test_source_k_eta_and_nested_owner_counts(self):
        from leanputer.kernel.major_rules import Path
        cfg=spec.MachineConfig(heap=32768,stack=128,context=64,constants=4,fuel=250000,word_bits=16)
        circuit=CircuitHarness(cfg);seen=set();checks=0
        for doc in cases():
            with self.subTest(doc=doc['name']):
                source,args,decls=program.parse_document(doc);oracle=EnvironmentDriver(source).check();self.assertEqual(oracle.status,'ACCEPT',(doc['name'],oracle))
                source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls));observed=False
                for step in range(cfg.fuel+2):
                    state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1] if r['sp'] else [0]*6;key=None
                    if r['task'] in (spec.Task.PREPARE_RECURSOR_MAJOR,spec.Task.STRUCTURE_INFO):
                        node=state['heap'][r['x']] if r['x']<cfg.heap else [0]*4
                        key=(int(r['task']),int(r['mode']),r['major_path'],r['structure_pc'],node[0],bool(r['r']))
                    elif r['mode']==spec.Mode.RETURN and frame[3] in (spec.Task.PREPARE_RECURSOR_MAJOR,spec.Task.STRUCTURE_INFO):key=('return',int(frame[3]),frame[0],bool(r['r']))
                    if doc['name']=='restored-owner-parameter-count' and r['task']==spec.Task.PREPARE_RECURSOR_MAJOR and r['mode']==spec.Mode.MAJOR_CONSTRUCTOR and r['major_path']==Path.ETA_BUILD:
                        self.assertEqual(r['major_parameters'],1);observed=True
                    before=canonical(state) if key is not None and key not in seen else None
                    expected=machine.step()
                    if before is not None:
                        actual=circuit.step(before);checks+=1;seen.add(key)
                        if actual!=expected:
                            differences={k:(actual['regs'][k],int(expected['regs'][k])) for k in spec.REGISTERS if actual['regs'][k]!=expected['regs'][k]}
                            self.fail(str((doc['name'],step,key,differences)))
                    if expected['regs']['status']:break
                r=machine.state['regs'];self.assertEqual((r['status'],r['reason']),(spec.Outcome.DONE,0),
                    (doc['name'],step,{k:int(r[k])for k in ('status','reason','task','mode','major_path','major_parameters','free')}))
                if doc['name']=='restored-owner-parameter-count':self.assertTrue(observed)
                print('original source major expansion',doc['name'],'DONE',step+1,'steps',flush=True)
        print('major expansion selected Boolean transitions',checks,flush=True)


if __name__=='__main__':unittest.main()
