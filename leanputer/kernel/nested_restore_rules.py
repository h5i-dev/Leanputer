"""Pinned restore_nested expression wrapper and fixed preorder callback.

Restores family applications, constructor parameters/universes and auxiliary
recursor names. It never checks or publishes declarations. Entire generated
schemes and RHSs must subsequently pass the transaction's restored checks.
"""
from enum import IntEnum
from .arena import Tag
from .native_cells import CellTag as C, VectorKind as V
from .traversal_machine import Mode,Task,Outcome,Reason


class E(IntEnum):
    INIT=0; OPENED=1; REWRITTEN=2; FOLDED=3


class P(IntEnum):
    INIT=0; RENAME=1; RENAMED=2; SPINE=3; FUNCTION=4; ARGS=5; FAMILY=6
    CTOR_CELL=7; CTOR=8; TEMPLATE=9; INSTANTIATED=10; TRAILING=11; FINISH=12
    ORIGINAL_SPINE=13; ORIGINAL_HEAD=14; CTOR_CONST=15; CTOR_PARAMS=16; CTOR_TRAILING=17
    RENAME_CONST=18; ORIGINAL_PARAMETERS=19; ORIGINAL_APPLIED=20


def emit_rules(c):
    r,n,f=c.r,c.read['node'],c.read['frame'];top=c.sub(r['sp'],1)
    def controller(task,pcname):
        active=c.AND(c.task(task),c.mode(Mode.WALK))
        def at(pc,tag=None):
            g=c.AND(active,c.eq(r[pcname],pc))
            if tag is None:return g
            valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(tag))
            c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);return c.AND(g,valid)
        def go(g,pc,**kw):c.emit(g,**{pcname:pc},**kw)
        def call(g,pc,subtask,x,mode=Mode.WALK,**kw):
            room=c.lt(r['sp'],c.cfg.stack);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.STACK);g=c.AND(g,room)
            c.write('stack',g,r['sp'],(0,pc,0,task,0,0))
            c.emit(g,sp=c.add(r['sp'],1),task=subtask,mode=mode,x=x,depth=0,**kw)
        def store(g,row,pc,**kw):
            room=c.lt(r['free'],c.cfg.heap);c.stop(c.AND(g,c.NOT(room)),Outcome.RESOURCE,Reason.HEAP);g=c.AND(g,room)
            c.write('heap',g,r['free'],row);go(g,pc,free=c.add(r['free'],1),**kw)
        ret=c.AND(c.mode(Mode.RETURN),c.NOT(c.eq(r['sp'],0)),c.eq(f['task'],task))
        c.emit(ret,sp=top,task=task,mode=Mode.WALK,x=r['r'],**{pcname:f['original']})
        return at,go,call,store
    at,go,call,store=controller(Task.RESTORE_NESTED_EXPR,'restore_expr_pc')
    g=at(E.INIT)
    expr=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.NOT(c.lt(n['tag'],Tag.BVAR)),c.NOT(c.lt(Tag.MDATA,n['tag'])))
    binder=c.OR(c.eq(r['stage_parameter_count'],0),c.tag(Tag.PI,Tag.LAM))
    c.stop(c.AND(g,c.NOT(c.AND(expr,binder))),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,expr,binder)
    c.emit(g,restore_parameter_base=r['ctx'],restore_prefix_tag=c.mux(c.tag(Tag.LAM),Tag.LAM,Tag.PI),rewrite_restoring=1)
    call(g,E.OPENED,Task.OPEN_RAW_PREFIX,r['x'],raw_prefix_count=r['stage_parameter_count'],open_tag=c.mux(c.tag(Tag.LAM),Tag.LAM,Tag.PI))
    g=at(E.OPENED);c.emit(g,restore_parameter_end=r['ctx'])
    call(g,E.REWRITTEN,Task.REWRITE_NESTED,r['r'],rewrite_pc=0)
    call(at(E.REWRITTEN),E.FOLDED,Task.FOLD_TELESCOPE,r['r'],Mode.FOLD_SELECT,fold_body=r['r'],fold_base=r['restore_parameter_base'],fold_tag=r['restore_prefix_tag'])
    g=at(E.FOLDED);c.emit(g,rewrite_restoring=0);c.ret(g,r['r'])

    at,go,call,store=controller(Task.RESTORE_NESTED_CALLBACK,'restore_cb_pc')
    g=at(P.INIT);c.emit(g,restore_cb_root=r['x'],restore_cb_rename=r['restore_rec_map'])
    go(c.AND(g,c.tag(Tag.CONST)),P.RENAME,restore_cb_symbol=n['a'],restore_cb_levels=n['b'],x=r['restore_rec_map'])
    call(c.AND(g,c.NOT(c.tag(Tag.CONST))),P.SPINE,Task.APPLICATION_SPINE,r['x'])
    g=at(P.RENAME);empty=c.eq(r['restore_cb_rename'],0)
    call(c.AND(g,empty),P.SPINE,Task.APPLICATION_SPINE,r['restore_cb_root'])
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.NESTED_REC_MAP))
    c.stop(c.AND(g,c.NOT(empty),c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,c.NOT(empty),valid)
    same=c.eq(n['a'],r['restore_cb_symbol'])
    go(c.AND(g,same),P.RENAME_CONST,restore_cb_new_symbol=n['b'])
    go(c.AND(g,c.NOT(same)),P.RENAME,restore_cb_rename=n['c'],x=n['c'])
    store(at(P.RENAME_CONST),(Tag.CONST,r['restore_cb_new_symbol'],r['restore_cb_levels'],0),P.RENAMED,restore_cb_result=r['free'])
    c.ret(at(P.RENAMED),r['restore_cb_result'])
    go(at(P.SPINE),P.FUNCTION,x=r['r'])
    g=at(P.FUNCTION,C.APPLICATION_SPINE);go(g,P.ARGS,restore_cb_function=n['a'],restore_cb_arguments=n['b'],x=n['b'])
    g=at(P.ARGS,C.VECTOR)
    valid=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,valid)
    go(g,P.ORIGINAL_HEAD,restore_cb_argument_count=n['a'],x=r['restore_cb_function'],restore_cb_lookup=r['stage_maps'])
    g=at(P.ORIGINAL_HEAD);constant=c.tag(Tag.CONST)
    c.ret(c.AND(g,c.NOT(constant)),0)
    go(c.AND(g,constant),P.FAMILY,restore_cb_symbol=n['a'],restore_cb_constructor=0,x=r['stage_maps'])
    g=at(P.FAMILY);empty=c.eq(r['restore_cb_lookup'],0)
    go(c.AND(g,empty),P.CTOR_CELL,restore_cb_lookup=r['stage_ctor_maps'],x=r['stage_ctor_maps'])
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.NESTED_SPECIALIZATION))
    c.stop(c.AND(g,c.NOT(empty),c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,c.NOT(empty),valid)
    same=c.eq(n['b'],r['restore_cb_symbol'])
    go(c.AND(g,same),P.TEMPLATE,restore_cb_template=n['a'])
    go(c.AND(g,c.NOT(same)),P.FAMILY,restore_cb_lookup=n['c'],x=n['c'])
    g=at(P.CTOR_CELL);empty=c.eq(r['restore_cb_lookup'],0);c.ret(c.AND(g,empty),0)
    valid=c.AND(c.NOT(c.eq(r['x'],0)),c.lt(r['x'],r['free']),c.tag(C.VECTOR_CELL))
    c.stop(c.AND(g,c.NOT(empty),c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX);g=c.AND(g,c.NOT(empty),valid)
    go(g,P.CTOR,restore_cb_next=n['b'],x=n['a'])
    g=at(P.CTOR,C.NESTED_CONSTRUCTOR_MAP);same=c.eq(n['a'],r['restore_cb_symbol'])
    go(c.AND(g,c.NOT(same)),P.CTOR_CELL,restore_cb_lookup=r['restore_cb_next'],x=r['restore_cb_next'])
    go(c.AND(g,same),P.ORIGINAL_SPINE,restore_cb_constructor=n['b'],x=n['c'])
    g=at(P.ORIGINAL_SPINE,C.NESTED_SPECIALIZATION);go(g,P.TEMPLATE,restore_cb_template=n['a'])
    g=at(P.TEMPLATE);enough=c.NOT(c.lt(r['restore_cb_argument_count'],r['stage_parameter_count']))
    c.stop(c.AND(g,c.NOT(enough)),Outcome.INVALID,Reason.SYNTAX)
    call(c.AND(g,enough),P.INSTANTIATED,Task.INSTANTIATE_SCOPE,r['restore_cb_template'],abstract_base=r['restore_parameter_base'],abstract_end=r['restore_parameter_end'])
    g=at(P.INSTANTIATED);ctor=c.NOT(c.eq(r['restore_cb_constructor'],0))
    call(c.AND(g,c.NOT(ctor)),P.FINISH,Task.APPLY_VECTOR_SLICE,r['restore_cb_arguments'],slice_body=r['r'],slice_start=r['stage_parameter_count'],slice_take=c.sub(r['restore_cb_argument_count'],r['stage_parameter_count']))
    call(c.AND(g,ctor),P.CTOR_CONST,Task.APPLICATION_SPINE,r['r'])
    go(at(P.CTOR_CONST),P.CTOR_PARAMS,x=r['r'])
    g=at(P.CTOR_PARAMS,C.APPLICATION_SPINE);go(g,P.CTOR_TRAILING,restore_cb_original_args=n['b'],x=n['a'])
    g=at(P.CTOR_TRAILING,Tag.CONST)
    store(g,(Tag.CONST,r['restore_cb_constructor'],n['b'],0),P.TRAILING,restore_cb_result=r['free'])
    go(at(P.TRAILING),P.ORIGINAL_PARAMETERS,x=r['restore_cb_original_args'])
    g=at(P.ORIGINAL_PARAMETERS,C.VECTOR)
    valid=c.AND(c.eq(n['c'],V.REFERENCES),c.eq(c.mux(c.eq(n['a'],0),0,1),c.mux(c.eq(n['b'],0),0,1)))
    c.stop(c.AND(g,c.NOT(valid)),Outcome.INVALID,Reason.SYNTAX)
    call(c.AND(g,valid),P.ORIGINAL_APPLIED,Task.APPLY_VECTOR_SLICE,r['restore_cb_original_args'],slice_body=r['restore_cb_result'],slice_start=0,slice_take=n['a'])
    call(at(P.ORIGINAL_APPLIED),P.FINISH,Task.APPLY_VECTOR_SLICE,r['restore_cb_arguments'],slice_body=r['r'],slice_start=r['stage_parameter_count'],slice_take=c.sub(r['restore_cb_argument_count'],r['stage_parameter_count']))
    c.ret(at(P.FINISH),r['r'])


def step(machine):
    from .algorithm_reference import ReferenceRules
    c=ReferenceRules(machine);emit_rules(c);c.apply()
