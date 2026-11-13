# Shared lowering optimization and ablation

The optimized and reference lowerings implement the same 49 operational phases
and consume identical prepared state. `--reference-lowering` selects the
pre-optimization construction. Artifact metadata records this choice.

Optimizations are configuration-only compiler transformations:

- Fold literal Boolean constants and identity expressions.
- Compute unsigned carry/borrow terms in parallel; fuse context-minus-index-
  minus-one into one subtraction with an incoming borrow.
- Eliminate gates that cannot reach selected outputs, retaining the public
  input/state layout and remapping only work wires.
- Combine semantic write payloads once per bank before applying per-cell
  address masks. Compilation asserts that bank writes share an address.

For heap=128, stack=32, context=16, constants=8, universe=4, fuel=512:

| Measurement | Reference | Optimized |
| --- | ---: | ---: |
| State bits | 6,090 | 6,090 |
| Address-1 FFN depth | 22 | 5 |
| Address-2 FFN depth | 28 | 9 |
| Transition FFN depth | 40 | 25 |
| Attention stages/step | 2 | 2 |
| Shared sequential stages/step | 92 | 41 |
| Buffer bytes | 8,882,256 | 2,101,556 |
| Sparse nonzeros | 424,009 | 94,200 |

There is also a one-stage initializer applied once. At fuel=512, strict checking
applies 513 transitions: the optimized total is 21,034 sequential stages,
including absorption steps after individual proofs finish. This is not a claim
of fewer than eleven layers or an end-to-end depth reduction to 41.

Full-state CPU/CUDA traces cover all 49 phases. A separate test compares both
lowerings against the same independent traces. Arithmetic tests exhaust all
4-bit operand/borrow combinations and compare seeded 12-bit operations. A
liveness regression ensures unused long gate chains are removed. The Lean
`factor_shared_mask` lemma proves binary mask factoring; n-ary gate arithmetic
is proved separately. Compiler optimization and float32 execution as a whole
remain unverified.

Development CUDA samples for three real exported conversion cases gave 19.499s
(reference) and 7.897s (optimized), with peak PyTorch allocator bytes 22,033,408
and 12,622,848. Outcomes were identical: eta exhausted 512 fuel, while proof
irrelevance and an opaque proof dependency accepted. These samples were taken
during development with other validation work and are not controlled benchmark
results. The evaluation harness must reproduce timing under controlled runs.

## Attention writes and CUDA replay

An independently selectable `attention_delta` backend removes complete memory
banks from the transition FFN's work wires. The FFN emits next registers plus
write address/enable/payload. Fixed address attention reads the old payload;
ReLU gates the selected address by enable, and a rank-one delta update writes
new minus old payload. This is actual memory addressing and fixed tensor
arithmetic, with no host mutation of semantic memory. Both backends use the same
state ABI and operational semantics. Artifacts record the memory backend.

CUDA graphs capture the same module forward and identity state copy. Replaying
captures only changes launch scheduling. Graph setup and steady replay are
measured separately; all fuel steps still execute. Address/read/write tests,
CPU/CUDA full-state traces and cross-proof graph reuse tests cover this path.
See the mathlib report for the preserved large negative CUDA result and the
new backend's initial measured costs. Claims based solely on static buffer or
stage reductions are insufficient to establish an end-to-end speedup.
