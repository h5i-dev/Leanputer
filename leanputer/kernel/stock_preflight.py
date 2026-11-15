"""Compile the original kernel preflight predicates into fixed stock circuits.

The decision graph is compiler data, independent of source declarations. Its
predicates become stock neural weights, not an inference-time host evaluator or
Boolean instruction interpreter. The original prefix effects are retained.
"""
from collections import Counter,defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class DataPredicate:
    node: int


@dataclass(frozen=True)
class ControlChoice:
    variable: int
    cases: tuple


class PreflightPlan:
    def __init__(self,compiler,partition):
        self.compiler=compiler;self.graph=compiler.g;self.partition=partition
        self.invalid=self.graph.pred(compiler.invalid_syntax)
        self.actives=tuple(sorted(set(i for i in compiler.active_nodes if i<=compiler.preflight_active)))
        self.opaque=frozenset((self.invalid,*self.actives));self.memo={};self.aliases={}
        from .control_ir import Bit
        for index in self.actives:
            n=self.graph.nodes[index]
            if n.op!='all':continue
            for arg in n.args:
                child=self.graph.nodes[arg]
                if child.op!='not':continue
                base=[Bit(i,0)for i in n.args if i!=arg]
                rejected=self.graph.AND(*base,Bit(child.args[0],0)).word
                self.aliases[rejected]=self.graph.AND(*base,self.graph.NOT(Bit(index,0))).word
        self.effects=tuple(compiler.effects[:compiler.preflight_effect_count])
        if any(effect.kind!='merge_fields'for effect in self.effects):raise ValueError('native preflight supports original register prefix effects')
        self.field_names=tuple(sorted({name for e in self.effects for name,node in e.values},key=lambda name:next(i for i,(n,w)in enumerate(compiler.layout.fields)if n==name)))
        if 2*len(self.field_names)+1>7:raise ValueError('preflight result and update masks exceed one RF row')
        self.roots=(compiler.preflight_active,)+tuple(root for e in self.effects for root in(e.guard,*(node for name,node in e.values)))
        seen=set();inputs=set()
        def visit(i):
            if i in seen or i==self.invalid:return
            seen.add(i);node=self.graph.nodes[i]
            if node.op=='input':inputs.add(node.data)
            for child in node.args:visit(child)
        for root in self.roots:visit(root)
        self.inputs=tuple(sorted(inputs));self.normalized={root:self.normalize(self.aliases.get(root,root),root if root in self.actives else None)for root in (*self.actives,*self.roots)}
        choices=set();leaves=set()
        def inspect(tree):
            if isinstance(tree,DataPredicate):leaves.add(tree.node);return
            if tree in choices:return
            choices.add(tree)
            for low,high,child in tree.cases:inspect(child)
        for tree in self.normalized.values():inspect(tree)
        self.report=dict(source_defined=True,original_prefix_effects=len(self.effects),input_words=self.inputs,updated_fields=self.field_names,typed_nodes=len(seen),typed_operations=dict(Counter(self.graph.nodes[i].op for i in seen)),control_choice_nodes=len(choices),control_intervals=sum(len(tree.cases)for tree in choices),data_predicates=len(leaves),all_control_values_covered=True)

    def normalize(self,index,active=None):
        key=index,active
        if key in self.memo:return self.memo[key]
        opaque=self.opaque-frozenset((active,))
        tests={variable:values for variable,values in self.partition.tests(index,opaque).items()if self.partition.variables[variable]in('task','mode')}
        if not tests:result=DataPredicate(index)
        else:
            variable=min(tests,key=lambda v:(self.partition.variables[v]!='task',-len(tests[v])))
            breaks={0,1<<self.graph.nodes[variable].width}
            for value in tests[variable]:
                if 0<=value<max(breaks):breaks.update((value,value+1))
            breaks=sorted(breaks);parts=[]
            for low,end in zip(breaks,breaks[1:]):
                cofactor=self.partition.cofactor(index,variable,low,end-1,opaque)
                if cofactor==index:raise ValueError('preflight control normalization did not remove a test')
                child=self.normalize(cofactor,active)
                if parts and parts[-1][2]==child:parts[-1]=(parts[-1][0],end-1,child)
                else:parts.append((low,end-1,child))
            result=ControlChoice(variable,tuple(parts))
        self.memo[key]=result;return result

    def permutation(self):
        # Main register words used by the preflight are DATA in a fixed layout.
        # Grouping them changes transport/storage only, never their values.
        names=[name for name,width in self.compiler.layout.fields]
        first=sorted((names.index(name)for name in self.inputs if not name.startswith('read/')))
        if len(first)>8:raise ValueError('preflight main operands exceed two RF rows')
        order=first+[i for i in range(len(names))if i not in first]
        inverse=[0]*len(order)
        for physical,logical in enumerate(order):inverse[logical]=physical
        return tuple(inverse)


