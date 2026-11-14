"""Exact bounded-word operations emitted as ordinary stock SwiGLU units.

Unsigned comparison propagates a one-bit borrow from low to high bytes. Each
threshold argument lies in [-255,256], an exact BF16 integer domain. It does
not form a 16-bit number in a floating-point residual or narrow its precision.
"""
from .control_packing import PackedBit
from .native_vendor.qwenputer.expr import Expr


def digit_value(builder,bits,memo):
    """Reassemble contiguous packed pieces without unpacking canceled low bits."""
    result=Expr();start=0
    while start<len(bits):
        first=bits[start];end=start+1
        if isinstance(first,PackedBit):
            while end<len(bits) and isinstance(bits[end],PackedBit) and bits[end].feature.terms==first.feature.terms and bits[end].bit==first.bit+end-start:
                end+=1
            length=end-start
            if first.bit==0:
                value=first.feature
                for high in range(first.digit_bits-1,length-1,-1):
                    value=value-(1<<high)*PackedBit(first.feature,high,first.digit_bits,first.scope).realize(builder,memo)
            else:
                value=sum(((1<<i)*b.realize(builder,memo)for i,b in enumerate(bits[start:end])),Expr())
        else:value=first
        result=result+(1<<start)*value;start=end
    return result


def unsigned_lt(builder, left, right, memo):
    graph=builder.graph;one=graph.one
    width=max(len(left),len(right));left=list(left)+[Expr()]*(width-len(left));right=list(right)+[Expr()]*(width-len(right))
    borrow=Expr()
    for offset in range(0,width,8):
        delta=digit_value(builder,right[offset:offset+8],memo)-digit_value(builder,left[offset:offset+8],memo)+borrow
        borrow=builder.word_ffn([(1,one,delta),(-1,one,delta-one)],'word-lt/borrow')
    return borrow


def add_sub(builder,operation,left,right,borrow_in,memo):
    graph=builder.graph;one=graph.one
    width=max(len(left),len(right));left=list(left)+[Expr()]*(width-len(left));right=list(right)+[Expr()]*(width-len(right))
    carry=one if borrow_in else Expr();result=[]

    for offset in range(0,width,4):
        precision=min(4,width-offset);base=1<<precision
        a=digit_value(builder,left[offset:offset+precision],memo);b=digit_value(builder,right[offset:offset+precision],memo)
        if operation=='add':
            total=a+b+carry
            carry=builder.word_ffn([(1,one,total-(base-1)*one),(-1,one,total-base*one)],'word-add/carry')
            value=total-base*carry
        else:
            total=a-b-carry
            carry=builder.word_ffn([(1,one,-total),(-1,one,-total-one)],'word-sub/borrow')
            value=total+base*carry
        if builder.scope is not None:value=builder.word_ffn([(1,one,value)],'word-result')
        result.extend(PackedBit(value,bit,precision,builder.scope)for bit in range(precision))
    if operation=='sub':result.append(carry)
    return result


def equal(builder,left,right,memo):
    graph=builder.graph;one=graph.one
    width=max(len(left),len(right));left=list(left)+[Expr()]*(width-len(left));right=list(right)+[Expr()]*(width-len(right))
    flags=[]
    for offset in range(0,width,8):
        delta=digit_value(builder,left[offset:offset+8],memo)-digit_value(builder,right[offset:offset+8],memo)
        flags.append(builder.word_ffn([(1,one,delta+one),(-2,one,delta),(1,one,delta-one)],'word-eq'))
    return builder.gate('and',flags,'word-eq/all')


def select(builder,left,right,condition,memo):
    graph=builder.graph;one=graph.one
    width=max(len(left),len(right));left=list(left)+[Expr()]*(width-len(left));right=list(right)+[Expr()]*(width-len(right))
    result=[]
    yes,no=condition,one-condition
    if builder.scope is not None:
        guard=builder.scratch_guards[builder.scope]
        # Shared predicates read zero outside the owner even when the local
        # condition's physical slot contains a different owner's value.
        yes=graph.ffn([(1,condition,guard)],name='word-mux/yes',min_level=builder.barrier)
        no=graph.ffn([(1,one,guard-yes)],name='word-mux/no',min_level=builder.barrier)
    for offset in range(0,width,8):
        precision=min(8,width-offset)
        a=digit_value(builder,left[offset:offset+8],memo);b=digit_value(builder,right[offset:offset+8],memo)
        value=graph.ffn([(1,a,yes),(1,b,no)],name='word-mux',min_level=builder.barrier)
        graph.nodes[-1].scope=builder.scope
        if builder.scope is not None:graph.nodes[-1].scope_guard=builder.scratch_guards[builder.scope]
        result.extend(PackedBit(value,bit,precision,builder.scope)for bit in range(precision))
    return result
