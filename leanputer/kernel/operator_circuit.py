"""AOT neural lowering of complete source-operator data effects.

No inference-time gate tape, evaluator, CPU instruction set or host checker is
introduced. Source word DAGs become fixed SwiGLU expressions; source effects
retain their conditional OR-merge semantics. Operand/destination bindings are
compiler data and must be connected to the model-owned source controller/RAM.
"""
from collections import defaultdict
from types import SimpleNamespace
from ..native_vendor.qwenputer.expr import Expr
from .stock_preflight_graph import PreflightCircuit


class SharedExpressionGraph:
    """Compile-time CSE for immutable neural expressions, independent of names."""
    def __init__(self,graph):
        self.base=graph;self.cache={};self.hits=0

    def __getattr__(self,name):return getattr(self.base,name)

    def ffn(self,terms,name='ffn',into=None,min_level=0):
        if into is not None:
            return self.base.ffn(terms,name=name,into=into,min_level=min_level)
        def form(value):return tuple(sorted(value.terms.items()))
        key=(min_level,tuple(sorted((coefficient,form(a),form(b))for coefficient,a,b in terms if coefficient)))
        if key not in self.cache:self.cache[key]=self.base.ffn(terms,name=name,min_level=min_level)
        else:self.hits+=1
        return self.cache[key]


class SourceEffectCircuit(PreflightCircuit):
    """Compile an arbitrary cofactored source region, not declaration shapes."""
    def __init__(self,builder,typed_graph,inputs,parameters=None):
        plan=SimpleNamespace(graph=typed_graph,actives=(),invalid=-1)
        super().__init__(builder,plan,inputs,Expr())
        self.parameters=parameters or {}
        self.finite_choices=0

    def node(self,index,root=False):
        n=self.plan.graph.nodes[index]
        if index in self.nodes:return self.nodes[index]
        if n.op=='choose':
            def finite_test(i):
                node=self.plan.graph.nodes[i]
                if node.op=='eq':
                    for a,b in(node.args,node.args[::-1]):
                        if self.plan.graph.nodes[b].op=='const':return a,(self.plan.graph.nodes[b].data,)
                if node.op=='any':
                    pieces=[finite_test(child)for child in node.args]
                    if pieces and all(piece and piece[0]==pieces[0][0]for piece in pieces):
                        return pieces[0][0],tuple(sorted({value for piece in pieces for value in piece[1]}))
                return None
            chain={};cursor=index;variable=None
            while self.plan.graph.nodes[cursor].op=='choose':
                node=self.plan.graph.nodes[cursor];test=finite_test(node.args[0])
                if test is None or(variable is not None and variable!=test[0]):break
                variable=test[0]
                for value in test[1]:chain.setdefault(value,node.args[1])
                cursor=node.args[2]
            if len(chain)>=3:
                selector=self.node(variable);alternatives=defaultdict(list);selected=[]
                for value,alternative in chain.items():
                    condition=self.equal_const(selector,value);alternatives[alternative].append(condition);selected.append(condition)
                alternatives[cursor].append(self.one-sum(selected,Expr()))
                words=[]
                for alternative,conditions in alternatives.items():
                    condition=sum(conditions,Expr());word=self.node(alternative)
                    words.append([self.AND([condition,bit],'kernel-table-value')for bit in word])
                result=[sum((word[bit]for word in words),Expr())for bit in range(n.width)]
                self.nodes[index]=result;self.finite_choices+=1;return result
        if n.op=='const'and n.data in self.parameters:
            word=self.parameters[n.data]
            return word[:n.width]+[self.zero]*max(0,n.width-len(word))
        return super().node(index,root=root)

    def effect_outputs(self,effects):
        values=defaultdict(list);guards=defaultdict(list);writes=defaultdict(list)
        for index,effect in effects:
            guard=self.node(effect.guard)[0]
            if effect.kind=='merge_fields':
                for name,node in effect.values:
                    values[name].append((guard,self.node(node)));guards[name].append(guard)
            else:
                writes[effect.kind.removeprefix('write_')].append(
                    (guard,self.node(effect.address),[self.node(node)for node in effect.values]))
        fields={}
        for name,items in values.items():
            width=len(items[0][1])
            word=[self.OR([self.AND([guard,word[bit]],'kernel-effect-value')for guard,word in items],
                          'kernel-effect-or')for bit in range(width)]
            fields[name]=(self.OR(guards[name],'kernel-field-mask'),word)
        banks={}
        for bank,items in writes.items():
            address=[self.OR([self.AND([guard,address[bit]])for guard,address,row in items])for bit in range(len(items[0][1]))]
            row=[[self.OR([self.AND([guard,row[field][bit]])for guard,address,row in items])
                  for bit in range(len(items[0][2][field]))]for field in range(len(items[0][2]))]
            banks[bank]=(self.OR([guard for guard,address,row in items]),address,row)
        return fields,banks


