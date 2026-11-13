"""General iterative Expr/Level traversals from Lean instantiate/abstract.

Every binder passes its depth through the same work stack. Local references are
opaque leaves: an occurrence walk must not follow their context/type entries.
"""
from .arena import KernelError, LevelTag, Tag, children, rebuild


def transform(arena, root, visit):
    """Postorder DAG transform; visit(ref, depth) may replace a whole subtree."""
    arena.expr(root)
    pending = [(root, 0, False)]
    result = {}
    while pending:
        arena.check_stack(pending); arena.tick()
        ref, depth, returning = pending.pop()
        key = (ref, depth)
        if key in result:
            continue
        row = arena.expr(ref)
        if not returning:
            replacement = visit(ref, depth)
            if replacement is not None:
                arena.expr(replacement)
                result[key] = replacement
                continue
            pending.append((ref, depth, True))
            for child, increment in reversed(children(row)):
                pending.append((child, arena.word(depth+increment), False))
        else:
            result[key] = rebuild(arena, row, [result[(c, depth+d)] for c, d in children(row)])
    return result[(root, 0)]


def lift(arena, root, amount, cutoff=0):
    arena.word(amount); arena.word(cutoff)
    def visit(ref, depth):
        row = arena.expr(ref)
        if row.tag == Tag.BVAR and row.a >= cutoff+depth:
            return arena.mk(Tag.BVAR, arena.word(row.a+amount))
        return None
    return transform(arena, root, visit)


def instantiate(arena, root, substitutions, start=0):
    """Substitute #start onward; substitutions[0] replaces the innermost slot.

    This is Lean kernel instantiate, not instantiate_rev. Replacements are lifted
    by traversal depth, and larger free indices decrease by the removed arity.
    """
    arena.word(start)
    substitutions = tuple(substitutions)
    for ref in substitutions:
        arena.expr(ref)
    if not substitutions:
        arena.expr(root)
        return root
    lifted = {}
    def visit(ref, depth):
        row = arena.expr(ref)
        if row.tag != Tag.BVAR or row.a < start+depth:
            return None
        index = row.a-start-depth
        if index >= len(substitutions):
            return arena.mk(Tag.BVAR, row.a-len(substitutions))
        key = (index, depth)
        if key not in lifted:
            lifted[key] = lift(arena, substitutions[index], depth)
        return lifted[key]
    return transform(arena, root, visit)


def instantiate_rev(arena, root, outer_to_inner):
    return instantiate(arena, root, tuple(reversed(outer_to_inner)))


def abstract(arena, root, outer_to_inner):
    """Abstract Local identities; existing bound variables remain unchanged.

    Matches abstract.cpp: last matching identity gets #depth, first gets
    #(depth+n-1). Domains of inner binders are traversed at the outer depth.
    """
    indices = {}
    locals_ = tuple(outer_to_inner)
    for i, local in enumerate(locals_):
        row = arena.expr(local)
        if row.tag != Tag.LOCAL:
            raise KernelError('abstraction expects internal locals')
        indices[row.a] = len(locals_)-1-i
    def visit(ref, depth):
        row = arena.expr(ref)
        if row.tag == Tag.LOCAL and row.a in indices:
            return arena.mk(Tag.BVAR, arena.word(depth+indices[row.a]))
        return None
    return transform(arena, root, visit)


def walk(arena, root):
    """Iterative occurrence traversal, shared DAG nodes visited once."""
    pending = [root]
    seen = set()
    while pending:
        arena.check_stack(pending); arena.tick()
        ref = pending.pop()
        if ref in seen:
            continue
        seen.add(ref)
        row = arena.expr(ref)
        yield ref, row
        pending.extend(child for child, _ in reversed(children(row)))


def has_constant(arena, root, symbols):
    symbols = frozenset(symbols)
    return any(row.tag == Tag.CONST and row.a in symbols for _, row in walk(arena, root))


