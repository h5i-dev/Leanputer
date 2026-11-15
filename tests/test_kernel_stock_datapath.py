"""Shared module evidence only; does NOT admit original declarations."""
import importlib.util,sys,unittest


@unittest.skipUnless(sys.version_info>=(3,11)and importlib.util.find_spec('transformers'),'native stock environment')
class SharedDatapathTest(unittest.TestCase):
    def test_three_rf_ports_rom_and_word_result_feed_back_without_host_dispatch(self):
        self.check_core('flat')

    def test_byte_page_weight_rom_reuses_rows_across_page_boundary(self):
        self.check_core('byte_pages')

    def test_publication_preserves_gap_reason_and_result(self):
        import torch
        from leanputer.kernel.stock_datapath import build,CoreRecord,WordAction as O,rf_address as rf
        chip=build([CoreRecord(O.CALL_HANDLER,yes=2,no=1),CoreRecord(O.PUBLISH_RESULT,dest=rf(6),a=rf(1),b=rf(2),auxiliary=6),CoreRecord(O.MOVE,dest=rf(3),immediate=0xabcd,literal_a=True,yes=3),CoreRecord(O.RETURN_HANDLER)],rom_layout='byte_pages')
        packets=[]
        for status,reason,result in((1,0,65535),(4,11,0x1234)):
            words=[0,status,reason,0,0,0,result];bits=[word>>i&1 for word in words for i in range(16)]+[0]*14
            packets.append(chip.packet(boot=[1],pending_enable=[1],pending_payload=bits))
        masks={'full_attention':None,'linear_attention':None}
        with torch.no_grad():
            out=chip.model(inputs_embeds=chip.embeddings(torch.stack(packets)[:,None]),use_cache=True,position_ids=torch.zeros(2,1,dtype=torch.long),attention_mask=masks)
            state=chip.embeddings(torch.zeros(2,1,chip.slots.next-13))
            for _ in range(4):
                out=chip.model(inputs_embeds=state,past_key_values=out.past_key_values,use_cache=True,output_hidden_states=True,position_ids=torch.zeros(2,1,dtype=torch.long),attention_mask=masks)
                state=out.hidden_states[-2]
        word=lambda bits:sum(int(v)<<i for i,v in enumerate(bits))
        values=out.logits[:,0].float().tolist()
        self.assertEqual([[word(v[16:32]),word(v[32:48]),word(v[48:64])]for v in values],[[1,0,65535],[4,11,0x1234]])

    def test_indexed_control_pages_preserve_all_word_default_values(self):
        import torch
        from leanputer.kernel.stock_datapath import build,CoreRecord,WordAction as O,rf_address as rf
        program=[CoreRecord(O.JUMP,yes=4)for _ in range(512)]
        program[0]=CoreRecord(O.SWITCH4,a=rf(0),literal_b=True,yes=2,auxiliary=16)
        program[1]=CoreRecord(O.SWITCH8,a=rf(1),literal_b=True,yes=3,auxiliary=256)
        program[2]=CoreRecord(O.MOVE,dest=rf(2),literal_a=True,immediate=65535,yes=1)
        program[3]=CoreRecord(O.MOVE,dest=rf(3),literal_a=True,immediate=65535,yes=4)
        program[4]=CoreRecord(O.STOP_OK,yes=4)
        for i in range(16):program[16+i]=CoreRecord(O.MOVE,dest=rf(2),literal_a=True,immediate=i,yes=1)
        for i in range(256):program[256+i]=CoreRecord(O.MOVE,dest=rf(3),literal_a=True,immediate=i,yes=4)
        chip=build(program,rom_layout='byte_pages',compact_attention=True)
        inputs=(0,15,16,255,256,65535);packets=[]
        for value in inputs:
            payload=[value>>i&1 for _ in range(2)for i in range(16)]+[0]*94
            packets.append(chip.packet(boot=[1],pending_row=[0]*9,pending_enable=[1],pending_payload=payload))
        masks={'full_attention':None,'linear_attention':None}
        positions=torch.zeros(len(inputs),1,dtype=torch.long)
        with torch.no_grad():
            out=chip.model(inputs_embeds=chip.embeddings(torch.stack(packets)[:,None]),past_key_values=chip.new_cache(),use_cache=True,position_ids=positions,attention_mask=masks)
            cache=out.past_key_values;state=chip.embeddings(torch.zeros(len(inputs),1,chip.slots.next-13))
            for _ in range(7):
                out=chip.model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True,position_ids=positions,attention_mask=masks)
                state=out.hidden_states[-2]
        from leanputer.native_vendor.qwenputer.ir import A_BIT
        word=lambda b:sum(int(v)<<i for i,v in enumerate(b))
        for head in chip.report['rf_heads']:
            if head['page']:continue
            values=cache.layers[head['layer']].recurrent_states[0][:,0,0,2:128]/A_BIT
            self.assertEqual([[word(row[32:48]),word(row[48:64])]for row in values.float().tolist()],[[v if v<16 else 65535,v if v<256 else 65535]for v in inputs])

    def test_shared_bitwise_and_shift_word_lanes(self):
        import torch
        from leanputer.kernel.stock_datapath import build,CoreRecord,WordAction as O,rf_address as rf
        target=rf(3400)
        program=[CoreRecord(O.MOVE,dest=target,immediate=0xabc1,literal_a=True,yes=1),
                 CoreRecord(O.SHR_LOOP,dest=target,a=target,auxiliary=4,yes=2),CoreRecord(O.SHL_LOOP,dest=target,a=target,auxiliary=4,yes=3),
                 CoreRecord(O.OR,dest=target,a=target,immediate=15,literal_b=True,yes=4),
                 CoreRecord(O.AND,dest=target,a=target,immediate=0xfff,literal_b=True,yes=5),
                 CoreRecord(O.XOR,dest=target,a=target,immediate=0x3333,literal_b=True,yes=6),
                 CoreRecord(O.EQ_BRANCH,a=target,b=rf(1),yes=7,no=8),CoreRecord(O.STOP_OK,yes=7),CoreRecord(O.STOP_INVALID,yes=8)]
        chip=build(program,rom_layout='byte_pages');payloads=[]
        for claim in(0x38fc,0x38fd):
            bits=[0]*16+[claim>>i&1 for i in range(16)]+[0]*94
            payloads.append(chip.packet(boot=[1],pending_row=[0]*9,pending_enable=[1],pending_payload=bits))
        masks={'full_attention':None,'linear_attention':None}
        with torch.no_grad():
            out=chip.model(inputs_embeds=chip.embeddings(torch.stack(payloads)[:,None]),use_cache=True,position_ids=torch.zeros(2,1,dtype=torch.long),attention_mask=masks)
            cache=out.past_key_values;state=chip.embeddings(torch.zeros(2,1,chip.slots.next-13))
            for _ in range(20):
                out=chip.model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True,position_ids=torch.zeros(2,1,dtype=torch.long),attention_mask=masks)
                cache=out.past_key_values;state=out.hidden_states[-2]
        word=lambda b:sum(int(v)<<i for i,v in enumerate(b))
        self.assertEqual([word(row[16:32])for row in out.logits[:,0].float().tolist()],[1,2])
        self.assertEqual([word(row[48:64])for row in out.logits[:,0].float().tolist()],[0x38fc]*2)

    def test_shadow_or_merge_unique_dirty_queue_and_commit(self):
        import torch
        from leanputer.kernel.stock_datapath import build,CoreRecord,FieldRecord,WordAction as O,rf_address as rf
        # Main rows are even, shadows odd. Field18's two simultaneous values
        # must OR before publication; queue it once, then preserve its old value
        # across a second semantic transaction that updates another field.
        program=[FieldRecord(((rf(18),0xff0,True),(rf(18),0xf00f,True),(rf(19),rf(2900),False)),1),
                 FieldRecord(tuple((rf(28+i),i+1,True)for i in range(3)),2),
                 FieldRecord(tuple((rf(31+i),i+4,True)for i in range(3)),3),
                 CoreRecord(O.COMMIT_FIELDS,yes=4),
                 FieldRecord(((rf(19),7,True),),5),CoreRecord(O.COMMIT_FIELDS,yes=6),
                 CoreRecord(O.EQ_BRANCH,a=rf(18),b=rf(2901),yes=7,no=8),
                 CoreRecord(O.STOP_OK,yes=7),CoreRecord(O.STOP_INVALID,yes=8)]
        chip=build(program,rom_layout='byte_pages');packets=[]
        for row in(2,3,414):
            batch=[]
            for claim in(65535,65534):
                words={18:123,19:456,2900:0xabcd,2901:claim}
                values=[words.get(7*row+slot,0)for slot in range(7)]
                payload=[v>>bit&1 for v in values for bit in range(16)]+[0]*14
                batch.append(chip.packet(boot=[1],pending_row=[row>>bit&1 for bit in range(9)],pending_enable=[1],pending_payload=payload))
            packets.append(torch.stack(batch))
        masks={'full_attention':None,'linear_attention':None};counts=[]
        with torch.no_grad():
            boot=chip.embeddings(torch.stack(packets,dim=1))
            out=chip.model(inputs_embeds=boot,past_key_values=chip.new_cache(),use_cache=True,position_ids=torch.zeros(2,len(packets),dtype=torch.long),attention_mask=masks)
            cache=out.past_key_values;state=chip.embeddings(torch.zeros(2,1,chip.slots.next-13))
            for _ in range(46):
                out=chip.model(inputs_embeds=state,past_key_values=cache,use_cache=True,output_hidden_states=True,position_ids=torch.zeros(2,1,dtype=torch.long),attention_mask=masks)
                cache=out.past_key_values;state=out.hidden_states[-2]
                counts.append(int(state[0,0,chip.slots.groups['dirty_count']].float().matmul(2.**torch.arange(10))))
        word=lambda b:sum(int(v)<<i for i,v in enumerate(b))
        self.assertEqual([word(row[16:32])for row in out.logits[:,0].float().tolist()],[1,2])
        self.assertEqual(max(counts),8);self.assertEqual(counts[-1],0)
        from leanputer.native_vendor.qwenputer.ir import A_BIT
        for h in chip.report['rf_heads']:
            if h['page']:continue
            stored=cache.layers[h['layer']].recurrent_states[0][:,0,2,2:128]/A_BIT
            self.assertEqual([[word(values[64:80]),word(values[80:96])]for values in stored.float().tolist()],[[65535,7],[65535,7]])
            shadow=cache.layers[h['layer']].recurrent_states[0][:,0,3,114:121]/A_BIT
            self.assertEqual(shadow.sum().item(),0)
            extra=cache.layers[h['layer']].recurrent_states[0][:,0,4,2:98]/A_BIT
            self.assertEqual([[word(v[i:i+16])for i in range(0,96,16)]for v in extra.float().tolist()],[[1,2,3,4,5,6]]*2)
        print(chip.report,flush=True)

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
        from dataclasses import replace
        program=[replace(r,yes=r.yes+5*int(r.yes>=7),no=r.no+5*int(r.no>=7))for r in program]
        program[7:7]=[CoreRecord(O.HEAP_ROW_READ,dest=rf(504*7),a=rf(1),yes=8),CoreRecord(O.FRAME_ROW_READ,dest=rf(505*7),a=rf(3),yes=9),CoreRecord(O.CONTEXT_ROW_READ,dest=rf(506*7),a=rf(4),yes=10),CoreRecord(O.DECLARATION_ROW_READ,dest=rf(507*7),a=rf(5),yes=11),CoreRecord(O.CLEAR_RF_ROW,dest=rf(510*7),yes=12)]
        program[6]=replace(program[6],yes=7)
        chip=build(program,rom_layout='byte_pages',compact_attention=True)
        packets=[]
        for kind,address in((0,0),(0,1),(0,504),(0,505),(0,506),(0,507),(0,510),(1,273),(2,19),(3,5),(4,1)):
            batch=[]
            for claim in(65535,65534):
                words={1:273,2:65535,3:19,4:5,5:1,6:claim,8:0x1234}
                values=[words.get(address*7+slot,0)for slot in range(7)]if kind==0 else ([11,22,33,44,0x1234,66]if kind==4 else [11,22,33,44,55,66])
                if kind==0 and address==510:values=[11,22,33,44,55,66,77]
                if kind==0 and 504<=address<=507:values=[100*(address-503)+i+1 for i in range(7)]
                payload=[(value>>bit)&1 for value in values for bit in range(16)];payload += [1 if kind==0 and (address==510 or 504<=address<=507)else 0]*(126-len(payload))
                batch.append(chip.packet(boot=[1],pending_kind=[kind>>bit&1 for bit in range(3)],pending_row=[address>>bit&1 for bit in range(9)],pending_enable=[1],pending_payload=payload))
            packets.append(torch.stack(batch))
        masks={'full_attention':None,'linear_attention':None}
        with torch.no_grad():
            boot=chip.embeddings(torch.stack(packets,dim=1))
            out=chip.model(inputs_embeds=boot,past_key_values=chip.new_cache(),use_cache=True,position_ids=torch.zeros(2,len(packets),dtype=torch.long),attention_mask=masks)
            cache=out.past_key_values;state=chip.embeddings(torch.zeros(2,1,chip.slots.next-13))
            for _ in range(30):
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
        for head in chip.report['rf_heads']:
            if head['page']!=3:continue
            memory=cache.layers[head['layer']].recurrent_states[0][:,0]
            self.assertEqual(memory[:,126,2:].sum().item(),0)
            for row,expected in ((504,[11,65535,33,44,105,106,107]),(505,[11,22,65535,44,55,66,207]),(506,[65535,302,303,304,305,306,307]),(507,[11,22,33,44,0x1234,66,407])):
                values=(memory[:,row-384,2:128]/A_BIT).float().tolist()
                self.assertEqual([[word(v[i:i+16])for i in range(0,112,16)]for v in values],[expected,expected])
                self.assertTrue(all(v==1 for values_row in values for v in values_row[112:]))
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
        locations={(h['port'],h['page']):h['layer']for h in chip.report['rf_heads']}
        for page in range(chip.report['rf_rows_per_copy']//128):
            baseline=cache.layers[locations[0,page]].recurrent_states[0]
            for port in(1,2):self.assertTrue(torch.equal(baseline,cache.layers[locations[port,page]].recurrent_states[0]))
        print(chip.report,flush=True)
