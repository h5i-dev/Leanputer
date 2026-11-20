"""Ground conversion and inference on the node-transition table.

The same Row, Phase, and step() as the 24-row WHNF machine. WHNF rows are
reused. Opaque constants stay neutral. A ground DONE status is a successful
check; a WHNF DONE status is only a value. INVALID here is a rejected
judgment, not a missing-phase accident: every phase has an else row.

Codomain instantiation returns the Pi codomain at the Pi closure's
environment. Body comparison of two binders uses that same environment, so a
codomain that mentions the bound variable is not yet a separate closure.
Proof irrelevance is the neutral-constant case. Let extends the value
environment and the type context after the annotation check.
"""

from leanputer.kernel.node_transition import (
    DECL_AXIOM, DECL_DEF, DECL_OPAQUE, FRAME_APP_AFTER, FRAME_APP_ARG, FRAME_APP_FN,
    FRAME_APP_WHNF, FRAME_BIND_LAM, FRAME_BIND_PI, FRAME_BODY_LAM, FRAME_BODY_PI,
    FRAME_APP, FRAME_CHECK, FRAME_CHK_TERM, FRAME_CHK_WAIT, FRAME_CHK_WHNF, FRAME_CMP,
    FRAME_UPD,
    FRAME_CONV_L, FRAME_CONV_R, FRAME_ETA_BODY, FRAME_ETA_DOM, FRAME_ETA_TY,
    FRAME_HALT, FRAME_JOIN, FRAME_LET_ANN, FRAME_LET_BODY, FRAME_LET_VAL,
    FRAME_NAPP_FN, FRAME_PI_BODY, FRAME_PRF_CLS, FRAME_PRF_TY, FRAME_WHNF_BODY,
    FRAME_WHNF_DOM, HEAP, HEAP_OR_NULL, PC_APP_DOM0, PC_APP_DOM1, PC_APP_INST0,
    PC_APP_INST1, PC_APP_INST2, PC_APP_PUSH, PC_BUILD0, PC_BUILD1, PC_CMP,
    PC_CMP_NEU, PC_CMP_TERM, PC_ENTER, PC_ETA_B0, PC_ETA_B1, PC_ETA_B2, PC_ETA_B3,
    PC_ETA_B4, PC_ETA_CLO, PC_ETA_D0, PC_ETA_D1, PC_ETA_D3, PC_ETA_DPUSH,
    PC_ETA_HEAD, PC_ETA_TYPE, PC_EVAL, PC_INFER, PC_IRET, PC_LET_EXT1, PC_LET_EXT2, PC_LET_PREP,
    PC_LET_PUSH, PC_LET_VAL0, PC_LOOKUP, PC_NAPP_ARGS, PC_PI_B0, PC_PI_B1, PC_PI_B2,
    PC_PI_B3, PC_PI_B4, PC_PI_B5, PC_PI_B6, PC_PI_L0, PC_PI_L1, PC_PI_L2, PC_PI_PUSH,
    PC_PI_R0, PC_PI_R1, PC_POP_APP, PC_PRF0, PC_PRF1, PC_PRF_CLS0, PC_PRF_CLS1,
    PC_PRF_NEU, PC_PRF_PUSH, PC_PRF_R0, PC_PRF_R1, PC_PRF_R2, PC_PUSH_CHK,
    PC_PUSH_PAIR, PC_RET, PC_START_ARG, PC_TLOOK,
    STATUS_DONE, STATUS_INVALID, TAG_APP, TAG_BVAR, TAG_CLO, TAG_CONST, TAG_ENV,
    TAG_LAM, TAG_LET, TAG_NAPP, TAG_NEU, TAG_PI, TAG_SORT, WORD, Cell, Machine,
    Phase, Port, Regs, Table, UnsupportedInput, _Builder, _alloc, _as_tuple,
    _push, _replace, _row, run, whnf_table,
)


_FAIL = (('status', ('imm', STATUS_INVALID)),)
_K = Port('k', 'stk', 1, ('reg', 'K'))
_HP = ('hp',)
_NIL = ('null',)
_C = ('reg', 'C')
_E = ('reg', 'E')
_V = ('reg', 'V')
_A1 = ('reg', 'A1')
_A2 = ('reg', 'A2')
_U = ('reg', 'U')
_LVL = ('reg', 'lvl')


def _else(phase):
    return _row(phase, phase + '-else', (), _FAIL, fallback=True)


def _go(phase, name, guard, goto, assign=(), heap=None, stk=None, done=False):
    return _row(phase, name, guard, assign, heap, stk, goto, done)


def _pair(phase, name, guard, goto, assign=(), heap=None, stk=None, done=False):
    return (
        _go(phase, name, guard, goto, assign, heap, stk, done),
        _else(phase),
    )


def _heap(name, bank, rnd, addr, choices=(), refine=()):
    return Port(name, bank, rnd, addr, tuple(choices), tuple(refine))


