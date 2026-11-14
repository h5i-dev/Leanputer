"""Untrusted claim-name/scope/type validation and declaration-as-data boundary."""
from copy import deepcopy
import unittest
from leanputer.kernel import core_transition as program,traversal_machine as spec
from leanputer.kernel.admission import analyze_core
from leanputer.kernel.arena import LevelTag,KernelError
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.recursor import Constructor,Inductive
from tests.test_kernel_constructor_transition import native_cases,core
from tests.test_kernel_source_transition import name
from tests.test_kernel_traversal_machine import CircuitHarness


def mutual_claims():
    prop=['sort',['zero']];f=['const',name('F'),[]];g=['const',name('G'),[]]
    families=[dict(name=name(s),recursor_name=name(s)+[{'str':'rec'}],type=prop,constructors=[]) for s in ('F','G')]
    types=[['pi',0,['pi',0,f,prop],['pi',0,['pi',0,g,prop],['pi',0,major,['app',['var',which],['var',0]]]]]
        for major,which in ((f,2),(g,1))]
    claims=[dict(name=family['recursor_name'],level_params=[],type=type_ref) for family,type_ref in zip(families,types)]
    return core('mutual-claims',dict(kind='inductive_block',level_params=[],parameters=0,families=families,recursor_claims=claims))


def cases():
    good=native_cases()[0];result=[(good,'GAP','GAP_RECURSOR_GENERATION',1)]
    renamed=deepcopy(good);renamed['name']='alpha-universe-claim';claim=renamed['block']['recursor_claims'][0]
    original=claim['level_params'][0];replacement=name('v');claim['level_params'][0]=replacement
    pending=[claim['type']]
    while pending:
        node=pending.pop()
        if isinstance(node,list):
            if len(node)==2 and node[0]=='param' and node[1]==original:node[1]=replacement
            else:pending.extend(node)
    result.append((renamed,'GAP','GAP_RECURSOR_GENERATION',1))
    mutual=mutual_claims();result.append((mutual,'GAP','GAP_RECURSOR_GENERATION',2))
    bad=deepcopy(good);bad['name']='unknown-claim';bad['block']['recursor_claims'][0]['name']=name('foreign')
    result.append((bad,'INVALID','UNKNOWN_CONSTANT',0))
    bad=deepcopy(good);bad['name']='wrong-claim-universe-arity';bad['block']['recursor_claims'][0]['level_params'].pop(0)
    result.append((bad,'INVALID','UNIVERSE_ARITY',0))
    bad=deepcopy(good);bad['name']='duplicate-claim-parameters';ps=bad['block']['recursor_claims'][0]['level_params'];ps[0]=deepcopy(ps[1])
    result.append((bad,'INVALID','DUPLICATE_PARAMETER',0))
    bad=deepcopy(good);bad['name']='unscoped-claim-body';bad['block']['recursor_claims'][0]['type']=['var',0]
    result.append((bad,'INVALID','SCOPE',0))
    bad=deepcopy(mutual);bad['name']='duplicate-claim-names';bad['block']['recursor_claims'][1]=deepcopy(bad['block']['recursor_claims'][0])
    result.append((bad,'INVALID','DUPLICATE_DECLARATION',1))
    bad=deepcopy(good);bad['name']='wrong-claim-cannot-supply-a-type';bad['block']['recursor_claims'][0]['type']=['sort',['zero']]
    # General negative conversion performs typed inference; the historical
    # 16-frame bound exhausts its stack before the negative answer.
    result.append((bad,'RESOURCE','STACK',0))
    return result


