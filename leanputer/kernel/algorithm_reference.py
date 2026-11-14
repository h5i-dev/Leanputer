"""Development interpreter for fixed Boolean rule definitions.

Never imported by a native runner: compiler lowering calls the rule definitions
with RuleCompiler instead. This adapter evaluates only word/guard/memory writes;
it does not infer, normalize, specialize expressions, or approve declarations.
Algorithm expectations must be checked against the independent kernel SPEC.
"""
from .traversal_machine import Mode, Outcome, Reason


class ReferenceRules:
    def __init__(self, machine):
        self.state, self.cfg = machine.state, machine.cfg
        self.r = dict(machine.state['regs'])
        self.width = self.cfg.word_bits
        self.mask = (1 << self.width)-1
        r = self.r
        node = machine.state['heap'][r['x']] if 0 <= r['x'] < self.cfg.heap else [0]*4
        frame = machine.state['stack'][r['sp']-1] if r['sp'] else [0]*6
        self.read = {'node': dict(zip(('tag','a','b','c'),node)),
            'frame': dict(zip(('phase','original','depth','task','first','second'),frame))}
        self.updates, self.writes = {}, {}
        self.active = r['status'] == Outcome.RUNNING

    def AND(self, *xs): return int(all(xs))
    def OR(self, *xs): return int(any(xs))
    def NOT(self, x): return int(not x)
    def eq(self, x, y): return int(x == y)
    def lt(self, x, y): return int(x < y)
    def add(self, x, y): return (x+y)&self.mask
    def sub(self, x, y): return (x-y)&self.mask
    def mux(self, guard, x, y): return x if guard else y
    def word_low_bits(self,value,count): return value&((1<<count)-1)
    def word_lsb(self,value): return value&1
    def word_shr1(self,value): return value>>1
    def word_shl1(self,value): return (value<<1)&self.mask
    def mode(self, mode): return int(self.active and self.r['mode'] == mode)
    def task(self, task): return int(self.r['task'] == task)
    def tag(self, *tags): return int(self.read['node']['tag'] in tags)

    def emit(self, guard, **updates):
        if not guard: return
        for key, value in updates.items():
            value = int(value)
            if key in self.updates and self.updates[key] != value:
                raise AssertionError(('overlapping fixed rules', key, self.updates[key], value))
            self.updates[key] = value

    def stop(self, guard, status, reason=Reason.NONE):
        self.emit(guard, status=status, reason=reason)

    def ret(self, guard, value): self.emit(guard, mode=Mode.RETURN, r=value)

    def write(self, bank, guard, address, row):
        if not guard: return
        if bank in self.writes: raise AssertionError(('overlapping fixed writes', bank))
        self.writes[bank] = (int(address), list(map(int,row)))

    def checked_add(self, guard, x, y):
        overflow = x+y > self.mask
        self.stop(guard and overflow, Outcome.RESOURCE, Reason.INDEX)
        return int(guard and not overflow), self.add(x,y)

    def apply(self):
        self.state['regs'].update(self.updates)
        for bank, (address,row) in self.writes.items(): self.state[bank][address] = row