def has_loose_bvars(arena, root):
    pending, seen = [(root, 0)], set()
    while pending:
        arena.check_stack(pending); arena.tick()
        ref, depth = pending.pop()
        if (ref, depth) in seen:
            continue
        seen.add((ref, depth))
        row = arena.expr(ref)
        if row.tag == Tag.BVAR and row.a >= depth:
            return True
        pending.extend((child, arena.word(depth+increment)) for child, increment in children(row))
    return False


def check_scope(arena, root, locals_=None, universe_parameters=None):
    """Check all loose variables/local identities and bound universe symbols.

    This is scope validation only. It never computes or supplies an inferred
    type. If locals_ is omitted, even an arena-valid Local is rejected.
    """
    params = None if universe_parameters is None else frozenset(universe_parameters)
    seen_levels = set()
    def check_level(ref):
        stack = [ref]
        while stack:
            arena.check_stack(stack); arena.tick()
            level = stack.pop()
            if level in seen_levels:
                continue
            seen_levels.add(level)
            row = arena.level_row(level)
            if row.tag == LevelTag.PARAM and params is not None and row.a not in params:
                raise KernelError('unbound universe parameter')
            if row.tag == LevelTag.SUCC:
                stack.append(row.a)
            elif row.tag in (LevelTag.MAX, LevelTag.IMAX):
                stack.extend((row.a, row.b))
    def visit(ref, depth):
        row = arena.expr(ref)
        if row.tag == Tag.BVAR and row.a >= depth:
            raise KernelError('loose bound variable')
        if row.tag == Tag.LOCAL:
            if locals_ is None:
                raise KernelError('local in closed syntax')
            locals_.lookup(ref)
        if row.tag == Tag.SORT:
            check_level(row.a)
        elif row.tag == Tag.CONST:
            for level in arena.vector(row.b):
                check_level(level)
        return None
    transform(arena, root, visit)


def substitute_levels(arena, root, parameters, *, source_constructors=False):
    """Capture-free raw symbolic substitution (or pinned constructor updates).

    Source updates simplify CHANGED Max/IMax nodes only. Input/replacement raw
    levels are not silently normalized; empty/unchanged subtrees are retained.
    """
    if source_constructors:
        from .levels import LevelOps
        constructors = LevelOps(arena)
    for symbol, ref in parameters.items():
        arena.word(symbol); arena.level_row(ref)
    memo = {}
    def subst(root):
        pending = [(root, False)]
        while pending:
            arena.check_stack(pending); arena.tick()
            ref, returning = pending.pop()
            if ref in memo:
                continue
            row = arena.level_row(ref)
            if row.tag == LevelTag.PARAM:
                memo[ref] = parameters.get(row.a, ref)
                continue
            refs = ((row.a,) if row.tag == LevelTag.SUCC else
                    (row.a, row.b) if row.tag in (LevelTag.MAX, LevelTag.IMAX) else ())
            if not returning:
                pending.append((ref, True))
                pending.extend((r, False) for r in reversed(refs))
            else:
                new_refs = tuple(memo[r] for r in refs)
                if source_constructors and new_refs != refs and row.tag in (LevelTag.MAX, LevelTag.IMAX):
                    construct = constructors.max if row.tag == LevelTag.MAX else constructors.imax
                    memo[ref] = construct(*new_refs)
                else:
                    memo[ref] = arena.level(row.tag, *new_refs)
        return memo[root]
    def visit(ref, depth):
        row = arena.expr(ref)
        if row.tag == Tag.SORT:
            return arena.mk(Tag.SORT, subst(row.a))
        if row.tag == Tag.CONST:
            return arena.const(row.a, [subst(u) for u in arena.vector(row.b)])
        return None
    return transform(arena, root, visit)


def instantiate_levels(arena, root, parameters):
    """Pinned symbolic instantiation; replacement arguments are simultaneous."""
    return substitute_levels(arena, root, parameters, source_constructors=True)


def spine(arena, root):
    args = []
    while arena.expr(root).tag == Tag.APP:
        arena.tick()
        row = arena.expr(root)
        args.append(row.b)
        arena.check_stack(args)
        root = row.a
    args.reverse()
    return root, tuple(args)
