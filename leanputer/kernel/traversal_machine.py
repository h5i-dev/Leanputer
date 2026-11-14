"""General expression traversal as bounded, explicit kernel transitions.

This is a kernel operation controller, not a proof-supplied instruction stream.
LIFT/INSTANTIATE/ABSTRACT/OCCURS use one stack and the same all-tag child walk.
The beta/literal-Let/metadata subservice calls that substitution operation via
private continuations. Checked-environment/local-let and other WHNF rules are
not implemented by this subservice.
The stock compiler receives capacities only. Syntax and operand vectors are
loaded as data. Python step() is solely a development reference.
"""
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum
import torch
from ..bitvec import pack_words, unpack_words
from .arena import Arena, KernelError, LevelTag, Limits, ResourceError, Tag, children
from .native_cells import CellTag, VectorKind


class Outcome(IntEnum):
    RUNNING = 0
    DONE = 1                     # Operation completed, NOT proof acceptance.
    INVALID = 2
    RESOURCE = 3
    GAP = 4                      # Unimplemented required service, NOT rejection.
    UNSUPPORTED_PROFILE = 5      # Actual kernel interface outside inference target.


class Reason(IntEnum):
    NONE = 0
    SYNTAX = 1
    HEAP = 2
    STACK = 3
    INDEX = 4
    FUEL = 5
    SCOPE = 6
    CONTEXT = 7
    EXPECT_PI = 8
    EXPECT_LAM = 9
    UNIVERSE = 10
    GAP_CONVERSION = 11
    GAP_ENVIRONMENT = 12
    EXPECT_SORT = 13
    TYPE_MISMATCH = 14
    GAP_PRIMITIVE = 16
    GAP_PROJECTION = 17
    UNKNOWN_CONSTANT = 18
    UNIVERSE_ARITY = 19
    DUPLICATE_PARAMETER = 20
    UNAVAILABLE_BODY = 21
    DUPLICATE_DECLARATION = 22
    INVALID_DECLARATION = 23
    GAP_INDUCTIVE = 24
    GAP_RECURSOR_CLAIM = 25
    NATIVE_EXECUTION = 26
    NEGATIVE_OCCURRENCE = 27
    INVALID_INDUCTIVE_APPLICATION = 28
    GAP_RECURSOR_GENERATION = 29
    INVALID_RECURSOR_NAME = 30
    INVALID_PROJECTION = 33
    GAP_NESTED_RESTORATION = 32
    INVALID_NESTED_PARAMETERS = 31
    UNSUPPORTED_DECLARATION = 15  # Shared reporting ABI; never emitted here.


class Task(IntEnum):
    LIFT = 0
    INSTANTIATE = 1
    ABSTRACT = 2
    OCCURS = 3
    BETA_ZETA = 4
    INSTANTIATE_ONE = 5          # Internal service call, no proof-data entry.
    OPEN_TELESCOPE = 6          # Declared Pi/Lam prefix, closed raw syntax input.
    VARIABLE_SCOPE = 7          # BVar/Local scope only, not universe checking.
    ROUNDTRIP_TELESCOPE = 8     # Wrapper tests OPEN then the internal FOLD.
    ABSTRACT_ONE = 9            # Internal semantic subroutine only.
    FOLD_TELESCOPE = 10         # Internal: consumes derived Local records.
    LEVEL_SCOPE = 11            # Internal typed-cell level walk/membership.
    LEVEL_SUBSTITUTE = 12       # Simultaneous raw level substitution.
    EXPR_LEVEL_SUBSTITUTE = 13  # All Expr tags; Sort/Const call the same level op.
    LEVEL_EQUAL = 14            # Structural equality, NOT definitional equality.
    LEVEL_NOT_ZERO = 15         # Source necessarily-nonzero predicate.
    LEVEL_OFFSET = 16           # Strip Succ and return (r, level_offset).
    LEVEL_MAX = 17              # Pinned smart constructor, two raw operands.
    LEVEL_IMAX = 18             # Same source constructor, calls MAX/nonzero.
    LEVEL_INSTANTIATE = 19      # Source substitution: changed Max/IMax use smart constructors.
    EXPR_LEVEL_INSTANTIATE = 20 # Same source operation throughout expression syntax.
    LEVEL_ORDER = 21            # Total structural base order, successor offsets last.
    LEVEL_NORMALIZE = 22        # Generic canonical normalization of all levels.
    LEVEL_MERGE = 23            # Internal: merge two normalized Max chains.
    LEVEL_NORMAL_SUCC = 24      # Internal: distribute one Succ over normalized Max.
    LEVEL_EQUIVALENT = 25       # Normalize both sides, then shared structural ==.
    LEVEL_GEQ = 26              # Pinned conservative is_geq, no numeric grounding.
    LEVEL_GEQ_CORE = 27         # Internal normalized Max/IMax/offset traversal.
    EXPR_SCOPE = 28             # Closed raw Expr plus scoped Sort/Const universes.
    EXPR_EQUAL = 29             # Erased-syntax equality; false is NOT defeq false.
    VECTOR_EQUAL = 30           # Internal typed vector service (levels/limbs/bytes).
    INFER = 31                 # Generic checked inference; missing services -> GAP.
    CONVERT_POSITIVE = 32       # Positive shortcut; false only for unequal Sorts.
    ENV_LOOKUP = 33             # Private checked list only; NEVER raw signatures.
    LOAD_PARAMETERS = 34        # Raw symbolic scheme list -> checked unique scope slots.
    CHECK_NAME = 35             # Generic structured-name/profile guard, no library catalog.
    CHECK_SOURCE = 36           # Source transaction; required missing callbacks GAP.
    CONSUME_PARAMETERS = 37     # Reuse derived Locals; dependent domain checking.
    PREPARE_REUSE = 38          # Public operation wrapper, not source admission.
    HAS_CONSTANTS = 39          # Composable symbol-set Expr occurrence callback.
    ANALYZE_HEADERS = 40        # General private header phase; not block admission.
    HAS_FAMILIES = 41           # Borrow symbol scratch after live Locals; return Bool.
    FAMILY_APPLICATION = 42    # Exact current-family/uniform parameter/index predicate.
    FORMAL_LEVELS = 43         # Internal checked symbol window -> Param-level vector.
    CHECK_POSITIVITY = 44      # General CORE operation after nested elimination.
    ABSTRACT_SCOPE = 45        # Derived Local records -> shared multi-abstraction.
    RECURSIVE_ARGUMENT = 46    # Generic functional prefix/index template derivation.
    REVERSE_LIST = 47          # Internal counted immutable reference-vector builder.
    CHECK_CONSTRUCTORS = 48    # Typed CORE operation under private header overlay.
    GET_NAME_PATH = 49         # Raw structured-name lookup, no profile/admission answer.
    CHECK_RECURSOR_NAME = 50   # Source mk_rec_name relation over arbitrary raw names.
    CHECK_CORE_NAMES = 51      # Validate all derived recursor-name/namespace claims.
    DECLARE_CONSTRUCTORS = 52  # Private signatures from fully checked pending records.
    INIT_ELIMINATION = 53      # General source elimination-universe/K analysis.
    FRESH_LOCAL = 54           # Internal generated binder, never a raw type answer.
    APPLY_SCOPE = 55           # Apply Expr to derived Locals in a context interval.
    BUILD_MOTIVES = 56         # Generic all-family first mk_rec_infos loop.
    BLOCK_FLAGS = 57           # Raw-domain source recursion/reflexivity metadata.
    INSTANTIATE_SCOPE = 58     # Reverse substitution from a derived Local window.
    SNAPSHOT_SCOPE = 59        # Immutable vector of derived Local records.
    OPEN_RECURSIVE_PREFIX = 60 # General generated dependent prefix/index templates.
    APPLY_LIST = 61            # Apply a generated Expr list after skipping a prefix.
    FIND_MOTIVE = 62           # Checked family identity -> generated motive Local.
    BUILD_MINORS = 63          # Generic all-constructor minor and functional IH pass.
    BUILD_RECURSOR_TYPES = 64  # Generic closed recursor schemes over all locals.
    RESTORE_SCOPE = 65         # Shared derived Local/field-vector context traversal.
    BUILD_RECURSOR_RULES = 66  # Generic constructor computation RHS generation.
    ASSEMBLE_RECURSORS = 67    # Generic grouped counts/rules/private signatures.
    INSTANTIATE_SCHEME = 68    # Shared pure scheme zip/source-level substitution.
    SIGNATURE_VECTOR_LOOKUP = 69 # Current generated signature set only.
    SYMBOL_MEMBER = 70         # Immutable word-list membership, no type answer.
    CHECK_RECURSOR_CLAIMS = 71 # Infer and compare untrusted generated-type claims.
    APPLICATION_SPINE = 72    # Pure get_app_fn/get_app_args, immutable result.
    APPLY_VECTOR_SLICE = 73   # Pure contiguous Expr vector application.
    APPLY_RECURSOR_RULE = 74  # Shared source rule lookup/specialization/application.
    VECTOR_REFERENCE = 75    # Bounded typed reference-vector selection; 0 if absent.
    PREPARE_RECURSOR_MAJOR = 76 # Source K/WHNF/structure preparation; literal GAP.
    REDUCE_RECURSOR = 77      # General checked recursor reduction, reentrant.
    GATHER_RECURSOR_ARGUMENTS = 78 # Bridge existing WHNF pending application frames.
    PRIOR_BLOCK_LOOKUP = 79   # Pure original-block ownership registry lookup.
    COMPARE_NAME_PATH = 80    # Generic structured name equality/prefix comparison.
    INTERN_NAME_PATH = 81     # Canonical data path -> existing/new symbol in weights.
    VECTOR_SPLICE = 82        # Generic typed prefix + suffix[skip:], immutable.
    WORD_DECIMAL = 83         # Bounded source counter -> decimal UTF8 bytes.
    REPLACE_NAME_PREFIX = 84  # Generic source Name.replacePrefix via shared data ops.
    MAKE_RECURSOR_NAME = 85   # Source rec/rec_index construction, names/counts as data.
    OPEN_RAW_PREFIX = 86      # Exact raw dependent Pi/Lam prefix; syntax variables only.
    HAS_LOOSE_BVARS = 87      # Generic source syntactic loose-BVar predicate.
    LOOSE_BVAR_WALK = 88      # Internal all-Expr depth-aware predicate walker.
    HAS_RAW_FAMILIES = 89     # Same occurrence operation over raw all-queued family data.
    IS_NESTED_APPLICATION = 90 # Complete source application/parameter/occurrence condition.
    INSTANTIATE_PI_PARAMETERS = 91 # Raw Pi strip + bulk instantiate_rev at declared count.
    CONVERT = 102             # General task-owned typed conversion.
    LEVELS_EQUIVALENT = 103    # Counted symbolic universe-vector comparison.
    NAT_BINDINGS = 107       # Checked genuine natural literal bindings.
    NAT_LITERAL = 108        # Arbitrary limb inference/constructor preparation.
    QUOT_REDUCE = 106        # Reentrant initialized quotient computation.
    QUOT_INITIALIZE = 105    # Genuine quot.cpp atomic source initialization.
    STRUCTURE_INFO = 104      # Checked nonrecursive structure/count query.
    FAMILY_INFO = 98           # Checked family counts from origin/private header provenance.
    PROJECTION_INFER = 99      # General dependent projection type rule.
    PROJECTION_REDUCE = 100    # General checked-constructor projection reduction.
    PROJECTION_BRIDGE = 101    # Frame-only WHNF continuation; not an entry task.
    RESTORE_NESTED_BLOCK = 97  # Restored rechecks and atomic source publication.
    RESTORE_NESTED_EXPR = 95   # General leading-prefix reopen/restore/fold.
    RESTORE_NESTED_CALLBACK = 96 # Fixed restoration preorder callback.
    NESTED_STAGE = 92          # Original raw block -> private growing expanded block.
    REWRITE_NESTED = 93       # Fixed preorder callback, all expression children.
    REPLACE_NESTED = 94       # Structural specialization and whole prior-block copy.