def ground_table():
    """WHNF rows plus inference, conversion, eta, and proof irrelevance."""
    whnf = whnf_table()
    ev, ret = whnf.phase(PC_EVAL), whnf.phase(PC_RET)
    n_a, n_b, n_c = ('field', 'n', 'a'), ('field', 'n', 'b'), ('field', 'n', 'c')
    k_a, k_b = ('field', 'k', 'a'), ('field', 'k', 'b')
    v_a, v_b = ('field', 'v', 'a'), ('field', 'v', 'b')
    b_a, b_b = ('field', 'b', 'a'), ('field', 'b', 'b')
    l_a, l_b = ('field', 'l', 'a'), ('field', 'l', 'b')
    r_a, r_b, r_c = ('field', 'r', 'a'), ('field', 'r', 'b'), ('field', 'r', 'c')
    p_a, p_b, p_c = ('field', 'p', 'a'), ('field', 'p', 'b'), ('field', 'p', 'c')
    d_a = ('field', 'd', 'a')
    e_b = ('field', 'e', 'b')
    m_a, m_b = ('field', 'm', 'a'), ('field', 'm', 'b')
    const_g = (('tag', 'n', TAG_CONST),)
    bvar_g = (('tag', 'n', TAG_BVAR),)
    clo_app = (('kind', 'k', FRAME_APP_WHNF), ('tag', 'v', TAG_CLO))
    whnf_eval = ev.rows[:-1] + (
        _go('EVAL', 'E-opaque', (('tag', 'n', TAG_CONST), ('decl', 'd', DECL_OPAQUE)), 'RET',
            (('V', _HP),), _alloc(TAG_NEU, _C, ('imm', 0), ('imm', 0))),
    ) + ev.rows[-1:]
    ret_extra = (
        _go('RET', 'R-dom-sort', (
            ('kind', 'k', FRAME_WHNF_DOM), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_SORT),
        ), 'ENTER', (('lvl', b_a),)),
        _go('RET', 'R-imax0', (
            ('kind', 'k', FRAME_WHNF_BODY), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_SORT),
            ('eq', b_a, 0),
        ), 'IRET', (('V', _HP), ('A2', _NIL)), _alloc(TAG_SORT, ('imm', 0), ('imm', 0), ('imm', 0)), ('pop',)),
        _go('RET', 'R-imax-dom', (
            ('kind', 'k', FRAME_WHNF_BODY), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_SORT),
            ('ne', b_a, 0), ('ge', k_b, b_a),
        ), 'IRET', (('V', _HP), ('A2', _NIL)), _alloc(TAG_SORT, k_b, ('imm', 0), ('imm', 0)), ('pop',)),
        _go('RET', 'R-imax-body', (
            ('kind', 'k', FRAME_WHNF_BODY), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_SORT),
            ('ne', b_a, 0), ('lt', k_b, b_a),
        ), 'IRET', (('V', _HP), ('A2', _NIL)), _alloc(TAG_SORT, b_a, ('imm', 0), ('imm', 0)), ('pop',)),
        _go('RET', 'R-chk-whnf', (
            ('kind', 'k', FRAME_CHK_WHNF), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_SORT),
        ), 'INFER', (('C', k_a), ('E', _NIL), ('U', _NIL)), stk=_replace(FRAME_CHK_TERM, k_b)),
        _go('RET', 'R-conv-r', (('kind', 'k', FRAME_CONV_R),), 'EVAL',
            (('C', k_a), ('E', k_b)), stk=_replace(FRAME_CONV_L, _V, k_b)),
        _go('RET', 'R-conv-l', (('kind', 'k', FRAME_CONV_L),), 'CMP',
            (), stk=_replace(FRAME_CMP, k_a, _V)),
        _go('RET', 'R-app-whnf', clo_app + (('tag', 'b', TAG_PI),), 'START_ARG', (('C', _V),)),
        _go('RET', 'R-napp-fn', (('kind', 'k', FRAME_NAPP_FN),), 'NAPP_ARGS', (('C', k_a), ('V', k_b))),
        _go('RET', 'R-join', (('kind', 'k', FRAME_JOIN),), 'RET', stk=('pop',)),
        _go('RET', 'R-chk-ok', (('kind', 'k', FRAME_CHK_WAIT),), 'RET',
            (('status', ('imm', STATUS_DONE)),), done=True),
        _go('RET', 'R-eta-ty', (
            ('kind', 'k', FRAME_ETA_TY), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_PI),
        ), 'ETA_D0'),
        _go('RET', 'R-eta-dom', (('kind', 'k', FRAME_ETA_DOM),), 'ETA_B0'),
        _go('RET', 'R-eta-body', (('kind', 'k', FRAME_ETA_BODY),), 'CMP',
            (), stk=_replace(FRAME_CMP, k_a, _V)),
        _go('RET', 'R-prf-sort', (
            ('kind', 'k', FRAME_PRF_TY), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_SORT),
        ), 'RET', _FAIL),
        _go('RET', 'R-prf-neu', (('kind', 'k', FRAME_PRF_TY), ('tag', 'v', TAG_NEU)), 'PRF_CLS0'),
        _go('RET', 'R-prf-cls', (
            ('kind', 'k', FRAME_PRF_CLS), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_SORT),
            ('eq', b_a, 0),
        ), 'PRF_R0', (('C', k_a),), stk=('pop',)),
        _go('RET', 'R-prf-cls-ne', (
            ('kind', 'k', FRAME_PRF_CLS), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_SORT),
            ('ne', b_a, 0),
        ), 'RET', _FAIL),
        _go('RET', 'R-let-ann', (
            ('kind', 'k', FRAME_LET_ANN), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_SORT),
        ), 'LET_VAL0'),
        _go('RET', 'R-pi-body', (('kind', 'k', FRAME_PI_BODY),), 'PI_B0'),
        _go('RET', 'R-app-after', (('kind', 'k', FRAME_APP_AFTER),), 'APP_INST0'),
        _go('RET', 'R-let-body', (('kind', 'k', FRAME_LET_BODY),), 'LET_EXT1'),
    )
    # Choice guards are subsets of the row that reads that cell.
    choices = (
        ((('kind', 'k', FRAME_APP), ('tag', 'v', TAG_CLO)), v_a),
        ((('kind', 'k', FRAME_UPD),), k_a),
        ((('kind', 'k', FRAME_PRF_TY), ('tag', 'v', TAG_CLO)), v_a),
        ((('kind', 'k', FRAME_WHNF_DOM), ('tag', 'v', TAG_CLO)), v_a),
        ((('kind', 'k', FRAME_WHNF_BODY), ('tag', 'v', TAG_CLO)), v_a),
        ((('kind', 'k', FRAME_CHK_WHNF), ('tag', 'v', TAG_CLO)), v_a),
        (clo_app, v_a),
        ((('kind', 'k', FRAME_ETA_TY), ('tag', 'v', TAG_CLO)), v_a),
        ((('kind', 'k', FRAME_PRF_CLS), ('tag', 'v', TAG_CLO)), v_a),
        ((('kind', 'k', FRAME_LET_ANN), ('tag', 'v', TAG_CLO)), v_a),
    )
    phases = [
        Phase('EVAL', PC_EVAL, ev.reads, ev.alus, whnf_eval, dict(ev.entry)),
        whnf.phase(PC_LOOKUP),
        Phase('RET', PC_RET, (
            _K,
            Port('v', 'heap_a', 1, _V),
            Port('b', 'heap_b', 2, _NIL, choices),
        ), (), ret.rows[:-1] + ret_extra + ret.rows[-1:], {'V': HEAP}),
        _phase_infer(n_a, n_b, const_g, bvar_g, d_a, p_a, p_b, p_c),
        _phase_iret(k_a, k_b),
        _phase_tlook(p_a, p_b, p_c),
        _phase_enter(k_a, k_b, n_a, n_b),
        *_binder_build(k_a, k_b, n_a, n_b),
        _phase_push_chk(k_a),
        _phase_cmp(k_a, l_a, r_a),
        _phase_cmp_term(n_a, m_a),
        _phase_cmp_neu(n_a, m_a),
        _phase_start_arg(k_a, k_b, n_b),
        *_app_dom(k_a, k_b, v_a, v_b, b_a),
        *_app_inst(k_a, v_a, v_b, n_b),
        _phase_pop_app(),
        _phase_push_pair(),
        *_napp(l_b, ('field', 'l', 'c'), r_b, r_c),
        *_pi_dom(k_a, k_b, n_a, v_b, m_a),
        *_pi_body(k_a, k_b, v_a, v_b, n_b, m_b),
        *_eta(k_a, k_b, v_a, v_b, b_a, b_b, d_a),
        *_proof(k_a, k_b, d_a),
        *_let(k_a, k_b, n_a, n_b, n_c, e_b),
    ]
    return Table(tuple(phases))


