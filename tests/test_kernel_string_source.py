"""Original-source String primitives with general Char/List/String layouts."""
import json
from pathlib import Path
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from tests.test_kernel_nat_literal_source import document as nat_document
from tests.test_kernel_quotient_source import name,const,pi,lam,app,raw
from tests.test_kernel_traversal_machine import CircuitHarness
from tests.test_kernel_source_nested_transaction import assert_public_matches_independent,canonical


TEXT='A\0λ𐐷'


def source_document(fields=1,mode='projection',text=TEXT):
    zero=['zero'];one=['succ',zero];two=['succ',one];u=['param',name('listUniverse')]
    prop=('sort',zero);type0=('sort',one);nat=const('Nat');char=const('Char');string=const('String')
    listchar=app(const('List',zero),char)
    eq=json.loads(Path('tests/fixtures/kernel-source-smoke.jsonl').read_text().splitlines()[2])['declarations'][0]
    def block(symbol,ty,ctors,params=0,levels=[]):
        return dict(kind='inductive_block',level_params=levels,parameters=params,recursor_claims=[],families=[dict(
            name=name(symbol),recursor_name=name(symbol+'.rec'),type=raw(ty),constructors=[dict(name=name(n),type=raw(t))for n,t in ctors])])
    lu=app(const('List',u),'a');su=('sort',['succ',u])
    lists=block('List',pi('a',su,su),[
        ('List.nil',pi('a',su,lu)),('List.cons',pi('a',su,pi('x','a',pi('xs',lu,lu)))),
        ('arbitraryExtraListConstructor',pi('a',su,lu))],1,[name('listUniverse')])
    characters=block('Char',type0,[('arbitraryCharacterStorage',pi('n',nat,char))])
    ofnat=dict(kind='definition',name=name('Char.ofNat'),level_params=[],type=raw(pi('n',nat,char)),value=raw(const('arbitraryCharacterStorage')))
    ctor=pi('l',listchar,string)
    body=const('arbitraryStringStorage')
    if fields==3:
        relation=app(const('Eq',one),nat,'n','n')
        ctor=pi('l',listchar,pi('n',nat,pi('proof',relation,string)))
        body=lam('l',listchar,app(const('arbitraryStringStorage'),'l',const('Nat.zero'),app(const('Eq.refl',one),nat,const('Nat.zero'))))
    strings=block('String',type0,[('arbitraryStringStorage',ctor)])
    oflist=dict(kind='opaque'if mode=='opaque'else'definition',name=name('String.ofList'),level_params=[],type=raw(pi('l',listchar,string)),value=raw(body))
    decls=[nat_document('0')['declarations'][0],eq,lists,characters,ofnat,strings,oflist]
    expected_list=app(const('List.nil',zero),char)
    for c in reversed(text):expected_list=app(const('List.cons',zero),char,app(const('Char.ofNat'),('nat',str(ord(c)))),expected_list)
    literal=('string',text)
    if mode=='recursor':
        minor=lam('l',listchar,prop)
        if fields==3:minor=lam('l',listchar,lam('n',nat,lam('proof',app(const('Eq',one),nat,'n','n'),prop)))
        ty=app(const('String.rec',two),lam('s',string,type0),minor,literal)
        value=pi('P',prop,pi('h','P','P'));kind='definition'
    elif mode=='opaque':
        expr=app(const('String.ofList'),expected_list)
        ty=app(const('Eq',one),string,literal,expr);value=app(const('Eq.refl',one),string,expr);kind='theorem'
    else:
        index=1 if fields==3 else 0
        result_type=nat if fields==3 else listchar
        expected=('nat','0')if fields==3 else expected_list
        projection=('proj',name('String'),index,raw(literal))
        ty=app(const('Eq',one),result_type,projection,expected);value=app(const('Eq.refl',one),result_type,expected);kind='theorem'
    return dict(format='leanputer.kernel-source.v1',status='EXPORTED',name=f'source-String-{fields}-{mode}',declarations=decls,
        target=dict(kind=kind,name=name('arbitraryStringProof'),level_params=[],type=raw(ty),value=raw(value)))


