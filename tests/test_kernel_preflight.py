import unittest
from types import SimpleNamespace


class FixedPreflightCircuitTest(unittest.TestCase):
    def test_original_prefix_masks_values_and_body_guard(self):
        from leanputer.kernel.control_capture import TypedRuleCompiler
        from leanputer.kernel.control_phases import PhasePartition
        from leanputer.kernel.control_reference import evaluate
        from leanputer.kernel.control_ir import Node
        from leanputer.kernel.stock_preflight import PreflightPlan
        from leanputer.kernel.stock_preflight_graph import PreflightCircuit
        from leanputer.kernel.traversal_machine import MachineConfig,RegisterLayout,StateLayout,Task,Mode
        from leanputer.kernel.arena import Tag
        from leanputer.native_machine import NativeBuilder
        from leanputer.native_vendor.qwenputer.ir import ONE,FFN
        cfg=MachineConfig(heap=512,stack=32,context=8,constants=4,word_bits=16)
        compiler=TypedRuleCompiler(RegisterLayout(StateLayout(cfg)))
        plan=PreflightPlan(compiler,PhasePartition(compiler,contract_only=True))
        builder=NativeBuilder(intermediate=512,reset_layers=0)
        inputs={name:[builder.feature(f'preflight/{name}/{i}')for i in range(16)]for name in plan.inputs}
        invalid=builder.feature('invalid');circuit=PreflightCircuit(builder,plan,inputs,invalid);output=circuit.outputs()
        base=dict(arg_base=0,count=0,free=4,fuel=10,mode=int(Mode.WALK),status=0,task=int(Task.INFER),x=1)
        base['read/node/tag']=int(Tag.SORT)
        cases=[({},0),({'fuel':0},0),({'status':1},0),({},1),({'x':4},0),({'x':65535},0),({'task':int(Task.INSTANTIATE),'arg_base':65535,'count':65535},0),({'task':int(Task.INSTANTIATE),'arg_base':8,'count':1},0),({'mode':65535},1),({'read/node/tag':65535},0)]
        for updates,bad in cases:
            with self.subTest(updates=updates,invalid=bad):
                data=dict(base,**updates);state={ONE:1}
                for name,word in inputs.items():
                    for bit,expr in enumerate(word):state[next(iter(expr.terms))]=data[name]>>bit&1
                state[next(iter(invalid.terms))]=bad
                def linear(expr):return sum(coefficient*state[index]for index,coefficient in expr.terms.items())
                for node in builder.graph.nodes:
                    self.assertIsInstance(node,FFN)
                    value=sum(coefficient*linear(a)*max(0,linear(b))for coefficient,a,b in node.terms)
                    state[node.out]=(state.get(node.out,0)if node.into else 0)+value
                actual=[]
                for word in output:
                    bits=[linear(bit)for bit in word]
                    self.assertTrue(all(value in(0,1)for value in bits),bits)
                    actual.append(sum(int(value)<<i for i,value in enumerate(bits)))
                source_nodes=list(compiler.g.nodes);source_nodes[plan.invalid]=Node('const',1,(),bad)
                get=evaluate(SimpleNamespace(nodes=source_nodes),None,data);values={};masks=set()
                for effect in plan.effects:
                    if get(effect.guard):
                        for name,node in effect.values:values[name]=values.get(name,0)|get(node);masks.add(name)
                expected=[values.get(name,0)for name in plan.field_names]+[int(name in masks)for name in plan.field_names]+[get(compiler.preflight_active)]
                self.assertEqual(actual,expected)

