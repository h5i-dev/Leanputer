"""Explicit conversion and opacity regressions; syntax fixtures, no certificates."""
from .dependent import Declaration as D

S0, S1 = ('sort', 0), ('sort', 1)
V0, V1 = ('var', 0), ('var', 1)
POLY_ID = ('lam', S1, ('lam', V0, V0))
POLY_TYPE = ('pi', S1, ('pi', V0, V1))


def conversion_cases():
    A, B, f, P, h = [('const', name) for name in ('A', 'B', 'f', 'P', 'h')]
    function = ('pi', A, B)
    eta_env = [D('A', S1), D('B', S1), D('f', function), D('P', ('pi', function, S0)), D('h', ('app', P, f))]
    eta = ('app', P, ('lam', A, ('app', f, V0)))
    Q, p, q, F = [('const', name) for name in ('Q', 'p', 'q', 'F')]
    proof_env = [D('Q', S0), D('p', Q), D('q', Q), D('F', ('pi', Q, S0)), D('h', ('app', F, p))]
    wrong_eta_env = eta_env+[D('k', B)]
    mixed_env = [D('P', S0), D('Q', S0), D('p', P), D('q', Q)]
    opaque = ('const', 'opaque_id')
    opaque_env = [D('opaque_id', POLY_TYPE, POLY_ID, opaque=True),
                  D('P', ('pi', POLY_TYPE, S0)), D('h', ('app', P, opaque))]
    return [
        ('function_eta', h, eta, eta_env, True),
        ('proof_irrelevance', h, ('app', F, q), proof_env, True),
        ('wrong_eta_body', h, ('app', P, ('lam', A, ('const', 'k'))), wrong_eta_env, False),
        ('different_propositions', q, P, mixed_env, False),
        ('opaque_delta_forbidden', h, ('app', P, POLY_ID), opaque_env, False),
    ]