class Mode(IntEnum):
    WALK = 0
    RETURN = 1
    RESUME = 2
    FIND = 3
    BETA_ZETA = 4
    TELESCOPE = 5
    BINDER_RECORD = 6
    FOLD_SELECT = 7
    FOLD_RECORD = 8
    FOLD_LOCAL = 9
    FOLD_BUILD = 10
    LEVEL_SELECT = 11
    LEVEL_BINDING = 12
    SORT_RESULT = 13
    CONST_VECTOR = 14
    CONST_CELL = 15
    CONST_RESULT = 16
    CONST_BUILD = 17
    CONST_FINISH = 18
    LEVEL_EQUAL_RIGHT = 19
    MAX_LEFT = 20
    MAX_RIGHT = 21
    MAX_RIGHT_CHILDREN = 22
    MAX_LEFT_CHILDREN = 23
    MAX_EQUAL_RESULT = 24
    IMAX_LEFT = 25
    IMAX_ONE = 26
    IMAX_RIGHT = 27
    ORDER_READ_LEFT = 28
    ORDER_READ_RIGHT = 29
    NORMAL_IMAX_RESULT = 30
    MERGE_LEFT = 31
    MERGE_RIGHT = 32
    MERGE_RECORD = 33
    MERGE_FOLD = 34
    MERGE_FINISH = 35
    GEQ_RIGHT = 36
    GEQ_LEFT = 37
    GEQ_FALLBACK_RIGHT = 38
    GEQ_FALLBACK_LEFT = 39
    GEQ_OFFSET_BASE = 40
    EXPR_EQUAL_RIGHT = 41
    VECTOR_HEADER_RIGHT = 42
    VECTOR_CELL_LEFT = 43
    VECTOR_CELL_RIGHT = 44
    INFER_SORT_EXPR = 45
    INFER_LOCAL_SELECT = 46
    INFER_LOCAL_RECORD = 47
    INFER_LOCAL_EXPR = 48
    INFER_DOMAIN_SORT = 49
    INFER_BINDER_RESULT = 50
    INFER_PI_BODY_SORT = 51
    INFER_LAM_RESULT = 52
    INFER_FUNCTION_PI = 53
    INFER_ARGUMENT_TYPE = 54
    INFER_APP_RESULT = 55
    INFER_LET_ANNOTATION = 56
    INFER_LET_SOURCE = 57
    INFER_LET_VALUE_TYPE = 58
    INFER_LET_INSTANTIATE = 59
    CONVERT_LEFT = 60
    CONVERT_RIGHT = 61
    ENV_CELL = 62
    ENV_SIGNATURE = 63
    CONST_SIGNATURE = 64
    CONST_SCHEME = 65
    CONST_EXPRESSION = 66
    CONST_PARAMETER_HEADER = 67
    CONST_LEVEL_HEADER = 68
    CONST_PARAMETER_CELL = 69
    CONST_LEVEL_CELL = 70
    PARAMETER_CELL = 71
    PARAMETER_DUPLICATE = 72
    NAME_TABLE_CELL = 73
    NAME_ENTRY = 74
    NAME_PATH = 75
    NAME_PATH_CELL = 76
    NAME_COMPONENT = 77
    NAME_BYTES = 78
    NAME_BYTE_CELL = 79
    SOURCE_READ = 80
    SOURCE_TYPE_SORT = 81
    SOURCE_REQUIRE_VALUE = 82
    SOURCE_COMMIT = 83
    SOURCE_SIGNATURE = 84
    SOURCE_LINK = 85
    TELESCOPE_READY = 86
    REUSE_LOOP = 87
    REUSE_BINDER = 88
    REUSE_SELECT = 89
    REUSE_RECORD = 90
    REUSE_INSTANTIATE = 91
    REUSE_SUBST_SELECT = 92
    REUSE_SUBST_RECORD = 93
    HEADER_VECTOR = 94
    HEADER_CELL = 95
    HEADER_FAMILY = 96
    HEADER_TYPE_SORT = 97
    HEADER_SORT = 98
    HEADER_STORE_FAMILY = 99
    HEADER_STORE_SCHEME = 100
    HEADER_STORE_SIGNATURE = 101
    HEADER_LINK = 102
    FAMILY_SET_CELL = 103
    FAMILY_SET_SIGNATURE = 104
    APP_SPINE = 105
    APP_SIGNATURE = 106
    APP_SCHEME = 107
    APP_METADATA = 108
    APP_ARGUMENT = 109
    APP_PARAMETER_SELECT = 110
    APP_PARAMETER_RECORD = 111
    FORMAL_SELECT = 112
    FORMAL_CELL = 113
    FORMAL_FINISH = 114
    POSITIVITY_NODE = 115
    ABSTRACT_SCOPE_SELECT = 116
    ABSTRACT_SCOPE_RECORD = 117
    ABSTRACT_SCOPE_LOCAL = 118
    RECURSIVE_NODE = 119
    RECURSIVE_CAPTURE = 120
    RECURSIVE_PREFIX_LINK = 121
    RECURSIVE_SKIP = 122
    RECURSIVE_INDEX = 123
    RECURSIVE_INDEX_STORE = 124
    REVERSE_LIST = 125
    REVERSE_FINISH = 126
    CTOR_FAMILY_CELL = 127
    CTOR_FAMILY_SIGNATURE = 128
    CTOR_FAMILY_SCHEME = 129
    CTOR_FAMILY_METADATA = 130
    CTOR_RAW_FAMILY = 131
    CTOR_FAMILY_AUX = 132
    CTOR_VECTOR = 133
    CTOR_CELL = 134
    CTOR_RECORD = 135
    CTOR_TYPE_SORT = 136
    CTOR_FIELDS = 137
    CTOR_FIELD_SORT = 138
    CTOR_FIELD_SELECT = 139
    CTOR_FIELD_RECORD = 140
    CTOR_FIELD_LINK = 141
    CTOR_STORE_META = 142
    CTOR_STORE_PENDING = 143
    CTOR_LINK = 144
    RECNAME_LEFT_HEADER = 145
    RECNAME_RIGHT_HEADER = 146
    RECNAME_LEFT_CELL = 147
    RECNAME_RIGHT_CELL = 148
    RECNAME_LEFT_PART = 149
    RECNAME_RIGHT_PART = 150
    RECNAME_SUFFIX_CELL = 151
    RECNAME_SUFFIX_PART = 152
    RECNAME_SUFFIX_HEADER = 153
    RECNAME_SUFFIX_BYTE = 154
    CORE_NAME_CELL = 155
    CORE_NAME_SIGNATURE = 156
    CORE_NAME_SCHEME = 157
    CORE_NAME_METADATA = 158
    CORE_NAME_RAW_FAMILY = 159
    CORE_NAME_AUX = 160
    CORE_NAME_STORE = 161
    DECL_CTOR_NAME = 162
    DECL_CTOR_FAMILY_SIGNATURE = 163
    DECL_CTOR_FAMILY_SCHEME = 164
    DECL_CTOR_FAMILY_METADATA = 165
    DECL_CTOR_RAW_FAMILY = 166
    DECL_CTOR_AUX = 167
    DECL_CTOR_VECTOR = 168
    DECL_CTOR_CELL = 169
    DECL_CTOR_RAW = 170
    DECL_CTOR_PENDING = 171
    DECL_CTOR_ANALYSIS = 172
    DECL_CTOR_STORE_INFO = 173
    DECL_CTOR_STORE_SCHEME = 174
    DECL_CTOR_STORE_SIGNATURE = 175
    DECL_CTOR_LINK = 176
    ELIM_PENDING_CELL = 177
    ELIM_PENDING = 178
    ELIM_ANALYSIS = 179
    ELIM_FIELDS = 180
    ELIM_RESULT_LEVEL = 181
    ELIM_FIELD_CELL = 182
    ELIM_FIELD = 183
    ELIM_LOCAL = 184
    ELIM_FIELD_SORT = 185
    ELIM_FIELD_LEVEL = 186
    ELIM_ARGUMENT = 187
    ELIM_APPEND = 188
    ELIM_PREPARE = 189
    ELIM_PARAMETERS = 190
    ELIM_FRESH = 191
    ELIM_SHIFT = 192
    ELIM_STORE_LEVEL = 193
    ELIM_STORE_CELL = 194
    ELIM_STORE_VECTOR = 195
    ELIM_STORE_METADATA = 196
    FRESH_LOCAL_RECORD = 197
    APPLY_SCOPE_SELECT = 198
    APPLY_SCOPE_RECORD = 199
    APPLY_SCOPE_LOCAL = 200
    MOTIVE_NAME = 201
    MOTIVE_SIGNATURE = 202
    MOTIVE_SORT = 203
    MOTIVE_CONSTANT = 204
    MOTIVE_SNAPSHOT_SELECT = 205
    MOTIVE_SNAPSHOT_VECTOR = 206
    MOTIVE_ELIM_SORT = 207
    MOTIVE_STORE_TELESCOPE = 208
    MOTIVE_STORE_INFO = 209
    MOTIVE_LINK = 210
    FLAGS_CTOR_CELL = 211
    FLAGS_PENDING = 212
    FLAGS_ANALYSIS = 213
    FLAGS_FIELDS = 214
    FLAGS_FIELD_CELL = 215
    FLAGS_FIELD = 216
    FLAGS_LOCAL = 217
    FLAGS_DOMAIN = 218
    FLAGS_NEXT = 219
    FLAGS_STORE = 220
    SNAPSHOT_SCOPE = 221
    SNAPSHOT_VECTOR = 222
    PREFIX_VECTOR = 223
    PREFIX_CELL = 224
    PREFIX_BINDER = 225
    PREFIX_INDICES = 226
    PREFIX_INDEX_CELL = 227
    PREFIX_INDEX_STORE = 228
    PREFIX_STORE = 229
    LIST_CELL = 230
    LIST_ARGUMENT = 231
    MOTIVE_FIND_CELL = 232
    MOTIVE_FIND_INFO = 233
    MOTIVE_FIND_RECORD = 234
    DECL_CTOR_ORDER = 235
    MINOR_VECTOR = 236
    MINOR_CELL = 237
    MINOR_PENDING = 238
    MINOR_ANALYSIS = 239
    MINOR_FIELD_VECTOR = 240
    MINOR_FIELD_CELL = 241
    MINOR_FIELD = 242
    MINOR_RESTORE_RECORD = 243
    MINOR_CONSTANT = 244
    MINOR_RESULT = 245
    MINOR_IH_VECTOR = 246
    MINOR_IH_CELL = 247
    MINOR_IH_FIELD = 248
    MINOR_IH_LOCAL = 249
    MINOR_OPENED = 250
    MINOR_IH_INDICES = 251
    MINOR_IH_RESULT = 252
    MINOR_STORE = 253
    MINOR_LINK = 254
    # These phases are always keyed by BUILD_RECURSOR_TYPES. Only task-scoped
    # builder values are shared; global Expr/fold/return/address modes are not.
    REC_TYPE_VECTOR = 211
    REC_TYPE_CELL = 212
    REC_TYPE_INFO = 213
    REC_TYPE_TELESCOPE = 214
    REC_TYPE_INDICES = 215
    REC_TYPE_INDEX_CELL = 216
    REC_TYPE_INDEX_RECORD = 217
    REC_TYPE_MAJOR = 218
    REC_TYPE_MOTIVE_RECORD = 219
    REC_TYPE_STORE = 220
    REC_TYPE_LINK = 223
    RESTORE_SCOPE_CELL = 212
    RESTORE_SCOPE_ITEM = 213
    RESTORE_SCOPE_RECORD = 214
    RULE_VECTOR = 145
    RULE_CELL = 146
    RULE_INFO = 147
    RULE_PENDING = 148
    RULE_ANALYSIS = 149
    RULE_MINOR_RECORD = 150
    RULE_FIELD_VECTOR = 151
    RULE_FIELD_CELL = 152
    RULE_FIELD = 153
    RULE_LOCAL = 154
    RULE_OPENED = 155
    RULE_FAMILY_INFO = 156
    RULE_TELESCOPE = 157
    RULE_CONSTANT = 158
    RULE_INDEX_VECTOR = 159
    RULE_IH_BODY = 160
    RULE_APPEND_IH = 161
    RULE_STORE = 162
    RULE_STORE_FAMILY = 163
    RULE_LINK = 164
    ASM_NAMES = 145
    ASM_FAMILY_LINK = 146
    ASM_BLOCK = 147
    ASM_AUX = 148
    ASM_VECTOR = 149
    ASM_CELL = 150
    ASM_TYPE = 151
    ASM_OWNER = 152
    ASM_SCHEME = 153
    ASM_HEADER = 154
    ASM_RAW_FAMILY = 155
    ASM_RAW_AUX = 156
    ASM_CTOR_VECTOR = 157
    ASM_RULE_VECTOR = 158
    ASM_RULE_CELL = 159
    ASM_RULE_INFO = 160
    ASM_RULE_STORE = 161
    ASM_COUNTS = 162
    ASM_RECURSOR = 163
    ASM_STORE_SCHEME = 164
    ASM_SIGNATURE = 165
    ASM_LINK = 166
    ASM_SIG_ORDER = 167
    SIGV_CELL = 145
    SIGV_SIGNATURE = 146
    CLAIM_VECTOR = 145
    CLAIM_CELL = 146
    CLAIM_RECORD = 147
    CLAIM_SIGNATURE = 148
    CLAIM_SCHEME = 149
    CLAIM_PARAMETER_VECTOR = 150
    CLAIM_SORT = 151
    CLAIM_STORE = 152
    SPINE_SCAN = 145
    SPINE_VECTOR = 146
    SPINE_RESULT = 147
    SLICE_CELL = 145
    SLICE_ARGUMENT = 146
    IOTA_SCHEME = 145
    IOTA_METADATA = 146
    IOTA_COUNTS = 147
    IOTA_SHARED_COUNTS = 148
    IOTA_REC_SPINE = 149
    IOTA_REC_HEAD = 150
    IOTA_REC_ARGUMENTS = 151
    IOTA_MAJOR_SPINE = 152
    IOTA_MAJOR_HEAD = 153
    IOTA_MAJOR_ARGUMENTS = 154
    IOTA_RULE_VECTOR = 155
    IOTA_RULE_CELL = 156
    IOTA_RULE = 157
    IOTA_PARAMETER_VECTOR = 158
    IOTA_LEVEL_VECTOR = 159
    MAJOR_METADATA = 145
    MAJOR_COUNTS = 146
    MAJOR_SHARED = 147
    MAJOR_BLOCK = 148
    MAJOR_FLAGS = 149
    MAJOR_STRUCTURE = 149
    MAJOR_OWNER = 150
    MAJOR_TYPE_APP = 151
    MAJOR_TYPE_HEAD = 152
    MAJOR_RULE_VECTOR = 153
    MAJOR_RULE_CELL = 154
    MAJOR_RULE = 155
    MAJOR_CONSTRUCTOR = 156
    MAJOR_VALUE = 157
    MAJOR_APP = 158
    MAJOR_HEAD = 159
    MAJOR_SIGNATURE = 160
    MAJOR_SCHEME = 161
    MAJOR_SORT = 162
    MAJOR_SORT_LEVEL = 163
    MAJOR_PROJECTION = 164
    MAJOR_APPLY_PROJECTION = 165
    REDUCE_SPINE = 145
    REDUCE_HEAD = 146
    REDUCE_SIGNATURE = 147
    REDUCE_SCHEME = 148
    REDUCE_METADATA = 149
    REDUCE_COUNTS = 150
    REDUCE_SHARED = 151
    REDUCE_ARGUMENTS = 152
    GATHER_SCAN = 153
    GATHER_SAVE = 154
    GATHER_RESTORE = 155
    PRIOR_BLOCK_CELL = 145
    PRIOR_BLOCK_ORIGIN = 146
    PATH_RIGHT_HEADER = 145
    PATH_LEFT_CELL = 146
    PATH_RIGHT_CELL = 147
    PATH_LEFT_PART = 148
    PATH_RIGHT_PART = 149
    INTERN_ROOT = 145
    INTERN_CELL = 146
    INTERN_ENTRY = 147
    INTERN_STORE_ENTRY = 148
    INTERN_STORE_CELL = 149
    INTERN_STORE_VECTOR = 150
    SPLICE_SUFFIX = 145
    SPLICE_SKIP = 146
    SPLICE_REVERSED = 147
    SPLICE_COPY = 148
    SPLICE_FINISH = 149
    DECIMAL_STEP = 145
    DECIMAL_FINISH = 146
    REPLACE_PREFIX_HEADER = 145
    GEN_REC_SUFFIX = 145
    GEN_REC_BYTE = 146
    GEN_REC_BYTES = 147
    GEN_REC_COMPONENT = 148
    GEN_REC_CELL = 149
    GEN_REC_PATH = 150
    RAW_PREFIX_LOOP = 145
    RAW_FAMILY_VECTOR = 145
    NESTED_APP_SPINE = 145
    NESTED_APP_HEAD = 146
    NESTED_APP_ORIGIN = 147
    NESTED_APP_BLOCK = 148
    NESTED_APP_ARGUMENTS = 149
    NESTED_APP_SELECT = 150
    NESTED_APP_RESULT = 151
    PI_PARAMS_HEADER = 145
    PI_PARAMS_CELL = 146
    PI_PARAMS_ARGUMENT = 147
    PI_PARAMS_STRIP = 148


