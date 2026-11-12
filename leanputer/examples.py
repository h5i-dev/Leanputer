from .terms import Var as V, Lam as L, App as A
from .checker import Config

PP, PQ, QR, PR = ('P', 'P'), ('P', 'Q'), ('Q', 'R'), ('P', 'R')
COMPOSE = (PQ, (QR, PR))
APPLY = (PQ, PQ)
CASES = [
    ('identity_P', L('p', 'P', V('p')), PP),
    ('identity_Q', L('q', 'Q', V('q')), ('Q', 'Q')),
    ('identity_R', L('r', 'R', V('r')), ('R', 'R')),
    ('identity_function', L('f', PQ, V('f')), APPLY),
    ('apply', L('f', PQ, L('p', 'P', A(V('f'), V('p')))), APPLY),
    ('compose', L('f', PQ, L('g', QR, L('p', 'P', A(V('g'), A(V('f'), V('p')))))), COMPOSE),
    ('constant', L('p', 'P', L('q', 'Q', V('p'))), ('P', ('Q', 'P'))),
    ('first', L('p', 'P', L('q', 'P', V('p'))), ('P', PP)),
    ('second', L('p', 'P', L('q', 'Q', V('q'))), ('P', ('Q', 'Q'))),
    ('beta_identity', L('p', 'P', A(L('q', 'P', V('q')), V('p'))), PP),
]

def demo_config(nodes=16):
    # Fixed public vocabulary; no proof inference or labels used for compilation.
    return Config(nodes)
