"""Small stock RF selector evidence, not source checking or admission."""
import importlib.util
import sys
import unittest


@unittest.skipUnless(sys.version_info >= (3,11) and importlib.util.find_spec('transformers'), 'native stock environment')
class SelectiveRowOperatorTest(unittest.TestCase):
    def test_independent_queries_all_pages_and_replica_writes(self):
        self.check_core()

    def test_seven_word_page_writes_preserve_other_pages_and_replicas(self):
        self.check_core(paged=True)

    def test_four_ports_with_paged_writes_and_independent_queries(self):
        self.check_core(paged=True,ports=4)

    def check_core(self,paged=False,ports=3):
        import torch
        from leanputer.kernel.selective_row_operator import build_selective_probe
        from leanputer.native_vendor.qwenputer.ir import A_BIT
        chip=build_selective_probe(paged_writes=paged,ports=ports)
        bits=lambda value,width:[value>>i&1 for i in range(width)]
        wordbits=lambda values:[b for value in values for b in bits(value,16)]
        rows=(0,33,127)
        data={row:[[((row+7)*997+index*3907+batch*101)&65535 for index in range(28)]
                   for batch in range(2)]for row in rows}
        data[127][0][27]=65535;data[33][1][0]=0;data[0][0][7]=32768
        boot=[]
        for row in rows:
            for page in range(4)if paged else (None,):
                groups={'pending_page':bits(page,2)}if paged else {}
                boot.append(torch.stack([chip.packet(pending=wordbits(data[row][batch][7*page:7*(page+1)]if paged else data[row][batch]),
                                                    pending_row=bits(row,7),pending_enable=[1],**groups)for batch in range(2)]))
        cache=chip.new_cache();masks={'full_attention':None,'linear_attention':None}
        with torch.no_grad():
            chip.model(inputs_embeds=chip.embeddings(torch.stack(boot,dim=1)),past_key_values=cache,
                       use_cache=True,position_ids=torch.zeros(2,len(boot),dtype=torch.long),attention_mask=masks)
            before=[cache.layers[layer].recurrent_states[0].clone()for layer in chip.report['memory_layers']]
            for memory in before:
                for row in rows:
                    for page in range(4):
                        expected=torch.tensor([wordbits(data[row][batch][7*page:7*(page+1)])for batch in range(2)]).float()
                        self.assertTrue(torch.equal((memory[:,page,row,2:114]/A_BIT).float(),expected),
                                        (row,page,'complete page payload'))
            packets=[]
            selected=[[(127,[6,0,3,6],1),(33,[0,6,2,1],1),(0,[3,4,5,6],1)],
                      [(33,[0,1,2,3],1),(127,[6,5,7,0],1),(0,[0,0,0,0],0)]]
            if ports==4:
                selected[0].append((33,[6,5,4,3],1));selected[1].append((0,[2,3,4,5],1))
            for batch in range(2):
                groups={}
                for port,(row,lanes,enabled)in enumerate(selected[batch]):
                    groups[f'row/{port}']=bits(row,7)
                    groups[f'lanes/{port}']=[b for lane in lanes for b in bits(lane,3)]
                    groups[f'enabled/{port}']=[enabled]
                packets.append(chip.packet(**groups))
            state=chip.embeddings(torch.stack(packets)[:,None])
            for _ in range(2):
                output=chip.model(inputs_embeds=state,past_key_values=cache,use_cache=True,
                                  output_hidden_states=True,position_ids=torch.zeros(2,1,dtype=torch.long),attention_mask=masks)
                state=output.hidden_states[-2]  # Fixed identity feedback.
        for port in range(ports):
            expected=[]
            for batch in range(2):
                row,lanes,enabled=selected[batch][port]
                expected.append(wordbits([data[row][batch][page*7+lane]if enabled and lane<7 else 0
                                          for page,lane in enumerate(lanes)]))
            self.assertTrue(torch.equal(state[:,0,chip.slots.groups[f'output/{port}']].float(),torch.tensor(expected).float()),port)
        for index,layer in enumerate(chip.report['memory_layers']):
            actual=cache.layers[layer].recurrent_states[0]
            self.assertTrue(torch.equal(actual,before[index]),'read-only preservation')
            self.assertTrue(torch.equal(actual,before[0]),'all replicas/all rows')
        self.assertTrue(torch.equal(output.logits[:,0].float(),state[:,0,chip.slots.groups['output/0']].float()))
        print(chip.report,flush=True)
