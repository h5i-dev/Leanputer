"""Compile-time unsigned bit-vector expressions over Boolean circuit wires."""
from .circuit import Circuit
from .logic import CompiledLogic


class Builder:
    def __init__(self, names):
        self.c = Circuit()
        self.inputs = [self.c.input(name) for name in names]
        self.zero, self.one = self.c.OR(), self.c.AND()

    def const(self, value, width):
        if not 0 <= value < 1 << width:
            raise ValueError('constant does not fit bit-vector')
        return tuple(self.one if value & (1 << i) else self.zero for i in range(width))

    def fit(self, value, width):
        return tuple(value[:width]) + (self.zero,) * max(0, width-len(value))

    def eq(self, a, b):
        width = max(len(a), len(b))
        return self.c.AND(*(self.c.NOT(self.xor(x, y)) for x, y in zip(self.fit(a, width), self.fit(b, width))))

    def xor(self, x, y):
        return self.c.OR(self.c.AND(x, self.c.NOT(y)), self.c.AND(self.c.NOT(x), y))

    def add(self, a, b):
        width = max(len(a), len(b))
        carry, result = self.zero, []
        for x, y in zip(self.fit(a, width), self.fit(b, width)):
            different = self.xor(x, y)
            result.append(self.xor(different, carry))
            carry = self.c.OR(self.c.AND(x, y), self.c.AND(different, carry))
        return tuple(result)

    def sub(self, a, b):
        width = max(len(a), len(b))
        carry, result = self.one, []
        for x, y in zip(self.fit(a, width), self.fit(b, width)):
            y = self.c.NOT(y)
            different = self.xor(x, y)
            result.append(self.xor(different, carry))
            carry = self.c.OR(self.c.AND(x, y), self.c.AND(different, carry))
        return tuple(result), self.c.NOT(carry)

    def lt(self, a, b):
        return self.sub(a, b)[1]

    def mux(self, condition, yes, no):
        width = max(len(yes), len(no))
        neg = self.c.NOT(condition)
        return tuple(self.c.OR(self.c.AND(condition, x), self.c.AND(neg, y))
                     for x, y in zip(self.fit(yes, width), self.fit(no, width)))

    def compile(self, outputs):
        return CompiledLogic(self.c, outputs)


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