def _phase_infer(n_a, n_b, const_g, bvar_g, d_a, p_a, p_b, p_c):
    name = 'INFER'
    rows = (
        _go(name, 'I-sort', (('tag', 'n', TAG_SORT),), 'IRET',
            (('V', _HP), ('A2', _NIL), ('lvl', ('alu', 1))),
            _alloc(TAG_SORT, ('alu', 1), ('imm', 0), ('imm', 0))),
        _go(name, 'I-var0', (('tag', 'n', TAG_BVAR), ('eq', n_a, 0), ('tag', 'p', TAG_ENV)), 'IRET',
            (('V', p_a), ('A2', p_b))),
        _go(name, 'I-var', (('tag', 'n', TAG_BVAR), ('ge', n_a, 1), ('tag', 'p', TAG_ENV)), 'TLOOK',
            (('A0', ('alu', 0)), ('A1', p_c))),
        _go(name, 'I-axiom', (('tag', 'n', TAG_CONST), ('decl', 'd', DECL_AXIOM)), 'IRET',
            (('V', d_a), ('A2', _NIL))),
        _go(name, 'I-def', (('tag', 'n', TAG_CONST), ('decl', 'd', DECL_DEF)), 'IRET',
            (('V', d_a), ('A2', _NIL))),
        _go(name, 'I-opaque', (('tag', 'n', TAG_CONST), ('decl', 'd', DECL_OPAQUE)), 'IRET',
            (('V', d_a), ('A2', _NIL))),
        _go(name, 'I-lam', (('tag', 'n', TAG_LAM),), 'INFER', (('C', n_a),),
            stk=_push(FRAME_BIND_LAM, _C, _E)),
        _go(name, 'I-pi', (('tag', 'n', TAG_PI),), 'INFER', (('C', n_a),),
            stk=_push(FRAME_BIND_PI, _C, _E)),
        _go(name, 'I-app', (('tag', 'n', TAG_APP),), 'INFER', (('C', n_a),),
            stk=_push(FRAME_APP_FN, _C, _E)),
        _go(name, 'I-let', (('tag', 'n', TAG_LET),), 'INFER', (('C', n_a),),
            stk=_push(FRAME_LET_ANN, _C, _E)),
        _else(name),
    )
    return Phase(name, PC_INFER, (
        Port('n', 'heap_a', 1, _C),
        Port('p', 'heap_b', 2, _NIL, ((bvar_g, _U),)),
        _K,
        Port('d', 'decl', 2, _NIL, ((const_g, n_a),)),
    ), (('sub', n_a, ('imm', 1)), ('add', n_a, ('imm', 1))), rows,
        {'C': HEAP, 'E': HEAP_OR_NULL, 'U': HEAP_OR_NULL})


def _phase_iret(k_a, k_b):
    name = 'IRET'
    rows = (
        _go(name, 'iret-check', (('kind', 'k', FRAME_CHECK),), 'EVAL',
            (('C', _V), ('E', _A2)), stk=_replace(FRAME_CHK_WHNF, k_a, k_b)),
        _go(name, 'iret-chk-term', (('kind', 'k', FRAME_CHK_TERM),), 'PUSH_CHK',
            (('C', _V), ('E', _A2)), stk=_replace(FRAME_CHK_WAIT, k_a)),
        _go(name, 'iret-bind-lam', (('kind', 'k', FRAME_BIND_LAM),), 'EVAL',
            (('C', _V), ('E', _A2)), stk=_replace(FRAME_WHNF_DOM, k_a, k_b)),
        _go(name, 'iret-bind-pi', (('kind', 'k', FRAME_BIND_PI),), 'EVAL',
            (('C', _V), ('E', _A2)), stk=_replace(FRAME_WHNF_DOM, k_a, k_b)),
        _go(name, 'iret-body-lam', (('kind', 'k', FRAME_BODY_LAM),), 'BUILD0'),
        _go(name, 'iret-body-pi', (('kind', 'k', FRAME_BODY_PI),), 'EVAL',
            (('C', _V), ('E', _A2)), stk=_replace(FRAME_WHNF_BODY, k_a, k_b)),
        _go(name, 'iret-app-fn', (('kind', 'k', FRAME_APP_FN),), 'EVAL',
            (('C', _V), ('E', _A2)), stk=_replace(FRAME_APP_WHNF, k_a, k_b)),
        _go(name, 'iret-app-arg', (('kind', 'k', FRAME_APP_ARG),), 'APP_DOM0'),
        _go(name, 'iret-let-ann', (('kind', 'k', FRAME_LET_ANN),), 'EVAL',
            (('C', _V), ('E', _A2))),
        _go(name, 'iret-let-val', (('kind', 'k', FRAME_LET_VAL),), 'LET_PREP'),
        _go(name, 'iret-let-body', (('kind', 'k', FRAME_LET_BODY),), 'IRET', stk=('pop',)),
        _else(name),
    )
    return Phase(name, PC_IRET, (_K,), (), rows, {'V': HEAP, 'A2': HEAP_OR_NULL})


