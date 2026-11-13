"""Count-independent telescope operations used by typing and inductives."""
from dataclasses import dataclass
from .arena import KernelError, Tag
from .operations import abstract, instantiate


@dataclass(frozen=True)
class Telescope:
    locals: tuple
    body: int


def open_telescope(arena, context, root, whnf, tag=Tag.PI, count=None):
    """Open binders in the caller's local scope, optionally consuming a prefix.

    whnf is an INTERNAL kernel service, not an export-time callback. The Python
    spec invokes another spec module. Native lowering must invoke weighted
    service transitions. No native loader calls this Python implementation.
    """
    if tag not in (Tag.PI, Tag.LAM):
        raise ValueError('expected Pi/Lam telescope')
    if count is not None:
        arena.word(count)
    opened = []
    while count is None or len(opened) < count:
        arena.tick()
        root = whnf(root)
        row = arena.expr(root)
        if row.tag != tag:
            if count is not None:
                raise KernelError('telescope shorter than declared prefix')
            break
        local = context.fresh(row.a, binder_info=row.c)
        opened.append(local)
        root = instantiate(arena, row.b, (local,))
    return Telescope(tuple(opened), root)


def fold_telescope(arena, context, locals_, body, tag=Tag.PI):
    if tag not in (Tag.PI, Tag.LAM):
        raise ValueError('expected Pi/Lam telescope')
    for local in reversed(tuple(locals_)):
        arena.tick()
        decl = context.lookup(local)
        body = arena.mk(tag, decl.type, abstract(arena, body, (local,)), decl.binder_info)
    return body


def consume_parameters(arena, context, root, parameters, whnf, convertible):
    """Reuse shared parameter Locals while checking each dependent domain."""
    for local in parameters:
        arena.tick()
        row = arena.expr(whnf(root))
        if row.tag != Tag.PI:
            raise KernelError('missing parameter binder')
        if not convertible(row.a, context.lookup(local).type):
            raise KernelError('nonuniform parameter domain')
        root = instantiate(arena, row.b, (local,))
    return root
