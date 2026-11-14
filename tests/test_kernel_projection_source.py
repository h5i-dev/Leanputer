"""Pinned projection rules through checked original-source environments."""
from copy import deepcopy
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.arena import Tag
from tests.test_kernel_source_nested_transaction import canonical
from tests.test_kernel_traversal_machine import CircuitHarness


def cases():
    name=lambda s:[{'str':s}]
    prop=['sort',['zero']];type0=['sort',['succ',['zero']]];type1=['sort',['succ',['succ',['zero']]]]
    truth=['pi',0,prop,['pi',0,['var',0],['var',1]]]
    proof=['lam',0,prop,['lam',0,['var',0],['var',0]]]
    def const(s,levels=()):return ['const',name(s),list(levels)]
    def block(s,ty,ctor,parameters=0,universes=()):
        return dict(kind='inductive_block',level_params=list(universes),parameters=parameters,recursor_claims=[],families=[dict(
            name=name(s),recursor_name=name(s)+[{'str':'rec'}],type=ty,constructors=[dict(name=name(s)+[{'str':'mk'}],type=ctor)])])
    def doc(label,decl,ty,value,kind='definition'):
        return dict(format='leanputer.kernel-source.v1',status='EXPORTED',name=label,declarations=[decl],target=dict(
            kind=kind,name=name(label),level_params=[],type=ty,value=value))
    dep=const('DependentBox')
    depblock=block('DependentBox',type1,['pi',0,type0,['pi',0,['var',0],dep]])
    good=doc('dependent-field',depblock,['pi',0,dep,['proj',name('DependentBox'),0,['var',0]]],
        ['lam',0,dep,['proj',name('DependentBox'),1,['var',0]]])
    fn=['pi',0,prop,prop];identity=['lam',0,prop,['var',0]]
    constructed=['app',['app',['const',name('DependentBox')+[{'str':'mk'}],[]],fn],identity]
    beta=doc('projection-surplus-beta',depblock,['app',['proj',name('DependentBox'),1,constructed],truth],proof,'theorem')
    wrong=deepcopy(good);wrong['name']='wrong-family';wrong['target']['value'][3][1]=name('Foreign')
    outside=deepcopy(good);outside['name']='out-of-range';outside['target']['value'][3][2]=7
    packed=const('ProofBox')
    propblock=block('ProofBox',prop,['pi',0,type0,['pi',0,truth,packed]])
    denied=doc('prop-data-denied',propblock,['pi',0,packed,type0],['lam',0,packed,['proj',name('ProofBox'),0,['var',0]]])
    skipped=doc('prop-unused-data-skipped',propblock,['pi',0,packed,truth],['lam',0,packed,['proj',name('ProofBox'),1,['var',0]]],'theorem')
    dependent_proof=['pi',0,['var',0],truth]
    dependent_block=block('ProofBox',prop,['pi',0,type0,['pi',0,dependent_proof,packed]])
    bad_dep=doc('prop-dependent-data-denied',dependent_block,['pi',0,packed,truth],['lam',0,packed,['proj',name('ProofBox'),1,['var',0]]])
    u=name('u');level=['succ',['param',u]];univ=['sort',level];p=const('ParamBox',[['param',u]])
    ptype=['pi',1,univ,univ]
    pctor=['pi',1,univ,['pi',0,['var',0],['app',p,['var',1]]]]
    pblock=block('ParamBox',ptype,pctor,1,[u]);applied=['app',const('ParamBox',[['zero']]),prop]
    param=doc('universe-parameter-prefix',pblock,['pi',0,applied,prop],['lam',0,applied,['proj',name('ParamBox'),0,['var',0]]])
    return [(good,True),(beta,True),(wrong,False),(outside,False),(denied,False),(skipped,True),(bad_dep,False),(param,True)]


class ProjectionSourceTest(unittest.TestCase):
    def test_pinned_dependency_prop_parameter_rules_and_whnf_composition(self):
        cfg=spec.MachineConfig(heap=8192,stack=64,context=32,constants=2,fuel=100000,word_bits=14)
        circuit=CircuitHarness(cfg);seen=set();checked=0
        tasks={spec.Task.FAMILY_INFO:'family_info_pc',spec.Task.PROJECTION_INFER:'projection_pc',spec.Task.PROJECTION_REDUCE:'projection_reduce_pc'}
        for doc,valid in cases():
            with self.subTest(doc=doc['name']):
                source,args,decls=program.parse_document(doc);oracle=EnvironmentDriver(source).check()
                self.assertEqual(oracle.status,'ACCEPT' if valid else 'REJECT',(doc['name'],oracle))
                source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
                for step in range(cfg.fuel+2):
                    state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1] if r['sp'] else [0]*6;key=None
                    if r['task'] in tasks and r['mode']==spec.Mode.WALK:
                        node=state['heap'][r['x']] if 0<=r['x']<cfg.heap else [0]*4
                        key=(int(r['task']),r[tasks[r['task']]],node[0],bool(node[1]),bool(node[2]),bool(node[3]),bool(r['r']))
                    elif r['mode']==spec.Mode.RETURN and frame[3] in set(tasks)|{spec.Task.PROJECTION_BRIDGE}:
                        key=('return',int(frame[3]),frame[0],frame[1] if frame[3]==spec.Task.FAMILY_INFO else 0,bool(r['r']))
                    elif r['task']==spec.Task.BETA_ZETA and r['mode']==spec.Mode.BETA_ZETA and state['heap'][r['x']][0]==Tag.PROJ:
                        key=('bridge',bool(r['sp']))
                    before=canonical(state) if key is not None and key not in seen else None
                    expected=machine.step()
                    if before is not None:
                        actual=circuit.step(before);checked+=1;seen.add(key)
                        if actual!=expected:
                            differences={k:(actual['regs'][k],int(expected['regs'][k])) for k in spec.REGISTERS if actual['regs'][k]!=expected['regs'][k]}
                            self.fail(str((doc['name'],step,key,differences)))
                    if expected['regs']['status']:break
                r=machine.state['regs']
                self.assertEqual(r['status'],spec.Outcome.DONE if valid else spec.Outcome.INVALID,
                    (doc['name'],step,{k:int(r[k]) for k in ('status','reason','task','mode','projection_pc','projection_reduce_pc','family_info_pc','x','free')}))
                if valid:self.assertEqual((r['sp'],r['ctx'],r['typing_active']),(0,0,0))
                else:self.assertEqual((r['reason'],r['raw_index']),(spec.Reason.INVALID_PROJECTION,1))
                print('projection source',doc['name'],spec.Outcome(r['status']).name,step+1,'steps',flush=True)
        print('projection selected Boolean transitions',checked,flush=True)


if __name__=='__main__':unittest.main()
