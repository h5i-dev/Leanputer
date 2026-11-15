"""Direct source-preflight word circuits; compiler only, no runtime evaluator."""
from ..native_vendor.qwenputer.expr import Expr
from .stock_preflight import ControlChoice,DataPredicate


class PreflightCircuit:
    def __init__(self,builder,plan,inputs,invalid):
        self.builder=builder;self.g=builder.graph;self.plan=plan;self.inputs=inputs;self.invalid=invalid
        self.nodes={};self.choices={};self.selectors={};self.one=self.g.one;self.zero=Expr()

    def AND(self,values,name='preflight-and'):
        if any(not value.terms for value in values):return self.zero
        values=[v for v in values if v.terms!=self.one.terms]
        values=list({tuple(sorted(v.terms.items())):v for v in values}.values())
        if not values:return self.one
        if len(values)==1:return values[0]
        return self.builder.gate('and',values,name)

    def OR(self,values,name='preflight-or'):
        if any(v.terms==self.one.terms for v in values):return self.one
        values=[v for v in values if v.terms]
        values=list({tuple(sorted(v.terms.items())):v for v in values}.values())
        if not values:return self.zero
        if len(values)==1:return values[0]
        # Inputs need not be exclusive. 1-relu(1-sum) is Boolean OR.
        return self.one-self.g.ffn([(1,self.one,self.one-sum(values,Expr()))],name=name)

    def literal(self,value,width):return[self.one if value>>i&1 else self.zero for i in range(width)]
    def equal_const(self,word,value):return self.AND([bit if value>>i&1 else self.one-bit for i,bit in enumerate(word)],'preflight-eq-constant')
    def less_const(self,word,value):
        if value<=0:return self.zero
        if value>=1<<len(word):return self.one
        # The highest differing-bit cases are disjoint, including high bits.
        return sum((self.AND([self.one-word[i]]+[word[j]if value>>j&1 else self.one-word[j]for j in range(i+1,len(word))],'preflight-lt-constant')for i in range(len(word))if value>>i&1),Expr())

    def add(self,a,b,subtract=False):
        if subtract:b=[self.one-bit for bit in b]
        generate=[self.AND([x,y],'preflight-carry-generate')for x,y in zip(a,b)]
        propagate=[x+y-2*z for x,y,z in zip(a,b,generate)]
        carry=[self.one if subtract else self.zero]
        for end in range(1,len(a)+1):
            terms=([self.AND(propagate[:end],'preflight-initial-carry')]if subtract else[])
            terms += [self.AND([generate[j]]+propagate[j+1:end],'preflight-carry')for j in range(end)]
            carry.append(sum(terms,Expr()))
        return[p+c-2*self.AND([p,c],'preflight-sum-bit')for p,c in zip(propagate,carry)]

    def node(self,index,root=False):
        if index in self.nodes:return self.nodes[index]
        if not root and index in self.plan.actives:return self.normalized(self.plan.normalized[index])
        if index==self.plan.invalid:result=[self.invalid]
        else:
            n=self.plan.graph.nodes[index];op=n.op
            if op=='input':result=self.inputs[n.data]
            elif op=='const':result=self.literal(n.data,n.width)
            elif op in('all','any'):
                values=[self.node(i)[0]for i in n.args];result=[self.AND(values)if op=='all'else self.OR(values)]
            elif op=='not':result=[self.one-self.node(n.args[0])[0]]
            elif op in('eq','ult'):
                left,right=(self.plan.graph.nodes[i]for i in n.args)
                if right.op=='const':
                    a=self.node(n.args[0]);value=right.data
                    result=[self.equal_const(a,value)if op=='eq'else self.less_const(a,value)]
                elif left.op=='const':
                    b=self.node(n.args[1]);value=left.data
                    result=[self.equal_const(b,value)if op=='eq'else self.one-self.less_const(b,value+1)]
                else:
                    a,b=(self.node(i)for i in n.args)
                    equal=[self.one-x-y+2*self.AND([x,y],'preflight-eq-bit')for x,y in zip(a,b)]
                    result=[self.AND(equal)]if op=='eq'else[sum((self.AND([self.one-a[i],b[i]]+equal[i+1:],'preflight-order')for i in range(len(a))),Expr())]
            elif op in('add','sub'):
                a,b=(self.node(i)for i in n.args);result=self.add(a,b,op=='sub')
            elif op=='extend':result=self.node(n.args[0])+[self.zero]*(n.width-self.plan.graph.nodes[n.args[0]].width)
            elif op=='slice':result=self.node(n.args[0])[n.data:n.data+n.width]
            elif op=='splice':result=[self.node(i)[bit]for i,bit in zip(n.args,n.data)]
            elif op=='choose':
                condition=self.node(n.args[0])[0];a,b=(self.node(i)for i in n.args[1:])
                result=[self.g.ffn([(1,x,condition),(1,y,self.one-condition)],name='preflight-data-choice')for x,y in zip(a,b)]
            else:raise ValueError('unsupported source-preflight word operator '+op)
        self.nodes[index]=result;return result

    def selector(self,variable,low,high):
        key=variable,low,high
        if key not in self.selectors:
            word=self.inputs[self.plan.graph.nodes[variable].data]
            if low==high:value=self.equal_const(word,low)
            else:value=self.AND([self.one-self.less_const(word,low),self.less_const(word,high+1)],'preflight-control-interval')
            self.selectors[key]=value
        return self.selectors[key]

    def normalized(self,tree):
        if tree in self.choices:return self.choices[tree]
        if isinstance(tree,DataPredicate):result=self.node(tree.node,root=True)
        else:
            terms=[]
            for low,high,child in tree.cases:
                word=self.normalized(child)
                if not any(bit.terms for bit in word):continue
                selected=self.selector(tree.variable,low,high)
                terms.append([self.AND([selected,bit],'preflight-selected-predicate')for bit in word])
            width=len(self.normalized(tree.cases[0][2]));result=[sum((word[i]for word in terms),Expr())for i in range(width)]
        self.choices[tree]=result;return result

    def outputs(self):
        plan=self.plan;values={name:[]for name in plan.field_names};masks={name:[]for name in plan.field_names}
        for effect in plan.effects:
            guard=self.normalized(plan.normalized[effect.guard])[0]
            for name,index in effect.values:
                word=self.normalized(plan.normalized[index]);values[name].append([self.AND([guard,bit],'preflight-update-value')for bit in word]);masks[name].append(guard)
        words=[]
        for name in plan.field_names:words.append([self.OR([word[i]for word in values[name]],'preflight-update-or')for i in range(16)])
        words += [[self.OR(masks[name])]+[self.zero]*15 for name in plan.field_names]
        words.append(self.normalized(plan.normalized[plan.compiler.preflight_active])+[self.zero]*15)
        return words
