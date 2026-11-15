"""Shared module evidence only; does NOT admit original declarations."""
import importlib.util,sys,unittest


@unittest.skipUnless(sys.version_info>=(3,11)and importlib.util.find_spec('transformers'),'native stock environment')
class SharedDatapathTest(unittest.TestCase):
    def test_three_rf_ports_rom_and_word_result_feed_back_without_host_dispatch(self):
        self.check_core('flat')

    def test_byte_page_weight_rom_reuses_rows_across_page_boundary(self):
        self.check_core('byte_pages')

    def test_arena_reads_writes_and_read_only_declaration_bank(self):
        import torch
        from leanputer.kernel.stock_datapath import build,CoreRecord,WordAction as O,rf_address as rf
        program=[CoreRecord(O.HEAP_WRITE,a=rf(1),b=rf(2),auxiliary=1,yes=1),
                 CoreRecord(O.HEAP_READ,dest=rf(10),a=rf(1),auxiliary=1,yes=2),
                 CoreRecord(O.FRAME_WRITE,a=rf(3),b=rf(10),auxiliary=2,yes=3),
                 CoreRecord(O.FRAME_READ,dest=rf(11),a=rf(3),auxiliary=2,yes=4),
                 CoreRecord(O.CONTEXT_WRITE,a=rf(4),b=rf(11),yes=5),
                 CoreRecord(O.CONTEXT_READ,dest=rf(12),a=rf(4),yes=6),
                 CoreRecord(O.DECLARATION_READ,dest=rf(13),a=rf(5),auxiliary=4,yes=7),
                 CoreRecord(O.EQ_BRANCH,a=rf(13),b=rf(8),yes=8,no=10),
                 CoreRecord(O.EQ_BRANCH,a=rf(12),b=rf(6),yes=9,no=10),
                 CoreRecord(O.STOP_OK,yes=9),CoreRecord(O.STOP_INVALID,yes=10)]
        chip=build(program,rom_layout='byte_pages')
        packets=[]
        for kind,address in((0,0),(0,1),(1,273),(2,19),(3,5),(4,1)):
            batch=[]
            for claim in(65535,65534):
                words={1:273,2:65535,3:19,4:5,5:1,6:claim,8:0x1234}
                values=[words.get(address*7+slot,0)for slot in range(7)]if kind==0 else ([11,22,33,44,0x1234,66]if kind==4 else [11,22,33,44,55,66])
                payload=[(value>>bit)&1 for value in values for bit in range(16)];payload += [0]*(126-len(payload))
                batch.append(chip.packet(boot=[1],pending_kind=[kind>>bit&1 for bit in range(3)],pending_row=[address>>bit&1 for bit in range(9)],pending_enable=[1],pending_payload=payload))
            packets.append(torch.stack(batch))
        masks={'full_attention':None,'linear_attention':None}
        with torch.no_grad():
            boot=chip.embeddings(torch.stack(packets,dim=1))
            out=chip.model(inputs_embeds=boot,use_cache=True,position_ids=torch.zeros(2,len(packets),dtype=torch.long),attention_mask=masks)
            cache=out.past_key_values;state=chip.embeddings(torch.zeros(2,1,chip.slots.next-13))
            for _ in range(18):
                out=chip.model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True,position_ids=torch.zeros(2,1,dtype=torch.long),attention_mask=masks)
                cache=out.past_key_values;state=out.hidden_states[-2]
        word=lambda b:sum(int(v)<<i for i,v in enumerate(b))
        self.assertEqual([word(row[16:32])for row in out.logits[:,0].float().tolist()],[1,2])
        # Binary payload storage is exact, including untouched row fields.
        from leanputer.native_vendor.qwenputer.ir import A_BIT
        for bank,row,expected in(('heap',17,[11,65535,33,44]),('stack',19,[11,22,65535,44,55,66]),('context',5,[65535]),('constants',1,[11,22,33,44,0x1234,66])):
            page=2 if bank=='heap'else 0
            head=next(h for h in chip.report['arena_heads']if h['bank']==bank and h['page']==page)
            stored=cache.layers[head['layer']].recurrent_states[0][:,0,row,2:2+16*len(expected)]/A_BIT
            self.assertEqual([[word(values[i:i+16])for i in range(0,len(values),16)]for values in stored.float().tolist()],[expected,expected])
        print(chip.report,flush=True)

    def check_core(self,rom_layout):
        import torch
        from leanputer.kernel.stock_datapath import build,CoreRecord,WordAction as O,rf_address
        program=[CoreRecord(O.MOVE,dest=rf_address(2603),a=rf_address(1),yes=1),CoreRecord(O.ADD,dest=rf_address(2604),a=rf_address(2603),b=rf_address(900),yes=2),CoreRecord(O.EQ_BRANCH,a=rf_address(2604),b=rf_address(600),yes=3,no=7),CoreRecord(O.SUB,dest=rf_address(2605),a=rf_address(2604),b=rf_address(900),yes=4),CoreRecord(O.EQ_BRANCH,a=rf_address(2605),b=rf_address(1),yes=5,no=7),CoreRecord(O.LT_BRANCH,a=rf_address(900),b=rf_address(1),yes=6,no=7),CoreRecord(O.STOP_OK,yes=6),CoreRecord(O.STOP_INVALID,yes=7)]
        if rom_layout=='byte_pages':
            from dataclasses import replace
            program=[CoreRecord(O.JUMP,yes=127)]+[CoreRecord(O.STOP_INVALID,yes=i)for i in range(1,127)]+[replace(r,yes=r.yes+127,no=r.no+127)for r in program]
        chip=build(program,rom_layout=rom_layout);self.assertLessEqual(chip.report['logical_dense_parameters'],100000000)
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
        first=1+chip.report['rom_layers']+chip.report['rom_decode_layers']
        for page in range(3):
            baseline=cache.layers[first+page].recurrent_states[0]
            for port in(1,2):self.assertTrue(torch.equal(baseline,cache.layers[first+3*port+page].recurrent_states[0]))
        print(chip.report,flush=True)
