"""Generic telescope rules: source-defined loops, counts are data."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from leanputer.kernel import reuse_transition as program,traversal_machine as spec
from leanputer.kernel.arena import LocalContext
from leanputer.kernel.operations import abstract,representation_equal
from leanputer.kernel.services import KernelServices
from leanputer.kernel.telescope import open_telescope,consume_parameters
from tests.test_kernel_source_transition import name,raw,source
from tests.test_kernel_traversal_machine import CircuitHarness
from tests.test_kernel_native_cells import decode_syntax


def cases():
    u=['param',name('u')]
    domains=[['sort',['succ',u]],['var',0],['pi',0,['var',1],['sort',['zero']]],['app',['var',0],['var',1]]]
    full=['sort',u]
    for domain in reversed(domains):full=['pi',0,domain,full]
    def doc(label,count,candidate,normalize=True):
        return dict(format='leanputer.kernel-telescope-reuse.v1',name=label,parameters=count,normalize=normalize,
            source=source(label,[],raw('definition','raw',full,candidate,[name('u')])))
    docs=[doc('prefix-'+str(n),n,full) for n in (0,1,2,4)]
    docs.append(doc('raw-constructor-prefix',3,full,False))
    docs.append(doc('metadata-whnf-prefix',3,['mdata',full]))
    bad=deepcopy(full);bad[2]=['sort',['zero']]
    docs.append(doc('different-sort-domain',1,bad))
    docs.append(doc('short-candidate',2,['sort',u]))
    docs.append(doc('raw-free-local-rejected',1,['pi',0,['local',12],['sort',u]]))
    docs.append(doc('parameter-prefix-too-long',5,full))
    docs.append(doc('physical-context-overflow',8,full))
    return docs


class TelescopeReuseTest(unittest.TestCase):
    def test_general_dependent_parameter_reuse_and_whnf(self):
        cfg=spec.MachineConfig(heap=256,stack=16,context=8,constants=2,fuel=1024,word_bits=9)
        circuit=CircuitHarness(cfg)
        expected=[('DONE','NONE')]*6+[
            ('INVALID','TYPE_MISMATCH'),('INVALID','EXPECT_PI'),('INVALID','SCOPE'),
            ('INVALID','EXPECT_PI'),('RESOURCE','CONTEXT')]
        for doc,want in zip(cases(),expected):
            source,args,decls=program.parse_document(doc)
            state=program.prepare(cfg,source,args,decls)
            self.assertEqual((state['regs']['ctx'],state['regs']['count']),(0,0))
            machine=spec.SpecMachine(cfg,state)
            for step in range(cfg.fuel+2):
                actual=circuit.step(state)
                self.assertEqual(actual,machine.step(),(doc['name'],step))
                state=actual
                if state['regs']['status']:break
            r=state['regs']
            self.assertEqual((spec.Outcome(r['status']).name,spec.Reason(r['reason']).name),want,(doc['name'],r))
            if want[0]=='DONE':
                # Independently run source operation; compare outputs after
                # abstracting the distinct fresh-Local namespaces. Posthoc only.
                a=source.arena;c=LocalContext(a);services=KernelServices(a,c)
                params=open_telescope(a,c,source.target.type,services.whnf,count=args[0]).locals
                result=consume_parameters(a,c,source.target.value,params,
                    services.whnf if args[1] else lambda x:x,services.convert)
                packed=SimpleNamespace(heap=state['heap'][:r['free']])
                _,decoded=decode_syntax(packed,a)
                locals_=tuple(decoded[state['heap'][state['context'][i][0]][1]] for i in range(r['reuse_base'],r['reuse_end']))
                self.assertTrue(representation_equal(a,abstract(a,result,params),abstract(a,decoded[r['r']],locals_)),doc['name'])
                self.assertEqual((r['ctx'],r['local_base'],r['sp']),(1+args[0],1,0))
                self.assertEqual(r['decl'],0)
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