CALL_BETA_ZETA = 16
PENDING_ARGUMENT = 17
CALL_TELESCOPE = 18
CALL_FOLD = 19
CALL_SORT_LEVEL = 20
CALL_CONST_LEVEL = 21
VECTOR_VALUE = 22
LEVEL_EQUAL_SECOND = 23
LEVEL_OR_SECOND = 24
CALL_MAX_COMPARE = 25
CALL_MAX_LEFT_OFFSET = 26
CALL_MAX_RIGHT_OFFSET = 27
CALL_IMAX_NONZERO = 28
CALL_IMAX_COMPARE = 29
CALL_ORDER_LEFT_OFFSET = 30
CALL_ORDER_RIGHT_OFFSET = 31
CALL_ORDER_BASE_COMPARE = 32
CALL_ORDER_FIRST = 33
CALL_ORDER_SECOND = 34
CALL_NORMAL_IMAX = 35
CALL_MERGE_ORDER = 36
CALL_MERGE_OFFSET = 37
CALL_EQUIVALENT_LEFT = 38
CALL_EQUIVALENT_RIGHT = 39
CALL_GEQ_LEFT = 40
CALL_GEQ_RIGHT = 41
CALL_GEQ_EQUAL = 42
CALL_GEQ_AND = 43
CALL_GEQ_MAX_FIRST = 44
CALL_GEQ_MAX_SECOND = 45
CALL_GEQ_OFFSET_LEFT = 46
CALL_GEQ_OFFSET_RIGHT = 47
CALL_GEQ_BASE_EQUAL = 48
EXPR_EQUAL_REST = 49
CALL_VECTOR_LEVEL_EQUAL = 50
CALL_INFER_BINDER_DOMAIN = 51
CALL_INFER_DOMAIN_WHNF = 52
CALL_INFER_OPEN = 53
CALL_INFER_BODY = 54
CALL_INFER_BODY_WHNF = 55
CALL_INFER_ABSTRACT = 56
CALL_INFER_PI_LEVEL = 57
CALL_INFER_FUNCTION = 58
CALL_INFER_FUNCTION_WHNF = 59
CALL_INFER_ARGUMENT = 60
CALL_INFER_ARGUMENT_CONVERT = 61
CALL_INFER_LET_TYPE = 62
CALL_INFER_LET_TYPE_WHNF = 63
CALL_INFER_LET_VALUE = 64
CALL_INFER_LET_CONVERT = 65
CALL_INFER_LET_BODY = 66
CALL_CONVERT_FAST = 67
CALL_CONVERT_LEFT_WHNF = 68
CALL_CONVERT_RIGHT_WHNF = 69
CALL_CONVERT_NORMAL = 70
CALL_INFER_CONSTANT_LOOKUP = 71
CALL_INFER_CONSTANT_SUBSTITUTE = 72
CALL_SOURCE_NAME = 73
CALL_SOURCE_DUPLICATE = 74
CALL_SOURCE_PARAMETERS = 75
CALL_SOURCE_TYPE_SCOPE = 76
CALL_SOURCE_TYPE_INFER = 77
CALL_SOURCE_TYPE_WHNF = 78
CALL_SOURCE_PROPOSITION = 79
CALL_SOURCE_VALUE_SCOPE = 80
CALL_SOURCE_VALUE_INFER = 81
CALL_SOURCE_VALUE_CONVERT = 82
CALL_TELESCOPE_WHNF = 83
CALL_REUSE_WHNF = 84
CALL_REUSE_CONVERT = 85
CALL_REUSE_SUBSTITUTE = 86
CALL_REUSE_SCOPE_TYPE = 87
CALL_REUSE_SCOPE_CANDIDATE = 88
CALL_REUSE_OPEN = 89
CALL_REUSE_FINISH = 90
CALL_OCCURRENCE_FINISH = 91
CALL_SOURCE_BLOCK_HEADERS = 92
CALL_HEADER_PARAMETERS = 93
CALL_HEADER_NAME = 94
CALL_HEADER_DUPLICATE_GLOBAL = 95
CALL_HEADER_DUPLICATE_PRIVATE = 96
CALL_HEADER_SCOPE = 97
CALL_HEADER_INFER = 98
CALL_HEADER_TYPE_WHNF = 99
CALL_HEADER_OPEN_PARAMETERS = 100
CALL_HEADER_CONSUME = 101
CALL_HEADER_INDICES = 102
CALL_HEADER_LEVEL = 103
CALL_FAMILY_OCCURRENCE = 104
CALL_HEADER_FORMAL_LEVELS = 105
CALL_APP_MEMBER = 106
CALL_APP_LOOKUP = 107
CALL_APP_LEVELS = 108
CALL_APP_INDEX = 109
CALL_APP_PARAMETER = 110
CALL_POS_WHNF = 111
CALL_POS_OCCURRENCE = 112
CALL_POS_DOMAIN = 113
CALL_POS_OPEN = 114
CALL_POS_APPLICATION = 115
CALL_ABSTRACT_SCOPE = 116
CALL_REC_WHNF = 117
CALL_REC_DOMAIN = 118
CALL_REC_OPEN = 119
CALL_REC_APPLICATION = 120
CALL_REC_INDEX = 121
CALL_REC_REVERSE_INDICES = 122
CALL_REC_REVERSE_PREFIX = 123
CALL_SOURCE_CORE_CONSTRUCTORS = 124
CALL_CTOR_NAME = 125
CALL_CTOR_DUPLICATE_DECLARATION = 126
CALL_CTOR_DUPLICATE_PENDING = 127
CALL_CTOR_SCOPE = 128
CALL_CTOR_INFER = 129
CALL_CTOR_TYPE_WHNF = 130
CALL_CTOR_CONSUME = 131
CALL_CTOR_FIELD_INFER = 132
CALL_CTOR_FIELD_WHNF = 133
CALL_CTOR_RESULT_PROP = 134
CALL_CTOR_FIELD_LEVEL = 135
CALL_CTOR_POSITIVITY = 136
CALL_CTOR_RECURSIVE = 137
CALL_CTOR_OPEN_FIELD = 138
CALL_CTOR_RESULT_APPLICATION = 139
CALL_CTOR_FIELD_VECTOR = 140
CALL_RECNAME_PARENT = 141
CALL_RECNAME_CANDIDATE = 142
CALL_RECNAME_COMPONENT = 143
CALL_SOURCE_CORE_NAMES = 144
CALL_CORE_NAME_PROFILE = 145
CALL_CORE_NAME_RELATION = 146
CALL_CORE_NAME_DECLARATION = 147
CALL_CORE_NAME_PENDING = 148
CALL_SOURCE_DECLARE_CONSTRUCTORS = 149
CALL_DECLARE_CTOR_LOOKUP = 150
CALL_ELIM_NONZERO = 151
CALL_ELIM_FIELD_INFER = 152
CALL_ELIM_FIELD_WHNF = 153
CALL_SOURCE_ELIMINATION = 154
CALL_MOTIVE_CONSUME = 155
CALL_MOTIVE_INDICES = 156
CALL_MOTIVE_PARAMETERS = 157
CALL_MOTIVE_APPLY_INDICES = 158
CALL_MOTIVE_MAJOR = 159
CALL_MOTIVE_FOLD = 160
CALL_MOTIVE_LOCAL = 161
CALL_MOTIVE_VECTOR = 162
CALL_SOURCE_MOTIVES = 163
CALL_FLAGS_OCCURRENCE = 164
CALL_SOURCE_FLAGS = 165
CALL_MOTIVE_SNAPSHOT = 166
CALL_PREFIX_DOMAIN = 167
CALL_PREFIX_LOCAL = 168
CALL_PREFIX_INDEX = 169
CALL_PREFIX_INDEX_VECTOR = 170
CALL_PREFIX_LOCAL_VECTOR = 171
CALL_DECLARE_CTOR_ORDER = 172
CALL_MINOR_OWN_MOTIVE = 173
CALL_MINOR_RESULT_INDICES = 174
CALL_MINOR_PARAMETERS = 175
CALL_MINOR_FIELDS = 176
CALL_MINOR_PREFIX = 177
CALL_MINOR_IH_MOTIVE = 178
CALL_MINOR_IH_INDICES = 179
CALL_MINOR_FUNCTION = 180
CALL_MINOR_IH_FOLD = 181
CALL_MINOR_IH_LOCAL = 182
CALL_MINOR_FOLD = 183
CALL_MINOR_LOCAL = 184
CALL_MINOR_VECTOR = 185
CALL_SOURCE_MINORS = 186
CALL_REC_TYPE_BODY = 187
CALL_REC_TYPE_FOLD = 188
CALL_REC_TYPE_SCOPE = 189
CALL_REC_TYPE_VECTOR = 190
CALL_SOURCE_REC_TYPES = 191
CALL_MINOR_RESTORE = 192
CALL_REC_TYPE_RESTORE = 193
CALL_RULE_LEVELS = 194
CALL_RULE_RESTORE = 195
CALL_RULE_MINOR_APPLY = 196
CALL_RULE_PREFIX = 197
CALL_RULE_FAMILY = 198
CALL_RULE_PARAMETERS = 199
CALL_RULE_MOTIVES = 200
CALL_RULE_MINORS = 201
CALL_RULE_INDICES = 202
CALL_RULE_FUNCTION = 203
CALL_RULE_IH_FOLD = 204
CALL_RULE_FINAL_FOLD = 205
CALL_RULE_SCOPE = 206
CALL_RULE_VECTOR = 207
CALL_SOURCE_RULES = 208
CALL_ASM_FAMILIES = 209
CALL_ASM_RULES = 210
CALL_ASM_SIGNATURES = 211
CALL_SOURCE_ASSEMBLY = 212
CALL_CLAIM_SEEN = 213
CALL_CLAIM_LOOKUP = 214
CALL_CLAIM_PARAMETERS = 215
CALL_CLAIM_SCOPE = 216
CALL_CLAIM_INFER = 217
CALL_CLAIM_WHNF = 218
CALL_CLAIM_RENAME = 219
CALL_CLAIM_CONVERT = 220
CALL_CLAIM_RESTORE = 221
CALL_SOURCE_CLAIMS = 222
CALL_IOTA_ZIP = 223
CALL_IOTA_PREFIX = 224
CALL_IOTA_FIELDS = 225
CALL_IOTA_EXTRA = 226
LOCAL_DECL_TAG = int(CellTag.LOCAL_DECL)  # Internal record, never an input Expr.


REGISTERS = ('mode', 'status', 'reason', 'fuel', 'free', 'sp', 'decl',
    'decl_count', 'ctx', 'x', 'depth', 'task', 'r', 'delta', 'cutoff', 'start',
    'count', 'i', 'found', 'root', 'substitution', 'limit', 'bounded', 'pending_open',
    'pending_fold', 'fold_body', 'domain', 'binder_info', 'abstract_uid', 'open_tag', 'fold_tag',
    'arg_base', 'parameter', 'lookup_level', 'const_original', 'expr_depth', 'level_map_head', 'level_map_result',
    'vec_length', 'vec_left', 'vec_build', 'vec_head', 'vec_changed', 'vector_result',
    'peer', 'left_tag', 'left_a', 'left_b', 'level_offset', 'pending_compare',
    'constructor_left', 'constructor_right', 'constructor_stage', 'left_base', 'left_offset', 'right_offset',
    'order_same_base', 'merge_l', 'merge_r', 'merge_hl', 'merge_tl', 'merge_hr', 'merge_tr',
    'merge_rev', 'merge_acc', 'merge_anchor', 'merge_chosen', 'merge_explicit', 'merge_exp_offset', 'merge_max_offset', 'geq_left', 'geq_right', 'left_c', 'vector_expected_role', 'vector_remaining', 'comparison_root', 'pending_infer', 'local_base', 'lookup_uid', 'lookup_index',
    'lookup_type', 'convert_left_level', 'raw_index', 'env_head', 'env_next', 'query_symbol', 'env_ready', 'signature_type', 'parameter_vector', 'level_vector',
    'parameter_head', 'level_head', 'zip_count', 'zip_remaining', 'zip_symbol', 'zip_parameter_next', 'pending_scope', 'symbols_root', 'name_table_left', 'name_table_next',
    'name_second', 'name_part', 'name_length', 'name_index', 'target_index', 'kernel_zero', 'active_kind',
    'active_symbol', 'active_parameters', 'active_type', 'active_value', 'active_extra', 'commit_scheme', 'commit_signature', 'pending_reuse', 'reuse_root', 'reuse_base', 'reuse_end',
    'reuse_index', 'reuse_whnf', 'reuse_body', 'reuse_domain',
    'occurrence_internal', 'occurrence_mark', 'occurrence_found', 'lookup_head',
    'header_parameters', 'header_parameter_count', 'header_vector', 'header_head', 'header_seen',
    'header_parameter_base', 'header_parameter_end', 'header_symbol', 'header_type', 'header_raw',
    'header_remaining', 'header_next', 'header_indices', 'header_current_level', 'header_result_level',
    'header_meta', 'header_scheme', 'header_signature',
    'family_set_cursor', 'family_set_remaining', 'family_set_next',
    'formal_count', 'formal_remaining', 'formal_i', 'formal_head', 'formal_value', 'header_levels',
    'app_args', 'app_arity', 'app_symbol', 'app_levels', 'app_signature', 'app_remaining', 'app_context_index', 'app_argument', 'app_next',
    'abstract_base', 'abstract_end', 'scope_cursor', 'scope_dest', 'reverse_length', 'reverse_remaining', 'reverse_head',
    'recursive_mark', 'recursive_prefix_rev', 'recursive_prefix_count', 'recursive_prefix_value',
    'recursive_family', 'recursive_skip', 'recursive_indices', 'recursive_index_remaining', 'recursive_index_rev',
    'recursive_index_next', 'recursive_index_vector', 'typing_active', 'typing_head', 'core_operation', 'core_index',
    'ctor_family_cursor', 'ctor_families_remaining', 'ctor_family_next', 'ctor_family_signature',
    'ctor_remaining', 'ctor_next', 'ctor_symbol', 'ctor_type', 'ctor_field_count', 'ctor_field_rev',
    'ctor_active_pi', 'ctor_field_domain', 'ctor_field_level', 'ctor_recursive', 'ctor_field_tail',
    'ctor_field_info', 'ctor_result_args', 'ctor_field_vector', 'ctor_meta', 'ctor_pending', 'ctor_names',
    'name_parent_symbol', 'name_candidate_symbol', 'recname_parent_path', 'recname_candidate_path',
    'recname_length', 'recname_head', 'recname_remaining', 'recname_right', 'recname_next_left', 'recname_next_right',
    'recname_part_left', 'recname_part_right', 'recname_part_tag', 'recname_part_value', 'recname_byte_index',
    'core_names_remaining', 'core_rec_names', 'core_name_next', 'core_name_family', 'core_name_family_symbol', 'core_name_symbol',
    'decl_ctor_families', 'core_ctor_declared', 'decl_ctor_family', 'decl_ctor_name_next', 'decl_ctor_remaining',
    'decl_ctor_ordinal', 'decl_ctor_next', 'decl_ctor_symbol', 'decl_ctor_type', 'decl_ctor_fields',
    'decl_ctor_info', 'decl_ctor_scheme', 'decl_ctor_signature', 'decl_ctor_pending', 'decl_ctor_order_rev', 'core_constructors',
    'core_K', 'core_elim_level', 'core_elim_info', 'core_rec_parameters', 'elim_large', 'elim_arguments',
    'elim_remaining', 'elim_head', 'elim_next', 'elim_record', 'elim_local', 'elim_old_head', 'elim_fresh', 'elim_cursor', 'elim_symbol_head',
    'fold_base', 'fresh_local', 'fresh_domain', 'fresh_record', 'apply_base', 'apply_end', 'apply_cursor', 'apply_body',
    'core_motives', 'motive_remaining', 'motive_rev', 'motive_family', 'motive_symbol', 'motive_next', 'motive_mark',
    'motive_family_symbol', 'motive_major', 'snapshot_count', 'snapshot_remaining', 'snapshot_head',
    'motive_indices', 'motive_local', 'motive_telescope', 'motive_info',
    'core_flags', 'core_recursive', 'core_reflexive', 'flags_pi', 'flags_ctor_next', 'flags_remaining', 'flags_field_next',
    'prefix_family', 'prefix_indices', 'prefix_mark', 'prefix_remaining', 'prefix_next', 'prefix_binder_info',
    'prefix_locals', 'prefix_index_rev', 'prefix_index_count', 'prefix_index_remaining', 'prefix_index_next', 'prefix_index_vector', 'opened_prefix',
    'list_head', 'list_skip', 'list_body', 'list_next', 'motive_query', 'motive_lookup_remaining', 'motive_lookup_next', 'motive_lookup_info',
    'core_minors', 'minor_rev', 'minor_remaining', 'minor_next', 'minor_pending', 'minor_mark', 'minor_symbol', 'minor_family', 'minor_fields',
    'minor_result_args', 'minor_field_count', 'minor_fields_end', 'minor_result_fn', 'minor_result_type',
    'minor_ih_remaining', 'minor_ih_next', 'minor_descriptor', 'minor_recursive_local', 'minor_ih_mark', 'minor_index_vector', 'minor_ih_motive',
    'minor_ih_target', 'minor_local', 'minor_info',
    'core_rec_types', 'rec_type_closed', 'rec_type_mark', 'rec_type_rev', 'rec_type_remaining', 'rec_type_next',
    'rec_type_family', 'rec_type_motive', 'rec_type_major', 'rec_type_symbol', 'rec_type_info', 'restore_length', 'restore_remaining', 'restore_next',
    'core_rules', 'core_rec_levels', 'rule_mark', 'rule_rev', 'rule_remaining', 'rule_next', 'rule_minor_record', 'rule_field_count',
    'rule_symbol', 'rule_family', 'rule_fields', 'rule_fields_end', 'rule_result', 'rule_field_remaining', 'rule_field_next',
    'rule_descriptor', 'rule_recursive_local', 'rule_ih_mark', 'rule_index_vector', 'rule_recursive_symbol', 'rule_recursive_fn',
    'rule_ih_target', 'rule_closed', 'rule_info', 'rule_family_info',
    'core_family_vector', 'core_rec_signatures', 'asm_names_remaining', 'asm_family_rev', 'asm_sig_rev', 'asm_family_value', 'asm_name_next',
    'asm_block', 'asm_aux', 'asm_remaining', 'asm_next', 'asm_family', 'asm_type', 'asm_symbol', 'asm_group_rev', 'asm_group_count',
    'asm_indices', 'asm_expected', 'asm_rule_remaining', 'asm_rule_next', 'asm_rule_ref', 'asm_group', 'asm_counts', 'asm_rec', 'asm_scheme', 'asm_signature',
    'header_block', 'signature_lookup_remaining', 'signature_lookup_next', 'claim_expected_uparams', 'claim_seen', 'claim_checked',
    'claim_remaining', 'claim_next', 'claim_symbol', 'claim_type', 'claim_parameters', 'claim_expected_type',
    'spine_head', 'spine_count', 'spine_function', 'spine_arguments',
    'slice_start', 'slice_take', 'slice_remaining', 'slice_next', 'slice_body',
    'reduction_rec_spine', 'reduction_major_spine', 'iota_symbol', 'iota_parameters', 'iota_rules',
    'iota_parameters_count', 'iota_indices', 'iota_prefix', 'iota_major_index', 'iota_rec_args', 'iota_levels',
    'iota_arg_count', 'iota_major_args', 'iota_constructor', 'iota_major_count', 'iota_remaining', 'iota_next',
    'iota_fields', 'iota_rhs', 'iota_uparams', 'vector_index', 'reference_remaining',
    'major_value', 'major_path', 'major_owner', 'major_rules', 'major_parameters', 'major_indices',
    'major_owner_symbol', 'major_type_arguments', 'major_type_levels', 'major_constructor', 'major_fields',
    'major_accumulator', 'major_cursor', 'major_projection',
    'reduce_major_index', 'gather_saved_sp', 'gather_expression', 'gather_base_sp', 'gather_result', 'prior_block_next',
    'path_prefix', 'path_left_remaining', 'path_left_head', 'path_right_remaining', 'path_right_cursor',
    'path_next_left', 'path_left_part', 'path_next_right', 'path_right_part', 'path_part_tag', 'path_part_payload',
    'intern_remaining', 'intern_length', 'intern_head', 'intern_maximum', 'intern_next', 'intern_candidate',
    'intern_symbol', 'intern_entry', 'intern_link',
    'splice_role', 'splice_skip', 'splice_prefix_length', 'splice_prefix_head', 'splice_length',
    'splice_tail', 'splice_suffix_remaining', 'splice_remaining',
    'decimal_value', 'decimal_number', 'decimal_head', 'decimal_count',
    'generated_rec_indexed', 'generated_rec_index', 'generated_suffix_head', 'generated_suffix_length',
    'generated_suffix_remaining', 'generated_suffix_bytes', 'generated_name_component', 'generated_name_cell',
    'raw_prefix_count', 'raw_prefix_remaining', 'raw_family_vector', 'family_occurrence_root',
    'nested_registry_head', 'nested_parameter_count', 'nested_parameter_index', 'nested_has_current', 'nested_has_loose',
    'pi_parameter_vector', 'pi_parameter_limit', 'pi_parameter_count', 'pi_parameter_remaining',
    'pi_parameter_vector_remaining', 'pi_parameter_cursor', 'pi_parameter_next',
    'stage_pc', 'stage_original', 'stage_uparams', 'stage_parameter_count', 'stage_levels',
    'stage_front', 'stage_front_count', 'stage_back', 'stage_back_count', 'stage_all', 'stage_all_count',
    'stage_done', 'stage_done_count', 'stage_family', 'stage_symbol', 'stage_type', 'stage_aux', 'stage_rec',
    'stage_ctor_cursor', 'stage_ctor_remaining', 'stage_ctor_next', 'stage_ctor_symbol', 'stage_ctor_type',
    'stage_ctors', 'stage_ctor_count', 'stage_param_snapshot', 'stage_parameters_base', 'stage_parameters_end',
    'stage_saved_ctx', 'stage_saved_count', 'stage_saved_arg_base', 'stage_reserved', 'stage_fresh_counter',
    'stage_maps', 'stage_ctor_maps', 'stage_original_count', 'stage_expanded', 'stage_original_claims',
    'copy_pc', 'copy_application', 'copy_origin', 'copy_spine', 'copy_arguments', 'copy_argument_count',
    'copy_function', 'copy_owner', 'copy_levels', 'copy_uparams', 'copy_parameter_count', 'copy_key',
    'copy_lookup', 'copy_lookup_next', 'copy_selected', 'copy_family_cursor', 'copy_family_remaining',
    'copy_family_next', 'copy_original_symbol', 'copy_family_type', 'copy_family_aux', 'copy_aux_symbol',
    'copy_rec_symbol', 'copy_template', 'copy_ctor_cursor', 'copy_ctor_remaining', 'copy_ctor_next',
    'copy_ctor_symbol', 'copy_ctor_type', 'copy_ctor_new_symbol', 'copy_ctors', 'copy_ctor_count',
    'copy_fold_type', 'copy_result', 'copy_name_candidate', 'copy_name_rec', 'copy_name_pass',
    'copy_name_query', 'copy_name_return', 'copy_name_origin',
    'rewrite_pc', 'stage_reserve_cursor', 'stage_reserve_remaining', 'stage_original_vector',
    'stage_reserve_next', 'stage_reserve_symbol', 'stage_reserve_aux', 'stage_reserve_ctor_vector',
    'stage_reserve_ctor_remaining', 'stage_reserve_ctor_next', 'stage_ctor_record',
    'stage_ctor_vector', 'stage_new_aux', 'stage_new_family', 'stage_final_vector',
    'copy_ctor_map_record', 'copy_ctor_record', 'copy_ctor_vector', 'copy_lookup_aux', 'copy_new_aux', 'copy_new_family', 'copy_original_ctor_vector', 'copy_original_vector', 'copy_template_head', 'copy_template_record',
    'restore_cb_argument_count', 'restore_cb_arguments', 'restore_cb_constructor', 'restore_cb_function', 'restore_cb_levels', 'restore_cb_lookup', 'restore_cb_new_symbol', 'restore_cb_next', 'restore_cb_original_args', 'restore_cb_pc', 'restore_cb_rename', 'restore_cb_result', 'restore_cb_root', 'restore_cb_symbol', 'restore_cb_template', 'restore_expr_pc', 'restore_parameter_base', 'restore_parameter_end', 'restore_prefix_tag', 'restore_rec_map', 'rewrite_restoring',
    'publish_K', 'publish_block', 'publish_check_cursor', 'publish_check_kind', 'publish_check_next', 'publish_check_payload', 'publish_check_rhs', 'publish_check_rule_next', 'publish_check_rules', 'publish_check_type', 'publish_compat', 'publish_counts', 'publish_ctor_fields', 'publish_ctor_next', 'publish_ctor_ordinal', 'publish_ctor_remaining', 'publish_ctor_symbol', 'publish_ctor_type', 'publish_current_family', 'publish_entry_kind', 'publish_entry_parameters', 'publish_entry_payload', 'publish_entry_return', 'publish_entry_scheme', 'publish_entry_signature', 'publish_entry_symbol', 'publish_entry_type', 'publish_expanded_head', 'publish_families', 'publish_family_cursor', 'publish_family_next', 'publish_family_remaining', 'publish_family_symbol', 'publish_family_type', 'publish_family_vector', 'publish_flags', 'publish_head', 'publish_main', 'publish_map_cursor', 'publish_map_next', 'publish_nindices', 'publish_nminors', 'publish_nmotives', 'publish_nparams', 'publish_old_head', 'publish_origin', 'publish_original_type', 'publish_owner_symbol', 'publish_payload', 'publish_pc', 'publish_raw_aux', 'publish_raw_family', 'publish_rec_index', 'publish_rec_new_symbol', 'publish_rec_next', 'publish_rec_old_symbol', 'publish_rec_owner', 'publish_rec_parameters', 'publish_rec_remaining', 'publish_rec_rules', 'publish_rec_source', 'publish_rec_type', 'publish_recs', 'publish_registry', 'publish_rule', 'publish_rule_constructor', 'publish_rule_count', 'publish_rule_fields', 'publish_rule_next', 'publish_rule_remaining', 'publish_rule_rhs', 'publish_rule_vector', 'publish_rules', 'publish_shared',
    'published_declarations', 'publish_entry_count', 'family_info_pc', 'info_indices', 'info_next', 'info_parameters', 'info_raw', 'info_remaining', 'info_symbol', 'projection_pc', 'projection_reduce_pc',
    'convert_pc', 'levels_eq_count', 'levels_eq_left', 'levels_eq_pc', 'levels_eq_right', 'levels_eq_value', 'structure_ctor', 'structure_detail', 'structure_fields', 'structure_parameters', 'structure_pc', 'structure_rec_symbol', 'structure_signature', 'structure_symbol',
    'quot_pc', 'quot_initialized', 'quot_head', 'quot_new', 'quot_build_base', 'quot_data_base',
    'quot_symbol_eq', 'quot_symbol_quot', 'quot_symbol_mk', 'quot_symbol_lift', 'quot_symbol_ind', 'quot_symbol_u', 'quot_symbol_v',
    'quot_eq_signature', 'quot_eq_type', 'quot_eq_u', 'quot_refl_type', 'quot_refl_u', 'quot_eq', 'quot_refl',
    'quot_parameters', 'quot_lift_parameters', 'quot_type', 'quot_ctor', 'quot_lift', 'quot_ind', 'quot_scheme', 'quot_signature',
    'quot_claim_kind', 'quot_claim_symbol', 'quot_claim_parameters', 'quot_claim_type', 'quot_expected', 'gather_service', 'quot_reduce_pc', 'quot_reduce_args', 'quot_reduce_element', 'quot_reduce_result',
    'nat_validated', 'nat_binding_pc', 'nat_name_base', 'nat_symbol_type', 'nat_symbol_zero', 'nat_symbol_succ',
    'nat_empty_levels', 'nat_type', 'nat_level_one', 'nat_expected_type', 'nat_expected_succ', 'nat_check_type', 'nat_family_signature',
    'nat_binding_remaining', 'nat_binding_seen', 'nat_binding_next', 'nat_literal_pc', 'nat_literal_operation', 'nat_literal_root', 'nat_literal_vector',
    'nat_limb_remaining', 'nat_limb_cursor', 'nat_limb_head', 'nat_limb_count', 'nat_borrow', 'nat_limb_next', 'nat_limb_value', 'nat_limb_drop',
    'nat_predecessor_vector', 'nat_predecessor', 'nat_succ_expression', 'nat_literal_result')
