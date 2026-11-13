"""Compile-time unsigned bit-vector expressions over Boolean circuit wires."""
from .circuit import Circuit
from .logic import CompiledLogic


class Builder:
    def __init__(self, names, optimized=True):
        self.c = Circuit()
        self.inputs = [self.c.input(name) for name in names]
        self.zero, self.one = self.c.OR(), self.c.AND()
        self.optimized = optimized

    def AND(self, *args):
        if self.optimized:
            if self.zero in args:
                return self.zero
            args = tuple(a for a in args if a != self.one)
            if not args:
                return self.one
        return self.c.AND(*args)

    def OR(self, *args):
        if self.optimized:
            if self.one in args:
                return self.one
            args = tuple(a for a in args if a != self.zero)
            if not args:
                return self.zero
        return self.c.OR(*args)

    def NOT(self, arg):
        if self.optimized:
            if arg == self.zero:
                return self.one
            if arg == self.one:
                return self.zero
        return self.c.NOT(arg)

    def const(self, value, width):
        if not 0 <= value < 1 << width:
            raise ValueError('constant does not fit bit-vector')
        return tuple(self.one if value & (1 << i) else self.zero for i in range(width))

    def fit(self, value, width):
        return tuple(value[:width]) + (self.zero,) * max(0, width-len(value))

    def eq(self, a, b):
        width = max(len(a), len(b))
        return self.AND(*(self.NOT(self.xor(x, y)) for x, y in zip(self.fit(a, width), self.fit(b, width))))

    def xor(self, x, y):
        if self.optimized and x == y:
            return self.zero
        return self.OR(self.AND(x, self.NOT(y)), self.AND(self.NOT(x), y))

    def add(self, a, b):
        width = max(len(a), len(b))
        if self.optimized:
            pairs = list(zip(self.fit(a, width), self.fit(b, width)))
            generate = [self.AND(x, y) for x, y in pairs]
            propagate = [self.xor(x, y) for x, y in pairs]
            carries = [self.zero] + [self.OR(*(self.AND(generate[j], *propagate[j+1:i]) for j in range(i)))
                                      for i in range(1, width)]
            return tuple(self.xor(p, carry) for p, carry in zip(propagate, carries))
        carry, result = self.zero, []
        for x, y in zip(self.fit(a, width), self.fit(b, width)):
            different = self.xor(x, y)
            result.append(self.xor(different, carry))
            carry = self.OR(self.AND(x, y), self.AND(different, carry))
        return tuple(result)

    def sub(self, a, b, borrow_in=False):
        width = max(len(a), len(b))
        if self.optimized:
            pairs = list(zip(self.fit(a, width), self.fit(b, width)))
            generate = [self.AND(self.NOT(x), y) for x, y in pairs]
            propagate = [self.NOT(self.xor(x, y)) for x, y in pairs]
            initial = self.one if borrow_in else self.zero
            borrows = [initial] + [self.OR(self.AND(initial, *propagate[:i]),
                                          *(self.AND(generate[j], *propagate[j+1:i]) for j in range(i)))
                                      for i in range(1, width+1)]
            result = tuple(self.xor(self.xor(x, y), borrow) for (x, y), borrow in zip(pairs, borrows))
            return result, borrows[-1]
        carry, result = self.zero if borrow_in else self.one, []
        for x, y in zip(self.fit(a, width), self.fit(b, width)):
            y = self.NOT(y)
            different = self.xor(x, y)
            result.append(self.xor(different, carry))
            carry = self.OR(self.AND(x, y), self.AND(different, carry))
        return tuple(result), self.NOT(carry)

    def lt(self, a, b):
        if self.optimized:
            width = max(len(a), len(b))
            pairs = list(zip(self.fit(a, width), self.fit(b, width)))
            equal = [self.NOT(self.xor(x, y)) for x, y in pairs]
            return self.OR(*(self.AND(self.NOT(x), y, *equal[i+1:]) for i, (x, y) in enumerate(pairs)))
        return self.sub(a, b)[1]

    def mux(self, condition, yes, no):
        width = max(len(yes), len(no))
        if self.optimized and condition in (self.one, self.zero):
            return self.fit(yes if condition == self.one else no, width)
        neg = self.NOT(condition)
        return tuple(x if self.optimized and x == y else self.OR(self.AND(condition, x), self.AND(neg, y))
                     for x, y in zip(self.fit(yes, width), self.fit(no, width)))

    def compile(self, outputs, target=None):
        if target is not None:
            return target(self.c, outputs)
        return CompiledLogic(self.c, outputs, prune=self.optimized)


def pack_words(words, widths):
    """Syntax/state serialization only, least significant bit first."""
    bits = []
    for value, width in zip(words, widths):
        if type(value) is not int or not 0 <= value < 1 << width:
            raise ValueError('state word outside encoding range')
        bits.extend(float(bool(value & (1 << i))) for i in range(width))
    return bits


def unpack_words(bits, widths):
    result, offset = [], 0
    for width in widths:
        result.append(sum(int(bits[offset+i]) << i for i in range(width)))
        offset += width
    return result
