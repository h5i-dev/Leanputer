Parameterized recursors are derived from validated declarations, with no named
Option/Either/Phantom rules or trusted elimination answers.

The checker validates and strips matching parameter binders, derives the expected
recursor tail under scoped parameters, shifts field/family types by binder depth,
and constructs parameterized constructor applications. Runtime arity includes
parameters and its head walk separates them from the actual stored field. Direct
recursive IH applications retain all parameters. The parameter context is cleared
before normal checking; a closed free-variable probe rejectsUNBOUND.

Actual Lean source cases cover Option Some/None, two parameters, a direct recursive
parameterized family, and a Prop-valued type parameter in a positive-Sort family.
FullΓ7/7/7/7/8, all admitted, no axioms. Positive steps1723/1646/2755/2704/1363,
allocated146/138/238/182/120nodes. Wrong minor result rejects; swapped generic
recursor signature rejects after6of7input declarations, scope leak after7of7.
A valid parameterized projection remainsUNSUPPORTED with2of2admitted; a valid
17parameter declaration exceeds context16 and reports RESOURCE with0of2admitted.
Independent Lean accepts both unsupported/resource examples. Renaming preserves
the entire input state. Retained nested Nat-like recursion, actual Function.mt,
neutral projection and PropK remain accepted.

Focused unit2PASS104.959s: every active full weighted state matches the spec,
with exact-bit absorbing checks on every remaining step; independent kernel replay.
Additional independent boundary assertions1PASS1.295s. No broad campaign.
Native15result10ACCEPT/3REJECT/1UNSUPPORTED/1CONTEXTresource; complete ordered
inputs/config/status/reason/steps/nodes/inputΓ/admittedΓ/assumptions match the spec.
The Mathlib857population still has only one targeted generic source smoke; no
whole-population fraction or catalog syntax-count claim follows.

```bash
.venv/bin/python -m leanputer.preparation --generic \
  --source examples/GenericParameters.lean --targets examples/generic-parameter-targets.json \
  --output /tmp/generic-parameter-rec.jsonl
.venv/bin/python -m unittest discover -s tests -p test_generic_parameter_rec.py -v
PYTHONPATH=. /mnt/scratch/leanputer-native-venv/bin/python -m leanputer.generic \
  --backend native --device cuda --input benchmarks/generic-parameter-rec/input.jsonl \
  --config benchmarks/generic-parameter-rec/config.json --batch-size 15 --report /tmp/generic-parameter-rec-native.json
```

Bounds256heap/32stack/16context/8constants/universe4/fuel2816. Actual largest source
allocates238nodes;128cells legitimately exhausts heap. Older admission examples
can now reach a resource limit instead of their former unsupported boundary.
Zero-parameter recursive unit budget1536 covers the extra generic builder steps.
These are changed features/bounds, not matched performance results. Prep elapsed
cost was unrecorded. Parameterized projections, indices, term parameters, multiple
or dependent stored fields and general nested recursion remain unsupported.
No formal whole-checker/numerical equivalence or broad native validation claim.

Stock native metrics:685,439,212BF16params/1,370,878,424weightbytes,H2112/L87,
FFN1024,ballast33. Compile10.805831s; fixed-fuel GPU359.331947s;80boot+
2818stockforwards. CUDApeak1,567,856,128bytes,hostRSS1,714,438,144bytes.
A10G/torch2.8.0+cu128/transformers5.19.0 reference fallback kernels. This is not
high-throughput proof checking, and no performance comparison with other bounds
or features is implied. No pretrained model or external checker is used at inference.