BANK_FIELDS = {'heap': 4, 'stack': 6, 'context': 1, 'constants': 6}


@dataclass(frozen=True)
class MachineConfig:
    heap: int = 64
    stack: int = 16
    context: int = 8
    constants: int = 2
    fuel: int = 256
    # Data symbols need not be smaller than a pointer. This bound is physical,
    # shared across all input names, not a compiled symbol whitelist.
    word_bits: int = 10

    def __post_init__(self):
        for field in ('heap', 'stack', 'context', 'constants'):
            n = getattr(self, field)
            if type(n) is not int or n < 2 or n & (n-1):
                raise ValueError('memory capacities must be powers of two >=2')
        if type(self.fuel) is not int or self.fuel < 1:
            raise ValueError('positive fuel required')
        if not 8 <= self.word_bits <= 21 or max(self.heap, self.stack, self.context, self.constants) >= 1 << self.word_bits:
            raise ValueError('memory pointers do not fit word width')


class StateLayout:
    def __init__(self, config):
        self.config = config
        self.fields = [(n, max(config.word_bits, config.fuel.bit_length()) if n == 'fuel' else config.word_bits)
                       for n in REGISTERS]
        self.banks = {}
        for bank, fields in BANK_FIELDS.items():
            start = sum(w for _, w in self.fields)
            self.fields.extend((f'{bank}/{i}/{j}', config.word_bits)
                for i in range(getattr(config, bank)) for j in range(fields))
            self.banks[bank] = (start, getattr(config, bank), fields*config.word_bits)
        self.names, self.slices = [], {}
        for name, width in self.fields:
            start = len(self.names)
            self.names.extend(f'{name}/{i}' for i in range(width))
            self.slices[name] = slice(start, len(self.names))
        self.widths = [w for _, w in self.fields]
        self.width = len(self.names)

    def encode(self, state):
        words = [state['regs'][n] for n in REGISTERS]
        words.extend(v for bank in BANK_FIELDS for row in state[bank] for v in row)
        return torch.tensor([pack_words(words, self.widths)], dtype=torch.float32)

    def decode(self, bits):
        if len(bits) != self.width or any(b not in (0, 1) for b in bits):
            raise ValueError('exact Boolean state required')
        words = unpack_words(bits, self.widths)
        state = {'regs': dict(zip(REGISTERS, words[:len(REGISTERS)]))}
        offset = len(REGISTERS)
        for bank, width in BANK_FIELDS.items():
            size = getattr(self.config, bank)
            state[bank] = [words[offset+i*width:offset+(i+1)*width] for i in range(size)]
            offset += size*width
        return state


class RegisterLayout:
    def __init__(self, state_layout):
        self.config = state_layout.config
        self.fields = state_layout.fields[:len(REGISTERS)]
        self.width = sum(w for _, w in self.fields)
        self.names = state_layout.names[:self.width]
        self.slices = {n: state_layout.slices[n] for n in REGISTERS}


def document(arena, root, task, operands=(), **arguments):
    """Serialize immutable raw syntax and operation arguments, with no answers."""
    return dict(format='leanputer.kernel-operation.v1', task=Task(task).name,
        levels=[[int(r.tag), r.a, r.b] for r in arena.levels[1:]],
        vectors=[list(v) for v in arena.vectors[1:]],
        rows=[[int(r.tag), r.a, r.b, r.c] for r in arena.rows[1:]],
        root=root, operands=list(operands), **arguments)


def parse_document(doc):
    """Syntax-only reconstruction. No scope/type/positivity/reduction calls."""
    if doc.get('format') != 'leanputer.kernel-operation.v1':
        raise ValueError('expected kernel-operation document')
    limits = Limits(expressions=max(1, len(doc['rows'])), levels=max(1, len(doc['levels'])),
        vector_cells=max(1, sum(1+len(v) for v in doc['vectors'])))
    a = Arena(limits)
    for i, row in enumerate(doc['levels'], 1):
        if a.level(*row) != i:
            raise KernelError('noncanonical level table')
    for i, vector in enumerate(doc['vectors'], 1):
        if a.vec(vector) != i:
            raise KernelError('noncanonical vector table')
    for i, row in enumerate(doc['rows'], 1):
        if a.mk(*row) != i:
            raise KernelError('noncanonical expression table')
    a.expr(doc['root'])
    task = Task[doc['task']]
    if task in (Task.INSTANTIATE_ONE, Task.ABSTRACT_ONE, Task.FOLD_TELESCOPE, Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.EXPR_LEVEL_SUBSTITUTE, Task.LEVEL_EQUAL, Task.LEVEL_NOT_ZERO, Task.LEVEL_OFFSET, Task.LEVEL_MAX, Task.LEVEL_IMAX, Task.LEVEL_INSTANTIATE, Task.EXPR_LEVEL_INSTANTIATE, Task.LEVEL_ORDER, Task.LEVEL_NORMALIZE, Task.LEVEL_MERGE, Task.LEVEL_NORMAL_SUCC, Task.LEVEL_EQUIVALENT, Task.LEVEL_GEQ, Task.LEVEL_GEQ_CORE, Task.EXPR_SCOPE, Task.EXPR_EQUAL, Task.VECTOR_EQUAL, Task.INFER, Task.CONVERT_POSITIVE, Task.ENV_LOOKUP, Task.LOAD_PARAMETERS, Task.CHECK_NAME, Task.CHECK_SOURCE, Task.CONSUME_PARAMETERS, Task.PREPARE_REUSE, Task.HAS_CONSTANTS, Task.ANALYZE_HEADERS, Task.HAS_FAMILIES, Task.FAMILY_APPLICATION, Task.FORMAL_LEVELS, Task.CHECK_POSITIVITY, Task.ABSTRACT_SCOPE, Task.RECURSIVE_ARGUMENT, Task.REVERSE_LIST, Task.CHECK_CONSTRUCTORS, Task.GET_NAME_PATH, Task.CHECK_RECURSOR_NAME, Task.CHECK_CORE_NAMES, Task.DECLARE_CONSTRUCTORS, Task.INIT_ELIMINATION, Task.FRESH_LOCAL, Task.APPLY_SCOPE, Task.BUILD_MOTIVES, Task.BLOCK_FLAGS, Task.INSTANTIATE_SCOPE, Task.SNAPSHOT_SCOPE, Task.OPEN_RECURSIVE_PREFIX, Task.APPLY_LIST, Task.FIND_MOTIVE, Task.BUILD_MINORS, Task.BUILD_RECURSOR_TYPES, Task.RESTORE_SCOPE, Task.BUILD_RECURSOR_RULES, Task.ASSEMBLE_RECURSORS, Task.INSTANTIATE_SCHEME, Task.SIGNATURE_VECTOR_LOOKUP, Task.SYMBOL_MEMBER, Task.CHECK_RECURSOR_CLAIMS, Task.APPLICATION_SPINE, Task.APPLY_VECTOR_SLICE, Task.APPLY_RECURSOR_RULE, Task.VECTOR_REFERENCE, Task.PREPARE_RECURSOR_MAJOR, Task.REDUCE_RECURSOR, Task.GATHER_RECURSOR_ARGUMENTS, Task.PRIOR_BLOCK_LOOKUP, Task.COMPARE_NAME_PATH, Task.INTERN_NAME_PATH, Task.VECTOR_SPLICE, Task.WORD_DECIMAL, Task.REPLACE_NAME_PREFIX, Task.MAKE_RECURSOR_NAME, Task.OPEN_RAW_PREFIX, Task.HAS_LOOSE_BVARS, Task.LOOSE_BVAR_WALK, Task.HAS_RAW_FAMILIES, Task.IS_NESTED_APPLICATION, Task.INSTANTIATE_PI_PARAMETERS, Task.NESTED_STAGE, Task.REWRITE_NESTED, Task.REPLACE_NESTED, Task.RESTORE_NESTED_EXPR, Task.RESTORE_NESTED_CALLBACK, Task.RESTORE_NESTED_BLOCK, Task.FAMILY_INFO, Task.PROJECTION_INFER, Task.PROJECTION_REDUCE, Task.PROJECTION_BRIDGE, Task.CONVERT, Task.LEVELS_EQUIVALENT, Task.STRUCTURE_INFO,Task.QUOT_INITIALIZE,Task.QUOT_REDUCE,Task.NAT_BINDINGS,Task.NAT_LITERAL):
        raise KernelError('internal service has no raw-data entry point')
    operands = tuple(a.word(v) for v in doc.get('operands', ()))
    if task == Task.INSTANTIATE:
        for value in operands:
            a.expr(value)
    elif task == Task.ABSTRACT and any(not v for v in operands):
        raise KernelError('zero local identity')
    if task in (Task.OPEN_TELESCOPE, Task.ROUNDTRIP_TELESCOPE, Task.VARIABLE_SCOPE) and operands:
        raise KernelError('closed variable-scope/telescope entry has no outer locals')
    limit = doc.get('limit')
    if limit is not None:
        a.word(limit)
    binder_tags = {'pi': Tag.PI, 'lam': Tag.LAM}
    open_kind = doc.get('open_binder', 'pi')
    fold_kind = doc.get('fold_binder', open_kind)
    if open_kind not in binder_tags or fold_kind not in binder_tags:
        raise KernelError('telescope binder kind must be pi or lam')
    request = dict(arena=a, root=doc['root'], task=task, operands=operands,
        delta=a.word(doc.get('amount', 0)), cutoff=a.word(doc.get('cutoff', 0)),
        start=a.word(doc.get('start', 0)), limit=limit,
        open_tag=int(binder_tags[open_kind]), fold_tag=int(binder_tags[fold_kind]))
    return request, None, ()


