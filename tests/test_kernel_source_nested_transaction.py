"""Original-source nested transaction; semantic and selected Boolean evidence.

No fixture ABI entry, no input checked metadata, no host admission at inference.
The independent executable EnvironmentDriver is a development oracle only.
"""
from copy import deepcopy
from pathlib import Path
import json
import time
import unittest
from leanputer.kernel import source_transition as program,traversal_machine as spec
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.native_cells import CellTag
from tests.test_kernel_traversal_machine import CircuitHarness


FIXTURE=Path('tests/fixtures/kernel-nested-source.jsonl')
NEW_TASKS={spec.Task.NESTED_STAGE:'stage_pc',spec.Task.REPLACE_NESTED:'copy_pc',spec.Task.REWRITE_NESTED:'rewrite_pc',
    spec.Task.RESTORE_NESTED_EXPR:'restore_expr_pc',spec.Task.RESTORE_NESTED_CALLBACK:'restore_cb_pc',spec.Task.RESTORE_NESTED_BLOCK:'publish_pc'}


def canonical(state):
    return {'regs':{k:int(v) for k,v in state['regs'].items()},
        **{bank:[[int(v) for v in row] for row in state[bank]] for bank in spec.BANK_FIELDS}}


def linked(state,head,tag=CellTag.VECTOR_CELL):
    result=[]
    while head:
        row=state['heap'][head]
        if row[0]!=tag:raise AssertionError((head,row))
        result.append(row[1]);head=row[2]
    return result


class SourceNestedTransactionTest(unittest.TestCase):
    def test_original_source_complete_transaction_and_selected_boolean_transitions(self):
        doc=json.loads(FIXTURE.read_text());source,args,decls=program.parse_document(doc)
        driver=EnvironmentDriver(source);oracle=driver.check();self.assertEqual(oracle.status,'ACCEPT');self.assertEqual(oracle.admitted_declarations,12)
        # Reparse raw source: independent SPEC mutations never enter native input.
        source,args,decls=program.parse_document(doc)
        cfg=spec.MachineConfig(heap=32768,stack=128,context=128,constants=4,fuel=500000,word_bits=16)
        machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls));circuit=CircuitHarness(cfg)
        seen=set();checked=0;start=time.monotonic();committed=[]
        for step in range(cfg.fuel+2):
            state=machine.state;r=state['regs'];frame=state['stack'][r['sp']-1] if r['sp'] else [0]*6
            key=None
            if r['task'] in NEW_TASKS and r['mode']==spec.Mode.WALK:
                node=state['heap'][r['x']] if 0<=r['x']<cfg.heap else [0]*4
                key=(int(r['task']),r[NEW_TASKS[r['task']]],node[0],bool(node[1]),bool(node[2]),bool(r['r']))
            elif r['mode']==spec.Mode.RETURN and frame[3] in NEW_TASKS:
                key=('return',int(frame[3]),frame[0],frame[1] if frame[3]!=spec.Task.REWRITE_NESTED else 0,bool(r['r']))
            elif r['mode']==spec.Mode.RETURN and frame[3]==spec.Task.CHECK_SOURCE and frame[0] in (0,14):
                key=('source',frame[0])
            before=canonical(state) if key is not None and key not in seen else None
            old_index=r['raw_index'];expected=machine.step()
            if before is not None:
                actual=circuit.step(before);checked+=1;seen.add(key)
                if actual!=expected:
                    differences={k:(actual['regs'][k],int(expected['regs'][k])) for k in spec.REGISTERS if actual['regs'][k]!=expected['regs'][k]}
                    self.fail(str((step,key,differences)))
            if expected['regs']['raw_index']!=old_index:committed.append(expected['regs']['raw_index'])
            if expected['regs']['status']:break
        state=machine.state;r=state['regs']
        self.assertEqual((r['status'],r['reason'],r['raw_index'],r['decl']),(spec.Outcome.DONE,0,2,2))
        self.assertEqual(committed,[1,2]);self.assertEqual((r['typing_active'],r['ctx'],r['sp']),(0,0,0))
        signatures=linked(state,r['env_head']);self.assertEqual(len(signatures),12)
        self.assertEqual((r['published_declarations'],program.admitted_declarations_from_state(r)),(12,12))
        origins=linked(state,r['nested_registry_head']);self.assertEqual(len(origins),2)
        self.assertEqual([state['heap'][ref][1] for ref in origins],[state['constants'][1][5],state['constants'][0][5]])
        # Every exposed family/constructor retains its original symbol; auxiliaries
        # are eliminated, while generated auxiliary recursors remain public.
        public_symbols={state['heap'][sig][1] for sig in signatures}
        auxiliary=set();head=r['stage_maps']
        while head:
            _,_,symbol,head=state['heap'][head];auxiliary.add(symbol)
        self.assertFalse(auxiliary & public_symbols)
        self.assertGreater(len(auxiliary),0)
        assert_public_matches_independent(self,state,driver)
        print('original source ACCEPT; steps',step+1,'heap',r['free'],'public signatures',len(signatures),
            'origins',len(origins),'selected Boolean transitions',checked,'seconds',time.monotonic()-start,flush=True)

    def test_bad_second_claim_and_heap_exhaustion_preserve_committed_prefix(self):
        for bad_claim,heap in ((True,32768),(False,8192)):
            with self.subTest(bad_claim=bad_claim,heap=heap):
                doc=json.loads(FIXTURE.read_text())
                if bad_claim:doc['declarations'][1]['recursor_claims'][0]['name']=[{'str':'unknown_restored_recursor'}]
                source,args,decls=program.parse_document(doc)
                cfg=spec.MachineConfig(heap=heap,stack=128,context=128,constants=4,fuel=500000,word_bits=16)
                machine=spec.SpecMachine(cfg,program.prepare(cfg,source,args,decls));prefix=None
                for step in range(cfg.fuel+2):
                    machine.step();r=machine.state['regs']
                    if r['raw_index']==1 and prefix is None:prefix=(r['env_head'],r['nested_registry_head'])
                    if r['status']:break
                self.assertIsNotNone(prefix)
                self.assertEqual((r['env_head'],r['nested_registry_head']),prefix)
                self.assertEqual((r['raw_index'],r['decl']),(1,1))
                self.assertEqual(r['status'],spec.Outcome.INVALID if bad_claim else spec.Outcome.RESOURCE)
                self.assertEqual(r['reason'],spec.Reason.UNKNOWN_CONSTANT if bad_claim else spec.Reason.HEAP)
                self.assertEqual(len(linked(machine.state,r['env_head'])),7)
                self.assertEqual(r['published_declarations'],7)
                self.assertEqual(len(linked(machine.state,r['nested_registry_head'])),1)