def _phase_tlook(p_a, p_b, p_c):
    name = 'TLOOK'
    rows = (
        _go(name, 'T-hit', (('eq', ('reg', 'A0'), 0), ('tag', 'p', TAG_ENV)), 'IRET',
            (('V', p_a), ('A2', p_b))),
        _go(name, 'T-walk', (('ge', ('reg', 'A0'), 1), ('tag', 'p', TAG_ENV)), 'TLOOK',
            (('A0', ('alu', 0)), ('A1', p_c))),
        _else(name),
    )
    return Phase(name, PC_TLOOK, (
        Port('p', 'heap_a', 1, _A1),
    ), (('sub', ('reg', 'A0'), ('imm', 1)),), rows, {'A1': HEAP_OR_NULL})


def _phase_enter(k_a, k_b, n_a, n_b):
    name = 'ENTER'
    kind = (('kind', 'k', FRAME_WHNF_DOM),)
    env = _alloc(TAG_ENV, n_a, k_b, _U)
    rows = (
        _go(name, 'enter-lam', kind + (('tag', 'n', TAG_LAM),), 'INFER',
            (('C', n_b), ('E', k_b), ('U', _HP)), env, _replace(FRAME_BODY_LAM, k_a, k_b)),
        _go(name, 'enter-pi', kind + (('tag', 'n', TAG_PI),), 'INFER',
            (('C', n_b), ('E', k_b), ('U', _HP)), env, _replace(FRAME_BODY_PI, k_a, _LVL)),
        _else(name),
    )
    return Phase(name, PC_ENTER, (
        _K, _heap('n', 'heap_b', 2, k_a, refine=kind),
    ), (), rows, {'U': HEAP_OR_NULL})


def _binder_build(k_a, k_b, n_a, n_b):
    return (
        Phase('BUILD0', PC_BUILD0, (_K,), (), _pair(
            'BUILD0', 'build0', (('kind', 'k', FRAME_BODY_LAM),), 'BUILD1', (('C', k_a),)), {}),
        Phase('BUILD1', PC_BUILD1, (
            _K, Port('n', 'heap_a', 1, _C),
        ), (), _pair(
            'BUILD1', 'build-pi', (('kind', 'k', FRAME_BODY_LAM), ('tag', 'n', TAG_LAM)), 'IRET',
            (('V', _HP), ('A2', k_b)), _alloc(TAG_PI, n_a, _V, ('imm', 0)), ('pop',)),
            {'V': HEAP}),
    )


def _phase_push_chk(k_a):
    return Phase('PUSH_CHK', PC_PUSH_CHK, (_K,), (), _pair(
        'PUSH_CHK', 'push-chk', (('kind', 'k', FRAME_CHK_WAIT),), 'EVAL',
        stk=_push(FRAME_CONV_R, k_a)), {})


def _phase_cmp(k_a, l_a, r_a):
    name = 'CMP'
    both = lambda left, right: (('kind', 'k', FRAME_CMP), ('tag', 'l', left), ('tag', 'r', right))
    rows = (
        _go(name, 'cmp-clo', both(TAG_CLO, TAG_CLO), 'CMP_TERM', (('A1', l_a), ('A2', r_a))),
        _go(name, 'cmp-neu', both(TAG_NEU, TAG_NEU), 'CMP_NEU', (('C', l_a), ('V', r_a))),
        _go(name, 'cmp-napp', both(TAG_NAPP, TAG_NAPP), 'PUSH_PAIR',
            (('C', l_a), ('V', r_a)), stk=_replace(FRAME_NAPP_FN, k_a, ('field', 'k', 'b'))),
        _go(name, 'cmp-eta-l', both(TAG_CLO, TAG_NEU), 'ETA_CLO', (('C', k_a), ('V', ('field', 'k', 'b')))),
        _go(name, 'cmp-eta-r', both(TAG_NEU, TAG_CLO), 'ETA_CLO', (('C', _V), ('V', k_a))),
        _else(name),
    )
    return Phase(name, PC_CMP, (
        _K,
        Port('r', 'heap_a', 1, _V),
        _heap('l', 'heap_b', 2, k_a, refine=(('kind', 'k', FRAME_CMP),)),
    ), (), rows, {'V': HEAP})


def _phase_cmp_term(n_a, m_a):
    name = 'CMP_TERM'
    both = lambda tag: (('tag', 'n', tag), ('tag', 'm', tag))
    rows = (
        _go(name, 'term-sort', both(TAG_SORT) + (('eq', n_a, m_a),), 'RET', stk=('pop',)),
        _go(name, 'term-sort-ne', both(TAG_SORT) + (('ne', n_a, m_a),), 'RET', _FAIL),
        _go(name, 'term-pi', both(TAG_PI), 'PI_L0'),
        _go(name, 'term-lam', both(TAG_LAM), 'PI_L0'),
        _else(name),
    )
    return Phase(name, PC_CMP_TERM, (
        Port('n', 'heap_a', 1, _A1), Port('m', 'heap_b', 1, _A2),
    ), (), rows)


