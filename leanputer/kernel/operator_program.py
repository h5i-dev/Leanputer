"""Complete source-operator IR, independent of declarations and word backend.

Factor control predicates instead of enumerating their Cartesian product.
Exact source data guards and simultaneous updates remain attached to operators.
This is compiler IR; it supplies no runtime interpreter to stock inference.
"""
from collections import defaultdict
from .semantic_phases import SemanticPhases
from .continuation_plan import compile_continuations
from .control_alias import ControlAliases


class OperatorProgram:
    def __init__(self,compiler,contract,addresses,alias_private_controls=False):
        self.compiler=compiler;self.contract=contract;self.addresses=addresses
        self.control=SemanticPhases(compiler,contract,build=False)
        self.aliases=ControlAliases(self.control,contract.body)if alias_private_controls else None
        self.control_nodes=[('const',0),('const',1)];control_ids={}
        def intern(value):
            if isinstance(value,int):return value
            if value[0]=='range':key=self.aliases.rewrite_atom(value)if self.aliases else value
            else:key=(value[0],tuple(sorted(intern(v)for v in value[1])))
            if key not in control_ids:
                control_ids[key]=len(self.control_nodes);self.control_nodes.append(key)
            return control_ids[key]
        groups=defaultdict(list)
        for index,effect in contract.body:groups[intern(self.control.project(effect.guard))].append((index,effect))
        self.groups=tuple((guard,tuple(effects))for guard,effects in groups.items())
        dependency_cache={}
        def fields(index):
            if index not in dependency_cache:
                node=compiler.g.nodes[index]
                dependency_cache[index]=frozenset((node.data,))if node.op=='input'else frozenset().union(*(fields(a)for a in node.args))
            return dependency_cache[index]
        self.operand_fields={}
        for index,effect in contract.body:
            roots=[effect.guard]+[node for name,node in effect.values]if effect.kind=='merge_fields'else[effect.guard,effect.address]+list(effect.values)
            self.operand_fields[index]=frozenset().union(*(fields(node)for node in roots))
        self.continuations=compile_continuations(compiler)
        represented={i for guard,effects in self.groups for i,effect in effects}
        represented.update(i for i,e in contract.prefix+contract.fallback)
        if represented!=set(range(len(compiler.effects))):raise ValueError('source operators omit effects')
        if contract.fallback:raise ValueError('GAP: operator body requires non-dominated prefix effects')

    def report(self):
        return dict(format='leanputer.complete-source-operator-ir.v1',
                    rule_families=len(self.compiler.families),source_effects=len(self.compiler.effects),
                    source_effects_represented=len(self.compiler.effects),
                    factored_control_groups=len(self.groups),prefix_effects=len(self.contract.prefix),
                    shared_control_predicate_nodes=len(self.control_nodes),
                    control_aliases=self.aliases.report()if self.aliases else None,
                    original_data_guards_preserved=True,immutable_old_state_or_merges_preserved=True,
                    source_stack_write_sites=len(self.continuations),
                    input_independent=True,all_logical_words_retained=True,
                    complete_descriptor_encoding_verified=False,stock_lowering_complete=False,
                    native_forwards=None,joint_delivery_gate=False)