def assert_public_matches_independent(test,state,driver):
    """Decode outputs for tests only; compare public schemes and every recursor RHS."""
    from types import SimpleNamespace
    from leanputer.kernel.arena import Tag,LevelTag
    from leanputer.kernel.operations import representation_equal,substitute_levels,transform
    from leanputer.kernel.native_cells import VectorKind
    from tests.test_kernel_native_cells import vector,decode_syntax
    packed=SimpleNamespace(heap=state['heap'][:state['regs']['free']]);a=driver.a
    _,expressions=decode_syntax(packed,a);symbols={}
    for ref in vector(packed,state['regs']['symbols_root'],VectorKind.REFERENCES):
        _,symbol,path,_=packed.heap[ref];parts=[]
        for ref in vector(packed,path,VectorKind.REFERENCES):
            tag,payload,_,_=packed.heap[ref]
            if tag==CellTag.NAME_STRING:parts.append(('str',bytes(vector(packed,payload,VectorKind.BYTES)).decode('utf-8')))
            else:parts.append(('num',sum(limb<<(16*i) for i,limb in enumerate(vector(packed,payload,VectorKind.LIMBS)))))
        symbols[symbol]=driver.symbols.intern_key(tuple(parts))
    def expression(ref,parameters,expected_parameters):
        substitution={symbol:a.level(LevelTag.PARAM,peer) for symbol,peer in zip(parameters,expected_parameters)}
        root=substitute_levels(a,expressions[ref],substitution)
        def rename(ref,depth):
            row=a.expr(ref)
            if row.tag==Tag.CONST:return a.const(symbols[row.a],a.vector(row.b))
            return None
        return transform(a,root,rename)
    found=set()
    for sig in linked(state,state['regs']['env_head']):
        _,symbol,type_ref,scheme=packed.heap[sig];symbol=symbols[symbol]
        # Γ is a persistent map: latest entry shadows a historical signature.
        if symbol in found:continue
        found.add(symbol)
        _,parameters,kind,payload=packed.heap[scheme];parameters=vector(packed,parameters,VectorKind.SYMBOLS)
        expected=driver.services.constants[symbol]
        test.assertEqual(len(parameters),len(expected.universe_parameters))
        test.assertTrue(representation_equal(a,expression(type_ref,parameters,expected.universe_parameters),expected.type),driver.symbols.names[symbol])
        if kind==10:
            record=driver.services.recursors[symbol];rules=vector(packed,packed.heap[payload][3],VectorKind.REFERENCES)
            test.assertEqual(len(rules),len(record.rules))
            for ref,rule in zip(rules,record.rules):
                _,ctor,fields,rhs=packed.heap[ref]
                test.assertEqual((symbols[ctor],fields),(rule.constructor,rule.fields))
                test.assertTrue(representation_equal(a,expression(rhs,parameters,expected.universe_parameters),rule.rhs),driver.symbols.names[symbol])
    test.assertEqual(found,set(driver.services.constants))


if __name__=='__main__':unittest.main()