def _phase_cmp_neu(n_a, m_a):
    name = 'CMP_NEU'
    both = (('tag', 'n', TAG_CONST), ('tag', 'm', TAG_CONST))
    rows = (
        _go(name, 'neu-eq', both + (('eq', n_a, m_a),), 'RET', stk=('pop',)),
        _go(name, 'neu-ne', both + (('ne', n_a, m_a),), 'PRF0'),
        _else(name),
    )
    return Phase(name, PC_CMP_NEU, (
        Port('n', 'heap_a', 1, _C), Port('m', 'heap_b', 1, _V),
    ), (), rows)


def _phase_start_arg(k_a, k_b, n_b):
    # Old C is the Pi closure. Push saves it while C becomes the argument.
    return Phase('START_ARG', PC_START_ARG, (
        _K, _heap('n', 'heap_b', 2, k_a, refine=(('kind', 'k', FRAME_APP_WHNF),)),
    ), (), _pair(
        'START_ARG', 'start-arg', (('kind', 'k', FRAME_APP_WHNF), ('tag', 'n', TAG_APP)), 'INFER',
        (('C', n_b), ('E', k_b)), stk=_push(FRAME_APP_ARG, _C, n_b)), {})


def _app_dom(k_a, k_b, v_a, v_b, b_a):
    return (
        Phase('APP_DOM0', PC_APP_DOM0, (_K,), (), _pair(
            'APP_DOM0', 'app-dom0', (('kind', 'k', FRAME_APP_ARG),), 'APP_DOM1', (('C', k_a),)), {}),
        Phase('APP_DOM1', PC_APP_DOM1, (
            _K,
            Port('v', 'heap_a', 1, _C),
            Port('b', 'heap_b', 2, _NIL, (((('tag', 'v', TAG_CLO),), v_a),)),
        ), (), _pair(
            'APP_DOM1', 'app-dom1', (
                ('kind', 'k', FRAME_APP_ARG), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_PI),
            ), 'APP_PUSH', (('C', b_a), ('E', v_b)), stk=_replace(FRAME_APP_AFTER, k_a, k_b)), {}),
    )


def _phase_stub_push(name, pc, guard, frame_a, frame_b, goto='EVAL'):
    """Push a convert of (frame sources) while C/E already hold the left side."""
    return Phase(name, pc, (_K,), (), _pair(
        name, name.lower(), guard, goto, stk=_push(FRAME_CONV_R, frame_a, frame_b)), {})


def _app_inst(k_a, v_a, v_b, n_b):
    return (
        Phase('APP_PUSH', PC_APP_PUSH, (_K,), (), _pair(
            'APP_PUSH', 'app-push', (('kind', 'k', FRAME_APP_AFTER),), 'EVAL',
            (('C', _V), ('E', _A2)), stk=_push(FRAME_CONV_R, _C, _E)), {}),
        Phase('APP_INST0', PC_APP_INST0, (_K,), (), _pair(
            'APP_INST0', 'app-inst0', (('kind', 'k', FRAME_APP_AFTER),), 'APP_INST1', (('C', k_a),)), {}),
        Phase('APP_INST1', PC_APP_INST1, (
            Port('v', 'heap_a', 1, _C),
        ), (), _pair(
            'APP_INST1', 'app-inst1', (('tag', 'v', TAG_CLO),), 'APP_INST2',
            (('C', v_a), ('E', v_b))), {}),
        Phase('APP_INST2', PC_APP_INST2, (
            _K, Port('n', 'heap_a', 1, _C),
        ), (), _pair(
            'APP_INST2', 'app-inst2', (('tag', 'n', TAG_PI),), 'POP_APP',
            (('V', n_b), ('A2', _E)), stk=('pop',)), {}),
    )


def _phase_pop_app():
    return Phase('POP_APP', PC_POP_APP, (_K,), (), _pair(
        'POP_APP', 'pop-app', (('kind', 'k', FRAME_APP_WHNF),), 'IRET', stk=('pop',)), {})


def _phase_push_pair():
    return Phase('PUSH_PAIR', PC_PUSH_PAIR, (), (), _pair(
        'PUSH_PAIR', 'push-pair', (), 'CMP', stk=_push(FRAME_CMP, _C, _V)), {})


def _napp(l_b, l_c, r_b, r_c):
    return (
        Phase('NAPP_ARGS', PC_NAPP_ARGS, (
            Port('l', 'heap_a', 1, _C), Port('r', 'heap_b', 1, _V), _K,
        ), (), _pair(
            'NAPP_ARGS', 'napp-args', (('tag', 'l', TAG_NAPP), ('tag', 'r', TAG_NAPP)), 'PI_B6',
            (('C', l_b), ('E', l_c), ('V', r_b), ('A2', r_c)), stk=('pop',)), {}),
        # Reuse PUSH_PAIR's sibling: a one-row phase would need another pc.
        # NAPP pushes from the armed registers in a dedicated row of PUSH_PAIR.
    )