def prepare(config, request, _unused=None, _declarations=()):
    a, operands = request['arena'], request['operands']
    if len(a.rows) > config.heap or len(operands) > config.context:
        raise ResourceError('input arena/vector capacity')
    words = [v for row in a.rows[1:] for v in (int(row.tag), row.a, row.b, row.c)]
    words += list(operands)+[request[n] for n in ('delta', 'cutoff', 'start')]
    if request['limit'] is not None:
        words.append(request['limit'])
    if any(v >= 1 << config.word_bits for v in words):
        raise ResourceError('input word width')
    state = {'regs': dict.fromkeys(REGISTERS, 0)}
    for bank, fields in BANK_FIELDS.items():
        state[bank] = [[0]*fields for _ in range(getattr(config, bank))]
    state['heap'][1:len(a.rows)] = [[int(r.tag), r.a, r.b, r.c] for r in a.rows[1:]]
    state['context'][:len(operands)] = [[v] for v in operands]
    state['regs'].update(fuel=config.fuel, free=len(a.rows), x=request['root'],
        root=request['root'], task=int(request['task']), count=len(operands), ctx=len(operands),
        **{n: request[n] for n in ('delta', 'cutoff', 'start', 'open_tag', 'fold_tag')})
    if request['task'] == Task.BETA_ZETA:
        state['regs']['mode'] = int(Mode.BETA_ZETA)
    if request['task'] in (Task.OPEN_TELESCOPE, Task.ROUNDTRIP_TELESCOPE):
        state['regs'].update(task=int(Task.VARIABLE_SCOPE), pending_open=1,
            bounded=int(request['limit'] is not None), limit=request['limit'] or 0,
            pending_fold=int(request['task'] == Task.ROUNDTRIP_TELESCOPE))
    return state


def boot_length(bank, state):
    return state['regs']['free'] if bank == 'heap' else state['regs']['count'] if bank == 'context' else 0


