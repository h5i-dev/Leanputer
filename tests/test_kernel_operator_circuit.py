"""AOT source effect lowering checks; no inference host evaluator is provided."""
import unittest
from types import SimpleNamespace


class SourceOperatorCircuitTest(unittest.TestCase):
    def test_word_arithmetic_finite_choice_and_conditional_or_writes(self):
        from leanputer.kernel.control_ir import TypedBuilder
        from leanputer.kernel.control_capture import Effect
        from leanputer.kernel.control_reference import evaluate
        from leanputer.kernel.operator_circuit import SourceOperatorLibrary
        from leanputer.native_machine import NativeBuilder
        from leanputer.native_vendor.qwenputer.ir import ONE,FFN
        names=('a','b','mode','selector')
        g=TypedBuilder([f'{name}/{bit}'for name in names for bit in range(16)])
        w=lambda name:g.node('input',16,data=name)
        const=lambda value:g.const(value,16)
        eq=lambda name,value:g.eq(w(name),const(value))
        table=w('b')
        for value,result in reversed(((0,7),(9,65535),(128,513))):table=g.mux(eq('selector',value),const(result),table)
        first=g.AND(eq('mode',3),g.lt(w('a'),w('b')))
        second=eq('mode',3)
        effects=[Effect('merge_fields',g.pred(first),(('u',g.add(w('a'),w('b')).node),('v',g.sub(w('a'),w('b'))[0].node)),'test',0,'test'),
                 Effect('merge_fields',g.pred(second),(('u',table.node),),'test',0,'test'),
                 Effect('write_heap',g.pred(first),(const(2).node,w('a').node,w('b').node,table.node),'test',0,'test',g.sub(w('a'),const(1))[0].node),
                 Effect('write_heap',g.pred(second),(const(3).node,w('b').node,w('a').node,const(0).node),'test',0,'test',w('b').node)]
        compiler=SimpleNamespace(g=g,layout=SimpleNamespace(fields=[('u',16),('v',16)]),effects=effects,
                                 families=(),preflight_effect_count=0,cfg=SimpleNamespace(heap=512,stack=32,context=8,constants=4,word_bits=16))
        builder=NativeBuilder(intermediate=256,reset_layers=0)
        words=[[builder.feature(f'operand/{i}/{bit}')for bit in range(16)]for i in range(4)]
        code=[builder.feature(f'code/{i}')for i in range(2)]
        library=SourceOperatorLibrary(builder,compiler,[dict(effects=tuple(enumerate(effects)),aliases=set(range(4)))],words,code)
        roles,globals,banks=library.selected_outputs()
        self.assertGreater(library.finite_choices,0)
        cases=[dict(a=0,b=1,mode=3,selector=0),dict(a=65534,b=65535,mode=3,selector=9),
               dict(a=65535,b=0,mode=3,selector=128),dict(a=7,b=7,mode=0,selector=65535)]
        for inputs in cases:
            values={ONE:1}
            for bit,feature in enumerate(code):values[next(iter(feature.terms))]=0
            for index,name in enumerate(library.inputs[0]):
                for bit,feature in enumerate(words[index]):values[next(iter(feature.terms))]=inputs[name]>>bit&1
            def expr(value):return sum(coefficient*values[d]for d,coefficient in value.terms.items())
            for node in sorted(library.graph.nodes,key=lambda n:n.level):
                self.assertIsInstance(node,FFN)
                values[node.out]=sum(coefficient*expr(a)*max(0,expr(b))for coefficient,a,b in node.terms)
            read=lambda bits:sum(int(expr(value))<<i for i,value in enumerate(bits))
            get=evaluate(g,None,inputs);merged={};row=[0]*4;address=0;written=False
            for effect in effects:
                if not get(effect.guard):continue
                if effect.kind=='merge_fields':
                    for name,node in effect.values:merged[name]=merged.get(name,0)|get(node)
                else:
                    written=True;address|=get(effect.address);row=[a|get(b)for a,b in zip(row,effect.values)]
            for mask,destination,word in roles:
                name=compiler.layout.fields[read(destination)][0]
                if expr(mask):self.assertEqual(read(word),merged[name])
                else:self.assertEqual(read(word),0)
            mask,where,actual=banks['heap']
            self.assertEqual(bool(expr(mask)),written)
            self.assertEqual(read(where),address)
            self.assertEqual([read(word)for word in actual],row)
