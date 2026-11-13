"""Seeded benchmark generation. No oracle, reduction, or type inference here."""
import argparse
import copy
import json
from pathlib import Path
import random


def document(name, term, claim, family, **metadata):
    return dict(format='leanputer.dependent.v1', name=name, term=term, claim=claim,
                environment=[], provenance=dict(family=family, **metadata))


def syntax_paths(term, prefix=()):
    yield prefix, term
    if isinstance(term, (tuple, list)) and len(term) == 3 and term[0] in ('pi', 'lam', 'app'):
        yield from syntax_paths(term[1], prefix+(1,))
        yield from syntax_paths(term[2], prefix+(2,))


def replace_at(term, path, replacement):
    if not path:
        return copy.deepcopy(replacement)
    result = list(term)
    result[path[0]] = replace_at(result[path[0]], path[1:], replacement)
    return result


def exhaustive_small():
    """All depth<=1 terms over four leaves, against every leaf claim (208)."""
    leaves = [['sort', 0], ['sort', 1], ['var', 0], ['var', 1]]
    terms = leaves + [[tag, left, right] for tag in ('pi', 'lam', 'app')
                      for left in leaves for right in leaves]
    return [document(f'exhaustive/{i:03d}/{j}', term, claim, 'exhaustive_depth1')
            for i, term in enumerate(terms) for j, claim in enumerate(leaves)]


def resource_cases():
    """Unlabeled valid judgments stressing documented, configuration-dependent bounds."""
    records = [document('bounds/universe', ['sort', 5], ['sort', 6], 'resource_boundary')]
    for depth in (48, 140):
        term, claim = ['var', 0], ['sort', 0]
        for _ in range(depth):
            term = ['lam', ['sort', 0], term]
            claim = ['pi', ['sort', 0], claim]
        records.append(document(f'bounds/binders-{depth}', term, claim, 'resource_boundary'))
    return records


def generate(seed=814732, synthetic=96, mutations=192, fuzz=192, real=()):
    rng = random.Random(seed)
    records = [copy.deepcopy(d) for d in real]
    generated = []
    for index in range(synthetic):
        level = index % 3
        universe, v0, v1 = ['sort', level], ['var', 0], ['var', 1]
        if index % 4 == 0:
            # Dependent identity for a family B : A -> Sort v.
            other = (index//3) % 3
            term = ['lam', universe, ['lam', ['pi', v0, ['sort', other]],
                    ['lam', v1, ['lam', ['app', v1, v0], v0]]]]
            claim = ['pi', universe, ['pi', ['pi', v0, ['sort', other]],
                     ['pi', v1, ['pi', ['app', v1, v0], ['app', ['var', 2], v1]]]]]
            family = 'dependent_family'
        else:
            term = ['lam', universe, ['lam', v0, v0]]
            claim = ['pi', universe, ['pi', v0, v1]]
            family = 'polymorphic_identity'
        # Syntactic redex wrappers preserve the stated judgment by construction.
        # The generated claim is still checked; no inferred certificates are used.
        for _ in range((index//3) % 3):
            term = ['app', ['lam', claim, ['var', 0]], term]
        if family == 'polymorphic_identity' and index % 5 == 0:
            claim_level = 0 if level == 0 else level+1
            claim = ['app', ['lam', ['sort', claim_level], ['var', 0]], claim]
        generated.append(document(f'synthetic/{index:04d}', term, claim, family,
                                  seed=seed, universe=level, variant=index))
    records.extend(generated)
    pool = [d for d in records if 'term' in d]
    for index in range(mutations):
        original = rng.choice(pool)
        item = copy.deepcopy(original)
        item['name'] = f'mutation/{index:04d}'
        field = rng.choice(['term', 'claim'])
        path, node = rng.choice(list(syntax_paths(item[field])))
        tag = node[0]
        if tag == 'var': replacement = ['var', node[1]+rng.choice([1, 2, 15])]
        elif tag == 'sort': replacement = ['sort', node[1]+1]
        elif tag == 'const': replacement = ['var', 0]
        else:
            replacement = [tag, node[2], node[1]] if rng.random() < .5 else rng.choice([node[1], node[2], ['sort', 0]])
        item[field] = replace_at(item[field], path, replacement)
        item['provenance'] = dict(family='mutation', seed=seed, source=original['name'], field=field, path=list(path))
        records.append(item)
    def random_term(depth):
        if depth == 0 or rng.random() < .4:
            return rng.choice([['sort', 0], ['sort', 1], ['var', 0], ['var', 1]])
        return [rng.choice(['pi', 'lam', 'app']), random_term(depth-1), random_term(depth-1)]
    for index in range(fuzz):
        records.append(document(f'fuzz/{index:04d}', random_term(3), rng.choice([['sort',0], ['sort',1], ['pi',['sort',0],['sort',0]]]),
                                'untyped_fuzz', seed=seed))
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real', type=Path, help='existing elaborated JSONL corpus')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=814732)
    parser.add_argument('--synthetic', type=int, default=96)
    parser.add_argument('--mutations', type=int, default=192)
    parser.add_argument('--fuzz', type=int, default=192)
    parser.add_argument('--exhaustive-small', action='store_true')
    parser.add_argument('--resource-cases', action='store_true')
    args = parser.parse_args(argv)
    real = [json.loads(line) for line in args.real.read_text().splitlines() if line.strip()] if args.real else []
    result = generate(args.seed, args.synthetic, args.mutations, args.fuzz, real)
    if args.exhaustive_small: result.extend(exhaustive_small())
    if args.resource_cases: result.extend(resource_cases())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(d)+'\n' for d in result))
    print(json.dumps(dict(output=str(args.output), documents=len(result), seed=args.seed)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