def _pi_dom(k_a, k_b, n_a, v_b, m_a):
    # Left term is in A1, right term in A2, clos on the CMP frame.
    # PI_L0 arms C with the left closure and keeps the term addresses.
    return (
        Phase('PI_L0', PC_PI_L0, (_K,), (), _pair(
            'PI_L0', 'pi-l0', (('kind', 'k', FRAME_CMP),), 'PI_L1',
            (), stk=_replace(FRAME_PI_BODY, k_a, k_b)), {}),
        Phase('PI_L1', PC_PI_L1, (_K,), (), _pair(
            'PI_L1', 'pi-l1', (('kind', 'k', FRAME_PI_BODY),), 'PI_L2', (('C', k_a),)), {}),
        Phase('PI_L2', PC_PI_L2, (
            Port('v', 'heap_a', 1, _C),
            Port('n', 'heap_b', 1, _A1),
        ), (), (
            _go('PI_L2', 'pi-l2-lam', (('tag', 'v', TAG_CLO), ('tag', 'n', TAG_LAM)), 'PI_R0',
                (('C', n_a), ('E', v_b))),
            _go('PI_L2', 'pi-l2-pi', (('tag', 'v', TAG_CLO), ('tag', 'n', TAG_PI)), 'PI_R0',
                (('C', n_a), ('E', v_b))),
            _else('PI_L2'),
        )),
        Phase('PI_R0', PC_PI_R0, (_K,), (), _pair(
            'PI_R0', 'pi-r0', (('kind', 'k', FRAME_PI_BODY),), 'PI_R1', (('V', k_b),)), {}),
        Phase('PI_R1', PC_PI_R1, (
            Port('v', 'heap_a', 1, _V),
            Port('m', 'heap_b', 1, _A2),
        ), (), (
            _go('PI_R1', 'pi-r1-lam', (('tag', 'v', TAG_CLO), ('tag', 'm', TAG_LAM)), 'PI_PUSH',
                (('V', m_a), ('A2', v_b))),
            _go('PI_R1', 'pi-r1-pi', (('tag', 'v', TAG_CLO), ('tag', 'm', TAG_PI)), 'PI_PUSH',
                (('V', m_a), ('A2', v_b))),
            _else('PI_R1'),
        )),
    )


def _pi_body(k_a, k_b, v_a, v_b, n_b, m_b):
    return (
        Phase('PI_B0', PC_PI_B0, (_K,), (), _pair(
            'PI_B0', 'pi-b0', (('kind', 'k', FRAME_PI_BODY),), 'PI_B1', (('C', k_a),)), {}),
        Phase('PI_B1', PC_PI_B1, (
            Port('v', 'heap_a', 1, _C),
        ), (), _pair(
            'PI_B1', 'pi-b1', (('tag', 'v', TAG_CLO),), 'PI_B2',
            (('A1', v_a), ('E', v_b))), {}),
        Phase('PI_B2', PC_PI_B2, (
            Port('n', 'heap_a', 1, _A1),
        ), (), (
            _go('PI_B2', 'pi-b2-lam', (('tag', 'n', TAG_LAM),), 'PI_B3', (('C', n_b),)),
            _go('PI_B2', 'pi-b2-pi', (('tag', 'n', TAG_PI),), 'PI_B3', (('C', n_b),)),
            _else('PI_B2'),
        )),
        Phase('PI_B3', PC_PI_B3, (_K,), (), _pair(
            'PI_B3', 'pi-b3', (('kind', 'k', FRAME_PI_BODY),), 'PI_B4', (('V', k_b),)), {}),
        Phase('PI_B4', PC_PI_B4, (
            Port('v', 'heap_a', 1, _V),
        ), (), _pair(
            'PI_B4', 'pi-b4', (('tag', 'v', TAG_CLO),), 'PI_B5',
            (('A2', v_a), ('A1', v_b))), {}),
        Phase('PI_B5', PC_PI_B5, (
            Port('m', 'heap_a', 1, _A2), _K,
        ), (), (
            _go('PI_B5', 'pi-b5-lam', (('tag', 'm', TAG_LAM),), 'PI_B6',
                (('V', m_b), ('A2', _A1)), stk=('pop',)),
            _go('PI_B5', 'pi-b5-pi', (('tag', 'm', TAG_PI),), 'PI_B6',
                (('V', m_b), ('A2', _A1)), stk=('pop',)),
            _else('PI_B5'),
        )),
        Phase('PI_B6', PC_PI_B6, (), (), _pair(
            'PI_B6', 'pi-b6', (), 'EVAL', stk=_push(FRAME_CONV_R, _V, _A2)), {}),
        Phase('PI_PUSH', PC_PI_PUSH, (), (), _pair(
            'PI_PUSH', 'pi-push', (), 'EVAL', stk=_push(FRAME_CONV_R, _V, _A2)), {}),
    )


