"""Focused projection soundness checks; no model or proof-specific program."""
import unittest
from types import SimpleNamespace


class SemanticProjectionTest(unittest.TestCase):
    def test_unknown_negation_and_root_caller_return_preserve_effects(self):
        from leanputer.kernel.control_ir import TypedBuilder
        from leanputer.kernel.control_capture import Effect
        from leanputer.kernel.control_reference import evaluate
        from leanputer.kernel.semantic_phases import SemanticPhases
        from leanputer.kernel.traversal_machine import Mode
        names=('mode','task','sp','test_pc','data','read/frame/task','read/frame/phase')
        g=TypedBuilder([f'{name}/{bit}'for name in names for bit in range(16)])
        word=lambda name:g.node('input',16,data=name)
        eq=lambda name,value:g.eq(word(name),g.const(value,16))
        empty=eq('sp',0);zero=eq('data',0)
        guards=[g.AND(eq('mode',int(Mode.WALK)),eq('task',0),eq('test_pc',1),g.NOT(zero)),
                g.AND(eq('mode',int(Mode.RETURN)),g.NOT(empty),eq('read/frame/task',1),eq('read/frame/phase',2)),
                g.AND(eq('mode',int(Mode.RETURN)),empty),
                g.NOT(g.eq(g.add(word('test_pc'),g.const(1,16)),g.const(3,16))),
                g.NOT(g.AND(eq('task',0),zero))]
        effects=[Effect('merge_fields',g.pred(guard),(),__file__,0,'test')for guard in guards]
        variables={i:n.data for i,n in enumerate(g.nodes)if n.op=='input'and n.data not in('sp','data')}
        domains={i:(0,65535)for i in variables}
        compiler=SimpleNamespace(g=g,effects=effects)
        contract=SimpleNamespace(variables=variables,contract_domains=domains,body=tuple(enumerate(effects)),prefix=(),fallback=())
        program=SemanticPhases(compiler,contract)
        cases=[(0,0,0,0,0,0,0),(0,0,1,1,1,0,0),(0,1,2,2,0,1,2),
               (1,0,0,65535,1,1,2),(1,1,32,1,0,1,2),(1,0,1,2,1,0,65535)]
        for values in cases:
            inputs=dict(zip(names,values));node=program.root
            while node[0]=='switch':
                variable,cases=program.switches[node[1]]
                value=int(inputs['sp']==0)if variable==program.stack_empty else inputs[program.variables[variable]]
                node=next(child for low,high,child in cases if low<=value<=high)
            possible=set(program.regions[node[1]])
            get=evaluate(g,None,inputs)
            actual={index for index,effect in enumerate(effects)if get(effect.guard)}
            self.assertTrue(actual<=possible,(inputs,actual,possible))
