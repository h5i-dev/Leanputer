"""Table-driven Lean node-transition machine.

The same table drives the reference executor, the static checks, and the
cost report. Rows are data. The executor has no per-row callback.

Resolved limits, recorded here so later rows do not reopen them:

* Address 0 is a null cell. Any other address outside the allocated bank is
  an invalid-port cell. Neither tag matches a real row, so a bad eager read
  falls through to the phase ``else`` instead of looking like a real term.
* RET port B reads ``v.a`` only when the stack frame is ``F_APP`` and ``v``
  is ``CLO``. ``NAPP.a`` is the function value, not ``CLO.tm``, and is not
  used as that address. ``F_UPD`` reads ``k.a``. Every other case reads null.
* Fuel 0 is the first resource and changes only ``status``. Heap allocation
  is checked before a stack push. A failed heap or stack transition
  decrements fuel and writes nothing else. ``hp``, ``K``, and ``fuel`` move
  by fixed structural updates, not by the two programmable ALU lanes.
* A memo write sets the memo word and the memo bit of an ``ENV`` cell read
  on this transition. The other words stay. A second write, or a write that
  is not an ``ENV`` cell, is ``INVALID`` and does not store. ``DONE`` is
  produced only by a row marked ``done``.
* Fuel 0 is detected without subtracting from the unsigned fuel word.
  ``hp``, ``K``, and ``fuel`` then move by fixed adders. Those adders are
  not the two programmable ALU lanes.
* The 24-row WHNF table has no opaque row. ``DECL_OPAQUE`` is rejected at
  load until a ground table adds an explicit row. An unknown constant is a
  declaration index 0 and runs to ``INVALID``; it is not a host exception.
* ``benchmarks/kernel-full-source-stock/source.jsonl`` contains an inductive
  block and a recursor claim. Ground-only checking cannot admit that pair
  before inductive support exists. This declaration memory is not admission
  evidence and is not a trusted signature for that block.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


WORD_BITS = 16
WORD = (1 << WORD_BITS) - 1

STATUS_RUN = 0
STATUS_DONE = 1
STATUS_INVALID = 2
STATUS_RESOURCE = 3

TAG_NULL = 0
TAG_BVAR = 1
TAG_SORT = 2
TAG_CONST = 3
TAG_APP = 4
TAG_LAM = 5
TAG_PI = 6
TAG_LET = 7
TAG_ENV = 8
TAG_CLO = 9
TAG_NEU = 10
TAG_NAPP = 11
TAG_INVALID = 15

FRAME_NONE = 0
FRAME_HALT = 1
FRAME_APP = 2
FRAME_UPD = 3
# Ground checking continuations. Each kind is one return action.
FRAME_CHECK = 4
FRAME_BIND_LAM = 5
FRAME_BIND_PI = 6
FRAME_WHNF_DOM = 7
FRAME_BODY_LAM = 8
FRAME_BODY_PI = 9
FRAME_CONV_L = 10
FRAME_CONV_R = 11
# Ground continuations. CHK_* is the top-level judgment. The rest are
# one return action each: compare, application, eta, or proof irrelevance.
FRAME_CHK_WHNF = 12
FRAME_CHK_TERM = 13
FRAME_CHK_WAIT = 14
FRAME_CMP = 15
FRAME_APP_FN = 16
FRAME_APP_WHNF = 17
FRAME_APP_ARG = 18
FRAME_APP_AFTER = 19
FRAME_WHNF_BODY = 20
FRAME_PI_BODY = 21
FRAME_NAPP_FN = 22
FRAME_JOIN = 23
FRAME_ETA_TY = 24
FRAME_ETA_DOM = 25
FRAME_ETA_BODY = 26
FRAME_PRF_TY = 27
FRAME_PRF_CLS = 28
FRAME_LET_ANN = 29
FRAME_LET_VAL = 30
FRAME_LET_BODY = 31

DECL_NONE = 0
DECL_AXIOM = 1
DECL_DEF = 2
DECL_OPAQUE = 3

PC_EVAL = 1
PC_LOOKUP = 2
PC_RET = 3
PC_INFER = 4
PC_IRET = 5
PC_TLOOK = 6
PC_CONV = 7
PC_ENTER, PC_BUILD0, PC_BUILD1 = 8, 9, 10
PC_PUSH_CHK, PC_CMP, PC_CMP_TERM, PC_CMP_NEU = 11, 12, 13, 14
PC_START_ARG, PC_APP_DOM0, PC_APP_DOM1, PC_APP_PUSH = 15, 16, 17, 18
PC_APP_INST0, PC_APP_INST1, PC_APP_INST2, PC_POP_APP = 19, 20, 21, 22
PC_PUSH_PAIR, PC_NAPP_ARGS = 23, 24
PC_PI_L0, PC_PI_L1, PC_PI_L2, PC_PI_R0, PC_PI_R1 = 25, 26, 27, 28, 29
PC_PI_B0, PC_PI_B1, PC_PI_B2, PC_PI_B3, PC_PI_B4, PC_PI_B5 = 30, 31, 32, 33, 34, 35
PC_PI_B6, PC_PI_PUSH = 36, 37
PC_ETA_CLO, PC_ETA_TYPE = 38, 39
PC_ETA_D0, PC_ETA_D1, PC_ETA_D2, PC_ETA_D3, PC_ETA_DPUSH = 40, 41, 42, 43, 44
PC_ETA_B0, PC_ETA_B1, PC_ETA_B2, PC_ETA_B3, PC_ETA_B4 = 45, 46, 47, 48, 49
PC_PRF0, PC_PRF1, PC_PRF_CLS0, PC_PRF_R0, PC_PRF_R1, PC_PRF_PUSH = 50, 51, 52, 53, 54, 55
PC_LET_VAL0, PC_LET_PREP, PC_LET_PUSH = 56, 57, 58
PC_LET_EXT1, PC_LET_EXT2 = 59, 60
PC_ETA_HEAD, PC_PRF_NEU, PC_PRF_CLS1, PC_PRF_R2 = 61, 62, 63, 64
PC_NAME = {
    PC_EVAL: 'EVAL', PC_LOOKUP: 'LOOKUP', PC_RET: 'RET',
    PC_INFER: 'INFER', PC_IRET: 'IRET', PC_TLOOK: 'TLOOK', PC_CONV: 'CONV',
    PC_ENTER: 'ENTER', PC_BUILD0: 'BUILD0', PC_BUILD1: 'BUILD1',
    PC_PUSH_CHK: 'PUSH_CHK', PC_CMP: 'CMP', PC_CMP_TERM: 'CMP_TERM', PC_CMP_NEU: 'CMP_NEU',
    PC_START_ARG: 'START_ARG', PC_APP_DOM0: 'APP_DOM0', PC_APP_DOM1: 'APP_DOM1',
    PC_APP_PUSH: 'APP_PUSH', PC_APP_INST0: 'APP_INST0', PC_APP_INST1: 'APP_INST1',
    PC_APP_INST2: 'APP_INST2', PC_POP_APP: 'POP_APP',
    PC_PUSH_PAIR: 'PUSH_PAIR', PC_NAPP_ARGS: 'NAPP_ARGS',
    PC_PI_L0: 'PI_L0', PC_PI_L1: 'PI_L1', PC_PI_L2: 'PI_L2', PC_PI_R0: 'PI_R0', PC_PI_R1: 'PI_R1',
    PC_PI_B0: 'PI_B0', PC_PI_B1: 'PI_B1', PC_PI_B2: 'PI_B2', PC_PI_B3: 'PI_B3',
    PC_PI_B4: 'PI_B4', PC_PI_B5: 'PI_B5', PC_PI_B6: 'PI_B6', PC_PI_PUSH: 'PI_PUSH',
    PC_ETA_CLO: 'ETA_CLO', PC_ETA_TYPE: 'ETA_TYPE',
    PC_ETA_D0: 'ETA_D0', PC_ETA_D1: 'ETA_D1', PC_ETA_D2: 'ETA_D2', PC_ETA_D3: 'ETA_D3',
    PC_ETA_DPUSH: 'ETA_DPUSH',
    PC_ETA_B0: 'ETA_B0', PC_ETA_B1: 'ETA_B1', PC_ETA_B2: 'ETA_B2', PC_ETA_B3: 'ETA_B3',
    PC_ETA_B4: 'ETA_B4',
    PC_PRF0: 'PRF0', PC_PRF1: 'PRF1', PC_PRF_CLS0: 'PRF_CLS0',
    PC_PRF_R0: 'PRF_R0', PC_PRF_R1: 'PRF_R1', PC_PRF_PUSH: 'PRF_PUSH',
    PC_LET_VAL0: 'LET_VAL0', PC_LET_PREP: 'LET_PREP', PC_LET_PUSH: 'LET_PUSH',
    PC_LET_EXT1: 'LET_EXT1', PC_LET_EXT2: 'LET_EXT2',
    PC_ETA_HEAD: 'ETA_HEAD', PC_PRF_NEU: 'PRF_NEU', PC_PRF_CLS1: 'PRF_CLS1',
    PC_PRF_R2: 'PRF_R2',
}
PC_OF = {name: pc for pc, name in PC_NAME.items()}

REGISTERS = (
    'pc', 'status', 'flags', 'C', 'E', 'K', 'V', 'A0', 'A1', 'A2', 'U', 'lvl', 'hp', 'fuel',
)
WORD_REGISTERS = ('C', 'E', 'K', 'V', 'A0', 'A1', 'A2', 'U', 'lvl', 'hp', 'fuel')
PROGRAMMABLE = ('pc', 'status', 'flags', 'C', 'E', 'V', 'A0', 'A1', 'A2', 'U', 'lvl')
REG_WIDTH = {
    'pc': 12, 'status': 4, 'flags': 8,
    **{name: WORD_BITS for name in WORD_REGISTERS},
}

CAUSE_FUEL = 'FUEL'
CAUSE_HEAP = 'HEAP'
CAUSE_STACK = 'STACK'
CAUSE_UNIVERSE = 'UNIVERSE'


class StaticRejection(ValueError):
    def __init__(self, check, detail):
        super().__init__(f'{check}: {detail}')
        self.check = check
        self.detail = detail


class UnsupportedInput(ValueError):
    pass


@dataclass(frozen=True)
class Profile:
    name: str = 'P0'
    heap_read_ports: int = 2
    read_rounds: int = 2
    stk_reads: int = 1
    decl_reads: int = 1
    heap_writes: int = 1
    stk_writes: int = 1
    predicate_bits: int = 3
    alu_lanes: int = 2


P0 = Profile()


@dataclass(frozen=True)
class Port:
    name: str
    bank: str
    round: int
    addr: tuple
    choices: tuple = ()
    # Atoms that pin an earlier cell before a direct field address is used.
    # When they fail, the address is null. A bare field address has no plan.
    refine: tuple = ()


@dataclass(frozen=True)
class Phase:
    name: str
    pc: int
    reads: tuple
    alus: tuple
    rows: tuple
    entry: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Row:
    phase: str
    name: str
    guard: tuple
    assign: tuple = ()
    heap: tuple | None = None
    stk: tuple | None = None
    goto: str = ''
    done: bool = False
    fallback: bool = False


@dataclass(frozen=True)
class Table:
    phases: tuple
    profile: Profile = P0

    def phase(self, pc):
        for phase in self.phases:
            if phase.pc == pc:
                return phase
        raise KeyError(pc)

    def rows(self):
        return tuple(row for phase in self.phases for row in phase.rows)


@dataclass
class Cell:
    tag: int = TAG_NULL
    a: int = 0
    b: int = 0
    c: int = 0
    m: int = 0
    memo: bool = False
    kind: int = 0

    def field(self, name):
        return getattr(self, name)


@dataclass
class Regs:
    pc: int = PC_EVAL
    status: int = STATUS_RUN
    flags: int = 0
    C: int = 0
    E: int = 0
    K: int = 0
    V: int = 0
    A0: int = 0
    A1: int = 0
    A2: int = 0
    U: int = 0
    lvl: int = 0
    hp: int = 1
    fuel: int = 0


@dataclass
class Machine:
    regs: Regs
    heap: list
    stk: list
    decl: list
    names: tuple = ()
    heap_cap: int = 512
    stack_cap: int = 32
    universe_cap: int = 4


def _null():
    return Cell()


def _invalid():
    return Cell(tag=TAG_INVALID, kind=FRAME_NONE)


def _clip(value):
    return int(value) & WORD


# Field sorts implied by a tag or a frame/decl kind. ZERO is the unused word.
HEAP = 'HEAP'
HEAP_OR_NULL = 'HEAP?'
DECL = 'DECL'
NAT = 'NAT'
NULL = 'NULL'
ZERO = 'ZERO'

_TERM_FIELDS = {
    TAG_BVAR: {'a': NAT},
    TAG_SORT: {'a': NAT},
    TAG_CONST: {'a': DECL, 'b': NULL},
    TAG_APP: {'a': HEAP, 'b': HEAP},
    TAG_LAM: {'a': HEAP, 'b': HEAP},
    TAG_PI: {'a': HEAP, 'b': HEAP},
    TAG_LET: {'a': HEAP, 'b': HEAP, 'c': HEAP},
    TAG_ENV: {'a': HEAP, 'b': HEAP_OR_NULL, 'c': HEAP_OR_NULL, 'm': HEAP},
    TAG_CLO: {'a': HEAP, 'b': HEAP_OR_NULL},
    TAG_NEU: {'a': HEAP},
    TAG_NAPP: {'a': HEAP, 'b': HEAP, 'c': HEAP_OR_NULL},
}
_FRAME_FIELDS = {
    FRAME_APP: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_UPD: {'a': HEAP, 'b': NULL},
    FRAME_HALT: {},
    FRAME_CHECK: {'a': HEAP, 'b': HEAP},
    FRAME_BIND_LAM: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_BIND_PI: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_WHNF_DOM: {'a': HEAP, 'b': HEAP_OR_NULL},
    # Lam keeps the term environment. Pi keeps the domain universe level.
    FRAME_BODY_LAM: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_BODY_PI: {'a': HEAP, 'b': NAT},
    FRAME_CONV_L: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_CONV_R: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_CHK_WHNF: {'a': HEAP, 'b': HEAP},
    FRAME_CHK_TERM: {'a': HEAP, 'b': NULL},
    FRAME_CHK_WAIT: {'a': HEAP, 'b': NULL},
    FRAME_CMP: {'a': HEAP, 'b': HEAP},
    FRAME_APP_FN: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_APP_WHNF: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_APP_ARG: {'a': HEAP, 'b': HEAP},
    FRAME_APP_AFTER: {'a': HEAP, 'b': HEAP},
    FRAME_WHNF_BODY: {'a': HEAP, 'b': NAT},
    FRAME_PI_BODY: {'a': HEAP, 'b': HEAP},
    FRAME_NAPP_FN: {'a': HEAP, 'b': HEAP},
    FRAME_JOIN: {},
    FRAME_ETA_TY: {'a': HEAP, 'b': HEAP},
    FRAME_ETA_DOM: {'a': HEAP, 'b': HEAP},
    FRAME_ETA_BODY: {'a': HEAP, 'b': HEAP},
    FRAME_PRF_TY: {'a': HEAP, 'b': HEAP},
    FRAME_PRF_CLS: {'a': HEAP, 'b': NULL},
    FRAME_LET_ANN: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_LET_VAL: {'a': HEAP, 'b': HEAP_OR_NULL},
    FRAME_LET_BODY: {'a': HEAP, 'b': HEAP_OR_NULL},
}
_DECL_FIELDS = {
    DECL_DEF: {'a': HEAP, 'b': HEAP},
    DECL_AXIOM: {'a': HEAP, 'b': NULL},
    DECL_OPAQUE: {'a': HEAP, 'b': HEAP},
}


def _compatible(have, need):
    if need is None:
        return True
    if have == need:
        return True
    if need == HEAP_OR_NULL and have in (HEAP, NULL, HEAP_OR_NULL, ZERO):
        return True
    if need == HEAP and have == HEAP:
        return True
    return False


def _predicate_atoms(guard):
    return tuple(atom for atom in guard if atom[0] in ('eq', 'ne', 'lt', 'ge', 'not_kind'))


def _comparator_key(atom):
    """One predicate bit. eq/ne share a bit, and lt/ge of the same pair share a bit."""
    op, left, right = atom[0], atom[1], atom[2]
    if op == 'not_kind':
        return ('not_kind', left, right)
    if op == 'ne':
        op = 'eq'
    elif op == 'lt':
        op = 'ge'
    return (op, left, right)


def _phase_predicate_keys(phase):
    keys = set()
    for row in phase.rows:
        for atom in _predicate_atoms(row.guard):
            keys.add(_comparator_key(atom))
    return keys


def _source_key(source):
    return source


def _eval_source(source, regs, cells, alu_values):
    kind = source[0]
    if kind == 'reg':
        return getattr(regs, source[1])
    if kind == 'field':
        return cells[source[1]].field(source[2])
    if kind == 'hp':
        return regs.hp
    if kind == 'imm':
        value = source[1]
        if type(value) is not int or not 0 <= value <= WORD:
            raise StaticRejection('width', f'immediate {value}')
        return value
    if kind == 'alu':
        return alu_values[source[1]]
    if kind == 'null':
        return 0
    raise StaticRejection('menu', f'unknown source {source}')


def _compare_values(kind, left, right):
    if kind == 'eq':
        return left == right
    if kind == 'ne':
        return left != right
    if kind == 'lt':
        return left < right
    if kind == 'ge':
        return left >= right
    raise StaticRejection('guard', f'unknown compare {kind}')


def _atom_holds(atom, regs, cells):
    kind = atom[0]
    if kind == 'tag':
        return cells[atom[1]].tag == atom[2]
    if kind == 'memo':
        return cells[atom[1]].memo
    if kind == 'not_memo':
        return not cells[atom[1]].memo
    if kind == 'kind':
        return cells[atom[1]].kind == atom[2]
    if kind == 'not_kind':
        return cells[atom[1]].kind != atom[2]
    if kind == 'decl':
        return cells[atom[1]].kind == atom[2]
    left = _eval_source(atom[1], regs, cells, ())
    right = atom[2]
    if isinstance(right, tuple):
        right = _eval_source(right, regs, cells, ())
    return _compare_values(kind, left, right)


def _guard_holds(row, regs, cells):
    return all(_atom_holds(atom, regs, cells) for atom in row.guard)


def _alu_value(alu, regs, cells):
    op, left, right = alu
    a = _eval_source(left, regs, cells, ())
    b = _eval_source(right, regs, cells, ())
    if op == 'sub':
        return _clip(a - b)
    if op == 'add':
        return _clip(a + b)
    raise StaticRejection('alu', f'unknown op {op}')


def _read_cell(machine, bank, addr):
    if addr == 0:
        return _null()
    if bank in ('heap_a', 'heap_b'):
        if not 1 <= addr < machine.regs.hp or addr > machine.heap_cap:
            return _invalid()
        return machine.heap[addr]
    if bank == 'stk':
        if addr != machine.regs.K or not 1 <= addr <= machine.stack_cap:
            return _invalid()
        return machine.stk[addr]
    if bank == 'decl':
        if not 1 <= addr < len(machine.decl):
            return _invalid()
        return machine.decl[addr]
    raise StaticRejection('read', f'unknown bank {bank}')


def _port_address(port, regs, cells):
    if port.refine and not all(_atom_holds(atom, regs, cells) for atom in port.refine):
        return 0
    if port.choices:
        for guard, source in port.choices:
            if all(_atom_holds(atom, regs, cells) for atom in guard):
                return _eval_source(source, regs, cells, ())
        return 0
    return _eval_source(port.addr, regs, cells, ())


def _select_row(phase, regs, cells):
    matched = [row for row in phase.rows if not row.fallback and _guard_holds(row, regs, cells)]
    if len(matched) > 1:
        names = ', '.join(row.name for row in matched)
        raise StaticRejection('exclusive', f'{phase.name} matched {names}')
    if len(matched) == 1:
        return matched[0]
    fallback = [row for row in phase.rows if row.fallback]
    if len(fallback) != 1:
        raise StaticRejection('exhaustive', f'{phase.name} has no else row')
    return fallback[0]


def _assigned_sources(row):
    sources = [source for _, source in row.assign]
    if row.heap is not None and row.heap[0] == 'alloc':
        sources.extend(row.heap[2:])
    if row.stk is not None and row.stk[0] in ('push', 'replace'):
        sources.extend(row.stk[2:])
    return sources


def step(machine, table):
    """One transition. Absorbing statuses do not change registers or banks."""
    regs = machine.regs
    event = {
        'pc': PC_NAME.get(regs.pc, regs.pc), 'row': None, 'cause': None, 'reads': {},
        'alloc': None, 'memo': None, 'stk': None, 'predicates': 0, 'alus': 0,
        'heap_ports': 0, 'rounds': 0, 'fuel_before': regs.fuel, 'fuel_delta': 0,
    }
    if regs.status != STATUS_RUN:
        event['row'] = 'absorb'
        return event
    if regs.fuel == 0:
        regs.status = STATUS_RESOURCE
        event['row'] = 'resource-fuel'
        event['cause'] = CAUSE_FUEL
        return event
    phase = table.phase(regs.pc)
    cells = {}
    rounds = set()
    heap_ports = 0
    ordered = sorted(phase.reads, key=lambda port: port.round)
    for port in ordered:
        addr = _port_address(port, regs, cells)
        cells[port.name] = _read_cell(machine, port.bank, addr)
        event['reads'][port.name] = addr
        rounds.add(port.round)
        if port.bank in ('heap_a', 'heap_b'):
            heap_ports += 1
    alu_values = tuple(_alu_value(alu, regs, cells) for alu in phase.alus)
    row = _select_row(phase, regs, cells)
    event['row'] = row.name
    event['predicates'] = len(_predicate_atoms(row.guard))
    event['alus'] = sum(1 for source in _assigned_sources(row) if source[0] == 'alu')
    event['heap_ports'] = heap_ports
    event['rounds'] = max(rounds) if rounds else 0
    allocating = row.heap is not None and row.heap[0] == 'alloc'
    pushing = row.stk is not None and row.stk[0] == 'push'
    if allocating and regs.hp > machine.heap_cap:
        regs.fuel = _clip(regs.fuel - 1)
        regs.status = STATUS_RESOURCE
        event['cause'] = CAUSE_HEAP
        event['fuel_delta'] = -1
        return event
    if pushing and regs.K >= machine.stack_cap:
        regs.fuel = _clip(regs.fuel - 1)
        regs.status = STATUS_RESOURCE
        event['cause'] = CAUSE_STACK
        event['fuel_delta'] = -1
        return event
    memo_plan = None
    if row.heap is not None and row.heap[0] == 'memo':
        _, port, value_src = row.heap
        addr = event['reads'][port]
        cell = cells[port]
        if port not in cells or not 1 <= addr < regs.hp or cell.tag != TAG_ENV:
            regs.status = STATUS_INVALID
            regs.fuel = _clip(regs.fuel - 1)
            event['cause'] = 'MEMO_ADDRESS'
            event['fuel_delta'] = -1
            return event
        if cell.memo:
            regs.status = STATUS_INVALID
            regs.fuel = _clip(regs.fuel - 1)
            event['cause'] = 'MEMO_TWICE'
            event['fuel_delta'] = -1
            return event
        memo_plan = (addr, _eval_source(value_src, regs, cells, alu_values))
    updates = {name: _eval_source(source, regs, cells, alu_values) for name, source in row.assign}
    if row.goto:
        updates['pc'] = PC_OF[row.goto]
    new_hp = regs.hp
    new_k = regs.K
    heap_cell = None
    stk_cell = None
    stk_addr = None
    if allocating:
        _, tag, a_src, b_src, c_src = row.heap
        heap_cell = (regs.hp, Cell(
            tag=tag,
            a=_eval_source(a_src, regs, cells, alu_values),
            b=_eval_source(b_src, regs, cells, alu_values),
            c=_eval_source(c_src, regs, cells, alu_values),
        ))
        new_hp = _clip(regs.hp + 1)
        event['alloc'] = regs.hp
    if row.stk is not None and row.stk[0] == 'push':
        _, kind, a_src, b_src = row.stk
        stk_addr = regs.K + 1
        stk_cell = Cell(
            kind=kind,
            a=_eval_source(a_src, regs, cells, alu_values),
            b=_eval_source(b_src, regs, cells, alu_values),
        )
        new_k = regs.K + 1
        event['stk'] = 'push'
    elif row.stk is not None and row.stk[0] == 'pop':
        if regs.K <= 0:
            regs.status = STATUS_INVALID
            regs.fuel = _clip(regs.fuel - 1)
            event['cause'] = 'EMPTY_STACK'
            event['fuel_delta'] = -1
            return event
        new_k = regs.K - 1
        event['stk'] = 'pop'
    elif row.stk is not None and row.stk[0] == 'replace':
        if regs.K <= 0:
            regs.status = STATUS_INVALID
            regs.fuel = _clip(regs.fuel - 1)
            event['cause'] = 'EMPTY_STACK'
            event['fuel_delta'] = -1
            return event
        _, kind, a_src, b_src = row.stk
        stk_addr = regs.K
        stk_cell = Cell(
            kind=kind,
            a=_eval_source(a_src, regs, cells, alu_values),
            b=_eval_source(b_src, regs, cells, alu_values),
        )
        event['stk'] = 'replace'
    if 'lvl' in updates and updates['lvl'] > machine.universe_cap:
        regs.fuel = _clip(regs.fuel - 1)
        regs.status = STATUS_RESOURCE
        event['cause'] = CAUSE_UNIVERSE
        event['fuel_delta'] = -1
        return event
    if heap_cell is not None:
        machine.heap[heap_cell[0]] = heap_cell[1]
    if memo_plan is not None:
        addr, value = memo_plan
        prior = machine.heap[addr]
        machine.heap[addr] = replace(prior, m=_clip(value), memo=True)
        event['memo'] = addr
    if stk_cell is not None:
        machine.stk[stk_addr] = stk_cell
    for name, value in updates.items():
        if name in ('pc', 'status', 'flags'):
            setattr(regs, name, int(value))
        else:
            setattr(regs, name, _clip(value))
    regs.hp = new_hp
    regs.K = new_k
    regs.fuel = _clip(regs.fuel - 1)
    event['fuel_delta'] = -1
    return event


def run(machine, table, max_steps=100000):
    trace = []
    peak_k = machine.regs.K
    while len(trace) < max_steps:
        event = step(machine, table)
        trace.append(event)
        peak_k = max(peak_k, machine.regs.K)
        if machine.regs.status != STATUS_RUN:
            break
    return {
        'trace': trace,
        'steps': sum(1 for event in trace if event['fuel_delta']),
        'fueled_rows': sum(1 for event in trace if event['fuel_delta']),
        'fuel_detections': sum(1 for event in trace if event['row'] == 'resource-fuel'),
        'absorbs': sum(1 for event in trace if event['row'] == 'absorb'),
        'transitions': len(trace),
        'allocs': sum(1 for event in trace if event['alloc']),
        'peak_k': peak_k,
        'peak_depth': max(0, peak_k - 1),
        'truncated': machine.regs.status == STATUS_RUN,
        'max_predicates': max((event['predicates'] for event in trace), default=0),
        'max_alus': max((event['alus'] for event in trace), default=0),
        'max_heap_ports': max((event['heap_ports'] for event in trace), default=0),
        'max_rounds': max((event['rounds'] for event in trace), default=0),
    }


# --- static checks ----------------------------------------------------------

_HEAP_BANKS = ('heap_a', 'heap_b')
_BANKS = ('heap_a', 'heap_b', 'stk', 'decl')
_SOURCE_KINDS = ('reg', 'field', 'hp', 'imm', 'alu', 'null')
_GUARD_KINDS = ('tag', 'memo', 'not_memo', 'kind', 'not_kind', 'decl', 'eq', 'ne', 'lt', 'ge')
_CHOICE_GUARDS = ('tag', 'memo', 'not_memo', 'kind', 'not_kind', 'decl')
_FIELD_NAMES = ('a', 'b', 'c', 'm')
_HEAP_TAGS = (
    TAG_NULL, TAG_BVAR, TAG_SORT, TAG_CONST, TAG_APP, TAG_LAM, TAG_PI, TAG_LET,
    TAG_ENV, TAG_CLO, TAG_NEU, TAG_NAPP, TAG_INVALID,
)
_FRAME_KINDS = (
    FRAME_NONE, FRAME_HALT, FRAME_APP, FRAME_UPD, FRAME_CHECK, FRAME_BIND_LAM,
    FRAME_BIND_PI, FRAME_WHNF_DOM, FRAME_BODY_LAM, FRAME_BODY_PI, FRAME_CONV_L,
    FRAME_CONV_R, FRAME_CHK_WHNF, FRAME_CHK_TERM, FRAME_CHK_WAIT, FRAME_CMP,
    FRAME_APP_FN, FRAME_APP_WHNF, FRAME_APP_ARG, FRAME_APP_AFTER, FRAME_WHNF_BODY,
    FRAME_PI_BODY, FRAME_NAPP_FN, FRAME_JOIN, FRAME_ETA_TY, FRAME_ETA_DOM,
    FRAME_ETA_BODY, FRAME_PRF_TY, FRAME_PRF_CLS, FRAME_LET_ANN, FRAME_LET_VAL,
    FRAME_LET_BODY,
)
_DECL_KINDS = (DECL_NONE, DECL_AXIOM, DECL_DEF, DECL_OPAQUE)
PC_SORT = 'PC'
STATUS_SORT = 'STATUS'
FLAGS_SORT = 'FLAGS'
STACK_SORT = 'STACK'
REG_SORT = {
    'pc': PC_SORT, 'status': STATUS_SORT, 'flags': FLAGS_SORT,
    'C': HEAP, 'E': HEAP_OR_NULL, 'K': STACK_SORT, 'V': HEAP,
    # A2 and U are addresses in the ground checker: A2 is a returned
    # environment and U is the type-context chain. WHNF never assigns them.
    'A0': NAT, 'A1': HEAP_OR_NULL, 'A2': HEAP_OR_NULL, 'U': HEAP_OR_NULL, 'lvl': NAT,
    'hp': HEAP, 'fuel': NAT,
}


def _phase_ports(phase):
    return {port.name: port for port in phase.reads}


def _field_sort(bank, tag_or_kind, field_name, memo=False):
    if bank in _HEAP_BANKS:
        if tag_or_kind in (TAG_NULL, TAG_INVALID):
            return ZERO
        sorts = _TERM_FIELDS.get(tag_or_kind, {})
        if field_name == 'm' and not memo and tag_or_kind == TAG_ENV:
            return NULL
        return sorts.get(field_name, ZERO)
    if bank == 'stk':
        return _FRAME_FIELDS.get(tag_or_kind, {}).get(field_name, ZERO)
    return _DECL_FIELDS.get(tag_or_kind, {}).get(field_name, ZERO)


def _source_width(source, ports):
    if not isinstance(source, tuple) or not source:
        raise StaticRejection('menu', f'source {source!r}')
    if source[0] == 'reg':
        if len(source) != 2 or source[1] not in REG_WIDTH:
            raise StaticRejection('menu', f'register {source!r}')
        return REG_WIDTH[source[1]]
    if source[0] == 'field':
        if len(source) != 3 or source[1] not in ports or source[2] not in _FIELD_NAMES:
            raise StaticRejection('menu', f'field {source!r}')
        return WORD_BITS
    raise StaticRejection('menu', f'source {source!r}')


def _check_guard_shape(phase, row):
    ports = _phase_ports(phase)
    for atom in row.guard:
        if not isinstance(atom, tuple) or not atom or atom[0] not in _GUARD_KINDS:
            raise StaticRejection('guard', f'{row.name} atom {atom!r}')
        kind = atom[0]
        if kind in ('tag', 'memo', 'not_memo', 'kind', 'not_kind', 'decl'):
            if len(atom) < 2 or atom[1] not in ports:
                raise StaticRejection('guard', f'{row.name} port in {atom}')
            bank = ports[atom[1]].bank
            if kind == 'tag' and (bank not in _HEAP_BANKS or len(atom) != 3 or atom[2] not in _HEAP_TAGS):
                raise StaticRejection('guard', f'{row.name} tag {atom}')
            if kind in ('memo', 'not_memo') and (bank not in _HEAP_BANKS or len(atom) != 2):
                raise StaticRejection('guard', f'{row.name} memo {atom}')
            if kind in ('kind', 'not_kind') and (bank != 'stk' or len(atom) != 3 or atom[2] not in _FRAME_KINDS):
                raise StaticRejection('guard', f'{row.name} kind {atom}')
            if kind == 'decl' and (bank != 'decl' or len(atom) != 3 or atom[2] not in _DECL_KINDS):
                raise StaticRejection('guard', f'{row.name} decl {atom}')
            continue
        if len(atom) != 3:
            raise StaticRejection('guard', f'{row.name} compare {atom}')
        width = _source_width(atom[1], ports)
        other = atom[2]
        if isinstance(other, tuple):
            _source_width(other, ports)
            continue
        if type(other) is not int or other < 0 or other >= (1 << width):
            raise StaticRejection('width', f'{row.name} compare immediate {other}')


def _known_source(source):
    return isinstance(source, tuple) and bool(source) and source[0] in _SOURCE_KINDS


def _check_addr_source(phase, port, source, guard):
    ports = _phase_ports(phase)
    if not _known_source(source):
        raise StaticRejection('menu', f'{phase.name} {port.name} address {source!r}')
    if source[0] in ('alu', 'hp', 'imm'):
        raise StaticRejection('sort', f'{phase.name} {port.name} address {source} is not typed')
    if source[0] == 'null':
        return
    if source[0] == 'reg':
        if len(source) != 2 or source[1] not in REG_SORT:
            raise StaticRejection('menu', f'{phase.name} address {source}')
        have = REG_SORT[source[1]]
    else:
        if len(source) != 3 or source[2] not in _FIELD_NAMES or source[1] not in ports:
            raise StaticRejection('menu', f'{phase.name} address {source}')
        earlier = ports[source[1]]
        if earlier.round >= port.round:
            raise StaticRejection('bounds', f'{phase.name} {port.name} depends on same-or-later {earlier.name}')
        pin = _one_pin(guard, source[1])
        if pin is None:
            raise StaticRejection('sort', f'{phase.name} {port.name} address {source} has no tag')
        have = _field_sort(earlier.bank, pin, source[2])
    if port.bank in _HEAP_BANKS and not _compatible(have, HEAP_OR_NULL):
        raise StaticRejection('sort', f'{phase.name} {port.name} reads {source} as {have}')
    if port.bank == 'decl' and have not in (DECL, NULL):
        raise StaticRejection('sort', f'{phase.name} decl address sort {have}')
    if port.bank == 'stk' and have != STACK_SORT:
        raise StaticRejection('sort', f'{phase.name} stack address {source}')


def _one_pin(guard, port_name):
    pins = [atom[2] for atom in guard if atom[0] in ('tag', 'kind', 'decl') and atom[1] == port_name]
    if len(set(pins)) != 1:
        return None
    return pins[0]


def _check_choice_guard(phase, port, guard):
    ports = _phase_ports(phase)
    if not guard:
        raise StaticRejection('bounds', f'{phase.name} {port.name} choice has an empty guard')
    for atom in guard:
        if not isinstance(atom, tuple) or not atom or atom[0] not in _CHOICE_GUARDS:
            raise StaticRejection('bounds', f'{phase.name} {port.name} choice guard {atom!r}')
        if len(atom) < 2 or atom[1] not in ports or ports[atom[1]].round >= port.round:
            raise StaticRejection('bounds', f'{phase.name} {port.name} choice uses {atom}')
    _check_guard_shape(phase, Row(phase.name, port.name, tuple(guard)))


def _check_read_plan(phase):
    for port in phase.reads:
        if port.choices and port.refine:
            raise StaticRejection('bounds', f'{phase.name} {port.name} mixes choices and refine')
        if port.bank == 'heap_a' and (port.choices or port.refine or port.addr[:1] != ('reg',)):
            raise StaticRejection('bounds', f'{phase.name} port A address is not a register')
        if port.bank == 'stk' and port.addr != ('reg', 'K'):
            raise StaticRejection('bounds', f'{phase.name} stack read is not the top')
        if port.choices:
            for guard, source in port.choices:
                _check_choice_guard(phase, port, guard)
                _check_addr_source(phase, port, source, guard)
            if port.addr != ('null',):
                _check_addr_source(phase, port, port.addr, ())
            continue
        if port.refine:
            _check_choice_guard(phase, port, port.refine)
        _check_addr_source(phase, port, port.addr, port.refine)
        if port.addr[:1] == ('field',) and not port.refine:
            raise StaticRejection('sort', f'{phase.name} {port.name} direct {port.addr} has no tag refinement')


def _check_op_shape(row):
    if row.heap is not None and row.heap[0] == 'alloc':
        if len(row.heap) != 5 or type(row.heap[1]) is not int or row.heap[1] not in _HEAP_TAGS:
            raise StaticRejection('sort', f'{row.name} alloc tag')
        for source in row.heap[2:]:
            if not _known_source(source):
                raise StaticRejection('menu', f'{row.name} alloc source {source!r}')
    if row.heap is not None and row.heap[0] == 'memo':
        if len(row.heap) != 3 or not _known_source(row.heap[2]):
            raise StaticRejection('write', f'{row.name} memo shape')
    if row.stk is not None and row.stk[0] in ('push', 'replace'):
        if len(row.stk) != 4 or row.stk[1] not in _FRAME_KINDS:
            raise StaticRejection('sort', f'{row.name} frame kind')
        for source in row.stk[2:]:
            if not _known_source(source):
                raise StaticRejection('menu', f'{row.name} frame source {source!r}')


def _check_profile(table):
    profile = table.profile
    seen_pc = set()
    seen_rows = set()
    for phase in table.phases:
        if phase.pc in seen_pc or phase.pc not in PC_NAME or phase.name != PC_NAME[phase.pc]:
            raise StaticRejection('bounds', f'phase {phase.name} pc {phase.pc}')
        seen_pc.add(phase.pc)
        names, banks = [], []
        for port in phase.reads:
            if port.name in names or port.bank in banks or port.bank not in _BANKS:
                raise StaticRejection('bounds', f'{phase.name} port {port.name} {port.bank}')
            if type(port.round) is not int or not 1 <= port.round <= profile.read_rounds:
                raise StaticRejection('bounds', f'{phase.name} read round {port.round}')
            names.append(port.name)
            banks.append(port.bank)
        heap_ports = [port for port in phase.reads if port.bank in _HEAP_BANKS]
        stk = [port for port in phase.reads if port.bank == 'stk']
        decl = [port for port in phase.reads if port.bank == 'decl']
        if len(heap_ports) > profile.heap_read_ports or len(stk) > profile.stk_reads or len(decl) > profile.decl_reads:
            raise StaticRejection('bounds', f'{phase.name} read profile')
        if len(phase.alus) > profile.alu_lanes:
            raise StaticRejection('bounds', f'{phase.name} has {len(phase.alus)} ALU lanes')
        for alu in phase.alus:
            if len(alu) != 3 or alu[0] not in ('add', 'sub'):
                raise StaticRejection('bounds', f'{phase.name} ALU op {alu!r}')
            for source in alu[1:]:
                if not _known_source(source) or source[0] == 'alu':
                    raise StaticRejection('bounds', f'{phase.name} ALU source {source!r}')
        _check_read_plan(phase)
        for row in phase.rows:
            if row.name in seen_rows or row.phase != phase.name:
                raise StaticRejection('bounds', f'row {row.name}')
            seen_rows.add(row.name)
            if len(_predicate_atoms(row.guard)) > profile.predicate_bits:
                raise StaticRejection('bounds', f'{row.name} predicate width')
            if row.fallback and row.guard:
                raise StaticRejection('exhaustive', f'{row.name} else row has a guard')
            _check_guard_shape(phase, row)
            if (row.heap is not None) + (0 if row.stk is None else 0) > profile.heap_writes:
                raise StaticRejection('bounds', f'{row.name} heap writes')
            if row.heap is not None and (row.heap[0] not in ('alloc', 'memo') or 1 > profile.heap_writes):
                raise StaticRejection('bounds', f'{row.name} heap op')
            if row.stk is not None and (row.stk[0] not in ('push', 'pop', 'replace') or 1 > profile.stk_writes):
                raise StaticRejection('bounds', f'{row.name} stk writes')
            if row.goto and row.goto not in PC_OF:
                raise StaticRejection('bounds', f'{row.name} goto {row.goto}')
            for name, source in row.assign:
                if name in ('hp', 'K', 'fuel'):
                    raise StaticRejection('bounds', f'{row.name} assigns structural {name}')
                if name not in PROGRAMMABLE or not _known_source(source):
                    raise StaticRejection('menu', f'{row.name} source {source!r}')
                if source[0] == 'alu' and (len(source) != 2 or type(source[1]) is not int or not 0 <= source[1] < len(phase.alus)):
                    raise StaticRejection('bounds', f'{row.name} ALU index')
            _check_op_shape(row)
        used = _phase_predicate_keys(phase)
        if len(used) > profile.predicate_bits:
            raise StaticRejection('bounds', f'{phase.name} uses {len(used)} predicate bits')


class _Cube:
    def __init__(self):
        self.tag, self.memo, self.kind = {}, {}, {}
        self.not_kind, self.nums = {}, {}
        self.rels = []


def _domain_hi(source):
    if source[0] == 'reg':
        return (1 << REG_WIDTH[source[1]]) - 1
    return WORD


def _nums_sat(cube):
    for source, constraints in cube.nums.items():
        lo, hi = 0, _domain_hi(source)
        eqs, banned = [], set()
        for op, imm in constraints:
            if op == 'eq':
                eqs.append(imm)
            elif op == 'ne':
                banned.add(imm)
            elif op == 'lt':
                hi = min(hi, imm - 1)
            elif op == 'ge':
                lo = max(lo, imm)
        if lo > hi:
            return False
        if eqs:
            value = eqs[0]
            if any(item != value for item in eqs) or not lo <= value <= hi or value in banned:
                return False
            continue
        if hi - lo + 1 > len(banned):
            continue
        if not any(value not in banned for value in range(lo, hi + 1)):
            return False
    return True


def _interval(constraints, source):
    """Inclusive range after immediate constraints. None means empty."""
    lo, hi = 0, _domain_hi(source)
    eqs, banned = [], set()
    for op, imm in constraints:
        if op == 'eq':
            eqs.append(imm)
        elif op == 'ne':
            banned.add(imm)
        elif op == 'lt':
            hi = min(hi, imm - 1)
        elif op == 'ge':
            lo = max(lo, imm)
    if eqs:
        value = eqs[0]
        if any(item != value for item in eqs) or not lo <= value <= hi or value in banned:
            return None
        return value, value
    if lo > hi:
        return None
    if hi - lo <= 64 and not any(value not in banned for value in range(lo, hi + 1)):
        return None
    return lo, hi


def _rels_sat(cube):
    """Word-versus-word EQ/NE/LT/GE. Intervals stay independent unless equated."""
    if not cube.rels:
        return True
    ranges = {}
    for source, constraints in cube.nums.items():
        interval = _interval(constraints, source)
        if interval is None:
            return False
        ranges[source] = interval
    parent = {}

    def find(source):
        parent.setdefault(source, source)
        ranges.setdefault(source, (0, _domain_hi(source)))
        if parent[source] != source:
            parent[source] = find(parent[source])
        return parent[source]

    def union(left, right):
        root_l, root_r = find(left), find(right)
        if root_l == root_r:
            return True
        lo = max(ranges[root_l][0], ranges[root_r][0])
        hi = min(ranges[root_l][1], ranges[root_r][1])
        if lo > hi:
            return False
        parent[root_r] = root_l
        ranges[root_l] = (lo, hi)
        return True

    orders = []
    diseq = []
    for op, left, right in cube.rels:
        find(left)
        find(right)
        if op == 'eq':
            if not union(left, right):
                return False
        elif op == 'ne':
            diseq.append((left, right))
        else:
            orders.append((op, left, right))
    for left, right in diseq:
        if find(left) == find(right):
            return False
        left_lo, left_hi = ranges[find(left)]
        right_lo, right_hi = ranges[find(right)]
        if left_lo == left_hi == right_lo == right_hi:
            return False
    seen = {}
    for op, left, right in orders:
        root_l, root_r = find(left), find(right)
        if root_l == root_r:
            if op == 'lt':
                return False
            continue
        lo_l, hi_l = ranges[root_l]
        lo_r, hi_r = ranges[root_r]
        if op == 'lt' and lo_l >= hi_r:
            return False
        if op == 'ge' and hi_l < lo_r:
            return False
        key = (op, root_l, root_r)
        seen[key] = True
    for op, left, right in orders:
        root_l, root_r = find(left), find(right)
        if op == 'lt' and seen.get(('lt', root_r, root_l)):
            return False
        if op == 'ge' and seen.get(('lt', root_l, root_r)):
            return False
        if op == 'lt' and seen.get(('ge', root_l, root_r)):
            return False
    return True


def _cube_from_guard(guard):
    cube = _Cube()
    for atom in guard:
        kind, port = atom[0], atom[1] if len(atom) > 1 else None
        if kind == 'tag':
            if cube.tag.get(port, atom[2]) != atom[2]:
                return None
            cube.tag[port] = atom[2]
        elif kind in ('kind', 'decl'):
            if cube.kind.get(port, atom[2]) != atom[2] or atom[2] in cube.not_kind.get(port, ()):
                return None
            cube.kind[port] = atom[2]
        elif kind == 'not_kind':
            if cube.kind.get(port) == atom[2]:
                return None
            cube.not_kind.setdefault(port, set()).add(atom[2])
        elif kind == 'memo':
            if cube.memo.get(port) is False:
                return None
            cube.memo[port] = True
        elif kind == 'not_memo':
            if cube.memo.get(port) is True:
                return None
            cube.memo[port] = False
        elif isinstance(atom[2], tuple):
            cube.rels.append((kind, atom[1], atom[2]))
        else:
            cube.nums.setdefault(atom[1], []).append((kind, atom[2]))
    if not _nums_sat(cube) or not _rels_sat(cube):
        return None
    return cube


def _merge(left, right):
    cube = _Cube()
    cube.tag, cube.memo, cube.kind = dict(left.tag), dict(left.memo), dict(left.kind)
    cube.not_kind = {name: set(values) for name, values in left.not_kind.items()}
    cube.nums = {key: list(values) for key, values in left.nums.items()}
    cube.rels = list(left.rels)
    for port, tag in right.tag.items():
        if cube.tag.get(port, tag) != tag:
            return None
        cube.tag[port] = tag
    for port, memo in right.memo.items():
        if port in cube.memo and cube.memo[port] != memo:
            return None
        cube.memo[port] = memo
    for port, kind in right.kind.items():
        if cube.kind.get(port, kind) != kind or kind in cube.not_kind.get(port, ()):
            return None
        cube.kind[port] = kind
    for port, banned in right.not_kind.items():
        if cube.kind.get(port) in banned:
            return None
        cube.not_kind.setdefault(port, set()).update(banned)
    for source, constraints in right.nums.items():
        cube.nums.setdefault(source, []).extend(constraints)
    cube.rels.extend(right.rels)
    if not _nums_sat(cube) or not _rels_sat(cube):
        return None
    return cube


def _check_exclusive(table):
    """Pairwise satisfiability. Independent words are not one shared sample."""
    for phase in table.phases:
        if sum(1 for row in phase.rows if row.fallback) != 1:
            raise StaticRejection('exhaustive', f'{phase.name} needs one else row')
        rows = [row for row in phase.rows if not row.fallback]
        cubes = []
        for row in rows:
            cube = _cube_from_guard(row.guard)
            if cube is None:
                raise StaticRejection('exclusive', f'{row.name} guard is unsatisfiable')
            cubes.append(cube)
        for index, row in enumerate(rows):
            for other, cube in zip(rows[index + 1:], cubes[index + 1:]):
                if _merge(cubes[index], cube) is not None:
                    raise StaticRejection('exclusive', f'{phase.name} {row.name} overlaps {other.name}')


def _pins(row):
    tags, kinds, memos = {}, {}, {}
    for atom in row.guard:
        if atom[0] == 'tag':
            tags[atom[1]] = atom[2]
        elif atom[0] in ('kind', 'decl'):
            kinds[atom[1]] = atom[2]
        elif atom[0] == 'memo':
            memos[atom[1]] = True
        elif atom[0] == 'not_memo':
            memos[atom[1]] = False
    return tags, kinds, memos


def _dest_sorts(phase):
    sorts = dict(REG_SORT)
    for name, sort in phase.entry.items():
        arch = REG_SORT.get(name)
        if arch is None:
            raise StaticRejection('sort', f'{phase.name} entry register {name}')
        if not _compatible(sort, arch):
            raise StaticRejection('sort', f'{phase.name} entry {name}:{sort} contradicts {arch}')
        sorts[name] = sort
    return sorts


def _implied_address(port, row):
    if port.choices:
        matches = [source for guard, source in port.choices if all(atom in row.guard for atom in guard)]
        return matches[0] if len(matches) == 1 else None
    if port.refine and not all(atom in row.guard for atom in port.refine):
        return None
    return port.addr


def _source_sort(source, phase, row, dest_sorts, alu_sorts):
    ports = _phase_ports(phase)
    tags, kinds, memos = _pins(row)
    kind = source[0]
    if kind == 'null':
        have = NULL
    elif kind == 'hp':
        have = HEAP
    elif kind == 'imm':
        have = ('imm', source[1])
    elif kind == 'alu':
        have = alu_sorts[source[1]]
    elif kind == 'reg':
        if source[1] not in dest_sorts:
            raise StaticRejection('menu', f'{row.name} register {source}')
        have = dest_sorts[source[1]]
        for port in phase.reads:
            pin = tags.get(port.name)
            if port.addr == source and pin not in (None, TAG_NULL, TAG_INVALID):
                have = HEAP
    elif kind == 'field':
        port = ports[source[1]]
        if port.bank in _HEAP_BANKS:
            if source[1] not in tags:
                raise StaticRejection('sort', f'{row.name} field {source} has no tag')
            pin = tags[source[1]]
            if source[2] == 'm' and not (pin == TAG_ENV and memos.get(source[1]) is True):
                raise StaticRejection('sort', f'{row.name} memo word {source} is not a committed ENV value')
            have = _field_sort(port.bank, pin, source[2], memo=True)
        else:
            if source[1] not in kinds:
                raise StaticRejection('sort', f'{row.name} field {source} has no kind')
            have = _field_sort(port.bank, kinds[source[1]], source[2])
        if have == HEAP_OR_NULL:
            for port in phase.reads:
                pin = tags.get(port.name)
                if pin not in (None, TAG_NULL, TAG_INVALID) and _implied_address(port, row) == source:
                    have = HEAP
    else:
        raise StaticRejection('menu', f'{row.name} source {source!r}')
    return have


def _immediate_fits(need, value, row, source):
    if type(value) is not int or value < 0 or value > WORD:
        raise StaticRejection('width', f'{row.name} immediate {value}')
    if need == STATUS_SORT:
        if value not in (STATUS_DONE, STATUS_INVALID, STATUS_RESOURCE):
            raise StaticRejection('stop', f'{row.name} status immediate {value}')
        return
    if need == PC_SORT and value in PC_NAME:
        return
    if need == FLAGS_SORT and value < (1 << REG_WIDTH['flags']):
        return
    if need == NAT and value <= WORD:
        return
    if need == ZERO and value == 0:
        return
    raise StaticRejection('sort', f'{row.name} immediate {value} is not a {need}')


def _fits(have, need, row, source):
    if isinstance(have, tuple) and have[:1] == ('imm',):
        _immediate_fits(need, have[1], row, source)
        return
    if have == NULL and need == ZERO:
        return
    if not _compatible(have, need):
        raise StaticRejection('sort', f'{row.name} {source} is {have}, needs {need}')


def _check_typed_row(phase, row):
    dest_sorts = _dest_sorts(phase)
    used = sorted({source[1] for _, source in row.assign if source[0] == 'alu'} |
                  {source[1] for source in _assigned_sources(row) if source[0] == 'alu'})
    alu_sorts = [None] * len(phase.alus)
    for index in used:
        _, left, right = phase.alus[index]
        for source in (left, right):
            if source[0] == 'imm':
                if type(source[1]) is not int or not 0 <= source[1] <= WORD:
                    raise StaticRejection('width', f'{row.name} ALU immediate {source[1]}')
                continue
            have = _source_sort(source, phase, row, dest_sorts, alu_sorts)
            if have != NAT:
                raise StaticRejection('sort', f'{row.name} ALU operand {source} is {have}')
        alu_sorts[index] = NAT
    for name, source in row.assign:
        _fits(_source_sort(source, phase, row, dest_sorts, alu_sorts), dest_sorts[name], row, source)
    if row.heap is not None and row.heap[0] == 'alloc':
        for field_name, source in zip(('a', 'b', 'c'), row.heap[2:]):
            need = _TERM_FIELDS.get(row.heap[1], {}).get(field_name, ZERO)
            _fits(_source_sort(source, phase, row, dest_sorts, alu_sorts), need, row, source)
    if row.stk is not None and row.stk[0] in ('push', 'replace'):
        for field_name, source in zip(('a', 'b'), row.stk[2:]):
            need = _FRAME_FIELDS.get(row.stk[1], {}).get(field_name, ZERO)
            _fits(_source_sort(source, phase, row, dest_sorts, alu_sorts), need, row, source)
    if row.heap is not None and row.heap[0] == 'memo':
        port_name, value = row.heap[1], row.heap[2]
        ports = _phase_ports(phase)
        if port_name not in ports or ports[port_name].bank not in _HEAP_BANKS:
            raise StaticRejection('write', f'{row.name} memo port {port_name} is not a heap read')
        tags, _, memos = _pins(row)
        if tags.get(port_name) != TAG_ENV or memos.get(port_name) is not False:
            raise StaticRejection('write', f'{row.name} memo is not an unmemoized ENV cell')
        _fits(_source_sort(value, phase, row, dest_sorts, alu_sorts), HEAP, row, value)
    tags, kinds, _memos = _pins(row)
    for port in phase.reads:
        pinned = tags.get(port.name) if port.bank in _HEAP_BANKS else kinds.get(port.name)
        mentions = any(source[0] == 'field' and source[1] == port.name for source in _assigned_sources(row))
        if pinned in (None, TAG_NULL, TAG_INVALID) and not mentions:
            continue
        if not port.choices and not port.refine:
            continue
        if _implied_address(port, row) is None:
            raise StaticRejection('sort', f'{row.name} reads {port.name} without one typed address plan')
    for atom in row.guard:
        if atom[0] in ('eq', 'ne', 'lt', 'ge'):
            for side in (atom[1], atom[2]):
                if isinstance(side, tuple) and side[0] == 'field':
                    have = _source_sort(side, phase, row, dest_sorts, alu_sorts)
                    if have == ZERO:
                        raise StaticRejection('sort', f'{row.name} compares untyped {side}')


def _check_sorts(table):
    for phase in table.phases:
        for row in phase.rows:
            _check_typed_row(phase, row)


def _check_writes(table):
    for row in table.rows():
        done = any(name == 'status' and source == ('imm', STATUS_DONE) for name, source in row.assign)
        if row.done != done:
            raise StaticRejection('stop', f'{row.name} DONE annotation does not match the status write')
        if any(name == 'status' and source == ('imm', STATUS_RUN) for name, source in row.assign):
            raise StaticRejection('stop', f'{row.name} assigns RUN')


def _check_absorbing(table):
    allowed = {('imm', STATUS_DONE), ('imm', STATUS_INVALID), ('imm', STATUS_RESOURCE)}
    for row in table.rows():
        for name, source in row.assign:
            if name == 'status' and source not in allowed:
                raise StaticRejection('stop', f'{row.name} status source {source}')


def validate_table(table, n_heap=512, intermediate=512, hidden_candidates=(768, 896, 1024)):
    """Reject a table that breaks a static rule or the layer/dense gate."""
    _check_profile(table)
    _check_exclusive(table)
    _check_sorts(table)
    _check_writes(table)
    _check_absorbing(table)
    report = budget(table, n_heap=n_heap, intermediate=intermediate, hidden_candidates=hidden_candidates)
    if not report['within_40_layers'] or not report['within_working_dense']:
        shape = report['selected_shape']
        raise StaticRejection(
            'budget',
            f"layers {report['layers']} dense {shape['logical_dense_parameters']} "
            f"channels {shape['channels_needed']} hidden {shape['hidden']}",
        )
    report['static_checks'] = ('bounds', 'exclusive', 'sort', 'write', 'stop', 'budget')
    return report

# --- cost -------------------------------------------------------------------

def _menus(table):
    menus = {name: {('keep', name)} for name in PROGRAMMABLE}
    packet = {name: set() for name in ('tag', 'a', 'b', 'c', 'm')}
    stk = {name: set() for name in ('kind', 'a', 'b')}
    for phase in table.phases:
        for row in phase.rows:
            written = set()
            for name, source in row.assign:
                if name in menus:
                    menus[name].add(source)
                    written.add(name)
            if row.goto:
                menus['pc'].add(('imm', PC_OF[row.goto]))
                written.add('pc')
            if 'pc' not in written:
                menus['pc'].add(('imm', phase.pc))
            if row.heap is not None and row.heap[0] == 'alloc':
                _, tag, a_src, b_src, c_src = row.heap
                packet['tag'].add(('imm', tag))
                packet['a'].add(a_src)
                packet['b'].add(b_src)
                packet['c'].add(c_src)
                packet['m'].add(('imm', 0))
            if row.heap is not None and row.heap[0] == 'memo':
                packet['m'].add(row.heap[2])
            if row.stk is not None and row.stk[0] in ('push', 'replace'):
                _, kind, a_src, b_src = row.stk
                stk['kind'].add(('imm', kind))
                stk['a'].add(a_src)
                stk['b'].add(b_src)
    return menus, packet, stk


def mux_units(table):
    menus, packet, stk = _menus(table)
    total = 0
    widths = {}
    for name, menu in menus.items():
        widths[name] = REG_WIDTH[name] * len(menu)
        total += widths[name]
    for name, menu in packet.items():
        widths['heap.' + name] = WORD_BITS * len(menu)
        total += widths['heap.' + name]
    for name, menu in stk.items():
        widths['stk.' + name] = WORD_BITS * len(menu)
        total += widths['stk.' + name]
    return total, widths


def control_width(table):
    menus, packet, stk = _menus(table)
    width = 0
    for menu in list(menus.values()) + list(packet.values()) + list(stk.values()):
        size = max(1, len(menu))
        bits = 1
        while (1 << bits) < size:
            bits += 1
        width += bits
    width += 2  # heap op: none / alloc / memo
    width += 2  # stack op: none / push / pop
    return width


def structural_bookkeeping(profile=P0):
    """Fixed hp/K/fuel adders. They are not the programmable ALU lanes and not U_mux menus."""
    ops = (
        {'name': 'fuel_decrement', 'width': WORD_BITS, 'when': 'fueled row', 'idle_on': 'fuel already 0'},
        {'name': 'hp_increment', 'width': WORD_BITS, 'when': 'alloc'},
        {'name': 'k_update', 'width': WORD_BITS, 'when': 'push or pop'},
    )
    return {
        'programmable_alu_lanes': profile.alu_lanes,
        'counted_in_programmable_alu': False,
        'counted_in_u_mux': False,
        'ops': ops,
        'bits': sum(op['width'] for op in ops),
    }


def residual_bits(table):
    """Conservative static column count. Not a placed stock schedule."""
    profile = table.profile
    registers = sum(REG_WIDTH.values())
    heap_cell = 5 * WORD_BITS
    stk_cell = 3 * WORD_BITS
    decl_cell = 3 * WORD_BITS
    addresses = (profile.heap_read_ports + profile.stk_reads + profile.decl_reads) * WORD_BITS
    pending = heap_cell + stk_cell
    alu = profile.alu_lanes * WORD_BITS
    structural = structural_bookkeeping(profile)['bits']
    predicates = profile.predicate_bits
    payload = profile.heap_read_ports * heap_cell + stk_cell + decl_cell
    control = control_width(table)
    columns = {
        'estimate': 'conservative_static',
        'stock_placement': False,
        'registers': registers,
        'read_payload': payload,
        'addresses': addresses,
        'pending_write': pending,
        'alu': alu,
        'structural': structural,
        'predicates': predicates,
        'control': control,
    }
    columns['total'] = sum(value for key, value in columns.items() if isinstance(value, int))
    return columns


def layer_count(n_rows, u_mux, n_heap, intermediate, profile=P0, v_heap=4):
    """Section 5 with heap value-heads separated from the stack and declaration layers."""
    i_eff = intermediate - 24
    if i_eff <= 0:
        raise ValueError('intermediate must exceed the 24 handover rows')
    heap_per_port = (n_heap + (128 * v_heap) - 1) // (128 * v_heap)
    rows = (n_rows + i_eff - 1) // i_eff
    mux = (u_mux + i_eff - 1) // i_eff
    memory = profile.heap_read_ports * heap_per_port + 2
    return 9 + memory + rows + mux, {
        'heap_layers_per_port': heap_per_port,
        'heap_layers': profile.heap_read_ports * heap_per_port,
        'stk_layers': 1,
        'decl_layers': 1,
        'match_layers': rows,
        'mux_layers': mux,
        'memory_layers': memory,
    }


def _dense_layer(hidden, intermediate, value_heads):
    mlp = 3 * hidden * intermediate
    if value_heads:
        return mlp + (258 + 386 * value_heads) * hidden + 1152 + 514 * value_heads
    return mlp + 12 * hidden + 4


def dense_parameters(hidden, intermediate, layers, memory, v_heap=4):
    """Price each memory layer with its own value-head count. Inert layers use the full-attention price."""
    heap_cost = memory['heap_layers'] * _dense_layer(hidden, intermediate, v_heap)
    small_cost = (memory['stk_layers'] + memory['decl_layers']) * _dense_layer(hidden, intermediate, 1)
    inert = layers - memory['memory_layers']
    if inert < 0:
        raise ValueError('layer count is below the memory layers')
    return heap_cost + small_cost + inert * _dense_layer(hidden, intermediate, 0) + 129 * hidden


def budget(table, n_heap=512, intermediate=512, hidden_candidates=(768, 896, 1024)):
    u_mux, menus = mux_units(table)
    layers, memory = layer_count(len(table.rows()), u_mux, n_heap, intermediate, table.profile)
    live = residual_bits(table)
    shapes = []
    for hidden in hidden_candidates:
        ballast = hidden // 64
        channels = ballast + 1 + live['total']
        dense = dense_parameters(hidden, intermediate, layers, memory)
        shapes.append({
            'hidden': hidden,
            'intermediate': intermediate,
            'ballast': ballast,
            'channels_needed': channels,
            'channel_gate': channels <= hidden,
            'layers': layers,
            'logical_dense_parameters': dense,
            'dense_gate': dense <= 48_290_654,
        })
    fitting = [shape for shape in shapes if shape['channel_gate']]
    selected = fitting[0] if fitting else shapes[-1]
    alt_layers, alt_memory = layer_count(len(table.rows()), u_mux, n_heap, 256, table.profile)
    alt = []
    for hidden in hidden_candidates:
        ballast = hidden // 64
        channels = ballast + 1 + live['total']
        dense = dense_parameters(hidden, 256, alt_layers, alt_memory)
        alt.append({
            'hidden': hidden, 'intermediate': 256, 'layers': alt_layers,
            'channels_needed': channels, 'channel_gate': channels <= hidden,
            'logical_dense_parameters': dense, 'dense_gate': dense <= 48_290_654,
        })
    return {
        'n_rows': len(table.rows()),
        'u_mux': u_mux,
        'menus': menus,
        'control_width': control_width(table),
        'residual_bits': live,
        'structural_bookkeeping': structural_bookkeeping(table.profile),
        'n_heap': n_heap,
        'intermediate': intermediate,
        'layers': layers,
        'memory': memory,
        'shapes': shapes,
        'selected_shape': selected,
        'intermediate_256': alt,
        'within_40_layers': layers <= 40,
        'within_working_dense': selected['logical_dense_parameters'] <= 48_290_654 and selected['channel_gate'],
        'modeled_one_transition_per_forward': True,
        'stock_forward_equivalence': False,
        'weights_emitted': False,
        'gpu_measured': False,
        'original_source_requires_inductive': True,
    }


def fixture_cost(n_rows, u_mux, n_heap, hidden, intermediate=512):
    """Formula fixture. Not a measurement of the WHNF table."""
    profile = P0
    layers, memory = layer_count(n_rows, u_mux, n_heap, intermediate, profile)
    return layers, dense_parameters(hidden, intermediate, layers, memory)


# --- WHNF table -------------------------------------------------------------

def _row(phase, name, guard, assign=(), heap=None, stk=None, goto=None, done=False, fallback=False):
    return Row(phase, name, tuple(guard), tuple(assign), heap, stk, goto or phase, done, fallback)


def _alloc(tag, a, b, c):
    return ('alloc', tag, a, b, c)


def _push(kind, a, b=('null',)):
    return ('push', kind, a, b)


def _replace(kind, a=('null',), b=('null',)):
    return ('replace', kind, a, b)


def whnf_table():
    """Section 8. E-clo is three rows and R-napp is two, plus three else rows."""
    n_a = ('field', 'n', 'a')
    n_b = ('field', 'n', 'b')
    n_c = ('field', 'n', 'c')
    e_a = ('field', 'e', 'a')
    e_b = ('field', 'e', 'b')
    e_c = ('field', 'e', 'c')
    e_m = ('field', 'e', 'm')
    k_a = ('field', 'k', 'a')
    k_b = ('field', 'k', 'b')
    p_a = ('field', 'p', 'a')
    p_b = ('field', 'p', 'b')
    p_c = ('field', 'p', 'c')
    p_m = ('field', 'p', 'm')
    q_a = ('field', 'q', 'a')
    q_b = ('field', 'q', 'b')
    q_c = ('field', 'q', 'c')
    q_m = ('field', 'q', 'm')
    v_b = ('field', 'v', 'b')
    b_b = ('field', 'b', 'b')
    d_b = ('field', 'd', 'b')
    reg_e = ('reg', 'E')
    reg_c = ('reg', 'C')
    reg_v = ('reg', 'V')
    reg_a1 = ('reg', 'A1')
    clo = _alloc(TAG_CLO, reg_c, reg_e, ('imm', 0))
    eval_rows = (
        _row('EVAL', 'E-app', (('tag', 'n', TAG_APP),), (('C', n_a),), stk=_push(FRAME_APP, n_b, reg_e)),
        _row('EVAL', 'E-beta', (('tag', 'n', TAG_LAM), ('kind', 'k', FRAME_APP)),
             (('C', n_b), ('E', ('hp',))),
             heap=_alloc(TAG_ENV, k_a, k_b, reg_e), stk=('pop',)),
        _row('EVAL', 'E-clo-lam', (('tag', 'n', TAG_LAM), ('not_kind', 'k', FRAME_APP)),
             (('V', ('hp',)),), heap=clo, goto='RET'),
        _row('EVAL', 'E-clo-pi', (('tag', 'n', TAG_PI),),
             (('V', ('hp',)),), heap=clo, goto='RET'),
        _row('EVAL', 'E-clo-sort', (('tag', 'n', TAG_SORT),),
             (('V', ('hp',)),), heap=clo, goto='RET'),
        _row('EVAL', 'E-zeta', (('tag', 'n', TAG_LET),),
             (('C', n_c), ('E', ('hp',))),
             heap=_alloc(TAG_ENV, n_b, reg_e, reg_e)),
        _row('EVAL', 'E-var0-memo', (('tag', 'n', TAG_BVAR), ('eq', n_a, 0), ('tag', 'e', TAG_ENV), ('memo', 'e')),
             (('V', e_m),), goto='RET'),
        _row('EVAL', 'E-var0-force',
             (('tag', 'n', TAG_BVAR), ('eq', n_a, 0), ('tag', 'e', TAG_ENV), ('not_memo', 'e')),
             (('C', e_a), ('E', e_b)), stk=_push(FRAME_UPD, reg_e)),
        _row('EVAL', 'E-var-walk', (('tag', 'n', TAG_BVAR), ('ne', n_a, 0), ('tag', 'e', TAG_ENV)),
             (('A0', ('alu', 0)), ('A1', e_c)), goto='LOOKUP'),
        _row('EVAL', 'E-delta', (('tag', 'n', TAG_CONST), ('decl', 'd', DECL_DEF)),
             (('C', d_b), ('E', ('null',)))),
        _row('EVAL', 'E-stuck', (('tag', 'n', TAG_CONST), ('decl', 'd', DECL_AXIOM)),
             (('V', ('hp',)),), heap=_alloc(TAG_NEU, reg_c, ('imm', 0), ('imm', 0)), goto='RET'),
        _row('EVAL', 'E-else', (), (('status', ('imm', STATUS_INVALID)),), fallback=True),
    )
    lookup_rows = (
        _row('LOOKUP', 'L-hit0-memo', (('eq', ('reg', 'A0'), 0), ('tag', 'p', TAG_ENV), ('memo', 'p')),
             (('V', p_m),), goto='RET'),
        _row('LOOKUP', 'L-hit0-force', (('eq', ('reg', 'A0'), 0), ('tag', 'p', TAG_ENV), ('not_memo', 'p')),
             (('C', p_a), ('E', p_b)), stk=_push(FRAME_UPD, reg_a1), goto='EVAL'),
        _row('LOOKUP', 'L-hit1-memo',
             (('eq', ('reg', 'A0'), 1), ('tag', 'p', TAG_ENV), ('tag', 'q', TAG_ENV), ('memo', 'q')),
             (('V', q_m),), goto='RET'),
        _row('LOOKUP', 'L-hit1-force',
             (('eq', ('reg', 'A0'), 1), ('tag', 'p', TAG_ENV), ('tag', 'q', TAG_ENV), ('not_memo', 'q')),
             (('C', q_a), ('E', q_b)), stk=_push(FRAME_UPD, p_c), goto='EVAL'),
        _row('LOOKUP', 'L-walk2', (('ge', ('reg', 'A0'), 2), ('tag', 'p', TAG_ENV), ('tag', 'q', TAG_ENV)),
             (('A0', ('alu', 0)), ('A1', q_c))),
        _row('LOOKUP', 'L-else', (), (('status', ('imm', STATUS_INVALID)),), fallback=True),
    )
    ret_rows = (
        _row('RET', 'R-halt', (('kind', 'k', FRAME_HALT),),
             (('status', ('imm', STATUS_DONE)),), done=True),
        _row('RET', 'R-update', (
            ('kind', 'k', FRAME_UPD), ('tag', 'b', TAG_ENV), ('not_memo', 'b'),
        ), (), heap=('memo', 'b', reg_v), stk=('pop',)),
        _row('RET', 'R-beta', (('kind', 'k', FRAME_APP), ('tag', 'v', TAG_CLO), ('tag', 'b', TAG_LAM)),
             (('C', b_b), ('E', ('hp',))),
             heap=_alloc(TAG_ENV, k_a, k_b, v_b), stk=('pop',), goto='EVAL'),
        _row('RET', 'R-napp-neu', (('kind', 'k', FRAME_APP), ('tag', 'v', TAG_NEU)),
             (('V', ('hp',)),),
             heap=_alloc(TAG_NAPP, reg_v, k_a, k_b), stk=('pop',)),
        _row('RET', 'R-napp-napp', (('kind', 'k', FRAME_APP), ('tag', 'v', TAG_NAPP)),
             (('V', ('hp',)),),
             heap=_alloc(TAG_NAPP, reg_v, k_a, k_b), stk=('pop',)),
        _row('RET', 'R-else', (), (('status', ('imm', STATUS_INVALID)),), fallback=True),
    )
    const_guard = (('tag', 'n', TAG_CONST),)
    env_guard = (('tag', 'p', TAG_ENV),)
    clo_guard = (('kind', 'k', FRAME_APP), ('tag', 'v', TAG_CLO))
    upd_guard = (('kind', 'k', FRAME_UPD),)
    phases = (
        Phase('EVAL', PC_EVAL, (
            Port('n', 'heap_a', 1, ('reg', 'C')),
            Port('e', 'heap_b', 1, ('reg', 'E')),
            Port('k', 'stk', 1, ('reg', 'K')),
            Port('d', 'decl', 2, ('null',), choices=((const_guard, n_a),)),
        ), (('sub', n_a, ('imm', 1)),), eval_rows, {'C': HEAP, 'E': HEAP_OR_NULL}),
        Phase('LOOKUP', PC_LOOKUP, (
            Port('p', 'heap_a', 1, ('reg', 'A1')),
            Port('q', 'heap_b', 2, ('null',), choices=((env_guard, p_c),)),
        ), (('sub', ('reg', 'A0'), ('imm', 2)),), lookup_rows, {'A1': HEAP_OR_NULL}),
        Phase('RET', PC_RET, (
            Port('k', 'stk', 1, ('reg', 'K')),
            Port('v', 'heap_a', 1, ('reg', 'V')),
            Port('b', 'heap_b', 2, ('null',), choices=(
                (clo_guard, ('field', 'v', 'a')),
                (upd_guard, k_a),
            )),
        ), (), ret_rows, {'V': HEAP}),
    )
    return Table(phases)


# --- input and readback -----------------------------------------------------

_SURFACE = {
    'var': TAG_BVAR, 'bvar': TAG_BVAR, 'sort': TAG_SORT, 'const': TAG_CONST,
    'app': TAG_APP, 'lam': TAG_LAM, 'pi': TAG_PI, 'let': TAG_LET,
}


def _as_tuple(term):
    if isinstance(term, (list, tuple)) and term and isinstance(term[0], str):
        return tuple(term)
    raise UnsupportedInput(f'not a ground term: {term!r}')


class _Builder:
    def __init__(self, allow_opaque=False):
        self.heap = [Cell()]
        self.decl = [Cell()]
        self.names = []
        self.allow_opaque = allow_opaque

    def cell(self, tag, a=0, b=0, c=0):
        self.heap.append(Cell(tag=tag, a=a, b=b, c=c))
        return len(self.heap) - 1

    def term(self, term):
        term = _as_tuple(term)
        head = term[0]
        if head in ('builtin', 'proj', 'nat'):
            raise UnsupportedInput(f'{head} is outside the WHNF ground fragment')
        tag = _SURFACE.get(head)
        if tag is None:
            raise UnsupportedInput(f'unsupported term {head}')
        if tag in (TAG_BVAR, TAG_SORT):
            if len(term) != 2 or type(term[1]) is not int or not 0 <= term[1] <= WORD:
                raise UnsupportedInput(f'{head} index does not fit in 16 bits')
            return self.cell(tag, term[1])
        if tag == TAG_CONST:
            if len(term) != 2 or not isinstance(term[1], str):
                raise UnsupportedInput('ground const has a name and no level arguments')
            # Index 0 is the empty declaration. EVAL then takes the else row.
            if term[1] not in self.names:
                return self.cell(TAG_CONST, 0)
            return self.cell(TAG_CONST, self.names.index(term[1]) + 1)
        if tag in (TAG_APP, TAG_LAM, TAG_PI) and len(term) == 3:
            left = 0 if term[1] is None else self.term(term[1])
            return self.cell(tag, left, self.term(term[2]))
        if tag == TAG_LET and len(term) == 4:
            return self.cell(TAG_LET, self.term(term[1]), self.term(term[2]), self.term(term[3]))
        raise UnsupportedInput(f'malformed {head}')

    def declaration(self, name, kind, type_term, value_term):
        if name in self.names:
            raise UnsupportedInput(f'duplicate declaration {name}')
        if kind == DECL_OPAQUE and not self.allow_opaque:
            raise UnsupportedInput('DECL_OPAQUE is outside the 24-row WHNF table')
        if kind not in (DECL_AXIOM, DECL_DEF, DECL_OPAQUE):
            raise UnsupportedInput(f'declaration kind {kind}')
        self.names.append(name)
        type_addr = self.term(type_term)
        if kind == DECL_AXIOM:
            if value_term is not None:
                raise UnsupportedInput('axiom has no value')
            value_addr = 0
        else:
            if value_term is None:
                raise UnsupportedInput('definition needs a value')
            value_addr = self.term(value_term)
        self.decl.append(Cell(kind=kind, a=type_addr, b=value_addr))
        return len(self.decl) - 1


def load_whnf(term, declarations=(), fuel=10000, heap_cap=512, stack_cap=32, allow_opaque=False):
    """Place a closed term and its declarations. Level arguments are unsupported."""
    if type(fuel) is not int or not 0 <= fuel <= WORD:
        raise UnsupportedInput('fuel does not fit in 16 bits')
    if type(heap_cap) is not int or not 1 <= heap_cap <= WORD:
        raise UnsupportedInput('heap capacity does not fit in 16 bits')
    if type(stack_cap) is not int or not 1 <= stack_cap <= WORD:
        raise UnsupportedInput('stack capacity does not fit in 16 bits')
    built = _Builder(allow_opaque=allow_opaque)
    for item in declarations:
        if isinstance(item, dict):
            name, kind, type_term, value = item['name'], item['kind'], item['type'], item.get('value')
        else:
            name, kind, type_term, value = item
        built.declaration(name, kind, type_term, value)
    root = built.term(term)
    if len(built.heap) - 1 > heap_cap:
        raise UnsupportedInput('input cells do not fit the heap capacity')
    heap = built.heap + [Cell() for _ in range(heap_cap - (len(built.heap) - 1))]
    stk = [Cell() for _ in range(stack_cap + 1)]
    stk[1] = Cell(kind=FRAME_HALT)
    regs = Regs(pc=PC_EVAL, status=STATUS_RUN, C=root, E=0, K=1, hp=len(built.heap), fuel=fuel)
    return Machine(regs, heap, stk, built.decl, tuple(built.names), heap_cap, stack_cap)


def _env_at(machine, env, index):
    while index:
        if env == 0:
            return None
        cell = machine.heap[env]
        if cell.tag != TAG_ENV:
            return None
        env = cell.c
        index -= 1
    if env == 0:
        return None
    cell = machine.heap[env]
    return cell if cell.tag == TAG_ENV else None


def readback_term(machine, addr, env=0, binders=0):
    if addr == 0:
        return ('null',)
    cell = machine.heap[addr]
    if cell.tag == TAG_BVAR:
        if cell.a < binders:
            return ('var', cell.a)
        found = _env_at(machine, env, cell.a - binders)
        if found is None:
            return ('var', cell.a)
        if found.memo:
            return readback_value(machine, found.m)
        return readback_term(machine, found.a, found.b, 0)
    if cell.tag == TAG_SORT:
        return ('sort', cell.a)
    if cell.tag == TAG_CONST:
        if not 1 <= cell.a <= len(machine.names):
            return ('const', None)
        return ('const', machine.names[cell.a - 1])
    if cell.tag == TAG_APP:
        return ('app', readback_term(machine, cell.a, env, binders), readback_term(machine, cell.b, env, binders))
    if cell.tag == TAG_LAM:
        return ('lam', readback_term(machine, cell.a, env, binders), readback_term(machine, cell.b, env, binders + 1))
    if cell.tag == TAG_PI:
        return ('pi', readback_term(machine, cell.a, env, binders), readback_term(machine, cell.b, env, binders + 1))
    if cell.tag == TAG_LET:
        return ('let', readback_term(machine, cell.a, env, binders), readback_term(machine, cell.b, env, binders),
                readback_term(machine, cell.c, env, binders + 1))
    raise UnsupportedInput(f'cannot read back tag {cell.tag}')


def readback_value(machine, addr):
    cell = machine.heap[addr]
    if cell.tag == TAG_CLO:
        return readback_term(machine, cell.a, cell.b, 0)
    if cell.tag == TAG_NEU:
        return readback_term(machine, cell.a, 0, 0)
    if cell.tag == TAG_NAPP:
        return ('app', readback_value(machine, cell.a), readback_term(machine, cell.b, cell.c, 0))
    raise UnsupportedInput(f'not a value tag {cell.tag}')


def readback(machine):
    if machine.regs.status != STATUS_DONE:
        raise UnsupportedInput('readback requires DONE')
    return readback_value(machine, machine.regs.V)