class SourceOperatorLibrary:
    """Fixed selector plus alpha-renamed operand ABI for ALL source regions.

    This is the neural kernel-body compiler. It does not assert a complete
    stock checker: source dispatch, operand gathers, cyclic allocation, prefix
    and atomic RAM publication have separate integration/resource obligations.
    """
    def __init__(self,builder,compiler,regions,operand_words,selector,literal_words=None):
        self.builder=builder;self.compiler=compiler;self.regions=regions
        self.shared=SharedExpressionGraph(builder.graph);builder.graph=self.shared
        self.inputs=[];self.destinations=[];self.cases=[];self.required_words=0;self.literals=[];self.finite_choices=0
        helper=SourceEffectCircuit(builder,compiler.g,{})
        for code,region in enumerate(regions):
            names=[];seen=set();literals=[]
            def visit(index):
                if index in seen:return
                seen.add(index);node=compiler.g.nodes[index]
                if node.op=='input'and node.data not in names:names.append(node.data)
                if literal_words is not None and node.op=='const'and node.width>1 and node.data<(1<<len(literal_words[0]))and node.data not in(0,1,compiler.cfg.heap,compiler.cfg.stack,compiler.cfg.context,compiler.cfg.constants,1<<compiler.cfg.word_bits)and node.data not in literals:
                    literals.append(node.data)
                for child in node.args:visit(child)
            for index,effect in region['effects']:
                visit(effect.guard)
                if effect.address>=0:visit(effect.address)
                for value in effect.values:visit(value[1]if effect.kind=='merge_fields'else value)
            self.required_words=max(self.required_words,len(names))
            if len(names)>len(operand_words):raise ValueError(f'RESOURCE: source operator {code} needs {len(names)} operand words, ABI has {len(operand_words)}')
            inputs={name:operand_words[index][:compiler.g.nodes[compiler.g.input_words[name]].width]
                    for index,name in enumerate(names)}
            if literal_words is not None and len(literals)>len(literal_words):raise ValueError('RESOURCE: source literal ABI is too small')
            parameters={value:literal_words[index]for index,value in enumerate(literals)}if literal_words is not None else None
            circuit=SourceEffectCircuit(builder,compiler.g,inputs,parameters)
            fields,banks=circuit.effect_outputs(region['effects'])
            self.finite_choices+=circuit.finite_choices
            enabled=helper.equal_const(selector,code)
            self.inputs.append(tuple(names));self.destinations.append(tuple(fields))
            self.literals.append(tuple(literals))
            self.cases.append((enabled,fields,banks))
        self.graph=self.shared.base
        from ..native_vendor.qwenputer.ir import FFN
        self.data_units=sum(len(n.terms)for n in self.graph.nodes if isinstance(n,FFN))

    def selected_outputs(self,global_fields=()):
        """One-hot operator selection, preserving within-region OR writes."""
        helper=SourceEffectCircuit(self.builder,self.compiler.g,{})
        global_fields=set(global_fields)
        names=[name for name,width in self.compiler.layout.fields]
        field_ids={name:index for index,name in enumerate(names)}
        role_count=max(sum(name not in global_fields for name in fields)for enabled,fields,banks in self.cases)
        role_values=[[]for _ in range(role_count)];role_masks=[[]for _ in range(role_count)]
        role_dest=[[]for _ in range(role_count)];globals=defaultdict(list);banks=defaultdict(list)
        for enabled,fields,writes in self.cases:
            private=sorted((name for name in fields if name not in global_fields),key=field_ids.__getitem__)
            for role,name in enumerate(private):
                mask,word=fields[name];active=helper.AND([enabled,mask],'kernel-operator-field')
                role_masks[role].append(active);role_values[role].append((active,word));role_dest[role].append((active,field_ids[name]))
            for name in fields.keys()&global_fields:
                mask,word=fields[name];globals[name].append((helper.AND([enabled,mask]),word))
            for name,(mask,address,row)in writes.items():banks[name].append((helper.AND([enabled,mask]),address,row))

        def reduce(values):
            # Selected cases are disjoint. Every partial sum is still Boolean;
            # bounded fan-in also avoids a large row of live case temporaries.
            values=[value for value in values if value.terms]
            if not values:return Expr()
            while len(values)>1:
                values=[self.shared.ffn([(1,self.shared.one,sum(values[i:i+16],Expr()))],name='kernel-selected-sum')
                        for i in range(0,len(values),16)]
            return values[0]

        def selected_word(items,width):
            result=[]
            for bit in range(width):
                grouped=defaultdict(list);expressions={}
                for active,word in items:
                    value=word[bit];key=tuple(sorted(value.terms.items()))
                    grouped[key].append(active);expressions[key]=value
                terms=[]
                for key,guards in grouped.items():
                    value=expressions[key]
                    if value.terms:terms.append(helper.AND([reduce(guards),value],'kernel-selected-value'))
                result.append(reduce(terms))
            return result

        output=[]
        for masks,items,destinations in zip(role_masks,role_values,role_dest):
            destination=[reduce([active for active,index in destinations if index>>bit&1])for bit in range(10)]
            output.append((reduce(masks),destination,selected_word(items,16)))
        global_output={name:(reduce([active for active,word in items]),selected_word(items,16))for name,items in globals.items()}
        bank_output={}
        for name,items in banks.items():
            bank_output[name]=(reduce([active for active,address,row in items]),
                               selected_word([(active,address)for active,address,row in items],16),
                               [selected_word([(active,row[field])for active,address,row in items],16)
                                for field in range(len(items[0][2]))])
        self.output_roles=output;self.global_outputs=global_output;self.bank_outputs=bank_output
        return output,global_output,bank_output

    def report(self):
        from ..native_vendor.qwenputer.ir import FFN
        nodes=self.graph.nodes
        covered=set().union(*(set(region['aliases'])for region in self.regions))
        return dict(source_regions=len(self.cases),source_effects=len(self.compiler.effects),
                    source_effect_ids_covered=len(covered),prefix_effects_separate=self.compiler.preflight_effect_count,
                    all_registered_rule_families=len(self.compiler.families),
                    required_operand_words=self.required_words,neural_ffn_units=sum(len(n.terms)for n in nodes if isinstance(n,FFN)),
                    kernel_data_units_before_selection=self.data_units,max_literal_words=max(map(len,self.literals),default=0),
                    finite_source_choice_tables=self.finite_choices,
                    graph_layers=self.graph.n_layers(),shared_expression_hits=self.shared.hits,
                    register_output_roles=len(getattr(self,'output_roles',())),
                    inference_interpreter=False,source_driver_integrated=False,
                    cyclic_layout_verified=False,stock_source_completed=False)