def _eta(k_a, k_b, v_a, v_b, b_a, b_b, d_a):
    lam = (('tag', 'v', TAG_CLO), ('tag', 'b', TAG_LAM))
    return (
        Phase('ETA_CLO', PC_ETA_CLO, (
            Port('v', 'heap_a', 1, _C),
            Port('b', 'heap_b', 2, _NIL, (((('tag', 'v', TAG_CLO),), v_a),)),
        ), (), _pair('ETA_CLO', 'eta-lam', lam, 'ETA_HEAD',
                     (('A1', b_b), ('E', v_b)), stk=_replace(FRAME_ETA_TY, _C, _V)), {}),
        Phase('ETA_HEAD', PC_ETA_HEAD, (
            Port('n', 'heap_a', 1, _V),
        ), (), _pair(
            'ETA_HEAD', 'eta-head', (('tag', 'n', TAG_NEU),), 'ETA_TYPE',
            (('V', ('field', 'n', 'a')),),
        )),
        Phase('ETA_TYPE', PC_ETA_TYPE, (
            Port('c', 'heap_a', 1, _V),
            Port('d', 'decl', 2, _NIL, (((('tag', 'c', TAG_CONST),), ('field', 'c', 'a')),)),
        ), (), (
            _go('ETA_TYPE', 'eta-type-ax', (('tag', 'c', TAG_CONST), ('decl', 'd', DECL_AXIOM)),
                'EVAL', (('C', d_a), ('E', _NIL))),
            _go('ETA_TYPE', 'eta-type-def', (('tag', 'c', TAG_CONST), ('decl', 'd', DECL_DEF)),
                'EVAL', (('C', d_a), ('E', _NIL))),
            _go('ETA_TYPE', 'eta-type-opq', (('tag', 'c', TAG_CONST), ('decl', 'd', DECL_OPAQUE)),
                'EVAL', (('C', d_a), ('E', _NIL))),
            _else('ETA_TYPE'),
        )),
        Phase('ETA_D0', PC_ETA_D0, (_K,), (), _pair(
            'ETA_D0', 'eta-d0', (('kind', 'k', FRAME_ETA_TY),), 'ETA_D1', (('C', k_a),)), {}),
        Phase('ETA_D1', PC_ETA_D1, (
            Port('v', 'heap_a', 1, _C),
            Port('b', 'heap_b', 2, _NIL, (((('tag', 'v', TAG_CLO),), v_a),)),
        ), (), _pair(
            'ETA_D1', 'eta-d1', lam, 'ETA_D3', (('C', b_a),)), {}),
        Phase('ETA_D3', PC_ETA_D3, (
            Port('v', 'heap_a', 1, _V),
            Port('b', 'heap_b', 2, _NIL, (((('tag', 'v', TAG_CLO),), v_a),)),
            _K,
        ), (), _pair(
            'ETA_D3', 'eta-d3', (
                ('kind', 'k', FRAME_ETA_TY), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_PI),
            ), 'ETA_DPUSH',
            (('V', b_a), ('A2', v_b)), stk=_replace(FRAME_ETA_DOM, k_a, k_b)), {}),
        Phase('ETA_DPUSH', PC_ETA_DPUSH, (), (), _pair(
            'ETA_DPUSH', 'eta-dpush', (), 'EVAL',
            (('C', _C), ('E', _E)), stk=_push(FRAME_CONV_R, _V, _A2)), {}),
        Phase('ETA_B0', PC_ETA_B0, (_K,), (), _pair(
            'ETA_B0', 'eta-b0', (('kind', 'k', FRAME_ETA_DOM),), 'ETA_B1', (('C', k_a),)), {}),
        Phase('ETA_B1', PC_ETA_B1, (
            _K,
            Port('v', 'heap_a', 1, _C),
            Port('b', 'heap_b', 2, _NIL, (((('tag', 'v', TAG_CLO),), v_a),)),
        ), (), _pair(
            'ETA_B1', 'eta-b1', lam + (('kind', 'k', FRAME_ETA_DOM),), 'ETA_B2',
            (('E', v_b), ('V', k_b), ('C', _HP)),
            _alloc(TAG_SORT, ('imm', 0), ('imm', 0), ('imm', 0)),
            _replace(FRAME_ETA_DOM, b_b, k_b)), {}),
        Phase('ETA_B2', PC_ETA_B2, (), (), _pair(
            'ETA_B2', 'eta-b2', (), 'ETA_B3', (('V', _HP),),
            _alloc(TAG_BVAR, ('imm', 0), ('imm', 0), ('imm', 0))), {}),
        Phase('ETA_B3', PC_ETA_B3, (), (), _pair(
            'ETA_B3', 'eta-b3', (), 'ETA_B4', (('C', _HP),),
            _alloc(TAG_ENV, _C, _NIL, _E)), {}),
        Phase('ETA_B4', PC_ETA_B4, (_K,), (), _pair(
            'ETA_B4', 'eta-b4', (('kind', 'k', FRAME_ETA_DOM),), 'EVAL',
            (('C', k_a), ('E', _C)),
            _alloc(TAG_NAPP, k_b, _V, _C), _replace(FRAME_ETA_BODY, _HP, k_b)), {}),
    )


def _decl_rows(phase, prefix, guard, goto, assign, stk):
    rows = []
    for name, kind in (('ax', DECL_AXIOM), ('def', DECL_DEF), ('opq', DECL_OPAQUE)):
        rows.append(_go(phase, prefix + name, guard + (('decl', 'd', kind),), goto, assign, stk=stk))
    rows.append(_else(phase))
    return tuple(rows)


def _proof(k_a, k_b, d_a):
    """Neutral head, then its declaration. P0 has two read rounds, so the const cell is saved first."""
    const_port = (
        Port('c', 'heap_a', 1, _V),
        Port('d', 'decl', 2, _NIL, (((('tag', 'c', TAG_CONST),), ('field', 'c', 'a')),)),
    )
    const_g = (('tag', 'c', TAG_CONST),)
    return (
        Phase('PRF0', PC_PRF0, (_K,), (), _pair(
            'PRF0', 'prf0', (('kind', 'k', FRAME_CMP),), 'PRF_NEU', (('C', k_a),)), {}),
        Phase('PRF_NEU', PC_PRF_NEU, (
            Port('n', 'heap_a', 1, _C),
        ), (), _pair(
            'PRF_NEU', 'prf-head', (('tag', 'n', TAG_NEU),), 'PRF1',
            (('V', ('field', 'n', 'a')),),
        )),
        Phase('PRF1', PC_PRF1, const_port + (_K,), (), _decl_rows(
            'PRF1', 'prf1-', const_g + (('kind', 'k', FRAME_CMP),), 'EVAL',
            (('C', d_a), ('E', _NIL)), _push(FRAME_PRF_TY, d_a, k_b))),
        Phase('PRF_CLS0', PC_PRF_CLS0, (
            Port('n', 'heap_a', 1, _V),
        ), (), _pair(
            'PRF_CLS0', 'prf-cls-head', (('tag', 'n', TAG_NEU),), 'PRF_CLS1',
            (('C', ('field', 'n', 'a')),),
        )),
        Phase('PRF_CLS1', PC_PRF_CLS1, (
            Port('c', 'heap_a', 1, _C),
            Port('d', 'decl', 2, _NIL, (((('tag', 'c', TAG_CONST),), ('field', 'c', 'a')),)),
            _K,
        ), (), _decl_rows(
            'PRF_CLS1', 'prf-cls-', const_g + (('kind', 'k', FRAME_PRF_TY),), 'EVAL',
            (('C', d_a), ('E', _NIL)), _replace(FRAME_PRF_CLS, k_a))),
        Phase('PRF_R0', PC_PRF_R0, (_K,), (), _pair(
            'PRF_R0', 'prf-r0', (('kind', 'k', FRAME_CMP),), 'PRF_R1', (('V', k_b),)), {}),
        Phase('PRF_R1', PC_PRF_R1, (
            Port('n', 'heap_a', 1, _V),
        ), (), _pair(
            'PRF_R1', 'prf-r-head', (('tag', 'n', TAG_NEU),), 'PRF_R2',
            (('V', ('field', 'n', 'a')),),
        )),
        Phase('PRF_R2', PC_PRF_R2, const_port + (_K,), (), _decl_rows(
            'PRF_R2', 'prf-r-', const_g + (('kind', 'k', FRAME_CMP),), 'PRF_PUSH',
            (('V', d_a), ('E', _NIL)), ('pop',))),
        Phase('PRF_PUSH', PC_PRF_PUSH, (), (), _pair(
            'PRF_PUSH', 'prf-push', (), 'EVAL', stk=_push(FRAME_CONV_R, _V)), {}),
    )