def emit_preflight_controller(native):
    """Lower bounded data gathers, exact prefix updates and the body guard."""
    from .stock_datapath import CoreRecord,FieldRecord,WordAction as O,rf_address
    from .stock_control import Value,temporary_address,main_address
    from .stock_source_ops import AffineAddressRecord,SparseSwitchRecord
    used=set()
    def use(address):used.add(address>>3)
    for record,yes,no in native.pending:
        if isinstance(record,CoreRecord):
            use(record.dest)
            if not record.literal_a:use(record.a)
            if not record.literal_b:use(record.b)
        elif isinstance(record,FieldRecord):
            for dest,value,literal in record.items:
                use(dest)
                if not literal:use(value)
        elif isinstance(record,AffineAddressRecord):
            use(record.dest)
            for address,coefficient in record.sources:use(address)
        elif isinstance(record,SparseSwitchRecord):use(record.a)
        else:raise ValueError('unmapped preflight scratch dependency')
    rows=[row for row in range(408,509)if row not in used][:3]
    if len(rows)!=3:raise ValueError('whole program lacks three unaliased preflight cache rows')
    plan=native.preflight_plan;plan.cache_rows=tuple(rows)
    if len(plan.inputs)>9:raise ValueError('source preflight exceeds three input triplets')
    addresses=[native.value(native.store.inputs[name]).value for name in plan.inputs]
    addresses += [0]*(9-len(addresses));native.region='source-preflight';native.mark(('native-preflight',))
    for row,first in zip(rows,range(0,9,3)):
        native.emit(O.PREFLIGHT_GATHER,dest=addresses[first+2],a=Value(addresses[first]),b=Value(addresses[first+1]),auxiliary=row)
    # Gather 0/1/2 stores three input words in each row. The checker reads all
    # nine words and replaces row0 with values/masks/active, all model-owned.
    native.emit(O.PREFLIGHT_CHECK,dest=rf_address(rows[2]*7),a=Value(rf_address(rows[0]*7)),b=Value(rf_address(rows[1]*7)),auxiliary=rows[0])
    for index,name in enumerate(plan.field_names):
        write,following=native.label(),native.label()
        native.emit(O.NONZERO_BRANCH,a=Value(rf_address(rows[0]*7+len(plan.field_names)+index)),yes=write,no=following);native.mark(write)
        dest=main_address(next(i for i,(field,width)in enumerate(native.store.compiler.layout.fields)if field==name))
        native.pending.append((FieldRecord(((dest,rf_address(rows[0]*7+index),False),),0),following,None));native.pending_regions.append(native.region);native.mark(following)
    native.emit(O.NONZERO_BRANCH,a=Value(rf_address(rows[0]*7+2*len(plan.field_names))),yes=('typed',native.store.entry_pc),no=('commit',))
    plan.report.update(cache_rows=rows,prefix_effects_lowered=True,body_requires_original_active_predicate=True,gather_forwards=3,check_forwards=1)
