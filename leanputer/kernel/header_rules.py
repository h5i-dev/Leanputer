"""Lower the general previous-environment inductive-header algorithm.

Private family records are generated only after weighted header checking. They
are not published to committed Γ. Remaining block stages still GAP in source.
"""
from .arena import Tag
from .native_cells import CellTag,VectorKind
from .traversal_machine import (Mode,Task,Outcome,Reason,CALL_HEADER_PARAMETERS,
    CALL_HEADER_NAME,CALL_HEADER_DUPLICATE_GLOBAL,CALL_HEADER_DUPLICATE_PRIVATE,
    CALL_HEADER_SCOPE,CALL_HEADER_INFER,CALL_HEADER_TYPE_WHNF,
    CALL_HEADER_OPEN_PARAMETERS,CALL_HEADER_CONSUME,CALL_HEADER_INDICES,CALL_HEADER_LEVEL,CALL_HEADER_FORMAL_LEVELS)

PRIVATE_PHASES=tuple(range(CALL_HEADER_PARAMETERS,CALL_HEADER_LEVEL+1))+(CALL_HEADER_FORMAL_LEVELS,)


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame']
    a,b,x,result=n['a'],n['b'],r['x'],r['r']
    top=c.sub(r['sp'],1);returning=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)))
    at=lambda phase:c.AND(returning,c.eq(f['phase'],phase))
    def call(guard,phase,task,x,mode=Mode.WALK,**updates):
        c.write('stack',guard,top,(phase,0,0,Task.ANALYZE_HEADERS,0,0))
        c.emit(guard,task=task,x=x,mode=mode,depth=0,**updates)
    call(at(CALL_HEADER_PARAMETERS),CALL_HEADER_FORMAL_LEVELS,Task.FORMAL_LEVELS,0)
    params=at(CALL_HEADER_FORMAL_LEVELS)
    c.emit(params,header_levels=result)
    end=c.g.add(c.g.fit(r['ctx'],c.width+1),c.g.fit(r['header_parameter_count'],c.width+1))
    enough=c.NOT(c.g.lt(c.g.const(c.cfg.context,c.width+1),end))
    c.stop(c.AND(params,c.NOT(enough)),Outcome.RESOURCE,Reason.CONTEXT)
    c.emit(c.AND(params,enough),task=Task.ANALYZE_HEADERS,mode=Mode.HEADER_VECTOR,x=r['header_vector'],
        header_parameter_base=r['ctx'],header_parameter_end=end[:c.width],local_base=r['ctx'])
    call(at(CALL_HEADER_NAME),CALL_HEADER_DUPLICATE_GLOBAL,Task.ENV_LOOKUP,0,query_symbol=r['header_symbol'],lookup_head=r['env_head'])
    for phase in (CALL_HEADER_DUPLICATE_GLOBAL,CALL_HEADER_DUPLICATE_PRIVATE):
        c.stop(c.AND(at(phase),c.NOT(c.eq(result,0))),Outcome.INVALID,Reason.DUPLICATE_DECLARATION)
    call(c.AND(at(CALL_HEADER_DUPLICATE_GLOBAL),c.eq(result,0)),CALL_HEADER_DUPLICATE_PRIVATE,Task.ENV_LOOKUP,0,
        query_symbol=r['header_symbol'],lookup_head=r['header_head'])
    call(c.AND(at(CALL_HEADER_DUPLICATE_PRIVATE),c.eq(result,0)),CALL_HEADER_SCOPE,Task.EXPR_SCOPE,r['header_type'])
    call(at(CALL_HEADER_SCOPE),CALL_HEADER_INFER,Task.INFER,r['header_type'],local_base=r['header_parameter_base'])
    call(at(CALL_HEADER_INFER),CALL_HEADER_TYPE_WHNF,Task.BETA_ZETA,result,Mode.BETA_ZETA)
    c.emit(at(CALL_HEADER_TYPE_WHNF),task=Task.ANALYZE_HEADERS,mode=Mode.HEADER_TYPE_SORT,x=result)
    call(c.OR(at(CALL_HEADER_OPEN_PARAMETERS),at(CALL_HEADER_CONSUME)),CALL_HEADER_INDICES,Task.OPEN_TELESCOPE,result,
        Mode.TELESCOPE,open_tag=Tag.PI,bounded=0,limit=0)
    c.emit(at(CALL_HEADER_INDICES),task=Task.ANALYZE_HEADERS,mode=Mode.HEADER_SORT,x=result)
    c.stop(c.AND(at(CALL_HEADER_LEVEL),c.eq(result,0)),Outcome.INVALID,Reason.UNIVERSE)
    c.emit(c.AND(at(CALL_HEADER_LEVEL),c.NOT(c.eq(result,0))),task=Task.ANALYZE_HEADERS,mode=Mode.HEADER_STORE_FAMILY)
    active=c.task(Task.ANALYZE_HEADERS)
    at_mode=lambda mode:c.AND(active,c.mode(mode))
    init=at_mode(Mode.WALK);room=c.lt(r['sp'],c.cfg.stack)
    c.stop(c.AND(init,c.NOT(room)),Outcome.RESOURCE,Reason.STACK)
    init=c.AND(init,room)
    c.write('stack',init,r['sp'],(CALL_HEADER_PARAMETERS,0,0,Task.ANALYZE_HEADERS,0,0))
    c.emit(init,sp=c.add(r['sp'],1),task=Task.LOAD_PARAMETERS,x=r['header_parameters'],
        header_parameter_count=a,header_vector=b,header_head=0,header_seen=0)
    header=at_mode(Mode.HEADER_VECTOR)
    valid=c.AND(c.eq(n['c'],VectorKind.REFERENCES),c.NOT(c.eq(a,0)),c.NOT(c.eq(b,0)))
    c.stop(c.AND(header,c.NOT(valid)),Outcome.INVALID,Reason.INVALID_DECLARATION)
    c.emit(c.AND(header,valid),mode=Mode.HEADER_CELL,x=b,header_remaining=a)
    cell=at_mode(Mode.HEADER_CELL);more=c.lt(1,r['header_remaining'])
    valid=c.AND(c.NOT(c.eq(r['header_remaining'],0)),c.eq(c.mux(c.eq(b,0),0,1),c.mux(more,1,0)))
    c.stop(c.AND(cell,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    c.emit(c.AND(cell,valid),mode=Mode.HEADER_FAMILY,x=a,header_next=b)
    family=at_mode(Mode.HEADER_FAMILY)
    ptr=lambda p:c.AND(c.NOT(c.eq(p,0)),c.lt(p,r['free']))
    valid=c.AND(c.NOT(c.eq(a,0)),ptr(b),ptr(n['c']))
    c.stop(c.AND(family,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    family=c.AND(family,valid)
    c.emit(family,header_symbol=a,header_type=b,header_raw=x)
    call(family,CALL_HEADER_NAME,Task.CHECK_NAME,r['symbols_root'],query_symbol=a)
    def ensure_sort(guard):
        stable=c.tag(Tag.PI,Tag.LAM,Tag.BVAR,Tag.LOCAL,Tag.NAT,Tag.STRING)
        c.stop(c.AND(guard,c.NOT(c.tag(Tag.SORT)),stable),Outcome.INVALID,Reason.EXPECT_SORT)
        c.stop(c.AND(guard,c.NOT(c.tag(Tag.SORT)),c.NOT(stable)),Outcome.GAP,Reason.GAP_CONVERSION)
        return c.AND(guard,c.tag(Tag.SORT))
    typed=ensure_sort(at_mode(Mode.HEADER_TYPE_SORT));first=c.eq(r['header_seen'],0)
    call(c.AND(typed,first),CALL_HEADER_OPEN_PARAMETERS,Task.OPEN_TELESCOPE,r['header_type'],Mode.TELESCOPE,
        open_tag=Tag.PI,bounded=1,limit=r['header_parameter_end'])
    call(c.AND(typed,c.NOT(first)),CALL_HEADER_CONSUME,Task.CONSUME_PARAMETERS,r['header_type'],
        reuse_base=r['header_parameter_base'],reuse_end=r['header_parameter_end'],reuse_whnf=1)
    tail=ensure_sort(at_mode(Mode.HEADER_SORT))
    c.emit(tail,header_indices=c.sub(r['ctx'],r['header_parameter_end']),header_current_level=a)
    c.emit(c.AND(tail,first),header_result_level=a,mode=Mode.HEADER_STORE_FAMILY)
    call(c.AND(tail,c.NOT(first)),CALL_HEADER_LEVEL,Task.LEVEL_EQUIVALENT,a,peer=r['header_result_level'])
    store=at_mode(Mode.HEADER_STORE_FAMILY)
    wide=c.g.add(c.g.fit(r['free'],c.width+1),c.g.const(4,c.width+1))
    enough=c.NOT(c.g.lt(c.g.const(c.cfg.heap,c.width+1),wide))
    c.stop(c.AND(store,c.NOT(enough)),Outcome.RESOURCE,Reason.HEAP)
    store=c.AND(store,enough)
    c.write('heap',store,r['free'],(CellTag.CHECKED_FAMILY,r['header_indices'],r['header_current_level'],r['header_raw']))
    c.emit(store,free=c.add(r['free'],1),header_meta=r['free'],mode=Mode.HEADER_STORE_SCHEME)
    store=at_mode(Mode.HEADER_STORE_SCHEME)
    c.write('heap',store,r['free'],(CellTag.CHECKED_SCHEME,r['header_parameters'],8,r['header_meta']))
    c.emit(store,free=c.add(r['free'],1),header_scheme=r['free'],mode=Mode.HEADER_STORE_SIGNATURE)
    store=at_mode(Mode.HEADER_STORE_SIGNATURE)
    c.write('heap',store,r['free'],(CellTag.CHECKED_SIGNATURE,r['header_symbol'],r['header_type'],r['header_scheme']))
    c.emit(store,free=c.add(r['free'],1),header_signature=r['free'],mode=Mode.HEADER_LINK)
    link=at_mode(Mode.HEADER_LINK)
    c.write('heap',link,r['free'],(CellTag.VECTOR_CELL,r['header_signature'],r['header_head'],0))
    c.emit(link,free=c.add(r['free'],1),header_head=r['free'],header_remaining=c.sub(r['header_remaining'],1),
        header_seen=c.add(r['header_seen'],1),ctx=r['header_parameter_end'])
    c.emit(c.AND(link,more),mode=Mode.HEADER_CELL,x=r['header_next'])
    c.emit(c.AND(link,c.NOT(more)),sp=top)
    c.ret(c.AND(link,c.NOT(more)),r['free'])
