"""Stock graph implementations of bounded source-address operations."""
from ..native_vendor.qwenputer.expr import Expr


def affine_address_value(builder,a,b,c,code):
    g=builder.graph;one=g.one;total=24*one+sum(((1<<i)*code[60+i]for i in range(3)),Expr())
    for index,word in enumerate((a,b,c)):
        for bit in range(3):total+=g.ffn([((1<<bit),word[bit],code[54+2*index]),(-(1<<bit),word[bit],code[55+2*index])],name='affine-term')
    # Signed three-term modulo8. Shift by24 preserves the remainder and
    # places every possible total in[3,52], exact integers in bfloat16.
    carries=[g.ffn([(1,one,total-(8*k-1)*one),(-1,one,total-8*k*one)],name='affine-modulo')for k in range(1,7)]
    digit=total-8*sum(carries,Expr())
    from ..control_packing import PackedBit
    memo={};return[PackedBit(digit,i,3).realize(builder,memo)for i in range(3)]


def sparse_switch_pc(builder,tables,word,code,active):
    g=builder.graph;one=g.one;branches=[];memo={}
    for index,cases in enumerate(tables):
        selected=builder.gate('and',[active]+[bit if index>>i&1 else one-bit for i,bit in enumerate(code[96:112])],'sparse-table')
        for value,target in cases:
            if value not in memo:memo[value]=builder.gate('and',[bit if value>>i&1 else one-bit for i,bit in enumerate(word)],'sparse-key')
            branches.append((target,builder.gate('and',[selected,memo[value]],'sparse-case')))
    taken=sum((condition for target,condition in branches),Expr())
    return[g.ffn([(1,code[58+i],one-taken)]+[(1,one,condition)for target,condition in branches if target>>i&1],name='sparse-pc')for i in range(16)]