class SpecMachine:
    def __init__(self, config, state):
        self.cfg, self.state = config, deepcopy(state)

    def step(self):
        s, cfg = self.state, self.cfg
        r = s['regs']
        if r['status']:
            return s
        def stop(status, reason=Reason.NONE):
            r.update(status=int(status), reason=int(reason))
        if r['fuel'] == 0:
            stop(Outcome.RESOURCE, Reason.FUEL)
            return s
        r['fuel'] -= 1
        def ret(ref):
            r.update(mode=Mode.RETURN, r=ref)
        def alloc(row):
            if r['free'] >= cfg.heap:
                stop(Outcome.RESOURCE, Reason.HEAP)
                return
            ref = r['free']
            s['heap'][ref] = list(row)
            r['free'] += 1
            ret(ref)
        def bounded(value):
            if value >= 1 << cfg.word_bits:
                stop(Outcome.RESOURCE, Reason.INDEX)
                return False
            return True
        if (not 0 < r['free'] <= cfg.heap or r['sp'] > cfg.stack or r['count'] > cfg.context or r['ctx'] > cfg.context
                or r['mode'] > Mode.MINOR_LINK or r['task'] > Task.NAT_LITERAL
                or r['bounded'] > 1 or r['pending_open'] > 1 or r['pending_fold'] > 1
                or r['typing_active'] > 1 or r['core_operation'] > 1 or r['occurrence_internal'] > 1 or r['occurrence_found'] > 1 or r['pending_reuse'] > 1 or r['reuse_whnf'] > 1 or r['pending_scope'] > 1 or r['env_ready'] > 1 or r['pending_infer'] > 1 or r['local_base'] > cfg.context
                or r['vec_changed'] > 1 or r['pending_compare'] > 2 or r['order_same_base'] > 1
                or r['open_tag'] not in (Tag.PI, Tag.LAM) or r['fold_tag'] not in (Tag.PI, Tag.LAM)):
            stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        uses_arguments = r['task'] in (Task.INSTANTIATE, Task.ABSTRACT, Task.OCCURS, Task.HAS_CONSTANTS, Task.FORMAL_LEVELS, Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.EXPR_LEVEL_SUBSTITUTE, Task.LEVEL_INSTANTIATE, Task.EXPR_LEVEL_INSTANTIATE, Task.EXPR_SCOPE)
        if uses_arguments and r['arg_base']+r['count'] > cfg.context:
            stop(Outcome.RESOURCE, Reason.CONTEXT)
            return s
        from . import level_normalize_machine as normalization
        from . import level_geq_machine as geq
        from . import expression_equal_machine as expression_equal
        from . import inference_machine as inference
        from . import environment_machine as environment
        from . import constant_machine as constant
        from . import parameter_machine as parameters
        from . import name_machine as names
        from . import source_machine as source
        from . import telescope_machine as telescope
        from . import occurrence_machine as occurrence
        from . import header_machine as header
        from . import family_occurrence_machine as family_occurrence
        from . import formal_levels_machine as formal_levels
        from . import family_application_machine as family_application
        from . import positivity_machine as positivity
        from . import abstract_scope_machine as abstract_scope
        from . import reverse_list_machine as reverse_list
        from . import recursive_argument_machine as recursive_argument
        from . import constructor_machine as constructor
        from . import recursor_name_machine as recursor_name
        from . import core_names_machine as core_names
        from . import declare_constructors_machine as declare_constructors
        from . import elimination_machine as elimination
        from . import binder_ops_machine as binder_ops
        from . import motive_machine as motive
        from . import block_flags_machine as block_flags
        from . import open_prefix_machine as open_prefix
        from . import generation_ops_machine as generation_ops
        from . import minor_machine as minor
        from . import recursor_type_machine as recursor_type
        from . import restore_scope_machine as restore_scope
        from . import recursor_rule_machine as recursor_rule
        from . import assemble_recursors_machine as assemble_recursors
        from . import claim_lookup_machine as claim_lookup
        from . import recursor_claim_machine as recursor_claim
        from . import application_ops_machine as application_ops
        from . import recursor_apply_machine as recursor_apply
        from . import major_machine as major
        from . import recursor_reduce_machine as recursor_reduce
        from . import prior_block_machine as prior_block
        from . import name_path_machine as name_path
        from . import name_intern_machine as name_intern
        from . import vector_splice_machine as vector_splice
        from . import decimal_machine as decimal
        from . import name_prefix_machine as name_prefix
        from . import make_rec_name_machine as make_rec_name
        from . import raw_prefix_machine as raw_prefix
        from . import nested_application_machine as nested_application
        from . import pi_parameters_machine as pi_parameters
        from . import nested_stage_rules, nested_copy_rules, nested_rewrite_rules, nested_restore_rules, nested_transaction_rules, projection_rules, conversion_rules, structure_info_rules, quotient_rules, quotient_reduce_rules, nat_literal_rules
        if r['mode'] == Mode.RETURN:
            if not r['sp']:
                if r['pending_reuse']:
                    r.update(mode=Mode.WALK, task=Task.PREPARE_REUSE, x=r['root'], pending_reuse=0)
                elif r['pending_open']:
                    r.update(mode=Mode.TELESCOPE, x=r['root'], task=Task.OPEN_TELESCOPE, depth=0, pending_open=0)
                elif r['pending_fold']:
                    r.update(mode=Mode.FOLD_SELECT, x=r['r'], fold_body=r['r'],
                        task=Task.FOLD_TELESCOPE, pending_fold=0, fold_base=0)
                elif r['pending_scope']:
                    r.update(mode=Mode.WALK, task=Task.EXPR_SCOPE, x=r['root'], depth=0, pending_scope=0)
                elif r['pending_infer']:
                    r.update(mode=Mode.WALK, task=Task.INFER, x=r['root'], local_base=r['ctx'], pending_infer=0)
                elif r['pending_compare']:
                    r.update(mode=Mode.WALK, x=r['r'], peer=r['comparison_root'],
                             task=Task.LEVEL_EQUAL if r['pending_compare'] == 1 else Task.EXPR_EQUAL, pending_compare=0)
                else:
                    stop(Outcome.DONE)
            else:
                phase, original, depth, task, first, second = s['stack'][r['sp']-1]
                if task in (Task.NESTED_STAGE,Task.REPLACE_NESTED,Task.REWRITE_NESTED,Task.RESTORE_NESTED_EXPR,Task.RESTORE_NESTED_CALLBACK,Task.RESTORE_NESTED_BLOCK,Task.FAMILY_INFO,Task.PROJECTION_INFER,Task.PROJECTION_REDUCE,Task.PROJECTION_BRIDGE,Task.CONVERT,Task.LEVELS_EQUIVALENT,Task.STRUCTURE_INFO,Task.QUOT_INITIALIZE,Task.QUOT_REDUCE,Task.NAT_BINDINGS,Task.NAT_LITERAL):
                    {Task.NESTED_STAGE:nested_stage_rules,Task.REPLACE_NESTED:nested_copy_rules,Task.REWRITE_NESTED:nested_rewrite_rules,Task.RESTORE_NESTED_EXPR:nested_restore_rules,Task.RESTORE_NESTED_CALLBACK:nested_restore_rules,Task.RESTORE_NESTED_BLOCK:nested_transaction_rules,Task.FAMILY_INFO:projection_rules,Task.PROJECTION_INFER:projection_rules,Task.PROJECTION_REDUCE:projection_rules,Task.PROJECTION_BRIDGE:projection_rules,Task.CONVERT:conversion_rules,Task.LEVELS_EQUIVALENT:conversion_rules,Task.STRUCTURE_INFO:structure_info_rules,Task.QUOT_INITIALIZE:quotient_rules,Task.QUOT_REDUCE:quotient_reduce_rules,Task.NAT_BINDINGS:nat_literal_rules,Task.NAT_LITERAL:nat_literal_rules}[task].step(self)
                elif task == Task.INSTANTIATE_PI_PARAMETERS:
                    pi_parameters.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task == Task.IS_NESTED_APPLICATION:
                    nested_application.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task == Task.OPEN_RAW_PREFIX:
                    raw_prefix.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task == Task.MAKE_RECURSOR_NAME:
                    make_rec_name.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task == Task.REPLACE_NAME_PREFIX:
                    name_prefix.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task == Task.VECTOR_SPLICE:
                    vector_splice.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task == Task.INTERN_NAME_PATH:
                    name_intern.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task == Task.COMPARE_NAME_PATH:
                    name_path.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task == Task.PRIOR_BLOCK_LOOKUP:
                    prior_block.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task in (Task.REDUCE_RECURSOR,Task.GATHER_RECURSOR_ARGUMENTS):
                    recursor_reduce.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif task == Task.PREPARE_RECURSOR_MAJOR:
                    major.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in recursor_apply.PRIVATE_PHASES:
                    recursor_apply.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in recursor_claim.PRIVATE_PHASES:
                    recursor_claim.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in assemble_recursors.PRIVATE_PHASES:
                    assemble_recursors.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in recursor_rule.PRIVATE_PHASES:
                    recursor_rule.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in recursor_type.PRIVATE_PHASES:
                    recursor_type.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in minor.PRIVATE_PHASES:
                    minor.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in open_prefix.PRIVATE_PHASES:
                    open_prefix.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in block_flags.PRIVATE_PHASES:
                    block_flags.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in motive.PRIVATE_PHASES:
                    motive.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in elimination.PRIVATE_PHASES:
                    elimination.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in declare_constructors.PRIVATE_PHASES:
                    declare_constructors.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in core_names.PRIVATE_PHASES:
                    core_names.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in recursor_name.PRIVATE_PHASES:
                    recursor_name.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in constructor.PRIVATE_PHASES:
                    constructor.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in recursive_argument.PRIVATE_PHASES:
                    recursive_argument.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in abstract_scope.PRIVATE_PHASES:
                    abstract_scope.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in positivity.PRIVATE_PHASES:
                    positivity.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in family_application.PRIVATE_PHASES:
                    family_application.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in family_occurrence.PRIVATE_PHASES:
                    family_occurrence.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in header.PRIVATE_PHASES:
                    header.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in occurrence.PRIVATE_PHASES:
                    occurrence.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in telescope.PRIVATE_PHASES:
                    telescope.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in source.PRIVATE_PHASES or (task == Task.CHECK_SOURCE and phase in (0,14,15)):
                    source.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in constant.PRIVATE_PHASES:
                    constant.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in inference.PRIVATE_PHASES:
                    inference.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in expression_equal.PRIVATE_PHASES:
                    expression_equal.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in geq.PRIVATE_PHASES:
                    geq.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase in normalization.PRIVATE_PHASES:
                    normalization.resume(self, (phase, original, depth, task, first, second), stop, ret, alloc)
                elif phase == CALL_BETA_ZETA:
                    r.update(sp=r['sp']-1, mode=Mode.BETA_ZETA, x=r['r'], depth=0, task=Task.BETA_ZETA)
                elif phase == CALL_TELESCOPE:
                    r.update(sp=r['sp']-1, mode=Mode.TELESCOPE, x=r['r'], depth=0, task=Task.OPEN_TELESCOPE)
                elif phase == CALL_FOLD:
                    r.update(sp=r['sp']-1, mode=Mode.FOLD_BUILD, x=r['r'], task=Task.FOLD_TELESCOPE)
                elif phase == CALL_SORT_LEVEL:
                    r.update(sp=r['sp']-1, mode=Mode.SORT_RESULT, x=original, depth=depth, task=task)
                elif phase == CALL_CONST_LEVEL:
                    r.update(sp=r['sp']-1, mode=Mode.CONST_RESULT, x=original, depth=depth, task=task)
                elif phase == CALL_ORDER_LEFT_OFFSET:
                    s['stack'][r['sp']-1] = [CALL_ORDER_RIGHT_OFFSET, r['r'], 0, Task.LEVEL_ORDER, r['level_offset'], 0]
                    r.update(mode=Mode.WALK, task=Task.LEVEL_OFFSET, x=original, level_offset=0)
                elif phase == CALL_ORDER_RIGHT_OFFSET:
                    s['stack'][r['sp']-1] = [CALL_ORDER_BASE_COMPARE, original, r['r'], Task.LEVEL_ORDER, first, r['level_offset']]
                    r.update(mode=Mode.WALK, task=Task.LEVEL_EQUAL, x=original, peer=r['r'])
                elif phase == CALL_ORDER_BASE_COMPARE:
                    r['sp'] -= 1
                    if r['r']:
                        r['order_same_base'] = 1
                        ret(0 if first == second else 1 if first < second else 2)
                    else:
                        r.update(mode=Mode.ORDER_READ_LEFT, task=Task.LEVEL_ORDER, x=original, peer=depth)
                elif phase == CALL_ORDER_FIRST:
                    if r['r']:
                        r.update(sp=r['sp']-1, order_same_base=0)
                        ret(r['r'])
                    else:
                        s['stack'][r['sp']-1] = [CALL_ORDER_SECOND, 0, 0, Task.LEVEL_ORDER, 0, 0]
                        r.update(mode=Mode.WALK, task=Task.LEVEL_ORDER, x=original, peer=depth)
                elif phase == CALL_ORDER_SECOND:
                    r.update(sp=r['sp']-1, order_same_base=0)
                    ret(r['r'])
                elif phase == CALL_MAX_COMPARE:
                    r.update(sp=r['sp']-1, mode=Mode.MAX_EQUAL_RESULT, x=r['constructor_left'] if first == 3 else r['constructor_right'],
                             task=Task.LEVEL_MAX, constructor_stage=first)
                elif phase == CALL_MAX_LEFT_OFFSET:
                    s['stack'][r['sp']-1] = [CALL_MAX_RIGHT_OFFSET, 0, 0, Task.LEVEL_MAX, 0, 0]
                    r.update(left_base=r['r'], left_offset=r['level_offset'], level_offset=0,
                             task=Task.LEVEL_OFFSET, mode=Mode.WALK, x=r['constructor_right'])
                elif phase == CALL_MAX_RIGHT_OFFSET:
                    s['stack'][r['sp']-1] = [CALL_MAX_COMPARE, 0, 0, Task.LEVEL_MAX, 5, 0]
                    r.update(right_offset=r['level_offset'], peer=r['r'], x=r['left_base'],
                             task=Task.LEVEL_EQUAL, mode=Mode.WALK)
                elif phase == CALL_IMAX_NONZERO:
                    r['sp'] -= 1
                    if r['r']:
                        r.update(mode=Mode.WALK, x=r['constructor_left'], peer=r['constructor_right'], task=Task.LEVEL_MAX)
                    else:
                        r.update(mode=Mode.IMAX_RIGHT, x=r['constructor_right'], task=Task.LEVEL_IMAX)
                elif phase == CALL_IMAX_COMPARE:
                    r['sp'] -= 1
                    if r['r']: ret(r['constructor_left'])
                    else: alloc((CellTag.LEVEL_IMAX, r['constructor_left'], r['constructor_right'], 0))
                elif phase == LEVEL_EQUAL_SECOND:
                    r['sp'] -= 1
                    if not r['r']: ret(0)
                    else: r.update(mode=Mode.WALK, x=original, peer=depth, task=Task.LEVEL_EQUAL)
                elif phase == LEVEL_OR_SECOND:
                    r['sp'] -= 1
                    if r['r']: ret(1)
                    else: r.update(mode=Mode.WALK, x=original, task=Task.LEVEL_NOT_ZERO)
                elif phase == PENDING_ARGUMENT:
                    r.update(mode=Mode.RESUME, x=original, depth=depth, task=task)
                else:
                    r.update(mode=Mode.RESUME, x=original, depth=depth, task=task)
            return s
        if r['task'] in (Task.NESTED_STAGE,Task.REPLACE_NESTED,Task.REWRITE_NESTED,Task.RESTORE_NESTED_EXPR,Task.RESTORE_NESTED_CALLBACK,Task.RESTORE_NESTED_BLOCK,Task.FAMILY_INFO,Task.PROJECTION_INFER,Task.PROJECTION_REDUCE,Task.PROJECTION_BRIDGE,Task.CONVERT,Task.LEVELS_EQUIVALENT,Task.STRUCTURE_INFO,Task.QUOT_INITIALIZE,Task.QUOT_REDUCE,Task.NAT_BINDINGS,Task.NAT_LITERAL):
            {Task.NESTED_STAGE:nested_stage_rules,Task.REPLACE_NESTED:nested_copy_rules,Task.REWRITE_NESTED:nested_rewrite_rules,Task.RESTORE_NESTED_EXPR:nested_restore_rules,Task.RESTORE_NESTED_CALLBACK:nested_restore_rules,Task.RESTORE_NESTED_BLOCK:nested_transaction_rules,Task.FAMILY_INFO:projection_rules,Task.PROJECTION_INFER:projection_rules,Task.PROJECTION_REDUCE:projection_rules,Task.PROJECTION_BRIDGE:projection_rules,Task.CONVERT:conversion_rules,Task.LEVELS_EQUIVALENT:conversion_rules,Task.STRUCTURE_INFO:structure_info_rules,Task.QUOT_INITIALIZE:quotient_rules,Task.QUOT_REDUCE:quotient_reduce_rules,Task.NAT_BINDINGS:nat_literal_rules,Task.NAT_LITERAL:nat_literal_rules}[r['task']].step(self)
            return s
        if r['task'] == Task.CHECK_SOURCE and r['mode'] != Mode.SOURCE_TYPE_SORT:
            source.step(self, 0, 0, 0, 0, stop, ret, alloc)
            return s
        if r['task'] == Task.ENV_LOOKUP and r['mode'] == Mode.WALK:
            environment.step(self, 0, 0, 0, 0, stop, ret, alloc)
            return s
        if formal_levels.step(self, 0, 0, 0, 0, stop, ret, alloc): return s
        if r['task']==Task.IS_NESTED_APPLICATION and r['mode'] in nested_application.NO_NODE:
            nested_application.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.OPEN_RAW_PREFIX and r['mode']==Mode.WALK:
            raw_prefix.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.MAKE_RECURSOR_NAME:
            make_rec_name.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.REPLACE_NAME_PREFIX and r['mode']==Mode.WALK:
            name_prefix.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.WORD_DECIMAL:
            decimal.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.VECTOR_SPLICE and r['mode'] in vector_splice.NO_NODE:
            vector_splice.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.INTERN_NAME_PATH and r['mode'] in name_intern.NO_NODE:
            name_intern.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.PRIOR_BLOCK_LOOKUP and r['mode']==Mode.WALK:
            prior_block.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.GATHER_RECURSOR_ARGUMENTS and r['mode'] in recursor_reduce.NO_NODE:
            recursor_reduce.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.PREPARE_RECURSOR_MAJOR and r['mode'] in major.NO_NODE:
            major.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.APPLICATION_SPINE and r['mode'] in application_ops.NO_NODE:
            application_ops.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.SYMBOL_MEMBER and not r['x']:
            claim_lookup.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.CHECK_RECURSOR_CLAIMS and r['mode'] in recursor_claim.NO_NODE:
            recursor_claim.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.ASSEMBLE_RECURSORS and r['mode'] in assemble_recursors.NO_NODE:
            assemble_recursors.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.BUILD_RECURSOR_RULES and r['mode'] in recursor_rule.NO_NODE:
            recursor_rule.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.BUILD_RECURSOR_TYPES and r['mode'] in recursor_type.NO_NODE:
            recursor_type.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.BUILD_MINORS and r['mode'] in minor.NO_NODE:
            minor.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.OPEN_RECURSIVE_PREFIX and r['mode'] in open_prefix.NO_NODE:
            open_prefix.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.SNAPSHOT_SCOPE:
            binder_ops.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if (r['task']==Task.FRESH_LOCAL and r['mode']==Mode.FRESH_LOCAL_RECORD) or (r['task']==Task.APPLY_SCOPE and r['mode']==Mode.APPLY_SCOPE_SELECT):
            binder_ops.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.BLOCK_FLAGS and r['mode'] in block_flags.NO_NODE:
            block_flags.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task']==Task.BUILD_MOTIVES and r['mode'] in motive.NO_NODE:
            motive.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task'] == Task.INIT_ELIMINATION and r['mode'] in elimination.NO_NODE:
            elimination.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task'] == Task.DECLARE_CONSTRUCTORS and r['mode'] in (Mode.WALK,Mode.DECL_CTOR_STORE_INFO,Mode.DECL_CTOR_STORE_SCHEME,Mode.DECL_CTOR_STORE_SIGNATURE,Mode.DECL_CTOR_LINK,Mode.DECL_CTOR_ORDER):
            declare_constructors.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task'] == Task.CHECK_CORE_NAMES and r['mode'] in (Mode.WALK, Mode.CORE_NAME_STORE):
            core_names.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task'] == Task.CHECK_RECURSOR_NAME and r['mode'] == Mode.WALK:
            recursor_name.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task'] == Task.CHECK_CONSTRUCTORS and r['mode'] in (Mode.WALK, Mode.CTOR_STORE_META, Mode.CTOR_STORE_PENDING, Mode.CTOR_LINK):
            constructor.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task'] == Task.REVERSE_LIST and r['mode'] != Mode.REVERSE_LIST:
            reverse_list.step(self, 0, 0, 0, 0, stop, ret, alloc); return s
        if r['task'] == Task.ANALYZE_HEADERS and r['mode'] in (Mode.HEADER_STORE_FAMILY, Mode.HEADER_STORE_SCHEME, Mode.HEADER_STORE_SIGNATURE, Mode.HEADER_LINK):
            header.step(self, 0, 0, 0, 0, stop, ret, alloc)
            return s
        if not 0 < r['x'] < r['free']:
            stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        tag, a, b, c = s['heap'][r['x']]
        level_scope = r['task'] == Task.LEVEL_SCOPE
        level_task = r['task'] in (Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.LEVEL_EQUAL, Task.LEVEL_NOT_ZERO, Task.LEVEL_OFFSET, Task.LEVEL_MAX, Task.LEVEL_IMAX, Task.LEVEL_INSTANTIATE, Task.LEVEL_ORDER, Task.LEVEL_NORMALIZE, Task.LEVEL_MERGE, Task.LEVEL_NORMAL_SUCC, Task.LEVEL_EQUIVALENT, Task.LEVEL_GEQ, Task.LEVEL_GEQ_CORE)
        header_tag = (CellTag.RAW_BLOCK if r['mode'] == Mode.WALK else CellTag.VECTOR if r['mode'] == Mode.HEADER_VECTOR else
            CellTag.VECTOR_CELL if r['mode'] == Mode.HEADER_CELL else CellTag.RAW_FAMILY if r['mode'] == Mode.HEADER_FAMILY else None)
        ctor_tag = {Mode.CTOR_FAMILY_CELL:CellTag.VECTOR_CELL,Mode.CTOR_FAMILY_SIGNATURE:CellTag.CHECKED_SIGNATURE,
            Mode.CTOR_FAMILY_SCHEME:CellTag.CHECKED_SCHEME,Mode.CTOR_FAMILY_METADATA:CellTag.CHECKED_FAMILY,
            Mode.CTOR_RAW_FAMILY:CellTag.RAW_FAMILY,Mode.CTOR_FAMILY_AUX:CellTag.RAW_FAMILY_AUX,Mode.CTOR_VECTOR:CellTag.VECTOR,
            Mode.CTOR_CELL:CellTag.VECTOR_CELL,Mode.CTOR_RECORD:CellTag.RAW_CONSTRUCTOR,Mode.CTOR_FIELD_RECORD:CellTag.LOCAL_DECL}.get(r['mode'])
        recname_tag = (CellTag.VECTOR if r['mode'] in (Mode.RECNAME_LEFT_HEADER,Mode.RECNAME_RIGHT_HEADER,Mode.RECNAME_SUFFIX_HEADER) else
            CellTag.VECTOR_CELL if r['mode'] in (Mode.RECNAME_LEFT_CELL,Mode.RECNAME_RIGHT_CELL,Mode.RECNAME_SUFFIX_CELL,Mode.RECNAME_SUFFIX_BYTE) else None)
        recname_part = r['mode'] in (Mode.RECNAME_LEFT_PART,Mode.RECNAME_RIGHT_PART,Mode.RECNAME_SUFFIX_PART)
        core_name_tag = {Mode.CORE_NAME_CELL:CellTag.VECTOR_CELL,Mode.CORE_NAME_SIGNATURE:CellTag.CHECKED_SIGNATURE,
            Mode.CORE_NAME_SCHEME:CellTag.CHECKED_SCHEME,Mode.CORE_NAME_METADATA:CellTag.CHECKED_FAMILY,
            Mode.CORE_NAME_RAW_FAMILY:CellTag.RAW_FAMILY,Mode.CORE_NAME_AUX:CellTag.RAW_FAMILY_AUX}.get(r['mode'])
        decl_ctor_tag = {Mode.DECL_CTOR_NAME:CellTag.VALIDATED_RECURSOR_NAME,Mode.DECL_CTOR_FAMILY_SIGNATURE:CellTag.CHECKED_SIGNATURE,
            Mode.DECL_CTOR_FAMILY_SCHEME:CellTag.CHECKED_SCHEME,Mode.DECL_CTOR_FAMILY_METADATA:CellTag.CHECKED_FAMILY,
            Mode.DECL_CTOR_RAW_FAMILY:CellTag.RAW_FAMILY,Mode.DECL_CTOR_AUX:CellTag.RAW_FAMILY_AUX,Mode.DECL_CTOR_VECTOR:CellTag.VECTOR,
            Mode.DECL_CTOR_CELL:CellTag.VECTOR_CELL,Mode.DECL_CTOR_RAW:CellTag.RAW_CONSTRUCTOR,Mode.DECL_CTOR_PENDING:CellTag.PENDING_CONSTRUCTOR,
            Mode.DECL_CTOR_ANALYSIS:CellTag.CONSTRUCTOR_ANALYSIS}.get(r['mode'])
        elimination_tag = (CellTag.LEVEL_ZERO <= tag <= CellTag.LEVEL_PARAM if r['mode'] in elimination.LEVEL_MODES else Tag.BVAR <= tag <= Tag.MDATA if r['mode']==Mode.ELIM_FIELD_SORT else tag == elimination.TAGS.get(r['mode']))
        motive_tag = (Tag.BVAR <= tag <= Tag.MDATA if r['mode']==Mode.MOTIVE_SORT else tag==motive.TAGS.get(r['mode']))
        flags_tag = (Tag.BVAR <= tag <= Tag.MDATA if r['mode']==Mode.FLAGS_DOMAIN else tag==block_flags.TAGS.get(r['mode']))
        generation_tag = (tag==CellTag.VECTOR if r['mode']==Mode.WALK else tag==CellTag.VECTOR_CELL if r['mode']==Mode.MOTIVE_FIND_CELL else tag==CellTag.MOTIVE_INFO if r['mode']==Mode.MOTIVE_FIND_INFO else tag==CellTag.LOCAL_DECL)
        restore_tag = (tag==CellTag.VECTOR if r['mode']==Mode.WALK else tag==CellTag.VECTOR_CELL if r['mode']==Mode.RESTORE_SCOPE_CELL else tag in (CellTag.LOCAL_DECL,CellTag.CONSTRUCTOR_FIELD) if r['mode']==Mode.RESTORE_SCOPE_ITEM else tag==CellTag.LOCAL_DECL if r['mode']==Mode.RESTORE_SCOPE_RECORD else False)
        claim_tag = (Tag.BVAR <= tag <= Tag.MDATA if r['mode']==Mode.CLAIM_SORT else tag==recursor_claim.TAGS.get(r['mode']))
        sigv_tag = (tag==CellTag.VECTOR if r['mode']==Mode.WALK else tag==CellTag.VECTOR_CELL if r['mode']==Mode.SIGV_CELL else tag==CellTag.CHECKED_SIGNATURE if r['mode']==Mode.SIGV_SIGNATURE else False)
        application_tag = (Tag.BVAR <= tag <= Tag.MDATA if r['task']==Task.APPLICATION_SPINE or r['mode']==Mode.SLICE_ARGUMENT else tag==CellTag.VECTOR if r['mode']==Mode.WALK else tag==CellTag.VECTOR_CELL if r['mode']==Mode.SLICE_CELL else False)
        iota_tag = (Tag.BVAR <= tag <= Tag.MDATA if r['mode'] in (Mode.IOTA_REC_HEAD,Mode.IOTA_MAJOR_HEAD) else tag==recursor_apply.TAGS.get(r['mode']))
        reference_tag = (tag==CellTag.VECTOR if r['mode']==Mode.WALK else tag==CellTag.VECTOR_CELL if r['mode']==Mode.SLICE_CELL else False)
        major_tag = (Tag.BVAR <= tag <= Tag.MDATA if r['mode'] in major.EXPRESSION_MODES else CellTag.LEVEL_ZERO <= tag <= CellTag.LEVEL_PARAM if r['mode']==Mode.MAJOR_SORT_LEVEL else tag==major.TAGS.get(r['mode']))
        reduce_tag = (Tag.BVAR <= tag <= Tag.MDATA if r['mode'] in (Mode.WALK,Mode.REDUCE_HEAD) else tag==recursor_reduce.REDUCE_TAGS.get(r['mode']))
        gather_tag = tag==recursor_reduce.GATHER_TAGS.get(r['mode'])
        prior_block_tag = tag==CellTag.VECTOR_CELL if r['mode']==Mode.PRIOR_BLOCK_CELL else tag==CellTag.BLOCK_ORIGIN if r['mode']==Mode.PRIOR_BLOCK_ORIGIN else False
        name_path_tag = (tag==CellTag.VECTOR if r['mode'] in (Mode.WALK,Mode.PATH_RIGHT_HEADER) else tag==CellTag.VECTOR_CELL if r['mode'] in (Mode.PATH_LEFT_CELL,Mode.PATH_RIGHT_CELL) else tag in (CellTag.NAME_STRING,CellTag.NAME_NUMERAL) if r['mode'] in (Mode.PATH_LEFT_PART,Mode.PATH_RIGHT_PART) else False)
        intern_tag = (tag==CellTag.VECTOR if r['mode'] in (Mode.WALK,Mode.INTERN_ROOT) else tag==CellTag.VECTOR_CELL if r['mode']==Mode.INTERN_CELL else tag==CellTag.SYMBOL_ENTRY if r['mode']==Mode.INTERN_ENTRY else False)
        splice_tag = (tag==CellTag.VECTOR if r['mode'] in (Mode.WALK,Mode.SPLICE_SUFFIX,Mode.SPLICE_REVERSED) else tag==CellTag.VECTOR_CELL if r['mode'] in (Mode.SPLICE_SKIP,Mode.SPLICE_COPY) else False)
        prefix_tag = tag==CellTag.VECTOR if r['mode']==Mode.REPLACE_PREFIX_HEADER else False
        raw_prefix_tag = (Tag.BVAR <= tag <= Tag.MDATA) if r['mode']==Mode.RAW_PREFIX_LOOP else False
        raw_family_tag = (tag==CellTag.VECTOR if r['mode']==Mode.RAW_FAMILY_VECTOR else tag==CellTag.VECTOR_CELL if r['mode']==Mode.FAMILY_SET_CELL else tag==CellTag.RAW_FAMILY if r['mode']==Mode.FAMILY_SET_SIGNATURE else Tag.BVAR <= tag <= Tag.MDATA if r['mode']==Mode.WALK else False)
        nested_app_tag = (Tag.BVAR <= tag <= Tag.MDATA if r['mode'] in (Mode.WALK,Mode.NESTED_APP_HEAD) else tag==nested_application.TAGS.get(r['mode']))
        pi_parameters_tag = (Tag.BVAR <= tag <= Tag.MDATA if r['mode'] in (Mode.WALK,Mode.PI_PARAMS_ARGUMENT,Mode.PI_PARAMS_STRIP) else tag==CellTag.VECTOR if r['mode']==Mode.PI_PARAMS_HEADER else tag==CellTag.VECTOR_CELL if r['mode']==Mode.PI_PARAMS_CELL else False)
        valid_tag = (pi_parameters_tag if r['task']==Task.INSTANTIATE_PI_PARAMETERS else nested_app_tag if r['task']==Task.IS_NESTED_APPLICATION else raw_family_tag if r['task']==Task.HAS_RAW_FAMILIES else raw_prefix_tag if r['task']==Task.OPEN_RAW_PREFIX else prefix_tag if r['task']==Task.REPLACE_NAME_PREFIX else splice_tag if r['task']==Task.VECTOR_SPLICE else intern_tag if r['task']==Task.INTERN_NAME_PATH else name_path_tag if r['task']==Task.COMPARE_NAME_PATH else prior_block_tag if r['task']==Task.PRIOR_BLOCK_LOOKUP else reduce_tag if r['task']==Task.REDUCE_RECURSOR else gather_tag if r['task']==Task.GATHER_RECURSOR_ARGUMENTS else major_tag if r['task']==Task.PREPARE_RECURSOR_MAJOR else reference_tag if r['task']==Task.VECTOR_REFERENCE else iota_tag if r['task']==Task.APPLY_RECURSOR_RULE else application_tag if r['task'] in (Task.APPLICATION_SPINE,Task.APPLY_VECTOR_SLICE) else claim_tag if r['task']==Task.CHECK_RECURSOR_CLAIMS else sigv_tag if r['task']==Task.SIGNATURE_VECTOR_LOOKUP else tag==CellTag.VECTOR_CELL if r['task']==Task.SYMBOL_MEMBER else tag==assemble_recursors.TAGS.get(r['mode']) if r['task']==Task.ASSEMBLE_RECURSORS else tag==recursor_rule.TAGS.get(r['mode']) if r['task']==Task.BUILD_RECURSOR_RULES else restore_tag if r['task']==Task.RESTORE_SCOPE else tag==recursor_type.TAGS.get(r['mode']) if r['task']==Task.BUILD_RECURSOR_TYPES else tag==minor.TAGS.get(r['mode']) if r['task']==Task.BUILD_MINORS else generation_tag if r['task']==Task.FIND_MOTIVE else tag==CellTag.VECTOR_CELL if r['task']==Task.APPLY_LIST and r['mode']==Mode.LIST_CELL else tag==open_prefix.TAGS.get(r['mode']) if r['task']==Task.OPEN_RECURSIVE_PREFIX else flags_tag if r['task']==Task.BLOCK_FLAGS else motive_tag if r['task']==Task.BUILD_MOTIVES else tag == CellTag.LOCAL_DECL if r['task']==Task.APPLY_SCOPE and r['mode']==Mode.APPLY_SCOPE_RECORD else elimination_tag if r['task'] == Task.INIT_ELIMINATION else tag == decl_ctor_tag if r['task'] == Task.DECLARE_CONSTRUCTORS else tag == core_name_tag if r['task'] == Task.CHECK_CORE_NAMES else (tag in (CellTag.NAME_STRING,CellTag.NAME_NUMERAL) if recname_part else tag == recname_tag) if r['task'] == Task.CHECK_RECURSOR_NAME else tag == ctor_tag if r['task'] == Task.CHECK_CONSTRUCTORS and ctor_tag is not None else tag == header_tag if r['task'] == Task.ANALYZE_HEADERS and header_tag is not None else names.valid_tag(r['mode'], tag) if r['task'] in (Task.CHECK_NAME,Task.GET_NAME_PATH) else
            tag == (CellTag.VECTOR if r['mode'] == Mode.WALK else CellTag.VECTOR_CELL) if r['task'] == Task.LOAD_PARAMETERS else
            tag == CellTag.CHECKED_FAMILY if r['mode'] == Mode.APP_METADATA else
            tag == CellTag.CHECKED_SCHEME if r['mode'] in (Mode.CONST_SCHEME, Mode.APP_SCHEME) else
            tag == CellTag.VECTOR if r['mode'] in (Mode.CONST_PARAMETER_HEADER, Mode.CONST_LEVEL_HEADER) else
            tag == CellTag.VECTOR_CELL if r['mode'] in (Mode.CONST_PARAMETER_CELL, Mode.CONST_LEVEL_CELL) else
            tag in (CellTag.CHECKED_SIGNATURE,CellTag.PENDING_CONSTRUCTOR) if r['mode'] == Mode.ENV_SIGNATURE else
            tag == CellTag.CHECKED_SIGNATURE if r['mode'] in ( Mode.CONST_SIGNATURE, Mode.FAMILY_SET_SIGNATURE, Mode.APP_SIGNATURE) else
            tag == CellTag.VECTOR_CELL if r['mode'] in (Mode.ENV_CELL, Mode.FAMILY_SET_CELL, Mode.APP_ARGUMENT, Mode.RECURSIVE_SKIP, Mode.RECURSIVE_INDEX, Mode.REVERSE_LIST) else
            tag == (CellTag.VECTOR_CELL if r['mode'] in (Mode.VECTOR_CELL_LEFT, Mode.VECTOR_CELL_RIGHT) else CellTag.VECTOR) if r['task'] == Task.VECTOR_EQUAL else
            tag == CellTag.VECTOR_CELL if r['mode'] == Mode.MERGE_FOLD else
            tag == LOCAL_DECL_TAG if r['mode'] in (Mode.FOLD_RECORD, Mode.INFER_LOCAL_RECORD, Mode.REUSE_RECORD, Mode.REUSE_SUBST_RECORD, Mode.APP_PARAMETER_RECORD, Mode.ABSTRACT_SCOPE_RECORD) else
            tag == CellTag.LEVEL_BINDING if r['mode'] == Mode.LEVEL_BINDING else
            tag == CellTag.VECTOR if r['mode'] == Mode.CONST_VECTOR else
            tag == CellTag.VECTOR_CELL if r['mode'] in (Mode.CONST_CELL, Mode.CONST_RESULT) else
            CellTag.LEVEL_ZERO <= tag <= CellTag.LEVEL_PARAM if level_task else Tag.BVAR <= tag <= Tag.MDATA)
        if not valid_tag:
            stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        task, depth = r['task'], r['depth']
        if binder_ops.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if pi_parameters.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if nested_application.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if raw_prefix.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if name_prefix.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if vector_splice.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if name_intern.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if name_path.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if prior_block.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if recursor_reduce.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if major.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if recursor_apply.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if application_ops.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if recursor_claim.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if claim_lookup.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if assemble_recursors.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if recursor_rule.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if restore_scope.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if recursor_type.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if minor.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if generation_ops.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if open_prefix.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if block_flags.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if motive.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if elimination.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if declare_constructors.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if core_names.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if recursor_name.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if constructor.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if recursive_argument.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if reverse_list.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if abstract_scope.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if positivity.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if family_application.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if family_occurrence.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if header.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if occurrence.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if telescope.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if source.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if names.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if parameters.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if constant.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if environment.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if inference.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if expression_equal.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if geq.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if normalization.step(self, tag, a, b, c, stop, ret, alloc):
            return s
        if r['task'] == Task.LEVEL_ORDER:
            if r['mode'] == Mode.WALK:
                if not 0 < r['peer'] < r['free']: stop(Outcome.INVALID, Reason.SYNTAX)
                elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [CALL_ORDER_LEFT_OFFSET, r['peer'], 0, Task.LEVEL_ORDER, 0, 0]
                    r.update(sp=r['sp']+1, mode=Mode.WALK, task=Task.LEVEL_OFFSET, level_offset=0)
            elif r['mode'] == Mode.ORDER_READ_LEFT:
                r.update(mode=Mode.ORDER_READ_RIGHT, left_tag=tag, left_a=a, left_b=b, x=r['peer'])
            elif r['mode'] == Mode.ORDER_READ_RIGHT:
                if tag != r['left_tag']:
                    r['order_same_base'] = 0
                    ret(1 if r['left_tag'] < tag else 2)
                elif tag == CellTag.LEVEL_PARAM:
                    r['order_same_base'] = 0
                    ret(0 if r['left_a'] == a else 1 if r['left_a'] < a else 2)
                elif tag not in (CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX):
                    stop(Outcome.INVALID, Reason.SYNTAX) # Equal bases handled before this mode.
                elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [CALL_ORDER_FIRST, r['left_b'], b, Task.LEVEL_ORDER, 0, 0]
                    r.update(sp=r['sp']+1, mode=Mode.WALK, x=r['left_a'], peer=a)
            else: stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        def call_level(phase, task, left, right=0, stage=0):
            if r['sp'] >= cfg.stack:
                stop(Outcome.RESOURCE, Reason.STACK)
            else:
                s['stack'][r['sp']] = [phase, 0, 0, Task.LEVEL_MAX, stage, 0]
                r.update(sp=r['sp']+1, mode=Mode.WALK, task=task, x=left, peer=right)
        def max_offset():
            call_level(CALL_MAX_LEFT_OFFSET, Task.LEVEL_OFFSET, r['constructor_left'])
            # The counter belongs to this service invocation, not caller data.
            if not r['status']: r['level_offset'] = 0
        if r['task'] in (Task.LEVEL_MAX, Task.LEVEL_IMAX):
            left, right = r['constructor_left'], r['constructor_right']
            if r['mode'] == Mode.WALK:
                if not 0 < r['peer'] < r['free']: stop(Outcome.INVALID, Reason.SYNTAX)
                else:
                    r.update(constructor_left=r['x'], constructor_right=r['peer'])
                    if r['task'] == Task.LEVEL_MAX: r['mode'] = Mode.MAX_LEFT
                    else: call_level(CALL_IMAX_NONZERO, Task.LEVEL_NOT_ZERO, r['peer'])
            elif r['mode'] == Mode.MAX_LEFT:
                if tag == CellTag.LEVEL_ZERO: ret(right)
                else: r.update(mode=Mode.MAX_RIGHT, x=right)
            elif r['mode'] == Mode.MAX_RIGHT:
                if tag == CellTag.LEVEL_ZERO: ret(left)
                else: call_level(CALL_MAX_COMPARE, Task.LEVEL_EQUAL, left, right)
            elif r['mode'] == Mode.MAX_RIGHT_CHILDREN:
                if tag == CellTag.LEVEL_MAX: call_level(CALL_MAX_COMPARE, Task.LEVEL_EQUAL, left, a, stage=1)
                else: r.update(mode=Mode.MAX_LEFT_CHILDREN, x=left)
            elif r['mode'] == Mode.MAX_LEFT_CHILDREN:
                if tag == CellTag.LEVEL_MAX: call_level(CALL_MAX_COMPARE, Task.LEVEL_EQUAL, right, a, stage=3)
                else: max_offset()
            elif r['mode'] == Mode.MAX_EQUAL_RESULT:
                stage, equal = r['constructor_stage'], bool(r['r'])
                if stage == 0:
                    if equal: ret(left)
                    else: r.update(mode=Mode.MAX_RIGHT_CHILDREN, x=right)
                elif stage in (1, 2):
                    if equal: ret(right)
                    elif stage == 1: call_level(CALL_MAX_COMPARE, Task.LEVEL_EQUAL, left, b, stage=2)
                    else: r.update(mode=Mode.MAX_LEFT_CHILDREN, x=left)
                elif stage in (3, 4):
                    if equal: ret(left)
                    elif stage == 3:
                        # MAX comparison return selects the corresponding raw
                        # node, so the current b is the LEFT Max RHS here.
                        call_level(CALL_MAX_COMPARE, Task.LEVEL_EQUAL, right, b, stage=4)
                    else: max_offset()
                elif stage == 5:
                    if equal: ret(left if r['left_offset'] >= r['right_offset'] else right)
                    else: alloc((CellTag.LEVEL_MAX, left, right, 0))
                else: stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['mode'] == Mode.IMAX_RIGHT:
                if tag == CellTag.LEVEL_ZERO: ret(right)
                else: r.update(mode=Mode.IMAX_LEFT, x=left)
            elif r['mode'] == Mode.IMAX_LEFT:
                if tag == CellTag.LEVEL_ZERO: ret(right)
                elif tag == CellTag.LEVEL_SUCC: r.update(mode=Mode.IMAX_ONE, x=a)
                else: call_level(CALL_IMAX_COMPARE, Task.LEVEL_EQUAL, left, right)
            elif r['mode'] == Mode.IMAX_ONE:
                if tag == CellTag.LEVEL_ZERO: ret(right)
                else: call_level(CALL_IMAX_COMPARE, Task.LEVEL_EQUAL, left, right)
            else: stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        # Reusable source-level predicates consume data DAGs, not names/shapes.
        if r['task'] == Task.LEVEL_EQUAL:
            if r['mode'] == Mode.WALK:
                if not 0 < r['peer'] < r['free']:
                    stop(Outcome.INVALID, Reason.SYNTAX)
                elif r['x'] == r['peer']:
                    ret(1)
                else:
                    r.update(mode=Mode.LEVEL_EQUAL_RIGHT, left_tag=tag, left_a=a, left_b=b, x=r['peer'])
            elif r['mode'] == Mode.LEVEL_EQUAL_RIGHT:
                if tag != r['left_tag']: ret(0)
                elif tag == CellTag.LEVEL_ZERO: ret(1)
                elif tag == CellTag.LEVEL_PARAM: ret(int(a == r['left_a']))
                elif tag == CellTag.LEVEL_SUCC:
                    r.update(mode=Mode.WALK, x=r['left_a'], peer=a)
                elif r['sp'] >= cfg.stack:
                    stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [LEVEL_EQUAL_SECOND, r['left_b'], b, Task.LEVEL_EQUAL, 0, 0]
                    r.update(sp=r['sp']+1, mode=Mode.WALK, x=r['left_a'], peer=a)
            else:
                stop(Outcome.INVALID, Reason.SYNTAX)
            return s
        if r['task'] == Task.LEVEL_NOT_ZERO:
            if tag in (CellTag.LEVEL_ZERO, CellTag.LEVEL_PARAM): ret(0)
            elif tag == CellTag.LEVEL_SUCC: ret(1)
            elif tag == CellTag.LEVEL_IMAX: r.update(mode=Mode.WALK, x=b)
            elif r['sp'] >= cfg.stack: stop(Outcome.RESOURCE, Reason.STACK)
            else:
                s['stack'][r['sp']] = [LEVEL_OR_SECOND, b, 0, Task.LEVEL_NOT_ZERO, 0, 0]
                r.update(sp=r['sp']+1, mode=Mode.WALK, x=a)
            return s
        if r['task'] == Task.LEVEL_OFFSET:
            if tag != CellTag.LEVEL_SUCC: ret(r['x'])
            elif bounded(r['level_offset']+1):
                r.update(mode=Mode.WALK, x=a, level_offset=r['level_offset']+1)
            return s
        if r['mode'] == Mode.SORT_RESULT:
            if tag != Tag.SORT:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif a == r['r']:
                ret(r['x'])
            else:
                alloc((Tag.SORT, r['r'], 0, 0))
            return s
        if r['mode'] == Mode.CONST_VECTOR:
            if c != VectorKind.LEVELS or bool(a) != bool(b):
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif not a:
                ret(r['const_original'])
            else:
                r.update(vec_length=a, vec_left=a, vec_build=a, vec_head=0, vec_changed=0,
                    mode=Mode.CONST_CELL, x=b)
            return s
        if r['mode'] == Mode.CONST_CELL:
            if not r['vec_left'] or bool(b) != (r['vec_left'] > 1):
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['sp'] >= cfg.stack:
                stop(Outcome.RESOURCE, Reason.STACK)
            else:
                s['stack'][r['sp']] = [CALL_CONST_LEVEL, r['x'], r['expr_depth'], task, 0, 0]
                r.update(sp=r['sp']+1, mode=Mode.WALK, x=a, depth=0,
                         task=Task.LEVEL_SCOPE if task == Task.EXPR_SCOPE else Task.LEVEL_INSTANTIATE if task == Task.EXPR_LEVEL_INSTANTIATE else Task.LEVEL_SUBSTITUTE)
            return s
        if r['mode'] == Mode.CONST_RESULT:
            changed = bool(r['vec_changed'] or a != r['r'])
            more = r['vec_left'] > 1
            if not r['vec_left']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif more or changed:
                if r['sp'] >= cfg.stack:
                    stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [VECTOR_VALUE, r['r'], 0, task, 0, 0]
                    r.update(sp=r['sp']+1, vec_left=r['vec_left']-1, vec_changed=int(changed),
                        mode=Mode.CONST_CELL if more else Mode.CONST_BUILD,
                        x=b if more else r['const_original'])
            else:
                r['sp'] -= r['vec_length']-1
                ret(r['const_original'])
            return s
        if r['mode'] == Mode.CONST_BUILD:
            if r['vec_build'] and (not r['sp'] or s['stack'][r['sp']-1][0] != VECTOR_VALUE):
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['free'] >= cfg.heap:
                stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                ref = r['free']
                if r['vec_build']:
                    value = s['stack'][r['sp']-1][1]
                    s['heap'][ref] = [CellTag.VECTOR_CELL, value, r['vec_head'], 0]
                    r.update(free=ref+1, vec_head=ref, vec_build=r['vec_build']-1, sp=r['sp']-1)
                else:
                    s['heap'][ref] = [CellTag.VECTOR, r['vec_length'], r['vec_head'], VectorKind.LEVELS]
                    r.update(free=ref+1, vector_result=ref, mode=Mode.CONST_FINISH)
            return s
        if r['mode'] == Mode.CONST_FINISH:
            if tag != Tag.CONST:
                stop(Outcome.INVALID, Reason.SYNTAX)
            else:
                alloc((Tag.CONST, a, r['vector_result'], 0))
            return s
        if r['mode'] == Mode.LEVEL_SELECT:
            if r['task']==Task.LEVEL_INSTANTIATE and r['level_map_head']:
                r.update(mode=Mode.LEVEL_BINDING,x=r['level_map_head'],level_map_result=r['lookup_level'])
            else:r.update(mode=Mode.LEVEL_BINDING, x=s['context'][r['arg_base']+r['i']][0])
            return s
        if r['mode'] == Mode.LEVEL_BINDING:
            heap_map=r['task']==Task.LEVEL_INSTANTIATE and bool(r['level_map_head'])
            more=r['i']+1<r['count']
            if not 0 < b < r['free'] or (heap_map and bool(c)!=more):
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif heap_map:
                # Nodes were prepended by the zip. The LAST matching node is
                # the FIRST original parameter, preserving instantiate_lparams
                # even for pure-operation arguments with repeated symbols.
                selected=b if a==r['parameter'] else r['level_map_result']
                r['level_map_result']=selected
                if more:r.update(x=c,i=r['i']+1)
                else:ret(selected)
            elif a == r['parameter']:
                ret(b)  # Simultaneous substitution: do NOT traverse replacement.
            elif more:
                r.update(mode=Mode.LEVEL_SELECT, x=r['lookup_level'], i=r['i']+1)
            else:
                ret(r['lookup_level'])
            return s
        if r['mode'] == Mode.FOLD_SELECT:
            if r['ctx'] < r['fold_base']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['ctx'] == r['fold_base']:
                ret(r['fold_body'])
            else:
                r.update(mode=Mode.FOLD_RECORD, x=s['context'][r['ctx']-1][0])
            return s
        if r['mode'] == Mode.FOLD_RECORD:
            if not 0 < a < r['free'] or not 0 < b < r['free']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            else:
                r.update(mode=Mode.FOLD_LOCAL, x=a, domain=b, binder_info=c)
            return s
        if r['mode'] == Mode.FOLD_LOCAL:
            if tag != Tag.LOCAL:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['sp'] >= cfg.stack:
                stop(Outcome.RESOURCE, Reason.STACK)
            else:
                s['stack'][r['sp']] = [CALL_FOLD, 0, 0, Task.FOLD_TELESCOPE, 0, 0]
                r.update(sp=r['sp']+1, mode=Mode.WALK, x=r['fold_body'], depth=0,
                    task=Task.ABSTRACT_ONE, abstract_uid=a)
            return s
        if r['mode'] == Mode.FOLD_BUILD:
            if r['ctx'] <= r['fold_base']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif r['free'] >= cfg.heap:
                stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                binder = r['free']
                s['heap'][binder] = [r['fold_tag'], r['domain'], r['r'], r['binder_info']]
                r.update(free=binder+1, fold_body=binder, ctx=r['ctx']-1,
                    mode=Mode.FOLD_SELECT, x=binder)
            return s
        if r['mode'] == Mode.TELESCOPE_READY:
            if r['bounded'] and r['ctx'] == r['limit']:
                ret(r['x'])
            elif tag != r['open_tag']:
                if r['bounded']: stop(Outcome.INVALID, Reason.EXPECT_PI if r['open_tag'] == Tag.PI else Reason.EXPECT_LAM)
                else: ret(r['x'])
            elif r['ctx'] >= cfg.context:
                stop(Outcome.RESOURCE, Reason.CONTEXT)
            elif r['sp'] >= cfg.stack:
                stop(Outcome.RESOURCE, Reason.STACK)
            elif r['free']+1 >= cfg.heap:
                stop(Outcome.RESOURCE, Reason.HEAP)
            else:
                local = r['free']
                s['heap'][local] = [Tag.LOCAL, local, 0, 0]
                r.update(free=local+1, r=local, mode=Mode.BINDER_RECORD)
            return s
        if r['mode'] == Mode.BINDER_RECORD:
            # The Local is already allocated. Its UID is its immutable arena
            # address, hence fresh relative to every earlier generated Local.
            record = r['free']
            s['heap'][record] = [LOCAL_DECL_TAG, r['r'], a, c]
            s['context'][r['ctx']] = [record]
            s['stack'][r['sp']] = [CALL_TELESCOPE, 0, 0, Task.OPEN_TELESCOPE, 0, 0]
            r.update(free=record+1, ctx=r['ctx']+1, sp=r['sp']+1,
                mode=Mode.WALK, x=b, depth=0, task=Task.INSTANTIATE_ONE, substitution=r['r'])
            return s
        if r['mode'] == Mode.BETA_ZETA:
            if tag == Tag.PROJ:
                projection_rules.step(self); return s
            if tag == Tag.MDATA:
                r['x'] = a
            elif tag == Tag.APP:
                if r['sp'] == cfg.stack:
                    stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [PENDING_ARGUMENT, r['x'], 0, Task.BETA_ZETA, b, 0]
                    r.update(sp=r['sp']+1, x=a)
            elif tag == Tag.LAM and r['sp'] and s['stack'][r['sp']-1][0] == PENDING_ARGUMENT:
                argument = s['stack'][r['sp']-1][4]
                s['stack'][r['sp']-1] = [CALL_BETA_ZETA, 0, 0, Task.BETA_ZETA, 0, 0]
                r.update(mode=Mode.WALK, x=b, substitution=argument, depth=0, task=Task.INSTANTIATE_ONE)
            elif tag == Tag.LET:
                if r['sp'] == cfg.stack:
                    stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [CALL_BETA_ZETA, 0, 0, Task.BETA_ZETA, 0, 0]
                    r.update(sp=r['sp']+1, mode=Mode.WALK, x=c, substitution=b, depth=0, task=Task.INSTANTIATE_ONE)
            else:
                ret(r['x'])
            return s
        if r['mode'] == Mode.FIND:
            if r['i'] >= r['count']:
                stop(Outcome.INVALID, Reason.SYNTAX)
            elif s['context'][r['arg_base']+r['i']][0] == a:
                if task == Task.OCCURS:
                    if r['occurrence_internal']:
                        r.update(occurrence_found=1,sp=r['occurrence_mark']+1,mode=Mode.RETURN,r=1)
                    else:r.update(found=1, sp=0, r=r['root']); stop(Outcome.DONE)
                elif level_scope:
                    ret(r['x'])
                else:
                    value = depth+r['count']-1-r['i']
                    if bounded(value):
                        alloc((Tag.BVAR, value, 0, 0))
            elif not r['i']:
                if level_scope: stop(Outcome.INVALID, Reason.UNIVERSE)
                else: ret(r['x'])
            else:
                r['i'] -= 1
            return s
        # Children have exactly the increments in arena.children, but no host
        # walk or supplied traversal schedule drives the actual transition.
        child_list = (((a, b) if tag == CellTag.LEVEL_MAX or tag == CellTag.LEVEL_IMAX and task != Task.LEVEL_NORMAL_SUCC else
                       (a,) if tag == CellTag.LEVEL_SUCC and task != Task.LEVEL_NORMAL_SUCC else ()) if level_task else
                      (a, b, c) if tag == Tag.LET else (a, b) if tag in (Tag.APP, Tag.PI, Tag.LAM)
                      else (c,) if tag == Tag.PROJ else (a,) if tag == Tag.MDATA else ())
        if r['mode'] == Mode.WALK and task in (Task.EXPR_LEVEL_SUBSTITUTE, Task.EXPR_LEVEL_INSTANTIATE, Task.EXPR_SCOPE):
            if not r['count'] and task != Task.EXPR_SCOPE:
                ret(r['x'])
                return s
            if tag == Tag.SORT:
                if r['sp'] >= cfg.stack:
                    stop(Outcome.RESOURCE, Reason.STACK)
                else:
                    s['stack'][r['sp']] = [CALL_SORT_LEVEL, r['x'], depth, task, 0, 0]
                    r.update(sp=r['sp']+1, mode=Mode.WALK, x=a, depth=0,
                         task=Task.LEVEL_SCOPE if task == Task.EXPR_SCOPE else Task.LEVEL_INSTANTIATE if task == Task.EXPR_LEVEL_INSTANTIATE else Task.LEVEL_SUBSTITUTE)
                return s
            if tag == Tag.CONST:
                r.update(const_original=r['x'], expr_depth=depth, mode=Mode.CONST_VECTOR, x=b)
                return s
        if r['mode'] == Mode.RESUME:
            if not r['sp']:
                stop(Outcome.INVALID, Reason.SYNTAX)
                return s
            frame = s['stack'][r['sp']-1]
            phase, original, old_depth, old_task, first, second = frame
            if phase == PENDING_ARGUMENT:
                if tag != Tag.APP:
                    stop(Outcome.INVALID, Reason.SYNTAX)
                else:
                    r['sp'] -= 1
                    if a == r['r']: ret(original)
                    else: alloc((Tag.APP, r['r'], first, 0))
                return s
            if not 1 <= phase <= len(child_list):
                stop(Outcome.INVALID, Reason.SYNTAX)
                return s
            if phase < len(child_list):
                increment = int(tag in (Tag.PI, Tag.LAM) and phase == 1 or tag == Tag.LET and phase == 2)
                if bounded(depth+increment):
                    frame[0] += 1
                    frame[3+phase] = r['r']
                    r.update(mode=Mode.WALK, x=child_list[phase], depth=depth+increment)
            else:
                refs = [first, second][:phase-1]+[r['r']]
                r['sp'] -= 1
                if task == Task.LEVEL_NORMALIZE:
                    normalization.finish(self, tag, refs)
                elif tuple(refs) == child_list:
                    ret(original)
                elif task == Task.LEVEL_INSTANTIATE and tag in (CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX):
                    r.update(mode=Mode.WALK, x=refs[0], peer=refs[1],
                             task=Task.LEVEL_MAX if tag == CellTag.LEVEL_MAX else Task.LEVEL_IMAX)
                elif tag in (Tag.APP, Tag.PI, Tag.LAM, CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX):
                    alloc((tag, refs[0], refs[1], c))
                elif tag == Tag.LET:
                    alloc((tag, *refs))
                elif tag == Tag.PROJ:
                    alloc((tag, a, b, refs[0]))
                else:
                    alloc((tag, refs[0], b, 0))
            return s
        if child_list:
            if r['sp'] == cfg.stack:
                stop(Outcome.RESOURCE, Reason.STACK)
            else:
                s['stack'][r['sp']] = [1, r['x'], depth, task, 0, 0]
                r.update(sp=r['sp']+1, mode=Mode.WALK, x=child_list[0])
        elif task == Task.LEVEL_NORMAL_SUCC:
            alloc((CellTag.LEVEL_SUCC, r['x'], 0, 0))
        elif task == Task.ABSTRACT_ONE and tag == Tag.LOCAL and a == r['abstract_uid']:
            alloc((Tag.BVAR, depth, 0, 0))
        elif level_scope and tag == CellTag.LEVEL_PARAM:
            if not r['count']: stop(Outcome.INVALID, Reason.UNIVERSE)
            else: r.update(mode=Mode.FIND, i=r['count']-1)
        elif task in (Task.LEVEL_SUBSTITUTE, Task.LEVEL_INSTANTIATE) and tag == CellTag.LEVEL_PARAM:
            if not r['count']: ret(r['x'])
            else: r.update(mode=Mode.LEVEL_SELECT, i=0, parameter=a, lookup_level=r['x'])
        elif task in (Task.VARIABLE_SCOPE, Task.EXPR_SCOPE) and (tag == Tag.LOCAL or tag == Tag.BVAR and a >= depth):
            stop(Outcome.INVALID, Reason.SCOPE)
        elif task == Task.LOOSE_BVAR_WALK and tag == Tag.BVAR and a >= depth:
            r.update(occurrence_found=1, sp=r['occurrence_mark']+1, mode=Mode.RETURN, r=1)
        elif tag == Tag.BVAR and task in (Task.LIFT, Task.INSTANTIATE, Task.INSTANTIATE_ONE):
            start = 0 if task == Task.INSTANTIATE_ONE else r['cutoff'] if task == Task.LIFT else r['start']
            count = 1 if task == Task.INSTANTIATE_ONE else r['count']
            offset = depth+start
            if not bounded(offset):
                return s
            if a < offset:
                ret(r['x'])
            elif task == Task.LIFT:
                value = a+r['delta']
                if bounded(value):
                    if value == a: ret(r['x'])
                    else: alloc((Tag.BVAR, value, 0, 0))
            elif a-offset >= count:
                if not count: ret(r['x'])
                else: alloc((Tag.BVAR, a-count, 0, 0))
            else:
                value = r['substitution'] if task == Task.INSTANTIATE_ONE else s['context'][r['arg_base']+a-offset][0]
                if not 0 < value < r['free']:
                    stop(Outcome.INVALID, Reason.SYNTAX)
                elif not depth:
                    ret(value)
                else:
                    r.update(x=value, depth=0, task=Task.LIFT, delta=depth, cutoff=0)
        elif ((tag == Tag.LOCAL and task == Task.ABSTRACT)
              or (tag == Tag.CONST and task == Task.OCCURS)) and r['count']:
            r.update(mode=Mode.FIND, i=r['count']-1)
        else:
            ret(r['x'])
        return s


def assumptions(_):
    return []


program_name = 'kernel.general-telescope-services.v4'
constant_fields = 6
first_banks = (('heap', 1), ('stack', 1), ('constants', 1))
second_banks = ('context',)
primitive_basis = ()
