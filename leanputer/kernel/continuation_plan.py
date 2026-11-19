"""Compile-time, source-derived continuation metadata for checker stack writes.

An extra physical stack word can hold a compiler control identity while the
original six semantic words stay intact. No declaration supplies that identity.
This plan is NOT yet an emitted continuation controller or invariant proof.
"""
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class ContinuationSite:
    identity: int
    effect: int
    phase_node: int
    owner_node: int
    phase_constant: object
    owner_constant: object
    source: str
    line: int


def compile_continuations(compiler):
    sites=[]
    for index,effect in enumerate(compiler.effects):
        if effect.kind!='write_stack':continue
        if len(effect.values)!=6:raise ValueError('original checker stack schema differs')
        phase,owner=effect.values[0],effect.values[3]
        p,o=compiler.g.nodes[phase],compiler.g.nodes[owner]
        sites.append(ContinuationSite(len(sites)+1,index,phase,owner,
                                      p.data if p.op=='const'else None,
                                      o.data if o.op=='const'else None,effect.source,effect.line))
    if len(sites)>65535:raise ValueError('RESOURCE: continuation metadata does not fit preserved word width')
    return tuple(sites)


def account_continuations(sites):
    return dict(format='leanputer.source-continuation-sites.v1',source_stack_write_sites=len(sites),
                semantic_stack_words=6,physical_stack_words=7,stack_capacity=32,
                metadata_bits=16,source_supplies_metadata=False,
                phase_constant_sites=sum(s.phase_constant is not None for s in sites),
                owner_constant_sites=sum(s.owner_constant is not None for s in sites),
                sites_by_source=dict(sorted(Counter(s.source for s in sites).items())),
                metadata_id_zero='Uninitialized; requires a proved invariant or full semantic fallback',
                all_source_stack_writes_covered=True,
                metadata_initialization_and_resume_invariant_verified=False,
                typed_successors_verified=False,physical_cache_layout_verified=False,
                source_native_forwards=None,joint_delivery_gate=False)
