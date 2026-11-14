"""Whole original-source quotient transaction and reductions; no primitive ABI."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from tests.test_kernel_source_nested_transaction import canonical,linked,assert_public_matches_independent
from tests.test_kernel_traversal_machine import CircuitHarness


def name(s):return [{'str':part} for part in s.split('.')]

def pi(x,t,b,bi=0):return ('pi',x,t,b,bi)

def lam(x,t,b,bi=0):return ('lam',x,t,b,bi)

def app(f,*args):
    for a in args:f=('app',f,a)
    return f


def const(n,*levels):return ('const',name(n),list(levels))


def raw(expr,scope=()):
    if isinstance(expr,str):return ['var',scope.index(expr)]
    tag,*args=expr
    if tag in ('pi','lam'):
        x,t,b,bi=args;return [tag,bi,raw(t,scope),raw(b,(x,)+scope)]
    if tag=='app':return ['app',raw(args[0],scope),raw(args[1],scope)]
    return [tag,*args]


def document():
    u=['param',name('claimUniverse')];v=['param',name('resultUniverse')]
    prop=('sort',['zero']);su=('sort',u);sv=('sort',v)
    relation=pi('x','a',pi('y','a',prop));q=app(const('Quot',u),'a','r')
    qt=pi('a',su,pi('r',relation,su),1)
    mt=pi('a',su,pi('r',relation,pi('x','a',q)),1)
    sanity=pi('x','a',pi('y','a',pi('h',app('r','x','y'),app(const('Eq',v),'b',app('f','x'),app('f','y')))))
    lt=pi('a',su,pi('r',relation,pi('b',sv,pi('f',pi('x','a','b'),pi('h',sanity,pi('q',q,'b'))),1),1),1)
    minor=pi('x','a',app('b',app(const('Quot.mk',u),'a','r','x')))
    it=pi('a',su,pi('r',relation,pi('b',pi('q',q,prop),pi('m',minor,pi('q',q,app('b','q'))),1),1),1)
    eq=json.loads(Path('tests/fixtures/kernel-source-smoke.jsonl').read_text().splitlines()[2])['declarations'][0]
    # The pinned initializer uses the ACTUAL sole constructor; it does not
    # require the ordinary library spelling Eq.refl.
    def rename(node):
        if node==name('Eq.refl'):return name('arbitraryEqualityConstructor')
        if isinstance(node,list):return [rename(x) for x in node]
        if isinstance(node,dict):return {k:rename(v) for k,v in node.items()}
        return node
    eq=rename(eq)
    declarations=[eq]
    for interface,n,ty in [('type','Quot',qt),('ctor','Quot.mk',mt),('lift','Quot.lift',lt),('ind','Quot.ind',it)]:
        declarations.append(dict(kind='quot_primitive',interface=interface,name=name(n),level_params=[name('claimUniverse')]+([name('resultUniverse')] if interface=='lift' else []),type=raw(ty)))
    identity=pi('a',su,pi('r',relation,pi('q',q,q)))
    value=lam('a',su,lam('r',relation,lam('q',q,'q')))
    return dict(format='leanputer.kernel-source.v1',status='EXPORTED',name='source-quotient',declarations=declarations,
        target=dict(kind='definition',name=name('quotientIdentity'),level_params=[name('claimUniverse')],type=raw(identity),value=raw(value)))


def lift_document(nested=False):
    doc=document();u=['param',name('claimUniverse')];su=('sort',u)
    rel=pi('y','a',pi('z','a',('sort',['zero'])))
    q=app(const('Quot',u),'a','r');mk=lambda x:app(const('Quot.mk',u),'a','r',x)
    eq=lambda ty,x,y:app(const('Eq',u),ty,x,y)
    identity=lam('y','a','y')
    sanity=pi('y','a',pi('z','a',pi('h',app('r','y','z'),eq('a','y','z'))))
    major=mk('x')
    binders=[('a',su),('r',rel),('h',sanity),('x','a')]
    if nested:
        inner_sanity=pi('y','a',pi('z','a',pi('h',app('r','y','z'),eq(q,mk('y'),mk('z')))))
        binders.insert(3,('inner_h',inner_sanity))
        major=app(const('Quot.lift',u,u),'a','r',q,lam('y','a',mk('y')),'inner_h',major)
    reduced=app(const('Quot.lift',u,u),'a','r','a',identity,'h',major)
    ty=eq('a',reduced,'x');value=app(const('arbitraryEqualityConstructor',u),'a','x')
    for x,t in reversed(binders):ty=pi(x,t,ty);value=lam(x,t,value)
    doc['name']='source-quot-lift-nested' if nested else 'source-quot-lift'
    doc['target'].update(kind='theorem',name=name(doc['name']),type=raw(ty),value=raw(value))
    return doc


def ind_document():
    doc=document();one=['succ',['zero']];prop=('sort',['zero'])
    truth=pi('P',prop,pi('h','P','P'));proof=lam('P',prop,lam('h','P','h'))
    relation=lam('x',prop,lam('y',prop,truth))
    q=app(const('Quot',one),prop,relation)
    motive=lam('q',q,truth);minor=lam('x',prop,const('proofIdentity'))
    major=app(const('Quot.mk',one),prop,relation,truth)
    value=app(const('Quot.ind',one),prop,relation,motive,minor,major,truth,const('proofIdentity'))
    doc['declarations'].append(dict(kind='definition',name=name('proofIdentity'),level_params=[],type=raw(truth),value=raw(proof)))
    doc['name']='source-quot-ind-surplus'
    doc['target'].update(name=name(doc['name']),level_params=[],type=raw(truth),value=raw(value))
    return doc


class QuotientSourceTest(unittest.TestCase):
    def test_original_source_initialization(self):
        self.seen=set();self.circuit=None;self.checks=0
        for doc in [document(),lift_document(),lift_document(True),ind_document()]:
            with self.subTest(doc=doc['name']):self.check_source(doc)
        print('Quot selected Boolean transitions',self.checks,flush=True)

    def test_failed_claim_and_allocator_failure_are_atomic(self):
        circuit=None
        for kind in ('name','type','arity','later','heap'):
            doc=document()
            if kind=='name':doc['declarations'][1]['name']=name('wrongPrimitiveBinding')
            elif kind=='type':doc['declarations'][1]['type']=['sort',['zero']]
            elif kind=='arity':doc['declarations'][1]['level_params']=[]
            elif kind=='later':doc['declarations'][3]['type']=['sort',['zero']]
            if kind!='heap':
                source,args,decls=program.parse_document(doc);oracle=EnvironmentDriver(source).check()
                self.assertEqual(oracle.status,'REJECT',(kind,oracle))
            cfg=spec.MachineConfig(heap=4096,stack=128,context=64,constants=8,fuel=100000,word_bits=16)
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
            if circuit is None:circuit=CircuitHarness(cfg)
            prefix=None;injected=False
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs']
                desired=3 if kind=='later' else 1
                if r['raw_index']==desired and prefix is None:
                    prefix=tuple(r[k] for k in ('env_head','nested_registry_head','published_declarations','quot_initialized'))
                if kind=='heap' and r['task']==spec.Task.QUOT_INITIALIZE and r['quot_pc']==18 and not injected:
                    # Exhaust the actual allocator at a transaction boundary.
                    # Unused physical rows cannot supply any checked signature.
                    r['free']=cfg.heap-1;injected=True
                prior_regs={k:int(v) for k,v in r.items()}
                machine.step()
                if r['status']:
                    before=canonical(state);before['regs']=prior_regs
                    self.assertEqual(circuit.step(before),canonical(state),kind)
                    break
            self.assertIsNotNone(prefix)
            self.assertEqual(tuple(r[k] for k in ('env_head','nested_registry_head','published_declarations','quot_initialized')),prefix,kind)
            self.assertEqual(r['raw_index'],3 if kind=='later' else 1)
            self.assertEqual(r['status'],spec.Outcome.RESOURCE if kind=='heap' else spec.Outcome.INVALID,(kind,r['reason']))
            print('Quot transaction atomic',kind,spec.Outcome(r['status']).name,spec.Reason(r['reason']).name,flush=True)

    def test_replacement_current_environment_and_original_nested_registry(self):
        circuit=None;seen=set();checks=0
        for kind in ('replacement','replacement-then-nested','bad-replacement-claim','shadowed-head','partially-shadowed-mutual'):
            doc=document();type0=('sort',['succ',['zero']]);prop=('sort',['zero'])
            old=dict(kind='inductive_block',level_params=[],parameters=0,recursor_claims=[],families=[dict(
                name=name('Quot'),recursor_name=name('Quot.rec'),type=raw(type0),constructors=[dict(name=name('Quot.mk'),type=raw(const('Quot')))])])
            if kind in ('shadowed-head','partially-shadowed-mutual'):
                old['parameters']=1
                old['families'][0].update(type=raw(pi('a',type0,type0)),constructors=[dict(name=name('Quot.mk'),type=raw(pi('a',type0,pi('x','a',app(const('Quot'),'a')))))])
            if kind=='partially-shadowed-mutual':
                old['families'].append(dict(name=name('SurvivingMember'),recursor_name=name('SurvivingMember.rec'),type=raw(pi('a',type0,type0)),constructors=[dict(
                    name=name('unrelatedMemberConstructor'),type=raw(pi('a',type0,pi('x','a',app(const('SurvivingMember'),'a')))))]))
            doc['declarations'].insert(0,old)
            if kind=='replacement-then-nested':
                nested=json.loads(Path('tests/fixtures/kernel-nested-source.jsonl').read_text())
                doc['declarations'].insert(1,nested['declarations'][0]);doc['declarations'].append(nested['declarations'][1]);doc['target']=nested['target']
            elif kind=='bad-replacement-claim':doc['declarations'][2]['type']=raw(prop)
            elif kind in ('shadowed-head','partially-shadowed-mutual'):
                family='AfterReplacement';ft=const(family)
                field=app(const('SurvivingMember'),ft)if kind=='partially-shadowed-mutual'else app(const('Quot',['succ',['zero']]),ft,lam('x',ft,lam('y',ft,pi('P',prop,pi('h','P','P')))))
                doc['declarations'].append(dict(kind='inductive_block',level_params=[],parameters=0,recursor_claims=[],families=[dict(
                    name=name(family),recursor_name=name(family+'.rec'),type=raw(type0),constructors=[dict(name=name(family+'.mk'),type=raw(pi('field',field,ft)))])]))
            source,args,decls=program.parse_document(doc);driver=EnvironmentDriver(source);oracle=driver.check()
            expected_oracle='REJECT'if kind in('bad-replacement-claim','shadowed-head')else'GAP'if kind=='partially-shadowed-mutual'else'ACCEPT'
            self.assertEqual(oracle.status,expected_oracle,(kind,oracle))
            cfg=spec.MachineConfig(heap=32768,stack=256,context=128,constants=16,fuel=600000,word_bits=16)
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
            if circuit is None:circuit=CircuitHarness(cfg)
            prefix=None
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1]if r['sp']else[0]*6;key=None
                if kind=='bad-replacement-claim'and r['raw_index']==2 and prefix is None:prefix=tuple(r[k]for k in('env_head','nested_registry_head','published_declarations','quot_initialized'))
                if r['task']==spec.Task.QUOT_INITIALIZE:key=('quot',r['quot_pc'],r['quot_new'],bool(r['r']))
                elif r['task']==spec.Task.IS_NESTED_APPLICATION:key=('condition',int(r['mode']),frame[0],bool(r['r']))
                elif r['task']==spec.Task.REPLACE_NESTED and r['copy_pc']>=58:key=('current-copy',r['copy_pc'],int(r['mode']),bool(r['r']))
                elif r['mode']==spec.Mode.RETURN and frame[3]in(spec.Task.QUOT_INITIALIZE,spec.Task.IS_NESTED_APPLICATION):key=('return',int(frame[3]),frame[0],frame[1],bool(r['r']))
                before=canonical(state)if key is not None and key not in seen else None
                state=machine.step();r=state['regs']
                if before is not None:
                    self.assertEqual(circuit.step(before),state,(kind,step,key));seen.add(key);checks+=1
                if r['status']:break
            expected=spec.Outcome.INVALID if expected_oracle=='REJECT'else spec.Outcome.GAP if expected_oracle=='GAP'else spec.Outcome.DONE
            self.assertEqual(r['status'],expected,(kind,r['reason'],step,r['task'],r['mode'],r['copy_pc']))
            if expected_oracle=='ACCEPT':
                self.assertEqual(oracle.assumptions,());assert_public_matches_independent(self,state,driver)
                self.assertEqual(r['published_declarations'],len(driver.services.constants))
                self.assertEqual(r['quot_initialized'],1)
                if kind=='replacement-then-nested':self.assertTrue(r['stage_maps']);self.assertEqual(len(linked(state,r['nested_registry_head'])),4)
            elif kind=='bad-replacement-claim':self.assertEqual(tuple(r[k]for k in('env_head','nested_registry_head','published_declarations','quot_initialized')),prefix)
            elif kind=='shadowed-head':self.assertEqual(r['reason'],spec.Reason.INVALID_INDUCTIVE_APPLICATION);self.assertEqual(r['stage_maps'],0)
            else:self.assertEqual(r['reason'],spec.Reason.GAP_PRIMITIVE);self.assertEqual((r['raw_index'],r['published_declarations'],len(linked(state,r['nested_registry_head']))),(6,11,2))
            print('Quot original-source replacement',kind,spec.Outcome(r['status']).name,spec.Reason(r['reason']).name,step+1,'steps',r['free'],'heap',r['published_declarations'],'public',flush=True)
        print('Quot replacement selected Boolean all-state transitions',checks,flush=True)

    def test_replacement_invalidates_model_generated_literal_binding_caches(self):
        from tests.test_kernel_string_source import source_document
        strings=source_document();doc=document();type0=['sort',['succ',['zero']]]
        old=dict(kind='inductive_block',level_params=[],parameters=0,recursor_claims=[],families=[dict(name=name('Quot'),recursor_name=name('Quot.rec'),type=type0,constructors=[dict(name=name('Quot.mk'),type=['const',name('Quot'),[]])])])
        doc['declarations']=[old]+strings['declarations']+[strings['target']]+doc['declarations'][1:]
        source,args,decls=program.parse_document(doc);driver=EnvironmentDriver(source);oracle=driver.check();self.assertEqual(oracle.status,'ACCEPT',oracle)
        cfg=spec.MachineConfig(heap=32768,stack=256,context=128,constants=16,fuel=600000,word_bits=16)
        source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls));circuit=CircuitHarness(cfg);checked=False
        keys=('nat_validated','nat_type_validated','bool_validated','string_validated','string_type_validated')
        for step in range(cfg.fuel+2):
            state=machine.state;r=state['regs']
            boundary=r['task']==spec.Task.QUOT_INITIALIZE and r['mode']==spec.Mode.WALK and r['quot_pc']==22
            if boundary:
                self.assertEqual(tuple(r[k]for k in keys),(1,1,0,1,1));before=canonical(state)
            state=machine.step();r=state['regs']
            if boundary:
                self.assertEqual(circuit.step(before),state);self.assertEqual(tuple(r[k]for k in keys),(0,0,0,0,0));checked=True
            if r['status']:break
        self.assertTrue(checked);self.assertEqual((r['status'],r['reason'],r['quot_initialized']),(spec.Outcome.DONE,0,1))
        self.assertEqual(tuple(r[k]for k in keys),(0,0,0,0,0));assert_public_matches_independent(self,state,driver);self.assertEqual(oracle.assumptions,())
        print('Quot replacement after original-source String/Nat computation: DONE',step+1,'steps',r['free'],'heap',r['published_declarations'],'public; one cache-clear Boolean ALL-state check',flush=True)

    def check_source(self,doc):
        source,args,decls=program.parse_document(doc);driver=EnvironmentDriver(source);oracle=driver.check()
        self.assertEqual(oracle.status,'ACCEPT',oracle)
        cfg=spec.MachineConfig(heap=16384,stack=128,context=64,constants=8,fuel=250000,word_bits=16)
        source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
        if self.circuit is None:self.circuit=CircuitHarness(cfg)
        for step in range(cfg.fuel+2):
            state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1] if r['sp'] else [0]*6;key=None
            if r['task'] in (spec.Task.QUOT_INITIALIZE,spec.Task.QUOT_REDUCE):
                key=(int(r['task']),r['quot_pc'] if r['task']==spec.Task.QUOT_INITIALIZE else r['quot_reduce_pc'],r['mode'],bool(r['r']))
            elif r['mode']==spec.Mode.RETURN and frame[3] in (spec.Task.QUOT_INITIALIZE,spec.Task.QUOT_REDUCE):
                key=('return',int(frame[3]),frame[0],frame[1],bool(r['r']))
            elif r['mode']==spec.Mode.CONST_SCHEME and state['heap'][r['x']][2]==11:key=('constant',state['heap'][r['x']][3])
            elif r['mode']==spec.Mode.RETURN and frame[3]==spec.Task.CHECK_SOURCE and frame[0]==15:key=('source-quot-return',)
            before=canonical(state) if key is not None and key not in self.seen else None
            state=machine.step()
            if before is not None:
                actual=self.circuit.step(before);self.checks+=1;self.seen.add(key)
                if actual!=state:
                    diff={k:(actual['regs'][k],int(state['regs'][k])) for k in spec.REGISTERS if actual['regs'][k]!=state['regs'][k]}
                    self.fail(str((doc['name'],step,key,diff)))
            if state['regs']['status']:break
        r=state['regs'];self.assertEqual((r['status'],r['reason']),(spec.Outcome.DONE,0),{k:r[k] for k in ('status','reason','task','mode','quot_pc','x','free','raw_index')})
        assert_public_matches_independent(self,state,driver)
        self.assertEqual(r['quot_initialized'],1);self.assertEqual(r['published_declarations'],8 if doc['name']=='source-quot-ind-surplus' else 7)
        self.assertEqual((r['raw_index'],r['ctx']-r['count'],r['sp']),(len(doc['declarations']),0,0))
        if doc['name']=='source-quot-ind-surplus':
            from types import SimpleNamespace
            from leanputer.kernel.operations import representation_equal
            from tests.test_kernel_native_cells import decode_syntax
            expected=source.declarations[-1].value
            self.assertTrue(representation_equal(driver.a,driver.services.whnf(driver.source.target.value),driver.source.declarations[-1].value))
            # Runtime operation under the environment admitted from ORIGINAL
            # source. This additional reduction is not a declaration admission.
            r.update(status=0,reason=0,task=spec.Task.BETA_ZETA,mode=spec.Mode.BETA_ZETA,
                x=state['constants'][r['target_index']][4],ctx=0,count=0,arg_base=0,local_base=0,fuel=cfg.fuel)
            for reduction_step in range(cfg.fuel+2):
                before=canonical(state);nr=state['regs'];frame=state['stack'][nr['sp']-1] if nr['sp'] else [0]*6
                key=None
                if nr['task']==spec.Task.QUOT_REDUCE:key=('ind-reduce',nr['quot_reduce_pc'],nr['mode'])
                elif nr['mode']==spec.Mode.RETURN and frame[3]==spec.Task.QUOT_REDUCE:key=('ind-return',frame[0])
                state=machine.step()
                if key is not None and key not in self.seen:
                    self.seen.add(key);self.checks+=1;self.assertEqual(self.circuit.step(before),state,key)
                if state['regs']['status']:break
            self.assertEqual(state['regs']['status'],spec.Outcome.DONE)
            _,expressions=decode_syntax(SimpleNamespace(heap=state['heap'][:state['regs']['free']]),source.arena)
            self.assertTrue(representation_equal(source.arena,expressions[state['regs']['r']],expected))
            print('source-derived environment Quot.ind runtime + surplus beta DONE',reduction_step+1,'steps',flush=True)
        print(doc['name'],'original-source Quot DONE' ,step+1,'steps',r['free'],'heap',flush=True)


if __name__=='__main__':unittest.main()
