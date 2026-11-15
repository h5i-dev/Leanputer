"""Shared module evidence only; does NOT admit original declarations."""
import importlib.util,sys,unittest


@unittest.skipUnless(sys.version_info>=(3,11)and importlib.util.find_spec('transformers'),'native stock environment')
class SharedDatapathTest(unittest.TestCase):
    def test_three_rf_ports_rom_and_word_result_feed_back_without_host_dispatch(self):
        import torch
        from leanputer.kernel.stock_datapath import build,CoreRecord,WordAction as O,rf_address
        program=[CoreRecord(O.MOVE,dest=rf_address(2603),a=rf_address(1),yes=1),CoreRecord(O.ADD,dest=rf_address(2604),a=rf_address(2603),b=rf_address(900),yes=2),CoreRecord(O.EQ_BRANCH,a=rf_address(2604),b=rf_address(600),yes=3,no=7),CoreRecord(O.SUB,dest=rf_address(2605),a=rf_address(2604),b=rf_address(900),yes=4),CoreRecord(O.EQ_BRANCH,a=rf_address(2605),b=rf_address(1),yes=5,no=7),CoreRecord(O.LT_BRANCH,a=rf_address(900),b=rf_address(1),yes=6,no=7),CoreRecord(O.STOP_OK,yes=6),CoreRecord(O.STOP_INVALID,yes=7)]
        chip=build(program);self.assertLessEqual(chip.report['logical_dense_parameters'],100000000)
        packets=[]
        for row in(0,128,85):
            batch=[]
            for claim in(0,1):
                words={1:65535,900:1,600:claim};data=[]
                for slot in range(7):data.extend((words.get(7*row+slot,65535 if row==0 else 0)>>bit)&1 for bit in range(16))
                data += [0]*14
                batch.append(chip.packet(boot=[1],pending_row=[(row>>bit)&1 for bit in range(9)],pending_enable=[1],pending_payload=data))
            packets.append(torch.stack(batch))
        initial=chip.embeddings(torch.zeros(2,1,chip.slots.next-13))
        with torch.no_grad():
            boot=chip.embeddings(torch.stack(packets,dim=1))
            # All-GDN stock models need explicit position/mask metadata because
            # DynamicCache has no full-attention sequence-length layer. These
            # constant kwargs depend only on tensor shape, never instructions.
            masks={'full_attention':None,'linear_attention':None}
            loaded=chip.model(inputs_embeds=boot,use_cache=True,position_ids=torch.zeros(2,boot.shape[1],dtype=torch.long),attention_mask=masks)
            state=initial;cache=loaded.past_key_values
            for _ in range(10):
                out=chip.model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True,position_ids=torch.zeros(2,1,dtype=torch.long),attention_mask=masks);cache=out.past_key_values;state=out.hidden_states[-2]
            bits=out.logits[:,0].float().tolist()
        word=lambda b:sum(int(v)<<i for i,v in enumerate(b))
        self.assertEqual([word(row[16:32])for row in bits],[1,2])
        self.assertEqual([word(row[48:64])for row in bits],[65535,0])
        # Query ports differ, but all writes must keep every RF replica exact.
        first=1+chip.report['rom_layers']
        for page in range(3):
            baseline=cache.layers[first+page].recurrent_states[0]
            for port in(1,2):self.assertTrue(torch.equal(baseline,cache.layers[first+3*port+page].recurrent_states[0]))
        print(chip.report,flush=True)
