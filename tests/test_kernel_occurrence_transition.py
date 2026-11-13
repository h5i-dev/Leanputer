"""Internal occurrence returns to its caller; every Expr child rule is shared."""
import unittest
from leanputer.kernel import occurrence_transition as program,traversal_machine as spec
from leanputer.kernel.arena import Arena,Tag,LevelTag
from leanputer.kernel.operations import has_constant
from tests.test_kernel_traversal_machine import CircuitHarness


def cases():
    a=Arena();u=a.level(LevelTag.PARAM,12);sort_=a.mk(Tag.SORT,u)
    missing=a.const(13,(u,));match=a.const(12,())
    v=a.mk(Tag.BVAR,0);local=a.mk(Tag.LOCAL,22)
    n=a.mk(Tag.NAT,a.vec((12,1)));s=a.mk(Tag.STRING,a.vec((12,13)))
    roots=[
        a.mk(Tag.APP,a.mk(Tag.LAM,sort_,match),missing),
        a.mk(Tag.LET,sort_,missing,a.mk(Tag.APP,v,match)),
        a.mk(Tag.PI,missing,a.mk(Tag.LAM,sort_,a.mk(Tag.MDATA,match))),
        a.mk(Tag.PROJ,12,0,missing), # Proj name/level Param are not Const occurrences.
        a.mk(Tag.APP,a.mk(Tag.APP,local,n),a.mk(Tag.APP,s,sort_)),
        a.mk(Tag.APP,missing,match),match,missing]
    docs=[spec.document(a,root,spec.Task.OCCURS,operands=(13,12) if i==6 else (12,)) for i,root in enumerate(roots)]
    docs[0]['argument_prefix']=[13,77]
    docs.append(spec.document(a,roots[0],spec.Task.OCCURS,operands=()))
    for i,d in enumerate(docs):d['name']='internal-occurrence-'+str(i)
    return docs


class InternalOccurrenceTest(unittest.TestCase):
    def test_early_match_returns_and_preserves_all_caller_context(self):
        cfg=spec.MachineConfig(heap=64,stack=16,context=8,constants=2,fuel=256,word_bits=8)
        circuit=CircuitHarness(cfg)
        for doc in cases():
            request,prefix,decls=program.parse_document(doc)
            state=program.prepare(cfg,request,prefix,decls)
            original_context=[row[:] for row in state['context']]
            free=state['regs']['free'];base=state['regs']['arg_base'];count=state['regs']['count']
            machine=spec.SpecMachine(cfg,state)
            callbacks=0;early_match=False
            for step in range(cfg.fuel+2):
                r=state['regs']
                if r['mode']==spec.Mode.RETURN and r['sp'] and state['stack'][r['sp']-1][0]==spec.CALL_OCCURRENCE_FINISH:
                    callbacks+=1;self.assertEqual(r['status'],spec.Outcome.RUNNING)
                    early_match|=bool(r['occurrence_found'])
                actual=circuit.step(state)
                self.assertEqual(actual,machine.step(),(doc['name'],step))
                state=actual
                if state['regs']['status']:break
            r=state['regs'];want=has_constant(request['arena'],request['root'],request['operands'])
            self.assertEqual((r['status'],r['reason'],r['r']),(spec.Outcome.DONE,spec.Reason.NONE,int(want)),doc['name'])
            self.assertEqual(callbacks,int(bool(count)),doc['name'])
            self.assertEqual(early_match,want)
            self.assertEqual((r['occurrence_internal'],r['sp'],r['found']),(0,0,0))
            self.assertEqual((r['arg_base'],r['count'],r['ctx'],r['free']),(base,count,len(prefix)+count,free))
            self.assertEqual(state['context'],original_context)
            self.assertEqual(circuit.step(state),state)


if __name__=='__main__':unittest.main()