class RecursorClaimTransitionTest(unittest.TestCase):
    def test_claims_are_inferred_renamed_compared_and_never_trusted_as_types(self):
        cfg=spec.MachineConfig(heap=512,stack=16,context=8,constants=2,fuel=8192,word_bits=10)
        circuit=CircuitHarness(cfg)
        for doc,status,reason,checked in cases():
            with self.subTest(label=doc['name']):
                source,args,decls=program.parse_document(doc);state=program.prepare(cfg,source,args,decls);machine=spec.SpecMachine(cfg,state);prefix=None
                for step in range(cfg.fuel+2):
                    r=state['regs']
                    if r['task']==spec.Task.CHECK_RECURSOR_CLAIMS and r['mode']==spec.Mode.WALK:prefix=deepcopy(state)
                    if prefix is not None:
                        actual=circuit.step(state);self.assertEqual(actual,machine.step(),(doc['name'],step));state=actual
                    else:
                        ref=machine.step();state={'regs':{k:int(v) for k,v in ref['regs'].items()},
                            **{bank:[[int(v) for v in row] for row in ref[bank]] for bank in spec.BANK_FIELDS}}
                    if state['regs']['status']:break
                self.assertIsNotNone(prefix);r=state['regs']
                self.assertEqual((spec.Outcome(r['status']).name,spec.Reason(r['reason']).name,r['claim_checked']),(status,reason,checked))
                self.assertEqual((r['env_head'],r['decl'],r['raw_index']),(0,0,0))
                self.assertEqual(r['typing_head'],prefix['regs']['typing_head'])
                if reason=='GAP_RECURSOR_GENERATION':self.assertEqual((r['ctx'],r['local_base'],r['count']),(r['claim_expected_uparams'],)*3)
                if status=='INVALID':
                    # Independent core algorithm rejects the same raw assertion;
                    # it never receives an inferred type from the native state.
                    driver=EnvironmentDriver(source);a=driver.a;block=decls[-1]
                    levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters)
                    inds=tuple(Inductive(a.const(f.symbol,levels),f.type,tuple(Constructor(ct.symbol,ct.type) for ct in f.constructors),f.recursor_symbol) for f in block.families)
                    with self.assertRaises(KernelError):analyze_core(driver.services,inds,block.universe_parameters,block.parameters,r['elim_fresh'] or len(driver.symbols.names)+1,block.recursor_claims)
                self.assertEqual(circuit.step(state),state)

    def test_negative_claim_at_adequate_physical_bounds(self):
        from tests.test_kernel_source_nested_transaction import canonical
        cfg=spec.MachineConfig(heap=4096,stack=64,context=32,constants=2,fuel=65536,word_bits=13)
        document=cases()[-1][0];source,args,decls=program.parse_document(document)
        machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls));circuit=CircuitHarness(cfg)
        seen=set()
        for step in range(cfg.fuel+2):
            state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1] if r['sp'] else [0]*6;key=None
            if r['task']==spec.Task.CONVERT:
                key=(int(r['mode']),r['convert_pc'],state['heap'][r['x']][0] if r['x']<cfg.heap else 0)
            elif r['mode']==spec.Mode.RETURN and frame[3]==spec.Task.CONVERT:key=('return',frame[0],bool(r['r']))
            before=canonical(state) if key is not None and key not in seen else None
            expected=machine.step()
            if before is not None:
                self.assertEqual(circuit.step(before),expected,(step,key));seen.add(key)
            if expected['regs']['status']:break
        r=machine.state['regs']
        self.assertEqual((r['status'],r['reason']),(spec.Outcome.INVALID,spec.Reason.TYPE_MISMATCH))
        self.assertEqual((r['env_head'],r['decl'],r['raw_index']),(0,0,0))
        driver=EnvironmentDriver(source);a=driver.a;block=decls[-1]
        levels=tuple(a.level(LevelTag.PARAM,p) for p in block.universe_parameters)
        inds=tuple(Inductive(a.const(f.symbol,levels),f.type,tuple(Constructor(ct.symbol,ct.type) for ct in f.constructors),f.recursor_symbol) for f in block.families)
        with self.assertRaises(KernelError):
            analyze_core(driver.services,inds,block.universe_parameters,block.parameters,r['elim_fresh'],block.recursor_claims)


if __name__=='__main__':unittest.main()
