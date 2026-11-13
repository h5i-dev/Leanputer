"""Symbolic universe operations from pinned Lean kernel/level.cpp.

Explicit work stacks implement normalize/is_equivalent/is_geq/is_not_zero.
Parameters stay symbolic during admission. Numeric grounding cannot stand in
for whether a universe is necessarily nonzero. This is executable spec code;
no native loader calls it and weighted level lowering is still a gap.
"""
from functools import cmp_to_key
from .arena import LevelTag


class LevelOps:
    def __init__(self, arena):
        self.a = arena
        self._normal = {}
        self._nonzero = {}

    def offset(self, ref):
        offset = 0
        while self.a.level_row(ref).tag == LevelTag.SUCC:
            self.a.tick()
            offset = self.a.word(offset+1)
            ref = self.a.level_row(ref).a
        return ref, offset

    def succ(self, ref, count=1):
        for _ in range(count):
            self.a.tick()
            ref = self.a.level(LevelTag.SUCC, ref)
        return ref

    def not_zero(self, root):
        a, pending = self.a, [(root, False)]
        while pending:
            a.check_stack(pending); a.tick()
            ref, returning = pending.pop()
            if ref in self._nonzero:
                continue
            row = a.level_row(ref)
            if row.tag in (LevelTag.ZERO, LevelTag.PARAM):
                self._nonzero[ref] = False
            elif row.tag == LevelTag.SUCC:
                self._nonzero[ref] = True
            elif not returning:
                pending.append((ref, True))
                refs = (row.b,) if row.tag == LevelTag.IMAX else (row.a, row.b)
                pending.extend((r, False) for r in refs)
            else:
                self._nonzero[ref] = (self._nonzero[row.b] if row.tag == LevelTag.IMAX
                                     else self._nonzero[row.a] or self._nonzero[row.b])
        return self._nonzero[root]

    def max(self, left, right):
        a = self.a
        lbase, lo = self.offset(left)
        rbase, ro = self.offset(right)
        if lbase == rbase:
            return left if lo >= ro else right
        if left == a.zero:
            return right
        if right == a.zero:
            return left
        lrow, rrow = a.level_row(left), a.level_row(right)
        if rrow.tag == LevelTag.MAX and left in (rrow.a, rrow.b):
            return right
        if lrow.tag == LevelTag.MAX and right in (lrow.a, lrow.b):
            return left
        return a.level(LevelTag.MAX, left, right)

    def imax(self, left, right):
        if self.not_zero(right):
            return self.max(left, right)
        if right == self.a.zero:
            return right
        if left in (self.a.zero, self.succ(self.a.zero)) or left == right:
            return right
        return self.a.level(LevelTag.IMAX, left, right)

    def _compare(self, left, right):
        # is_norm_lt: compare bases recursively, offsets last. Any stable total
        # symbol order canonicalizes the same expression multiset; symbols are
        # data IDs rather than host names/hashes.
        a, pending = self.a, [(left, right)]
        while pending:
            a.check_stack(pending); a.tick()
            left, right = pending.pop()
            if left == right:
                continue
            lb, lo = self.offset(left); rb, ro = self.offset(right)
            if lb == rb:
                return (lo > ro)-(lo < ro)
            lrow, rrow = a.level_row(lb), a.level_row(rb)
            if lrow.tag != rrow.tag:
                return (lrow.tag > rrow.tag)-(lrow.tag < rrow.tag)
            if lrow.tag == LevelTag.PARAM:
                return (lrow.a > rrow.a)-(lrow.a < rrow.a)
            pending.extend(((lrow.b, rrow.b), (lrow.a, rrow.a)))
        return 0

    def _max_args(self, roots):
        a, pending, args = self.a, list(roots), []
        while pending:
            a.check_stack(pending); a.tick()
            ref = pending.pop()
            row = a.level_row(ref)
            if row.tag == LevelTag.MAX:
                pending.extend((row.b, row.a))
            else:
                args.append(ref)
        return args

    def _normalize_max(self, roots):
        a = self.a
        args = self._max_args(roots)
        best = {}
        for ref in args:
            a.tick()
            base, offset = self.offset(ref)
            if base not in best or offset > best[base][0]:
                best[base] = (offset, ref)
        if a.zero in best and any(base != a.zero and offset >= best[a.zero][0]
                for base, (offset, _) in best.items()):
            del best[a.zero]
        args = sorted((ref for _, ref in best.values()), key=cmp_to_key(self._compare))
        result = args[-1]
        for ref in reversed(args[:-1]):
            a.tick()
            result = self.max(ref, result)
        return result

    def normalize(self, root):
        a, pending = self.a, [(root, False)]
        while pending:
            a.check_stack(pending); a.tick()
            ref, returning = pending.pop()
            if ref in self._normal:
                continue
            row = a.level_row(ref)
            if row.tag in (LevelTag.ZERO, LevelTag.PARAM):
                self._normal[ref] = ref
                continue
            refs = (row.a,) if row.tag == LevelTag.SUCC else (row.a, row.b)
            if not returning:
                pending.append((ref, True))
                pending.extend((r, False) for r in reversed(refs))
            elif row.tag == LevelTag.MAX:
                self._normal[ref] = self._normalize_max(self._normal[r] for r in refs)
            elif row.tag == LevelTag.IMAX:
                value = self.imax(self._normal[row.a], self._normal[row.b])
                self._normal[ref] = (self._normalize_max((value,))
                    if a.level_row(value).tag == LevelTag.MAX else value)
            else:
                child = self._normal[row.a]
                self._normal[ref] = (self._normalize_max(self.succ(r) for r in self._max_args((child,)))
                    if a.level_row(child).tag == LevelTag.MAX else self.succ(child))
        return self._normal[root]

    def equal(self, left, right):
        return left == right or self.normalize(left) == self.normalize(right)

    def is_zero(self, ref):
        return self.normalize(ref) == self.a.zero

    def geq(self, left, right):
        """Pinned is_geq_core, including its conservative IMax comparison."""
        a = self.a
        left, right = self.normalize(left), self.normalize(right)
        pending, memo = [(left, right, False)], {}
        def normalize_pair(x, y):
            return self.normalize(x), self.normalize(y)
        while pending:
            a.check_stack(pending); a.tick()
            x, y, returning = pending.pop()
            if (x, y) in memo:
                continue
            if x == y or y == a.zero:
                memo[x, y] = True
                continue
            xr, yr = a.level_row(x), a.level_row(y)
            groups, immediate = [], False
            if yr.tag == LevelTag.MAX:
                groups = [(normalize_pair(x, yr.a), normalize_pair(x, yr.b))]
            else:
                if xr.tag == LevelTag.MAX:
                    groups.extend(((normalize_pair(xr.a, y),), (normalize_pair(xr.b, y),)))
                if yr.tag == LevelTag.IMAX:
                    groups.append((normalize_pair(x, yr.a), normalize_pair(x, yr.b)))
                elif xr.tag == LevelTag.IMAX:
                    groups.append((normalize_pair(xr.b, y),))
                else:
                    xb, xo = self.offset(x); yb, yo = self.offset(y)
                    if xb == yb or yb == a.zero:
                        immediate = xo >= yo
                    elif xo == yo and xo > 0:
                        groups.append((normalize_pair(xb, yb),))
            if not returning:
                pending.append((x, y, True))
                pending.extend((p, q, False) for group in groups for p, q in group)
            else:
                memo[x, y] = immediate or any(all(memo[pair] for pair in group) for group in groups)
        return memo[left, right]