class StockFixedPreflightTest(unittest.TestCase):
    def test_stock_gathers_predicate_and_original_write_masks(self):
        import torch
        from leanputer.kernel.control_capture import TypedRuleCompiler
        from leanputer.kernel.control_phases import PhasePartition
        from leanputer.kernel.control_reference import evaluate
        from leanputer.kernel.stock_preflight import PreflightPlan
        from leanputer.kernel.stock_bounds import schema_from_compiler
        from leanputer.kernel.stock_control import main_address,temporary_address
        from leanputer.kernel.stock_datapath import build,CoreRecord,WordAction as O,rf_address
        from leanputer.kernel.traversal_machine import MachineConfig,RegisterLayout,StateLayout,Task,Mode
        from leanputer.kernel.arena import Tag
        from leanputer.native_vendor.qwenputer.ir import A_BIT
        cfg=MachineConfig(heap=512,stack=32,context=8,constants=4,word_bits=16)
        compiler=TypedRuleCompiler(RegisterLayout(StateLayout(cfg)));plan=PreflightPlan(compiler,PhasePartition(compiler,contract_only=True));plan.cache_rows=(440,441,442)
        schema=schema_from_compiler(compiler);names=[name for name,width in compiler.layout.fields]
        addresses=[temporary_address(0)if name=='read/node/tag'else main_address(names.index(name))for name in plan.inputs]
        program=[CoreRecord(O.PREFLIGHT_GATHER,dest=addresses[3*i+2],a=addresses[3*i],b=addresses[3*i+1],auxiliary=plan.cache_rows[i],yes=i+1)for i in range(3)]
        program += [CoreRecord(O.PREFLIGHT_CHECK,dest=rf_address(442*7),a=rf_address(440*7),b=rf_address(441*7),auxiliary=440,yes=4),CoreRecord(O.JUMP,yes=4)]
        chip=build(program,rom_layout='byte_pages',hidden=1024,intermediate=256,compact_attention=True,parallel_carry=True,datapath_layers=90,grouped_memory=True,bounds_schema=schema,reuse_transient_features=True,preflight_plan=plan)
        base={name:0 for name in names};base.update(free=4,fuel=10,x=1,task=int(Task.INFER),mode=int(Mode.WALK),open_tag=int(Tag.PI),fold_tag=int(Tag.PI))
        cases=[({},int(Tag.SORT)),({'fuel':0,'free':0},int(Tag.SORT)),({'free':0},int(Tag.SORT)),({},65535),({'task':int(Task.INSTANTIATE),'arg_base':65535,'count':1},int(Tag.SORT)),({'status':1,'free':0},int(Tag.SORT))]
        states=[dict(base,**updates)for updates,tag in cases]
        # Raw data transport only. Include every schema/input row, even zero
        # rows, so the test never supplies a preflight/invalidity answer.
        rows={main_address(index)>>3 for index,tree in schema}
        rows.update(address>>3 for address in addresses);rows.update(main_address(names.index(name))>>3 for name in('open_tag','fold_tag'))
        packets=[]
        for row in sorted(rows):
            batch=[]
            for state,(updates,tag)in zip(states,cases):
                values=[]
                for slot in range(7):
                    address=(row<<3)|slot
                    index=(row//2)*7+slot
                    values.append(tag if address==temporary_address(0)else state[names[index]]if row<272 and not row&1 and index<len(names)else 0)
                bits=[value>>i&1 for value in values for i in range(16)]+[0]*14
                batch.append(chip.packet(boot=[1],pending_enable=[1],pending_row=[row>>i&1 for i in range(9)],pending_payload=bits))
            packets.append(torch.stack(batch))
        masks={'full_attention':None,'linear_attention':None};batch=len(states)
        with torch.no_grad():
            boot=chip.embeddings(torch.stack(packets,dim=1));out=chip.model(inputs_embeds=boot,past_key_values=chip.new_cache(),use_cache=True,position_ids=torch.zeros(batch,len(packets),dtype=torch.long),attention_mask=masks)
            cache=out.past_key_values;state=chip.embeddings(torch.zeros(batch,1,chip.slots.next-chip.slots.prefix))
            for _ in range(6):
                out=chip.model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True,position_ids=torch.zeros(batch,1,dtype=torch.long),attention_mask=masks);state=out.hidden_states[-2]
        expected=[]
        for data,(updates,tag)in zip(states,cases):
            inputs=dict(data);inputs['read/node/tag']=tag;get=evaluate(compiler.g,None,inputs);values={};active=set()
            for effect in plan.effects:
                if get(effect.guard):
                    for name,node in effect.values:values[name]=values.get(name,0)|get(node);active.add(name)
            expected.append([values.get(name,0)for name in plan.field_names]+[int(name in active)for name in plan.field_names]+[get(compiler.preflight_active)])
        for head in chip.report['rf_heads']:
            if head['page']!=440//128:continue
            stored=(cache.layers[head['layer']].recurrent_states[0][:,head['value_head'],440%128,2:114]/A_BIT).float().tolist()
            self.assertTrue(all(value in(0,1)for item in stored for value in item))
            actual=[[sum(int(value)<<i for i,value in enumerate(item[first:first+16]))for first in range(0,112,16)]for item in stored]
            self.assertEqual(actual,expected)


if __name__=='__main__':unittest.main()
