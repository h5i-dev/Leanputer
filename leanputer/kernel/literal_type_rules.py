"""Shared weighted Literal.type binding check for the genuine literal types.

Ordinary formation is never dispatched here. Callers supply the fixed Nat or
String hook spelling; name interning, lookup, scheme checks and conversion are
one common algorithm. Constructor/expansion interfaces are checked separately
when a reduction actually needs them.
"""
from .arena import Tag
from .native_cells import CellTag as C,VectorKind as V
from .traversal_machine import Task
from .quotient_templates import Ref,name_syntax


def emit_type_binding(c,controller,start,prefix,parts):
    at,go,call,store,check=controller;r,n=c.r,c.read['node']
    key=lambda suffix:prefix+'_'+suffix
    value=lambda suffix:r[key(suffix)]
    def setgo(g,pc,**kw):go(g,pc,**{key(k):v for k,v in kw.items()})
    ready=c.OR(c.NOT(c.eq(value('type_validated'),0)),c.NOT(c.eq(value('validated'),0)))
    g=at(start);c.ret(c.AND(g,ready),1);setgo(c.AND(g,c.NOT(ready)),start+1,name_base=r['free'])
    syntax,path=name_syntax(parts)
    def ptr(v):return c.add(value('name_base'),v.index)if isinstance(v,Ref)else v
    for i,row in enumerate(syntax.rows):store(at(start+1+i),tuple(ptr(v)for v in row),start+2+i)
    call(at(start+1+len(syntax.rows)),start+2+len(syntax.rows),Task.INTERN_NAME_PATH,ptr(path))
    base=start+30
    setgo(at(start+2+len(syntax.rows)),base,symbol_type=r['r'])
    store(at(base),(C.VECTOR,0,0,V.LEVELS),base+1,**{key('infer_empty'):r['free']})
    store(at(base+1),(Tag.CONST,value('symbol_type'),value('infer_empty'),0),base+2,**{key('type'):r['free']})
    store(at(base+2),(C.LEVEL_SUCC,r['kernel_zero'],0,0),base+3,**{key('infer_level'):r['free']})
    store(at(base+3),(Tag.SORT,value('infer_level'),0,0),base+4,**{key('expected_type'):r['free']})
    call(at(base+4),base+5,Task.ENV_LOOKUP,0,query_symbol=value('symbol_type'),lookup_head=c.mux(c.eq(r['typing_active'],0),r['env_head'],r['typing_head']))
    go(at(base+5),base+6,x=r['r'])
    setgo(at(base+6,C.CHECKED_SIGNATURE),base+7,check_type=n['b']);go(at(base+6,C.CHECKED_SIGNATURE),base+7,x=n['c'])
    go(at(base+7,C.CHECKED_SCHEME),base+8,x=n['a'])
    valid=c.AND(c.eq(n['c'],V.SYMBOLS),c.eq(n['a'],0),c.eq(n['b'],0))
    # Both controller adapters report an unavailable/incompatible binding as GAP.
    g=check(at(base+8,C.VECTOR),valid)
    call(g,base+9,Task.CONVERT_POSITIVE,value('check_type'),peer=value('expected_type'))
    g=check(at(base+9),c.NOT(c.eq(r['r'],0)));c.emit(g,**{key('type_validated'):1});c.ret(g,1)