def _let(k_a, k_b, n_a, n_b, n_c, e_b):
    let_g = (('kind', 'k', FRAME_LET_ANN), ('tag', 'n', TAG_LET))
    return (
        Phase('LET_VAL0', PC_LET_VAL0, (
            _K, _heap('n', 'heap_b', 2, k_a, refine=(('kind', 'k', FRAME_LET_ANN),)),
        ), (), _pair(
            'LET_VAL0', 'let-val', let_g, 'INFER',
            (('C', n_b), ('E', k_b)), stk=_replace(FRAME_LET_VAL, k_a, k_b)), {}),
        Phase('LET_PREP', PC_LET_PREP, (
            _K, _heap('n', 'heap_b', 2, k_a, refine=(('kind', 'k', FRAME_LET_VAL),)),
        ), (), _pair(
            'LET_PREP', 'let-prep', (('kind', 'k', FRAME_LET_VAL), ('tag', 'n', TAG_LET)), 'LET_PUSH',
            (('C', n_a), ('E', k_b)), stk=_replace(FRAME_LET_BODY, k_a, k_b)), {}),
        Phase('LET_PUSH', PC_LET_PUSH, (_K,), (), _pair(
            'LET_PUSH', 'let-push', (('kind', 'k', FRAME_LET_BODY),), 'EVAL',
            (('C', _V), ('E', _A2)), stk=_push(FRAME_CONV_R, _C, _E)), {}),
        Phase('LET_EXT1', PC_LET_EXT1, (
            _K, _heap('n', 'heap_b', 2, k_a, refine=(('kind', 'k', FRAME_LET_BODY),)),
        ), (), _pair(
            'LET_EXT1', 'let-ext1', (('kind', 'k', FRAME_LET_BODY), ('tag', 'n', TAG_LET)), 'LET_EXT2',
            (('V', n_a), ('C', n_c), ('A1', _HP)),
            _alloc(TAG_ENV, n_b, k_b, k_b), _replace(FRAME_LET_BODY, k_a, _HP)), {}),
        Phase('LET_EXT2', PC_LET_EXT2, (
            Port('e', 'heap_a', 1, _A1),
        ), (), _pair(
            'LET_EXT2', 'let-ext2', (('tag', 'e', TAG_ENV),), 'INFER',
            (('E', _A1), ('U', _HP)),
            _alloc(TAG_ENV, _V, e_b, _U)), {}),
    )


def _normalize_decl(item):
    if isinstance(item, dict):
        name, type_term = item['name'], item['type']
        value = item.get('value')
        opaque = bool(item.get('opaque', False))
    elif hasattr(item, 'name') and hasattr(item, 'type'):
        name, type_term, value = item.name, item.type, item.value
        opaque = bool(item.opaque)
    else:
        return item
    if opaque:
        kind = DECL_OPAQUE
    elif value is None:
        kind = DECL_AXIOM
    else:
        kind = DECL_DEF
    return name, kind, type_term, value


def load_ground(term, claim, declarations=(), fuel=10000, heap_cap=512, stack_cap=32, universe_cap=4):
    """Load a closed judgment. DONE on this machine means the check succeeded.

    Declaration memory is not evidence that an inductive source block was admitted.
    """
    if type(fuel) is not int or not 0 <= fuel <= WORD:
        raise UnsupportedInput('fuel does not fit in 16 bits')
    if type(heap_cap) is not int or not 1 <= heap_cap <= WORD:
        raise UnsupportedInput('heap capacity does not fit in 16 bits')
    if type(stack_cap) is not int or not 2 <= stack_cap <= WORD:
        raise UnsupportedInput('stack capacity does not fit in 16 bits')
    if type(universe_cap) is not int or not 0 <= universe_cap <= WORD:
        raise UnsupportedInput('universe capacity does not fit in 16 bits')
    built = _Builder(allow_opaque=True)
    for item in declarations:
        name, kind, type_term, value = _normalize_decl(item)
        built.declaration(name, kind, type_term, value)
    term_addr = built.term(_as_tuple(term))
    claim_addr = built.term(_as_tuple(claim))
    if len(built.heap) - 1 > heap_cap:
        raise UnsupportedInput('input cells do not fit the heap capacity')
    heap = built.heap + [Cell() for _ in range(heap_cap - (len(built.heap) - 1))]
    stk = [Cell() for _ in range(stack_cap + 1)]
    stk[1] = Cell(kind=FRAME_HALT)
    stk[2] = Cell(kind=FRAME_CHECK, a=term_addr, b=claim_addr)
    regs = Regs(pc=PC_INFER, status=0, C=claim_addr, E=0, K=2, hp=len(built.heap), fuel=fuel)
    return Machine(regs, heap, stk, built.decl, tuple(built.names), heap_cap, stack_cap, universe_cap)


def check_ground(term, claim, declarations=(), fuel=10000, heap_cap=512, stack_cap=32, universe_cap=4):
    table = ground_table()
    machine = load_ground(term, claim, declarations, fuel, heap_cap, stack_cap, universe_cap)
    report = run(machine, table, max_steps=fuel + 5)
    return machine, report