class StringSourceTest(unittest.TestCase):
    def test_literal_type_and_helper_bootstrap_use_only_checked_String(self):
        circuit=None;seen=set();checks=0
        for bootstrap in (False,True):
            doc=source_document()
            if bootstrap:
                lc=app(const('List',['zero']),const('Char'))
                doc['declarations'][-1]['value']=raw(lam('xs',lc,('string',TEXT)))
            else:
                doc['declarations']=[dict(kind='inductive_block',level_params=[],parameters=0,recursor_claims=[],families=[dict(
                    name=name('String'),recursor_name=name('String.rec'),type=raw(('sort',['succ',['zero']])),constructors=[])])]
            doc['target']=dict(kind='definition',name=name('literalBeforeHelperClosure'),level_params=[],type=raw(const('String')),value=raw(('string',TEXT)))
            source,args,decls=program.parse_document(doc);driver=EnvironmentDriver(source);oracle=driver.check()
            self.assertEqual(oracle.status,'ACCEPT',(bootstrap,oracle))
            cfg=spec.MachineConfig(heap=8192,stack=256,context=128,constants=8,fuel=500000,word_bits=16)
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
            if circuit is None:circuit=CircuitHarness(cfg)
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1]if r['sp']else[0]*6;key=None
                if r['task']==spec.Task.STRING_BINDINGS:key=('type',r['string_binding_pc'],r['string_type_validated'])
                elif r['mode']==spec.Mode.RETURN and frame[3]==spec.Task.STRING_BINDINGS:key=('return',frame[0],frame[1])
                before=canonical(state)if key is not None and key not in seen else None
                state=machine.step();r=state['regs']
                if before is not None:
                    self.assertEqual(circuit.step(before),state,(bootstrap,step,key));seen.add(key);checks+=1
                if r['status']:break
            self.assertEqual((r['status'],r['reason'],r['string_type_validated'],r['string_validated']),(spec.Outcome.DONE,0,1,0))
            assert_public_matches_independent(self,state,driver);self.assertEqual(oracle.assumptions,())
            print('String original-source typing/helper-bootstrap',bootstrap,'DONE',step+1,'steps',r['free'],'heap',flush=True)
        print('String type/bootstrap selected Boolean transitions',checks,flush=True)

    def test_explicit_missing_mismatched_helper_and_resource_boundaries(self):
        for kind in ('missing','mismatched','negative-bytes','narrow-word'):
            doc=source_document(mode='recursor'if kind=='mismatched'else'projection');cfg=spec.MachineConfig(heap=32768,stack=256,context=128,constants=8,fuel=500000,word_bits=16)
            if kind=='missing':doc['declarations'].pop()
            elif kind=='mismatched':
                nt=const('Nat');doc['declarations'][4].update(type=raw(pi('n',nt,nt)),value=raw(lam('n',nt,'n')))
            elif kind=='negative-bytes':
                one=['succ',['zero']];st=const('String')
                doc['target'].update(type=raw(app(const('Eq',one),st,('string','λ'),('string','Λ'))),value=raw(app(const('Eq.refl',one),st,('string','Λ'))))
            else:cfg=spec.MachineConfig(heap=8192,stack=256,context=128,constants=8,fuel=500000,word_bits=14)
            if kind!='narrow-word':
                source,args,decls=program.parse_document(doc);oracle=EnvironmentDriver(source).check()
                self.assertEqual(oracle.status,'REJECT'if kind=='negative-bytes'else'GAP',(kind,oracle))
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs'];prior={k:int(v)for k,v in r.items()};machine.step()
                if r['status']:break
            expected=spec.Outcome.INVALID if kind=='negative-bytes'else spec.Outcome.RESOURCE if kind=='narrow-word'else spec.Outcome.GAP
            self.assertEqual(r['status'],expected,(kind,r['reason']))
            if kind=='narrow-word':self.assertEqual(r['reason'],spec.Reason.INDEX)
            self.assertEqual(r['published_declarations'],19 if kind=='missing' else 20)
            print('String boundary',kind,spec.Outcome(r['status']).name,spec.Reason(r['reason']).name,flush=True)
        from leanputer.kernel.arena import KernelError
        doc=source_document(text='\ud800')
        with self.assertRaisesRegex(KernelError,'Unicode'):program.parse_document(doc)

    def test_original_source_unicode_projection_recursor_and_opaque_extension(self):
        circuit=None;seen=set();checks=0
        for fields,mode,text in [(1,'projection',TEXT),(3,'projection',TEXT),(1,'recursor',TEXT),(3,'recursor',TEXT),(1,'opaque',TEXT),(1,'projection',''),(1,'projection',''.join(map(chr,(0x7f,0x80,0x7ff,0x800,0xd7ff,0xe000,0xffff,0x10000,0x10ffff))))]:
            doc=source_document(fields,mode,text);source,args,decls=program.parse_document(doc);driver=EnvironmentDriver(source);oracle=driver.check()
            self.assertEqual(oracle.status,'ACCEPT',(doc['name'],oracle))
            cfg=spec.MachineConfig(heap=32768,stack=256,context=128,constants=8,fuel=500000,word_bits=16)
            source,args,decls=program.parse_document(doc);machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls))
            if circuit is None:circuit=CircuitHarness(cfg)
            for step in range(cfg.fuel+2):
                state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1]if r['sp']else[0]*6;key=None
                owners={spec.Task.STRING_BINDINGS,spec.Task.STRING_LITERAL,spec.Task.STRING_WHNF,spec.Task.STRING_COMPARE}
                if r['mode']==spec.Mode.RETURN and frame[3]in owners:key=('return',int(frame[3]),frame[0],frame[1],bool(r['r']))
                elif r['task']==spec.Task.STRING_BINDINGS:key=('binding',r['string_binding_pc'],r['string_validated'],r['string_type_validated'])
                elif r['task']==spec.Task.STRING_LITERAL:
                    node=state['heap'][r['x']]if r['x']<cfg.heap else[0]*4
                    key=('literal',r['string_pc'],r['string_operation'],r['string_total'],r['string_needed']==1,bool(r['string_code_high']),bool(r['string_code_low']),bool(r['string_remaining']),bool(r['string_characters']),node[1] if r['string_pc']in(4,6)else 0)
                elif r['task']==spec.Task.STRING_WHNF:key=('whnf',r['string_whnf_pc'],frame[2],int(frame[3]))
                elif r['task']==spec.Task.STRING_COMPARE:key=('compare',r['string_compare_pc'],bool(r['r']))
                before=canonical(state)if key is not None and key not in seen else None
                state=machine.step();r=state['regs']
                if before is not None:
                    actual=circuit.step(before);seen.add(key);checks+=1
                    if actual!=state:
                        diff={k:(actual['regs'][k],int(r[k]))for k in spec.REGISTERS if actual['regs'][k]!=r[k]}
                        self.fail(str((doc['name'],step,key,diff)))
                if r['status']:break
            self.assertEqual((r['status'],r['reason']),(spec.Outcome.DONE,0),
                (doc['name'],step,{k:r[k]for k in('status','reason','task','mode','string_binding_pc','string_pc','string_whnf_pc','string_compare_pc','x','free','sp')}))
            self.assertEqual(oracle.assumptions,());assert_public_matches_independent(self,state,driver)
            print('String source',doc['name'],'DONE',step+1,'steps',r['free'],'heap',flush=True)
        print('String selected Boolean transitions',checks,flush=True)


if __name__=='__main__':unittest.main()
