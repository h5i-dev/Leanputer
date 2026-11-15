"""Launch scheduling for UNMODIFIED stock forward/cache and identity feedback.

No instruction decode, circuit executor, host semantics or cache implementation.
CUDA graphs capture the same PyTorch operations the stock model normally runs.
"""
import time
import torch


def cache_tensors(cache):
    result=[]
    for layer in cache.layers:
        for name in('conv_states','recurrent_states','keys','values','cumulative_length'):
            states=getattr(layer,name,{})
            values=[states]if isinstance(states,torch.Tensor)else states.values()if isinstance(states,dict)else states or []
            result.extend(value for value in values if isinstance(value,torch.Tensor))
    return result


def snapshot(cache,state):
    metadata=[getattr(layer,'cumulative_length_int',None)for layer in cache.layers]
    return [value.clone()for value in cache_tensors(cache)],state.clone(),metadata


def restore(cache,state,saved):
    tensors,initial,metadata=saved;current=cache_tensors(cache)
    if len(current)!=len(tensors):raise ValueError('stock cache tensor layout changed')
    for dest,value in zip(current,tensors):dest.copy_(value)
    state.copy_(initial)
    for layer,value in zip(cache.layers,metadata):
        if value is not None:layer.cumulative_length_int=value


class StockCudaGraph:
    def __init__(self,model,cache,state,progress=None):
        if state.device.type!='cuda':raise ValueError('stock CUDA capture requires CUDA tensors')
        started=time.perf_counter();self.state=state;self.cache=cache
        self.positions=torch.zeros(state.shape[:2],dtype=torch.long,device=state.device)
        self.masks={'full_attention':None,'linear_attention':None}
        self.addresses=[value.data_ptr()for value in cache_tensors(cache)]
        with torch.inference_mode():
            saved=snapshot(cache,state)
            stream=torch.cuda.Stream(device=state.device);stream.wait_stream(torch.cuda.current_stream(state.device))
            with torch.cuda.stream(stream):
                for index in range(3):
                    restore(cache,state,saved)
                    if progress:progress(dict(event='warmup-start',index=index,seconds=time.perf_counter()-started))
                    model(inputs_embeds=state,past_key_values=cache,use_cache=True,position_ids=self.positions,attention_mask=self.masks,output_hidden_states=True)
                    if progress:progress(dict(event='warmup-returned',index=index,seconds=time.perf_counter()-started))
            torch.cuda.current_stream(state.device).wait_stream(stream);torch.cuda.synchronize(state.device)
            restore(cache,state,saved)
            self.graph=torch.cuda.CUDAGraph()
            if progress:progress(dict(event='capture-start',seconds=time.perf_counter()-started))
            with torch.cuda.graph(self.graph),torch.inference_mode():
                output=model(inputs_embeds=state,past_key_values=cache,use_cache=True,position_ids=self.positions,attention_mask=self.masks,output_hidden_states=True)
                state.copy_(output.hidden_states[-2])
            self.logits=output.logits
            torch.cuda.synchronize(state.device);restore(cache,state,saved)
        if self.addresses!=[value.data_ptr()for value in cache_tensors(cache)]:raise ValueError('stock cache addresses changed during capture')
        self.setup_seconds=time.perf_counter()-started

    def replay(self):self.graph.replay()
