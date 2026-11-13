"""Lower the shared all-tag traversal controller to Boolean semantic IR.

Stock Qwen3.5/GatedDeltaNet emission is provided by native_machine. This module
has no runtime dependency on the Python kernel operations/reference machine.
"""
from ..bitvec import Builder
from . import level_constructor_rules, level_order_rules, level_normalize_rules, level_geq_rules, expression_equal_rules, inference_rules, environment_rules, constant_rules, parameter_rules, name_rules, source_rules, telescope_rules, occurrence_rules, header_rules, family_occurrence_rules, formal_levels_rules, family_application_rules, positivity_rules, abstract_scope_rules, reverse_list_rules, recursive_argument_rules, constructor_rules, recursor_name_rules, core_names_rules, declare_constructors_rules, elimination_rules, binder_ops_rules, motive_rules, block_flags_rules, open_prefix_rules, generation_ops_rules, minor_rules, recursor_type_rules, restore_scope_rules, recursor_rule_rules, assemble_recursors_rules, claim_lookup_rules, recursor_claim_rules, application_ops_rules, recursor_apply_rules, major_rules, recursor_reduce_rules, prior_block_rules
from .recursor_claim_rules import NO_NODE as CLAIM_NO_NODE, TAGS as CLAIM_TAGS
from .assemble_recursors_rules import NO_NODE as ASM_NO_NODE, TAGS as ASM_TAGS
from .recursor_rule_rules import NO_NODE as RULE_NO_NODE, TAGS as RULE_TAGS
from .recursor_type_rules import NO_NODE as REC_TYPE_NO_NODE, TAGS as REC_TYPE_TAGS
from .minor_rules import NO_NODE as MINOR_NO_NODE, TAGS as MINOR_TAGS
from .open_prefix_rules import NO_NODE as PREFIX_NO_NODE, TAGS as PREFIX_TAGS
from .block_flags_rules import NO_NODE as FLAGS_NO_NODE, TAGS as FLAGS_TAGS
from .motive_rules import NO_NODE as MOTIVE_NO_NODE, TAGS as MOTIVE_TAGS
from .elimination_rules import NO_NODE as ELIMINATION_NO_NODE, TAGS as ELIMINATION_TAGS, LEVEL_MODES as ELIMINATION_LEVEL_MODES
from .arena import Tag
from .native_cells import CellTag, VectorKind
from .traversal_machine import (MachineConfig, Mode, Outcome, Reason, Task,
    CALL_BETA_ZETA, PENDING_ARGUMENT, CALL_TELESCOPE, CALL_FOLD, CALL_SORT_LEVEL, CALL_CONST_LEVEL, CALL_NORMAL_IMAX, VECTOR_VALUE, LEVEL_EQUAL_SECOND, LEVEL_OR_SECOND, LOCAL_DECL_TAG,
    StateLayout, RegisterLayout, assumptions, boot_length, parse_document, prepare,
    program_name, constant_fields, first_banks, second_banks, primitive_basis)


PORTS = (('node', ('tag', 'a', 'b', 'c')),
         ('frame', ('phase', 'original', 'depth', 'task', 'first', 'second')),
         ('declaration', ('kind', 'symbol', 'parameters', 'type', 'value', 'extra')),
         ('operand', ('value',)))


def port_names(width, ports=PORTS):
    return [f'read/{p}/{f}/{i}' for p, fs in ports for f in fs for i in range(width)]


def state_words(g, layout):
    return {n: tuple(g.inputs[layout.slices[n]]) for n, _ in layout.fields}


def compile_addresses(layout, optimized=True, target=None):
    cfg, width = layout.config, layout.config.word_bits
    g = Builder(layout.names, optimized)
    r = state_words(g, layout)
    minus = g.sub(r['sp'], g.const(1, width))[0]
    first = g.compile(list(r['x'][:cfg.heap.bit_length()-1])+list(minus[:cfg.stack.bit_length()-1])+list(r['raw_index'][:cfg.constants.bit_length()-1]), target)
    g = Builder(layout.names+port_names(width, PORTS[:3]), optimized)
    r = state_words(g, layout)
    a = tuple(g.inputs[len(layout.names)+width:len(layout.names)+2*width])
    base = g.add(r['depth'], r['start'])
    relative = g.sub(a, base)[0]
    selecting = g.OR(g.eq(r['mode'], g.const(Mode.FIND, width)), g.eq(r['mode'], g.const(Mode.LEVEL_SELECT, width)), g.eq(r['mode'], g.const(Mode.PARAMETER_DUPLICATE, width)))
    index = g.add(r['arg_base'], g.mux(selecting, r['i'], relative))
    index = g.mux(g.eq(r['mode'], g.const(Mode.FOLD_SELECT, width)),
        g.sub(r['ctx'], g.const(1, width))[0], index)
    index = g.mux(g.eq(r['mode'], g.const(Mode.INFER_LOCAL_SELECT, width)), r['lookup_index'], index)
    reusing = g.OR(g.eq(r['mode'], g.const(Mode.REUSE_SELECT, width)),g.eq(r['mode'], g.const(Mode.REUSE_SUBST_SELECT, width)))
    index = g.mux(reusing, r['reuse_index'], index)
    index = g.mux(g.eq(r['mode'], g.const(Mode.CTOR_FIELD_SELECT, width)), g.sub(r['ctx'],g.const(1,width))[0], index)
    index = g.mux(g.eq(r['mode'], g.const(Mode.ABSTRACT_SCOPE_SELECT, width)), r['scope_cursor'], index)
    index = g.mux(g.eq(r['mode'], g.const(Mode.APP_PARAMETER_SELECT, width)), r['app_context_index'], index)
    index = g.mux(g.eq(r['mode'], g.const(Mode.FORMAL_SELECT, width)), g.add(r['arg_base'], r['formal_i']), index)
    index = g.mux(g.eq(r['mode'], g.const(Mode.ELIM_FRESH, width)), r['elim_cursor'], index)
    index = g.mux(g.eq(r['mode'], g.const(Mode.ELIM_SHIFT, width)), g.sub(r['elim_cursor'],g.const(1,width))[0], index)
    index = g.mux(g.eq(r['mode'], g.const(Mode.APPLY_SCOPE_SELECT, width)), r['apply_cursor'], index)
    index = g.mux(g.eq(r['mode'], g.const(Mode.SNAPSHOT_SCOPE, width)), r['scope_cursor'], index)
    second = g.compile(list(index[:cfg.context.bit_length()-1]), target)
    return first, second


class RuleCompiler:
    def __init__(self, layout, optimized=True, factor_choices=True):
        self.layout, self.cfg = layout, layout.config
        self.width = self.cfg.word_bits
        self.g = Builder(layout.names+port_names(self.width), optimized)
        self.r = state_words(self.g, layout)
        self.choices = {n: [] for n, _ in layout.fields}
        self.writes = {bank: [] for bank in ('heap', 'stack', 'context')}
        self.factor = factor_choices
        self.read = {}
        offset = len(layout.names)
        for port, fields in PORTS:
            self.read[port] = {}
            for field in fields:
                self.read[port][field] = tuple(self.g.inputs[offset:offset+self.width])
                offset += self.width
        self.active = self.AND(self.eq(self.r['status'], Outcome.RUNNING), self.NOT(self.eq(self.r['fuel'], 0)))
        self.stop(self.AND(self.eq(self.r['status'], Outcome.RUNNING), self.eq(self.r['fuel'], 0)), Outcome.RESOURCE, Reason.FUEL)
        self.emit(self.active, fuel=self.g.sub(self.r['fuel'], self.g.const(1, len(self.r['fuel'])))[0])
        invalid = self.OR(self.eq(self.r['free'], 0), self.lt(self.cfg.heap, self.r['free']),
            self.lt(self.cfg.stack, self.r['sp']), self.lt(self.cfg.context, self.r['count']), self.lt(self.cfg.context, self.r['ctx']),
            self.lt(Mode.MINOR_LINK, self.r['mode']), self.lt(Task.PRIOR_BLOCK_LOOKUP, self.r['task']),
            self.lt(1, self.r['bounded']), self.lt(1, self.r['pending_open']), self.lt(1, self.r['pending_fold']),
            self.lt(1, self.r['typing_active']), self.lt(1, self.r['core_operation']), self.lt(1, self.r['occurrence_internal']), self.lt(1, self.r['occurrence_found']), self.lt(1, self.r['pending_reuse']), self.lt(1, self.r['reuse_whnf']), self.lt(1, self.r['pending_scope']), self.lt(1, self.r['env_ready']), self.lt(1, self.r['pending_infer']), self.lt(self.cfg.context, self.r['local_base']),
            self.lt(1, self.r['vec_changed']), self.lt(2, self.r['pending_compare']), self.lt(1, self.r['order_same_base']),
            self.NOT(self.OR(self.eq(self.r['open_tag'], Tag.PI), self.eq(self.r['open_tag'], Tag.LAM))),
            self.NOT(self.OR(self.eq(self.r['fold_tag'], Tag.PI), self.eq(self.r['fold_tag'], Tag.LAM))))
        self.stop(self.AND(self.active, invalid), Outcome.INVALID, Reason.SYNTAX)
        self.active = self.AND(self.active, self.NOT(invalid))
        uses_arguments = self.OR(*(self.eq(self.r['task'], value) for value in
            (Task.INSTANTIATE, Task.ABSTRACT, Task.OCCURS, Task.HAS_CONSTANTS, Task.FORMAL_LEVELS, Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.EXPR_LEVEL_SUBSTITUTE, Task.LEVEL_INSTANTIATE, Task.EXPR_LEVEL_INSTANTIATE, Task.EXPR_SCOPE)))
        window_end = self.g.add(self.g.fit(self.r['arg_base'], self.width+1), self.g.fit(self.r['count'], self.width+1))
        window_bad = self.AND(uses_arguments, self.g.lt(self.g.const(self.cfg.context, self.width+1), window_end))
        self.stop(self.AND(self.active, window_bad), Outcome.RESOURCE, Reason.CONTEXT)
        self.active = self.AND(self.active, self.NOT(window_bad))
        ctor_no_node = self.AND(self.eq(self.r['task'], Task.CHECK_CONSTRUCTORS),self.OR(*(self.eq(self.r['mode'],m) for m in
            (Mode.WALK,Mode.CTOR_STORE_META,Mode.CTOR_STORE_PENDING,Mode.CTOR_LINK))))
        recname_init = self.AND(self.eq(self.r['task'],Task.CHECK_RECURSOR_NAME),self.eq(self.r['mode'],Mode.WALK))
        core_name_no_node = self.AND(self.eq(self.r['task'],Task.CHECK_CORE_NAMES),self.OR(self.eq(self.r['mode'],Mode.WALK),self.eq(self.r['mode'],Mode.CORE_NAME_STORE)))
        decl_ctor_no_node = self.AND(self.eq(self.r['task'],Task.DECLARE_CONSTRUCTORS),self.OR(*(self.eq(self.r['mode'],m) for m in
            (Mode.WALK,Mode.DECL_CTOR_STORE_INFO,Mode.DECL_CTOR_STORE_SCHEME,Mode.DECL_CTOR_STORE_SIGNATURE,Mode.DECL_CTOR_LINK,Mode.DECL_CTOR_ORDER))))
        elimination_no_node = self.AND(self.eq(self.r['task'],Task.INIT_ELIMINATION),self.OR(*(self.eq(self.r['mode'],m) for m in ELIMINATION_NO_NODE)))
        binder_no_node = self.OR(self.eq(self.r['task'],Task.SNAPSHOT_SCOPE),self.AND(self.eq(self.r['task'],Task.FRESH_LOCAL),self.eq(self.r['mode'],Mode.FRESH_LOCAL_RECORD)),
            self.AND(self.eq(self.r['task'],Task.APPLY_SCOPE),self.eq(self.r['mode'],Mode.APPLY_SCOPE_SELECT)))
        motive_no_node = self.AND(self.eq(self.r['task'],Task.BUILD_MOTIVES),self.OR(*(self.eq(self.r['mode'],m) for m in MOTIVE_NO_NODE)))
        flags_no_node = self.AND(self.eq(self.r['task'],Task.BLOCK_FLAGS),self.OR(*(self.eq(self.r['mode'],m) for m in FLAGS_NO_NODE)))
        prefix_no_node = self.AND(self.eq(self.r['task'],Task.OPEN_RECURSIVE_PREFIX),self.OR(*(self.eq(self.r['mode'],m) for m in PREFIX_NO_NODE)))
        minor_no_node = self.AND(self.eq(self.r['task'],Task.BUILD_MINORS),self.OR(*(self.eq(self.r['mode'],m) for m in MINOR_NO_NODE)))
        rec_type_no_node = self.AND(self.eq(self.r['task'],Task.BUILD_RECURSOR_TYPES),self.OR(*(self.eq(self.r['mode'],m) for m in REC_TYPE_NO_NODE)))
        rule_no_node = self.AND(self.eq(self.r['task'],Task.BUILD_RECURSOR_RULES),self.OR(*(self.eq(self.r['mode'],m) for m in RULE_NO_NODE)))
        asm_no_node = self.AND(self.eq(self.r['task'],Task.ASSEMBLE_RECURSORS),self.OR(*(self.eq(self.r['mode'],m) for m in ASM_NO_NODE)))
        claim_no_node = self.OR(self.AND(self.eq(self.r['task'],Task.SYMBOL_MEMBER),self.eq(self.r['x'],0)),
            self.AND(self.eq(self.r['task'],Task.CHECK_RECURSOR_CLAIMS),self.OR(*(self.eq(self.r['mode'],m) for m in CLAIM_NO_NODE))))
        application_no_node = self.AND(self.eq(self.r['task'],Task.APPLICATION_SPINE),self.OR(*(self.eq(self.r['mode'],m) for m in application_ops_rules.NO_NODE)))
        major_no_node = self.AND(self.eq(self.r['task'],Task.PREPARE_RECURSOR_MAJOR),self.OR(*(self.eq(self.r['mode'],m) for m in major_rules.NO_NODE)))
        gather_no_node = self.AND(self.eq(self.r['task'],Task.GATHER_RECURSOR_ARGUMENTS),self.OR(*(self.eq(self.r['mode'],m) for m in recursor_reduce_rules.NO_NODE)))
        prior_block_no_node = self.AND(self.eq(self.r['task'],Task.PRIOR_BLOCK_LOOKUP),self.eq(self.r['mode'],Mode.WALK))
        needs_node = self.AND(self.NOT(prior_block_no_node),self.NOT(gather_no_node),self.NOT(major_no_node),self.NOT(application_no_node),self.NOT(claim_no_node),self.NOT(asm_no_node),self.NOT(rule_no_node),self.NOT(rec_type_no_node),self.NOT(minor_no_node),self.NOT(prefix_no_node),self.NOT(flags_no_node),self.NOT(motive_no_node),self.NOT(binder_no_node),self.NOT(elimination_no_node),self.NOT(decl_ctor_no_node),self.NOT(core_name_no_node),self.NOT(recname_init),self.NOT(ctor_no_node),self.NOT(self.eq(self.r['mode'], Mode.RETURN)), self.NOT(self.eq(self.r['task'], Task.FORMAL_LEVELS)),
            self.NOT(self.AND(self.eq(self.r['task'], Task.REVERSE_LIST), self.NOT(self.eq(self.r['mode'], Mode.REVERSE_LIST)))),
            self.NOT(self.AND(self.eq(self.r['task'], Task.ENV_LOOKUP), self.eq(self.r['mode'], Mode.WALK))),
            self.NOT(self.AND(self.eq(self.r['task'], Task.CHECK_SOURCE), self.NOT(self.eq(self.r['mode'], Mode.SOURCE_TYPE_SORT)))),
            self.NOT(self.AND(self.eq(self.r['task'], Task.ANALYZE_HEADERS), self.OR(*(self.eq(self.r['mode'], m) for m in
                (Mode.HEADER_STORE_FAMILY, Mode.HEADER_STORE_SCHEME, Mode.HEADER_STORE_SIGNATURE, Mode.HEADER_LINK))))))
        internal_record = self.OR(self.eq(self.r['mode'], Mode.FOLD_RECORD), self.eq(self.r['mode'], Mode.INFER_LOCAL_RECORD), self.eq(self.r['mode'], Mode.REUSE_RECORD), self.eq(self.r['mode'], Mode.REUSE_SUBST_RECORD), self.eq(self.r['mode'], Mode.APP_PARAMETER_RECORD), self.eq(self.r['mode'], Mode.ABSTRACT_SCOPE_RECORD), self.eq(self.r['mode'], Mode.APPLY_SCOPE_RECORD))
        binding_record = self.eq(self.r['mode'], Mode.LEVEL_BINDING)
        loading_parameters = self.eq(self.r['task'], Task.LOAD_PARAMETERS)
        parameter_header = self.AND(loading_parameters, self.eq(self.r['mode'], Mode.WALK))
        parameter_cell = self.AND(loading_parameters, self.NOT(self.eq(self.r['mode'], Mode.WALK)))
        comparing_vector = self.eq(self.r['task'], Task.VECTOR_EQUAL)
        comparing_cell = self.OR(self.eq(self.r['mode'], Mode.VECTOR_CELL_LEFT), self.eq(self.r['mode'], Mode.VECTOR_CELL_RIGHT))
        vector_header = self.OR(parameter_header,self.eq(self.r['mode'], Mode.CONST_PARAMETER_HEADER), self.eq(self.r['mode'], Mode.CONST_LEVEL_HEADER), self.eq(self.r['mode'], Mode.CONST_VECTOR), self.AND(comparing_vector, self.NOT(comparing_cell)))
        merge_cell = self.eq(self.r['mode'], Mode.MERGE_FOLD)
        checked_family = self.eq(self.r['mode'], Mode.APP_METADATA)
        checked_scheme = self.OR(self.eq(self.r['mode'], Mode.CONST_SCHEME), self.eq(self.r['mode'], Mode.APP_SCHEME))
        environment_signature = self.OR(self.eq(self.r['mode'], Mode.ENV_SIGNATURE), self.eq(self.r['mode'], Mode.CONST_SIGNATURE), self.eq(self.r['mode'], Mode.FAMILY_SET_SIGNATURE), self.eq(self.r['mode'], Mode.APP_SIGNATURE))
        environment_cell = self.OR(self.eq(self.r['mode'], Mode.ENV_CELL), self.eq(self.r['mode'], Mode.FAMILY_SET_CELL), self.eq(self.r['mode'], Mode.APP_ARGUMENT), self.eq(self.r['mode'], Mode.RECURSIVE_SKIP), self.eq(self.r['mode'], Mode.RECURSIVE_INDEX), self.eq(self.r['mode'], Mode.REVERSE_LIST))
        vector_cell = self.OR(parameter_cell,self.eq(self.r['mode'], Mode.CONST_PARAMETER_CELL), self.eq(self.r['mode'], Mode.CONST_LEVEL_CELL), environment_cell,self.AND(comparing_vector, comparing_cell), merge_cell, self.eq(self.r['mode'], Mode.CONST_CELL), self.eq(self.r['mode'], Mode.CONST_RESULT))
        level_scope = self.OR(*(self.eq(self.r['task'], task) for task in
            (Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.LEVEL_EQUAL, Task.LEVEL_NOT_ZERO, Task.LEVEL_OFFSET, Task.LEVEL_MAX, Task.LEVEL_IMAX, Task.LEVEL_INSTANTIATE, Task.LEVEL_ORDER, Task.LEVEL_NORMALIZE, Task.LEVEL_MERGE, Task.LEVEL_NORMAL_SUCC, Task.LEVEL_EQUIVALENT, Task.LEVEL_GEQ, Task.LEVEL_GEQ_CORE)))
        expression_tag_bad = self.OR(self.lt(self.read['node']['tag'], Tag.BVAR), self.lt(Tag.MDATA, self.read['node']['tag']))
        level_tag_bad = self.OR(self.lt(self.read['node']['tag'], CellTag.LEVEL_ZERO), self.lt(CellTag.LEVEL_PARAM, self.read['node']['tag']))
        tag_bad = self.OR(self.AND(checked_family, self.NOT(self.eq(self.read['node']['tag'], CellTag.CHECKED_FAMILY))), self.AND(checked_scheme, self.NOT(self.eq(self.read['node']['tag'], CellTag.CHECKED_SCHEME))),
            self.AND(environment_signature, self.NOT(self.OR(self.eq(self.read['node']['tag'], CellTag.CHECKED_SIGNATURE),
                self.AND(self.eq(self.r['mode'],Mode.ENV_SIGNATURE),self.eq(self.read['node']['tag'],CellTag.PENDING_CONSTRUCTOR))))),
            self.AND(internal_record, self.NOT(self.eq(self.read['node']['tag'], LOCAL_DECL_TAG))),
            self.AND(binding_record, self.NOT(self.eq(self.read['node']['tag'], CellTag.LEVEL_BINDING))),
            self.AND(vector_header, self.NOT(self.eq(self.read['node']['tag'], CellTag.VECTOR))),
            self.AND(vector_cell, self.NOT(self.eq(self.read['node']['tag'], CellTag.VECTOR_CELL))),
            self.AND(self.NOT(checked_family), self.NOT(checked_scheme), self.NOT(environment_signature), self.NOT(internal_record), self.NOT(binding_record), self.NOT(vector_header), self.NOT(vector_cell),
                self.OR(self.AND(level_scope, level_tag_bad), self.AND(self.NOT(level_scope), expression_tag_bad))))
        name_task = self.OR(self.eq(self.r['task'], Task.CHECK_NAME),self.eq(self.r['task'],Task.GET_NAME_PATH))
        name_header = self.OR(*(self.eq(self.r['mode'], mode) for mode in (Mode.WALK, Mode.NAME_PATH, Mode.NAME_BYTES)))
        name_cell = self.OR(*(self.eq(self.r['mode'], mode) for mode in (Mode.NAME_TABLE_CELL, Mode.NAME_PATH_CELL, Mode.NAME_BYTE_CELL)))
        name_ok = self.OR(self.AND(name_header, self.eq(self.read['node']['tag'], CellTag.VECTOR)),
            self.AND(name_cell, self.eq(self.read['node']['tag'], CellTag.VECTOR_CELL)),
            self.AND(self.eq(self.r['mode'], Mode.NAME_ENTRY), self.eq(self.read['node']['tag'], CellTag.SYMBOL_ENTRY)),
            self.AND(self.eq(self.r['mode'], Mode.NAME_COMPONENT), self.OR(self.eq(self.read['node']['tag'], CellTag.NAME_STRING), self.eq(self.read['node']['tag'], CellTag.NAME_NUMERAL))))
        tag_bad = self.OR(self.AND(name_task, self.NOT(name_ok)), self.AND(self.NOT(name_task), tag_bad))
        header_task = self.eq(self.r['task'], Task.ANALYZE_HEADERS)
        header_special = self.OR(*(self.eq(self.r['mode'], m) for m in (Mode.WALK, Mode.HEADER_VECTOR, Mode.HEADER_CELL, Mode.HEADER_FAMILY)))
        header_ok = self.OR(*(self.AND(self.eq(self.r['mode'], m), self.eq(self.read['node']['tag'], t)) for m,t in
            ((Mode.WALK, CellTag.RAW_BLOCK),(Mode.HEADER_VECTOR, CellTag.VECTOR),(Mode.HEADER_CELL, CellTag.VECTOR_CELL),(Mode.HEADER_FAMILY, CellTag.RAW_FAMILY))))
        tag_bad = self.OR(self.AND(header_task, header_special, self.NOT(header_ok)),self.AND(self.NOT(self.AND(header_task, header_special)),tag_bad))
        ctor_task = self.eq(self.r['task'],Task.CHECK_CONSTRUCTORS)
        ctor_tags = ((Mode.CTOR_FAMILY_CELL,CellTag.VECTOR_CELL),(Mode.CTOR_FAMILY_SIGNATURE,CellTag.CHECKED_SIGNATURE),
            (Mode.CTOR_FAMILY_SCHEME,CellTag.CHECKED_SCHEME),(Mode.CTOR_FAMILY_METADATA,CellTag.CHECKED_FAMILY),
            (Mode.CTOR_RAW_FAMILY,CellTag.RAW_FAMILY),(Mode.CTOR_FAMILY_AUX,CellTag.RAW_FAMILY_AUX),(Mode.CTOR_VECTOR,CellTag.VECTOR),
            (Mode.CTOR_CELL,CellTag.VECTOR_CELL),(Mode.CTOR_RECORD,CellTag.RAW_CONSTRUCTOR),(Mode.CTOR_FIELD_RECORD,CellTag.LOCAL_DECL))
        ctor_special = self.OR(*(self.eq(self.r['mode'],m) for m,t in ctor_tags))
        ctor_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in ctor_tags))
        tag_bad = self.OR(self.AND(ctor_task,ctor_special,self.NOT(ctor_ok)),self.AND(self.NOT(self.AND(ctor_task,ctor_special)),tag_bad))
        recname_task = self.eq(self.r['task'],Task.CHECK_RECURSOR_NAME)
        recname_header = self.OR(*(self.eq(self.r['mode'],m) for m in (Mode.RECNAME_LEFT_HEADER,Mode.RECNAME_RIGHT_HEADER,Mode.RECNAME_SUFFIX_HEADER)))
        recname_cell = self.OR(*(self.eq(self.r['mode'],m) for m in (Mode.RECNAME_LEFT_CELL,Mode.RECNAME_RIGHT_CELL,Mode.RECNAME_SUFFIX_CELL,Mode.RECNAME_SUFFIX_BYTE)))
        recname_part = self.OR(*(self.eq(self.r['mode'],m) for m in (Mode.RECNAME_LEFT_PART,Mode.RECNAME_RIGHT_PART,Mode.RECNAME_SUFFIX_PART)))
        recname_ok = self.OR(self.AND(recname_header,self.eq(self.read['node']['tag'],CellTag.VECTOR)),
            self.AND(recname_cell,self.eq(self.read['node']['tag'],CellTag.VECTOR_CELL)),
            self.AND(recname_part,self.OR(self.eq(self.read['node']['tag'],CellTag.NAME_STRING),self.eq(self.read['node']['tag'],CellTag.NAME_NUMERAL))))
        tag_bad = self.OR(self.AND(recname_task,self.NOT(recname_ok)),self.AND(self.NOT(recname_task),tag_bad))
        core_name_task = self.eq(self.r['task'],Task.CHECK_CORE_NAMES)
        core_name_tags = ((Mode.CORE_NAME_CELL,CellTag.VECTOR_CELL),(Mode.CORE_NAME_SIGNATURE,CellTag.CHECKED_SIGNATURE),
            (Mode.CORE_NAME_SCHEME,CellTag.CHECKED_SCHEME),(Mode.CORE_NAME_METADATA,CellTag.CHECKED_FAMILY),
            (Mode.CORE_NAME_RAW_FAMILY,CellTag.RAW_FAMILY),(Mode.CORE_NAME_AUX,CellTag.RAW_FAMILY_AUX))
        core_name_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in core_name_tags))
        tag_bad = self.OR(self.AND(core_name_task,self.NOT(core_name_ok)),self.AND(self.NOT(core_name_task),tag_bad))
        decl_ctor_task = self.eq(self.r['task'],Task.DECLARE_CONSTRUCTORS)
        decl_ctor_tags = ((Mode.DECL_CTOR_NAME,CellTag.VALIDATED_RECURSOR_NAME),(Mode.DECL_CTOR_FAMILY_SIGNATURE,CellTag.CHECKED_SIGNATURE),
            (Mode.DECL_CTOR_FAMILY_SCHEME,CellTag.CHECKED_SCHEME),(Mode.DECL_CTOR_FAMILY_METADATA,CellTag.CHECKED_FAMILY),
            (Mode.DECL_CTOR_RAW_FAMILY,CellTag.RAW_FAMILY),(Mode.DECL_CTOR_AUX,CellTag.RAW_FAMILY_AUX),(Mode.DECL_CTOR_VECTOR,CellTag.VECTOR),
            (Mode.DECL_CTOR_CELL,CellTag.VECTOR_CELL),(Mode.DECL_CTOR_RAW,CellTag.RAW_CONSTRUCTOR),(Mode.DECL_CTOR_PENDING,CellTag.PENDING_CONSTRUCTOR),
            (Mode.DECL_CTOR_ANALYSIS,CellTag.CONSTRUCTOR_ANALYSIS))
        decl_ctor_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in decl_ctor_tags))
        tag_bad = self.OR(self.AND(decl_ctor_task,self.NOT(decl_ctor_ok)),self.AND(self.NOT(decl_ctor_task),tag_bad))
        elimination_task = self.eq(self.r['task'],Task.INIT_ELIMINATION)
        elimination_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in ELIMINATION_TAGS.items()),
            self.AND(self.OR(*(self.eq(self.r['mode'],m) for m in ELIMINATION_LEVEL_MODES)),self.NOT(level_tag_bad)),
            self.AND(self.eq(self.r['mode'],Mode.ELIM_FIELD_SORT),self.NOT(expression_tag_bad)))
        tag_bad = self.OR(self.AND(elimination_task,self.NOT(elimination_ok)),self.AND(self.NOT(elimination_task),tag_bad))
        motive_task = self.eq(self.r['task'],Task.BUILD_MOTIVES)
        motive_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in MOTIVE_TAGS.items()),
            self.AND(self.eq(self.r['mode'],Mode.MOTIVE_SORT),self.NOT(expression_tag_bad)))
        tag_bad = self.OR(self.AND(motive_task,self.NOT(motive_ok)),self.AND(self.NOT(motive_task),tag_bad))
        flags_task = self.eq(self.r['task'],Task.BLOCK_FLAGS)
        flags_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in FLAGS_TAGS.items()),
            self.AND(self.eq(self.r['mode'],Mode.FLAGS_DOMAIN),self.NOT(expression_tag_bad)))
        tag_bad = self.OR(self.AND(flags_task,self.NOT(flags_ok)),self.AND(self.NOT(flags_task),tag_bad))
        prefix_task = self.eq(self.r['task'],Task.OPEN_RECURSIVE_PREFIX)
        prefix_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in PREFIX_TAGS.items()))
        tag_bad = self.OR(self.AND(prefix_task,self.NOT(prefix_ok)),self.AND(self.NOT(prefix_task),tag_bad))
        generation_task = self.eq(self.r['task'],Task.FIND_MOTIVE)
        generation_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in generation_ops_rules.MOTIVE_TAGS.items()))
        list_cell = self.AND(self.eq(self.r['task'],Task.APPLY_LIST),self.eq(self.r['mode'],Mode.LIST_CELL))
        tag_bad = self.OR(self.AND(generation_task,self.NOT(generation_ok)),self.AND(list_cell,self.NOT(self.eq(self.read['node']['tag'],CellTag.VECTOR_CELL))),
            self.AND(self.NOT(generation_task),self.NOT(list_cell),tag_bad))
        minor_task = self.eq(self.r['task'],Task.BUILD_MINORS)
        minor_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in MINOR_TAGS.items()))
        tag_bad = self.OR(self.AND(minor_task,self.NOT(minor_ok)),self.AND(self.NOT(minor_task),tag_bad))
        rec_type_task = self.eq(self.r['task'],Task.BUILD_RECURSOR_TYPES)
        rec_type_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in REC_TYPE_TAGS.items()))
        tag_bad = self.OR(self.AND(rec_type_task,self.NOT(rec_type_ok)),self.AND(self.NOT(rec_type_task),tag_bad))
        restore_task = self.eq(self.r['task'],Task.RESTORE_SCOPE)
        restore_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.OR(*(self.eq(self.read['node']['tag'],t) for t in tags))) for m,tags in restore_scope_rules.TAGS.items()))
        tag_bad = self.OR(self.AND(restore_task,self.NOT(restore_ok)),self.AND(self.NOT(restore_task),tag_bad))
        rule_task = self.eq(self.r['task'],Task.BUILD_RECURSOR_RULES)
        rule_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in RULE_TAGS.items()))
        tag_bad = self.OR(self.AND(rule_task,self.NOT(rule_ok)),self.AND(self.NOT(rule_task),tag_bad))
        asm_task = self.eq(self.r['task'],Task.ASSEMBLE_RECURSORS)
        asm_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in ASM_TAGS.items()))
        tag_bad = self.OR(self.AND(asm_task,self.NOT(asm_ok)),self.AND(self.NOT(asm_task),tag_bad))
        sigv_task = self.eq(self.r['task'],Task.SIGNATURE_VECTOR_LOOKUP)
        sigv_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in claim_lookup_rules.TAGS.items()))
        member_task = self.eq(self.r['task'],Task.SYMBOL_MEMBER)
        claim_task = self.eq(self.r['task'],Task.CHECK_RECURSOR_CLAIMS)
        claim_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in CLAIM_TAGS.items()),
            self.AND(self.eq(self.r['mode'],Mode.CLAIM_SORT),self.NOT(expression_tag_bad)))
        tag_bad = self.OR(self.AND(sigv_task,self.NOT(sigv_ok)),self.AND(member_task,self.NOT(self.eq(self.read['node']['tag'],CellTag.VECTOR_CELL))),
            self.AND(claim_task,self.NOT(claim_ok)),self.AND(self.NOT(sigv_task),self.NOT(member_task),self.NOT(claim_task),tag_bad))
        spine_task = self.eq(self.r['task'],Task.APPLICATION_SPINE)
        slice_task = self.eq(self.r['task'],Task.APPLY_VECTOR_SLICE)
        slice_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in application_ops_rules.SLICE_TAGS.items()),
            self.AND(self.eq(self.r['mode'],Mode.SLICE_ARGUMENT),self.NOT(expression_tag_bad)))
        tag_bad = self.OR(self.AND(spine_task,expression_tag_bad),self.AND(slice_task,self.NOT(slice_ok)),self.AND(self.NOT(spine_task),self.NOT(slice_task),tag_bad))
        iota_task = self.eq(self.r['task'],Task.APPLY_RECURSOR_RULE)
        iota_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in recursor_apply_rules.TAGS.items()),
            self.AND(self.OR(*(self.eq(self.r['mode'],m) for m in recursor_apply_rules.EXPRESSION_MODES)),self.NOT(expression_tag_bad)))
        tag_bad = self.OR(self.AND(iota_task,self.NOT(iota_ok)),self.AND(self.NOT(iota_task),tag_bad))
        reference_task = self.eq(self.r['task'],Task.VECTOR_REFERENCE)
        reference_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in application_ops_rules.SLICE_TAGS.items()))
        tag_bad = self.OR(self.AND(reference_task,self.NOT(reference_ok)),self.AND(self.NOT(reference_task),tag_bad))
        major_task = self.eq(self.r['task'],Task.PREPARE_RECURSOR_MAJOR)
        major_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in major_rules.TAGS.items()),
            self.AND(self.OR(*(self.eq(self.r['mode'],m) for m in major_rules.EXPRESSION_MODES)),self.NOT(expression_tag_bad)),
            self.AND(self.eq(self.r['mode'],Mode.MAJOR_SORT_LEVEL),self.NOT(self.lt(self.read['node']['tag'],CellTag.LEVEL_ZERO)),self.NOT(self.lt(CellTag.LEVEL_PARAM,self.read['node']['tag']))))
        tag_bad = self.OR(self.AND(major_task,self.NOT(major_ok)),self.AND(self.NOT(major_task),tag_bad))
        reduce_task = self.eq(self.r['task'],Task.REDUCE_RECURSOR)
        gather_task = self.eq(self.r['task'],Task.GATHER_RECURSOR_ARGUMENTS)
        reduce_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in recursor_reduce_rules.REDUCE_TAGS.items()),
            self.AND(self.OR(self.eq(self.r['mode'],Mode.WALK),self.eq(self.r['mode'],Mode.REDUCE_HEAD)),self.NOT(expression_tag_bad)))
        gather_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in recursor_reduce_rules.GATHER_TAGS.items()))
        tag_bad = self.OR(self.AND(reduce_task,self.NOT(reduce_ok)),self.AND(gather_task,self.NOT(gather_ok)),self.AND(self.NOT(reduce_task),self.NOT(gather_task),tag_bad))
        prior_block_task = self.eq(self.r['task'],Task.PRIOR_BLOCK_LOOKUP)
        prior_block_ok = self.OR(*(self.AND(self.eq(self.r['mode'],m),self.eq(self.read['node']['tag'],t)) for m,t in prior_block_rules.TAGS.items()))
        tag_bad = self.OR(self.AND(prior_block_task,self.NOT(prior_block_ok)),self.AND(self.NOT(prior_block_task),tag_bad))
        node_bad = self.OR(self.eq(self.r['x'], 0), self.NOT(self.lt(self.r['x'], self.r['free'])), tag_bad)
        bad = self.AND(needs_node, node_bad)
        self.stop(self.AND(self.active, bad), Outcome.INVALID, Reason.SYNTAX)
        self.active = self.AND(self.active, self.NOT(bad))

    def v(self, value, width=None):
        return self.g.const(int(value), width or self.width) if isinstance(value, int) else value

    def AND(self, *bits): return self.g.AND(*bits)
    def OR(self, *bits): return self.g.OR(*bits)
    def NOT(self, bit): return self.g.NOT(bit)
    def eq(self, x, y): return self.g.eq(self.v(x), self.v(y))
    def lt(self, x, y): return self.g.lt(self.v(x), self.v(y))
    def add(self, x, y): return self.g.add(self.v(x), self.v(y))
    def sub(self, x, y): return self.g.sub(self.v(x), self.v(y))[0]
    def mux(self, bit, x, y): return self.g.mux(bit, self.v(x), self.v(y))
    def mode(self, value): return self.AND(self.active, self.eq(self.r['mode'], value))
    def task(self, value): return self.eq(self.r['task'], value)
    def tag(self, *values): return self.OR(*(self.eq(self.read['node']['tag'], t) for t in values))

    def emit(self, guard, **updates):
        for name, value in updates.items():
            self.choices[name].append((guard, self.v(value, len(self.r[name]))))

    def stop(self, guard, status, reason=Reason.NONE):
        self.emit(guard, status=status, reason=reason)

    def ret(self, guard, ref):
        self.emit(guard, mode=Mode.RETURN, r=ref)

    def checked_add(self, guard, x, y):
        wide = self.g.add(self.g.fit(self.v(x), self.width+1), self.g.fit(self.v(y), self.width+1))
        self.stop(self.AND(guard, wide[-1]), Outcome.RESOURCE, Reason.INDEX)
        return self.AND(guard, self.NOT(wide[-1])), wide[:self.width]

    def write(self, bank, guard, address, row):
        self.writes[bank].append((guard, self.v(address), [self.v(v) for v in row]))

    def alloc(self, guard, row):
        room = self.lt(self.r['free'], self.cfg.heap)
        self.stop(self.AND(guard, self.NOT(room)), Outcome.RESOURCE, Reason.HEAP)
        guard = self.AND(guard, room)
        self.write('heap', guard, self.r['free'], row)
        self.emit(guard, free=self.add(self.r['free'], 1))
        self.ret(guard, self.r['free'])

    def rules(self):
        r, node, frame = self.r, self.read['node'], self.read['frame']
        x, depth, task, result = (r[n] for n in ('x', 'depth', 'task', 'r'))
        a, b, c = (node[n] for n in ('a', 'b', 'c'))
        operand = self.read['operand']['value']
        nonempty = self.NOT(self.eq(r['sp'], 0))
        top = self.sub(r['sp'], 1)
        returning = self.mode(Mode.RETURN)
        top_return = self.AND(returning, self.NOT(nonempty))
        self.emit(self.AND(top_return, self.NOT(self.eq(r['pending_reuse'], 0))),
            mode=Mode.WALK, task=Task.PREPARE_REUSE, x=r['root'], pending_reuse=0)
        top_return = self.AND(top_return, self.eq(r['pending_reuse'], 0))
        start_open = self.AND(top_return, self.NOT(self.eq(r['pending_open'], 0)))
        self.emit(start_open, mode=Mode.TELESCOPE, x=r['root'], task=Task.OPEN_TELESCOPE, depth=0, pending_open=0)
        after_open = self.AND(top_return, self.eq(r['pending_open'], 0))
        start_fold = self.AND(after_open, self.NOT(self.eq(r['pending_fold'], 0)))
        self.emit(start_fold, mode=Mode.FOLD_SELECT, x=result, fold_body=result, task=Task.FOLD_TELESCOPE, pending_fold=0, fold_base=0)
        after_fold = self.AND(after_open, self.eq(r['pending_fold'], 0))
        self.emit(self.AND(after_fold, self.NOT(self.eq(r['pending_scope'], 0))),
            mode=Mode.WALK, task=Task.EXPR_SCOPE, x=r['root'], depth=0, pending_scope=0)
        after_scope = self.AND(after_fold, self.eq(r['pending_scope'], 0))
        self.emit(self.AND(after_scope, self.NOT(self.eq(r['pending_infer'], 0))),
            mode=Mode.WALK, task=Task.INFER, x=r['root'], local_base=r['ctx'], pending_infer=0)
        after_infer = self.AND(after_scope, self.eq(r['pending_infer'], 0))
        self.emit(self.AND(after_infer, self.NOT(self.eq(r['pending_compare'], 0))),
            mode=Mode.WALK, x=result, peer=r['comparison_root'],
            task=self.mux(self.eq(r['pending_compare'], 1), Task.LEVEL_EQUAL, Task.EXPR_EQUAL), pending_compare=0)
        self.stop(self.AND(after_infer, self.eq(r['pending_compare'], 0)), Outcome.DONE)
        internal_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_BETA_ZETA))
        self.emit(internal_return, sp=top, mode=Mode.BETA_ZETA, x=result, depth=0, task=Task.BETA_ZETA)
        telescope_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_TELESCOPE))
        self.emit(telescope_return, sp=top, mode=Mode.TELESCOPE, x=result, depth=0, task=Task.OPEN_TELESCOPE)
        fold_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_FOLD))
        self.emit(fold_return, sp=top, mode=Mode.FOLD_BUILD, x=result, task=Task.FOLD_TELESCOPE)
        sort_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_SORT_LEVEL))
        self.emit(sort_return, sp=top, mode=Mode.SORT_RESULT, x=frame['original'], depth=frame['depth'], task=frame['task'])
        const_return = self.AND(returning, nonempty, self.eq(frame['phase'], CALL_CONST_LEVEL))
        self.emit(const_return, sp=top, mode=Mode.CONST_RESULT, x=frame['original'], depth=frame['depth'], task=frame['task'])
        compare_return = self.AND(returning, nonempty, self.eq(frame['phase'], LEVEL_EQUAL_SECOND))
        self.emit(compare_return, sp=top)
        self.ret(self.AND(compare_return, self.eq(result, 0)), 0)
        self.emit(self.AND(compare_return, self.NOT(self.eq(result, 0))),
            mode=Mode.WALK, x=frame['original'], peer=frame['depth'], task=Task.LEVEL_EQUAL)
        or_return = self.AND(returning, nonempty, self.eq(frame['phase'], LEVEL_OR_SECOND))
        self.emit(or_return, sp=top)
        self.ret(self.AND(or_return, self.NOT(self.eq(result, 0))), 1)
        self.emit(self.AND(or_return, self.eq(result, 0)), mode=Mode.WALK, x=frame['original'], task=Task.LEVEL_NOT_ZERO)
        private_phase = self.OR(*(self.eq(frame['phase'], value) for value in
            (CALL_BETA_ZETA, CALL_TELESCOPE, CALL_FOLD, CALL_SORT_LEVEL, CALL_CONST_LEVEL, LEVEL_EQUAL_SECOND, LEVEL_OR_SECOND)+level_constructor_rules.PRIVATE_PHASES+level_order_rules.PRIVATE_PHASES+level_normalize_rules.PRIVATE_PHASES+level_geq_rules.PRIVATE_PHASES+expression_equal_rules.PRIVATE_PHASES+inference_rules.PRIVATE_PHASES+constant_rules.PRIVATE_PHASES+source_rules.PRIVATE_PHASES+telescope_rules.PRIVATE_PHASES+occurrence_rules.PRIVATE_PHASES+header_rules.PRIVATE_PHASES+family_occurrence_rules.PRIVATE_PHASES+family_application_rules.PRIVATE_PHASES+positivity_rules.PRIVATE_PHASES+abstract_scope_rules.PRIVATE_PHASES+recursive_argument_rules.PRIVATE_PHASES+constructor_rules.PRIVATE_PHASES+recursor_name_rules.PRIVATE_PHASES+core_names_rules.PRIVATE_PHASES+declare_constructors_rules.PRIVATE_PHASES+elimination_rules.PRIVATE_PHASES+motive_rules.PRIVATE_PHASES+block_flags_rules.PRIVATE_PHASES+open_prefix_rules.PRIVATE_PHASES+minor_rules.PRIVATE_PHASES+recursor_type_rules.PRIVATE_PHASES+recursor_rule_rules.PRIVATE_PHASES+assemble_recursors_rules.PRIVATE_PHASES+recursor_claim_rules.PRIVATE_PHASES+recursor_apply_rules.PRIVATE_PHASES))
        private_phase = self.OR(private_phase,*(self.eq(frame['task'],owner) for owner in (Task.PREPARE_RECURSOR_MAJOR,Task.REDUCE_RECURSOR,Task.GATHER_RECURSOR_ARGUMENTS,Task.PRIOR_BLOCK_LOOKUP)))
        self.emit(self.AND(returning, nonempty, self.NOT(private_phase)), mode=Mode.RESUME,
                  x=frame['original'], depth=frame['depth'], task=frame['task'])

        # Structural == walks pairs. A native allocation can duplicate a DAG;
        # address identity is only a fast path, never the complete predicate.
        comparing = self.AND(self.mode(Mode.WALK), self.task(Task.LEVEL_EQUAL))
        peer_ok = self.AND(self.NOT(self.eq(r['peer'], 0)), self.lt(r['peer'], r['free']))
        self.stop(self.AND(comparing, self.NOT(peer_ok)), Outcome.INVALID, Reason.SYNTAX)
        comparing = self.AND(comparing, peer_ok)
        identical = self.eq(x, r['peer'])
        self.ret(self.AND(comparing, identical), 1)
        self.emit(self.AND(comparing, self.NOT(identical)), mode=Mode.LEVEL_EQUAL_RIGHT,
            left_tag=node['tag'], left_a=a, left_b=b, x=r['peer'])
        right = self.mode(Mode.LEVEL_EQUAL_RIGHT)
        same_tag = self.eq(node['tag'], r['left_tag'])
        self.ret(self.AND(right, self.NOT(same_tag)), 0)
        right = self.AND(right, same_tag)
        self.ret(self.AND(right, self.tag(CellTag.LEVEL_ZERO)), 1)
        self.ret(self.AND(right, self.tag(CellTag.LEVEL_PARAM)), self.mux(self.eq(a, r['left_a']), 1, 0))
        self.emit(self.AND(right, self.tag(CellTag.LEVEL_SUCC)), mode=Mode.WALK, x=r['left_a'], peer=a)
        pair = self.AND(right, self.tag(CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX))
        pair_room = self.lt(r['sp'], self.cfg.stack)
        self.stop(self.AND(pair, self.NOT(pair_room)), Outcome.RESOURCE, Reason.STACK)
        pair = self.AND(pair, pair_room)
        self.write('stack', pair, r['sp'], (LEVEL_EQUAL_SECOND, r['left_b'], b, Task.LEVEL_EQUAL, 0, 0))
        self.emit(pair, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=r['left_a'], peer=a)
        not_zero = self.AND(self.mode(Mode.WALK), self.task(Task.LEVEL_NOT_ZERO))
        self.ret(self.AND(not_zero, self.tag(CellTag.LEVEL_ZERO, CellTag.LEVEL_PARAM)), 0)
        self.ret(self.AND(not_zero, self.tag(CellTag.LEVEL_SUCC)), 1)
        self.emit(self.AND(not_zero, self.tag(CellTag.LEVEL_IMAX)), x=b)
        or_branch = self.AND(not_zero, self.tag(CellTag.LEVEL_MAX))
        self.stop(self.AND(or_branch, self.NOT(pair_room)), Outcome.RESOURCE, Reason.STACK)
        or_branch = self.AND(or_branch, pair_room)
        self.write('stack', or_branch, r['sp'], (LEVEL_OR_SECOND, b, 0, Task.LEVEL_NOT_ZERO, 0, 0))
        self.emit(or_branch, sp=self.add(r['sp'], 1), x=a)
        offset = self.AND(self.mode(Mode.WALK), self.task(Task.LEVEL_OFFSET))
        self.ret(self.AND(offset, self.NOT(self.tag(CellTag.LEVEL_SUCC))), x)
        increment, next_offset = self.checked_add(self.AND(offset, self.tag(CellTag.LEVEL_SUCC)), r['level_offset'], 1)
        self.emit(increment, x=a, level_offset=next_offset)

        level_constructor_rules.emit_rules(self)
        level_order_rules.emit_rules(self)
        level_normalize_rules.emit_rules(self)
        level_geq_rules.emit_rules(self)
        expression_equal_rules.emit_rules(self)
        inference_rules.emit_rules(self)
        environment_rules.emit_rules(self)
        constant_rules.emit_rules(self)
        parameter_rules.emit_rules(self)
        name_rules.emit_rules(self)
        source_rules.emit_rules(self)
        telescope_rules.emit_rules(self)
        occurrence_rules.emit_rules(self)
        header_rules.emit_rules(self)
        family_occurrence_rules.emit_rules(self)
        formal_levels_rules.emit_rules(self)
        family_application_rules.emit_rules(self)
        positivity_rules.emit_rules(self)
        abstract_scope_rules.emit_rules(self)
        reverse_list_rules.emit_rules(self)
        recursive_argument_rules.emit_rules(self)
        constructor_rules.emit_rules(self)
        recursor_name_rules.emit_rules(self)
        core_names_rules.emit_rules(self)
        declare_constructors_rules.emit_rules(self)
        elimination_rules.emit_rules(self)
        binder_ops_rules.emit_rules(self)
        motive_rules.emit_rules(self)
        block_flags_rules.emit_rules(self)
        open_prefix_rules.emit_rules(self)
        generation_ops_rules.emit_rules(self)
        minor_rules.emit_rules(self)
        recursor_type_rules.emit_rules(self)
        restore_scope_rules.emit_rules(self)
        recursor_rule_rules.emit_rules(self)
        assemble_recursors_rules.emit_rules(self)
        claim_lookup_rules.emit_rules(self)
        recursor_claim_rules.emit_rules(self)
        application_ops_rules.emit_rules(self)
        recursor_apply_rules.emit_rules(self)
        major_rules.emit_rules(self)
        recursor_reduce_rules.emit_rules(self)
        prior_block_rules.emit_rules(self)

        sorting = self.mode(Mode.SORT_RESULT)
        self.stop(self.AND(sorting, self.NOT(self.tag(Tag.SORT))), Outcome.INVALID, Reason.SYNTAX)
        self.ret(self.AND(sorting, self.tag(Tag.SORT), self.eq(a, result)), x)
        self.alloc(self.AND(sorting, self.tag(Tag.SORT), self.NOT(self.eq(a, result))), (Tag.SORT, result, 0, 0))
        vector = self.mode(Mode.CONST_VECTOR)
        empty = self.eq(a, 0)
        vector_ok = self.AND(self.eq(c, VectorKind.LEVELS), self.eq(self.mux(empty, 1, 0), self.mux(self.eq(b, 0), 1, 0)))
        self.stop(self.AND(vector, self.NOT(vector_ok)), Outcome.INVALID, Reason.SYNTAX)
        self.ret(self.AND(vector, vector_ok, empty), r['const_original'])
        self.emit(self.AND(vector, vector_ok, self.NOT(empty)), vec_length=a, vec_left=a, vec_build=a,
            vec_head=0, vec_changed=0, mode=Mode.CONST_CELL, x=b)
        cell = self.mode(Mode.CONST_CELL)
        more_values = self.lt(1, r['vec_left'])
        cell_ok = self.AND(self.NOT(self.eq(r['vec_left'], 0)),
            self.eq(self.mux(more_values, 1, 0), self.mux(self.NOT(self.eq(b, 0)), 1, 0)))
        self.stop(self.AND(cell, self.NOT(cell_ok)), Outcome.INVALID, Reason.SYNTAX)
        stack_room = self.lt(r['sp'], self.cfg.stack)
        self.stop(self.AND(cell, cell_ok, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        call_level = self.AND(cell, cell_ok, stack_room)
        self.write('stack', call_level, r['sp'], (CALL_CONST_LEVEL, x, r['expr_depth'], task, 0, 0))
        self.emit(call_level, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=a, depth=0, task=self.mux(self.task(Task.EXPR_SCOPE), Task.LEVEL_SCOPE, self.mux(self.task(Task.EXPR_LEVEL_INSTANTIATE), Task.LEVEL_INSTANTIATE, Task.LEVEL_SUBSTITUTE)))
        value = self.mode(Mode.CONST_RESULT)
        value_ok = self.NOT(self.eq(r['vec_left'], 0))
        self.stop(self.AND(value, self.NOT(value_ok)), Outcome.INVALID, Reason.SYNTAX)
        changed = self.OR(self.NOT(self.eq(r['vec_changed'], 0)), self.NOT(self.eq(a, result)))
        push_value = self.AND(value, value_ok, self.OR(more_values, changed))
        self.stop(self.AND(push_value, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        push_value = self.AND(push_value, stack_room)
        self.write('stack', push_value, r['sp'], (VECTOR_VALUE, result, 0, task, 0, 0))
        self.emit(push_value, sp=self.add(r['sp'], 1), vec_left=self.sub(r['vec_left'], 1),
            vec_changed=self.mux(changed, 1, 0), mode=self.mux(more_values, Mode.CONST_CELL, Mode.CONST_BUILD),
            x=self.mux(more_values, b, r['const_original']))
        unchanged_vector = self.AND(value, value_ok, self.NOT(more_values), self.NOT(changed))
        self.emit(unchanged_vector, sp=self.sub(r['sp'], self.sub(r['vec_length'], 1)))
        self.ret(unchanged_vector, r['const_original'])
        building = self.mode(Mode.CONST_BUILD)
        has_value = self.NOT(self.eq(r['vec_build'], 0))
        build_ok = self.OR(self.NOT(has_value), self.AND(nonempty, self.eq(frame['phase'], VECTOR_VALUE)))
        self.stop(self.AND(building, self.NOT(build_ok)), Outcome.INVALID, Reason.SYNTAX)
        heap_room = self.lt(r['free'], self.cfg.heap)
        self.stop(self.AND(building, build_ok, self.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
        build_cell = self.AND(building, build_ok, heap_room, has_value)
        self.write('heap', build_cell, r['free'], (CellTag.VECTOR_CELL, frame['original'], r['vec_head'], 0))
        self.emit(build_cell, free=self.add(r['free'], 1), vec_head=r['free'], vec_build=self.sub(r['vec_build'], 1), sp=top)
        build_header = self.AND(building, build_ok, heap_room, self.NOT(has_value))
        self.write('heap', build_header, r['free'], (CellTag.VECTOR, r['vec_length'], r['vec_head'], VectorKind.LEVELS))
        self.emit(build_header, free=self.add(r['free'], 1), vector_result=r['free'], mode=Mode.CONST_FINISH)
        const_finish = self.mode(Mode.CONST_FINISH)
        self.stop(self.AND(const_finish, self.NOT(self.tag(Tag.CONST))), Outcome.INVALID, Reason.SYNTAX)
        self.alloc(self.AND(const_finish, self.tag(Tag.CONST)), (Tag.CONST, a, r['vector_result'], 0))

        heap_map=self.AND(self.task(Task.LEVEL_INSTANTIATE),self.NOT(self.eq(r['level_map_head'],0)))
        self.emit(self.AND(self.mode(Mode.LEVEL_SELECT),self.NOT(heap_map)), mode=Mode.LEVEL_BINDING, x=operand)
        self.emit(self.AND(self.mode(Mode.LEVEL_SELECT),heap_map),mode=Mode.LEVEL_BINDING,x=r['level_map_head'],level_map_result=r['lookup_level'])
        binding = self.mode(Mode.LEVEL_BINDING)
        value_valid = self.AND(self.NOT(self.eq(b, 0)), self.lt(b, r['free']))
        another_binding = self.lt(self.add(r['i'], 1), r['count'])
        tail_ok=self.eq(self.mux(self.eq(c,0),0,1),self.mux(another_binding,1,0))
        value_valid=self.AND(value_valid,self.OR(self.NOT(heap_map),tail_ok))
        self.stop(self.AND(binding, self.NOT(value_valid)), Outcome.INVALID, Reason.SYNTAX)
        binding = self.AND(binding, value_valid)
        matches = self.eq(a, r['parameter'])
        selected=self.mux(matches,b,r['level_map_result'])
        self.emit(self.AND(binding,heap_map),level_map_result=selected)
        self.emit(self.AND(binding,heap_map,another_binding),x=c,i=self.add(r['i'],1))
        self.ret(self.AND(binding,heap_map,self.NOT(another_binding)),selected)
        self.ret(self.AND(binding,self.NOT(heap_map), matches), b)
        self.emit(self.AND(binding,self.NOT(heap_map), self.NOT(matches), another_binding),
            mode=Mode.LEVEL_SELECT, x=r['lookup_level'], i=self.add(r['i'], 1))
        self.ret(self.AND(binding,self.NOT(heap_map), self.NOT(matches), self.NOT(another_binding)), r['lookup_level'])

        folding = self.mode(Mode.FOLD_SELECT)
        active_local = self.lt(r['fold_base'],r['ctx'])
        self.stop(self.AND(folding,self.lt(r['ctx'],r['fold_base'])),Outcome.INVALID,Reason.SYNTAX)
        self.ret(self.AND(folding,self.eq(r['ctx'],r['fold_base'])), r['fold_body'])
        self.emit(self.AND(folding, active_local), mode=Mode.FOLD_RECORD, x=operand)
        record = self.mode(Mode.FOLD_RECORD)
        valid_record = self.AND(self.NOT(self.eq(a, 0)), self.lt(a, r['free']), self.NOT(self.eq(b, 0)), self.lt(b, r['free']))
        self.stop(self.AND(record, self.NOT(valid_record)), Outcome.INVALID, Reason.SYNTAX)
        self.emit(self.AND(record, valid_record), mode=Mode.FOLD_LOCAL, x=a, domain=b, binder_info=c)
        local = self.mode(Mode.FOLD_LOCAL)
        valid_local = self.tag(Tag.LOCAL)
        self.stop(self.AND(local, self.NOT(valid_local)), Outcome.INVALID, Reason.SYNTAX)
        stack_room = self.lt(r['sp'], self.cfg.stack)
        self.stop(self.AND(local, valid_local, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        local = self.AND(local, valid_local, stack_room)
        self.write('stack', local, r['sp'], (CALL_FOLD, 0, 0, Task.FOLD_TELESCOPE, 0, 0))
        self.emit(local, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=r['fold_body'], depth=0,
            task=Task.ABSTRACT_ONE, abstract_uid=a)
        build = self.mode(Mode.FOLD_BUILD)
        self.stop(self.AND(build, self.NOT(active_local)), Outcome.INVALID, Reason.SYNTAX)
        heap_room = self.lt(r['free'], self.cfg.heap)
        self.stop(self.AND(build, active_local, self.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
        build = self.AND(build, active_local, heap_room)
        self.write('heap', build, r['free'], (r['fold_tag'], r['domain'], result, r['binder_info']))
        self.emit(build, free=self.add(r['free'], 1), fold_body=r['free'], ctx=self.sub(r['ctx'], 1),
            mode=Mode.FOLD_SELECT, x=r['free'])

        # Consume declared Pi binders by a count-driven loop. Each allocated
        # Local has an arena-address UID and a separate (Local,type,binderInfo)
        # record. The entry scope walk rejects raw free locals before opening.
        telescope = self.mode(Mode.TELESCOPE_READY)
        bounded = self.NOT(self.eq(r['bounded'], 0))
        at_limit = self.AND(bounded, self.eq(r['ctx'], r['limit']))
        self.ret(self.AND(telescope, at_limit), x)
        continue_open = self.AND(telescope, self.NOT(at_limit))
        pi = self.eq(node['tag'], r['open_tag'])
        expected = self.mux(self.eq(r['open_tag'], Tag.PI), Reason.EXPECT_PI, Reason.EXPECT_LAM)
        self.stop(self.AND(continue_open, self.NOT(pi), bounded), Outcome.INVALID, expected)
        self.ret(self.AND(continue_open, self.NOT(pi), self.NOT(bounded)), x)
        opening = self.AND(continue_open, pi)
        context_room = self.lt(r['ctx'], self.cfg.context)
        stack_room = self.lt(r['sp'], self.cfg.stack)
        heap_room = self.lt(self.add(r['free'], 1), self.cfg.heap)
        self.stop(self.AND(opening, self.NOT(context_room)), Outcome.RESOURCE, Reason.CONTEXT)
        self.stop(self.AND(opening, context_room, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        self.stop(self.AND(opening, context_room, stack_room, self.NOT(heap_room)), Outcome.RESOURCE, Reason.HEAP)
        opening = self.AND(opening, context_room, stack_room, heap_room)
        self.write('heap', opening, r['free'], (Tag.LOCAL, r['free'], 0, 0))
        self.emit(opening, free=self.add(r['free'], 1), r=r['free'], mode=Mode.BINDER_RECORD)
        recording = self.mode(Mode.BINDER_RECORD)
        self.write('heap', recording, r['free'], (LOCAL_DECL_TAG, result, a, c))
        self.write('context', recording, r['ctx'], (r['free'],))
        self.write('stack', recording, r['sp'], (CALL_TELESCOPE, 0, 0, Task.OPEN_TELESCOPE, 0, 0))
        self.emit(recording, free=self.add(r['free'], 1), ctx=self.add(r['ctx'], 1), sp=self.add(r['sp'], 1),
            mode=Mode.WALK, x=b, depth=0, task=Task.INSTANTIATE_ONE, substitution=result)

        # The beta/zeta service calls the SAME capture-avoiding substitution
        # walk, then resumes through a private continuation. App arguments are
        # internal stack frames, never an input-provided traversal schedule.
        reducing = self.mode(Mode.BETA_ZETA)
        self.emit(self.AND(reducing, self.tag(Tag.MDATA)), x=a)
        room = self.lt(r['sp'], self.cfg.stack)
        argument = self.AND(nonempty, self.eq(frame['phase'], PENDING_ARGUMENT))
        push_argument = self.AND(reducing, self.tag(Tag.APP))
        let_call = self.AND(reducing, self.tag(Tag.LET))
        pushing = self.OR(push_argument, let_call)
        self.stop(self.AND(pushing, self.NOT(room)), Outcome.RESOURCE, Reason.STACK)
        self.write('stack', self.AND(push_argument, room), r['sp'],
            (PENDING_ARGUMENT, x, 0, Task.BETA_ZETA, b, 0))
        self.emit(self.AND(push_argument, room), sp=self.add(r['sp'], 1), x=a)
        beta = self.AND(reducing, self.tag(Tag.LAM), argument)
        self.write('stack', beta, top, (CALL_BETA_ZETA, 0, 0, Task.BETA_ZETA, 0, 0))
        self.emit(beta, mode=Mode.WALK, x=b, substitution=frame['first'], depth=0, task=Task.INSTANTIATE_ONE)
        self.write('stack', self.AND(let_call, room), r['sp'], (CALL_BETA_ZETA, 0, 0, Task.BETA_ZETA, 0, 0))
        self.emit(self.AND(let_call, room), sp=self.add(r['sp'], 1), mode=Mode.WALK,
            x=c, substitution=b, depth=0, task=Task.INSTANTIATE_ONE)
        stuck = self.AND(reducing, self.NOT(self.OR(self.tag(Tag.MDATA, Tag.APP, Tag.LET), self.AND(self.tag(Tag.LAM), argument))))
        self.ret(self.AND(stuck, self.NOT(self.AND(self.tag(Tag.CONST), self.NOT(self.eq(r['env_ready'], 0))))), x)

        # Reverse list search implements Local abstraction and symbol-set DFS.
        finding = self.mode(Mode.FIND)
        valid = self.lt(r['i'], r['count'])
        self.stop(self.AND(finding, self.NOT(valid)), Outcome.INVALID, Reason.SYNTAX)
        matched = self.eq(operand, a)
        found = self.AND(finding, valid, matched)
        occurs_found = self.AND(found, self.task(Task.OCCURS))
        internal = self.NOT(self.eq(r['occurrence_internal'], 0))
        self.emit(self.AND(occurs_found, internal), occurrence_found=1, sp=self.add(r['occurrence_mark'], 1), mode=Mode.RETURN, r=1)
        self.emit(self.AND(occurs_found, self.NOT(internal)), found=1, sp=0, r=r['root'])
        self.stop(self.AND(occurs_found, self.NOT(internal)), Outcome.DONE)
        self.ret(self.AND(found, self.task(Task.LEVEL_SCOPE)), x)
        adding, bound_index = self.checked_add(self.AND(found, self.NOT(self.OR(self.task(Task.OCCURS), self.task(Task.LEVEL_SCOPE)))),
            depth, self.sub(self.sub(r['count'], 1), r['i']))
        self.alloc(adding, (Tag.BVAR, bound_index, 0, 0))
        missing = self.AND(finding, valid, self.NOT(matched))
        last = self.AND(missing, self.eq(r['i'], 0))
        self.stop(self.AND(last, self.task(Task.LEVEL_SCOPE)), Outcome.INVALID, Reason.UNIVERSE)
        self.ret(self.AND(last, self.NOT(self.task(Task.LEVEL_SCOPE))), x)
        self.emit(self.AND(missing, self.NOT(self.eq(r['i'], 0))), i=self.sub(r['i'], 1))

        level_task = self.OR(*(self.task(t) for t in (Task.LEVEL_SCOPE, Task.LEVEL_SUBSTITUTE, Task.LEVEL_INSTANTIATE, Task.LEVEL_NORMALIZE, Task.LEVEL_NORMAL_SUCC)))
        binary = self.OR(self.tag(Tag.APP, Tag.PI, Tag.LAM),
            self.AND(level_task, self.OR(self.tag(CellTag.LEVEL_MAX), self.AND(self.tag(CellTag.LEVEL_IMAX), self.NOT(self.task(Task.LEVEL_NORMAL_SUCC))))))
        let = self.tag(Tag.LET)
        unary = self.OR(self.tag(Tag.PROJ, Tag.MDATA),
            self.AND(level_task, self.tag(CellTag.LEVEL_SUCC), self.NOT(self.task(Task.LEVEL_NORMAL_SUCC))))
        branch = self.OR(binary, let, unary)
        walking = self.mode(Mode.WALK)
        expression_level = self.AND(walking, self.OR(self.task(Task.EXPR_LEVEL_SUBSTITUTE), self.task(Task.EXPR_LEVEL_INSTANTIATE), self.task(Task.EXPR_SCOPE)))
        no_bindings = self.AND(self.eq(r['count'], 0), self.NOT(self.task(Task.EXPR_SCOPE)))
        self.ret(self.AND(expression_level, no_bindings), x)
        sort_call = self.AND(expression_level, self.NOT(no_bindings), self.tag(Tag.SORT))
        self.stop(self.AND(sort_call, self.NOT(stack_room)), Outcome.RESOURCE, Reason.STACK)
        sort_call = self.AND(sort_call, stack_room)
        self.write('stack', sort_call, r['sp'], (CALL_SORT_LEVEL, x, depth, task, 0, 0))
        self.emit(sort_call, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=a, depth=0, task=self.mux(self.task(Task.EXPR_SCOPE), Task.LEVEL_SCOPE, self.mux(self.task(Task.EXPR_LEVEL_INSTANTIATE), Task.LEVEL_INSTANTIATE, Task.LEVEL_SUBSTITUTE)))
        self.emit(self.AND(expression_level, self.NOT(no_bindings), self.tag(Tag.CONST)),
            const_original=x, expr_depth=depth, mode=Mode.CONST_VECTOR, x=b)
        intercepted = self.AND(expression_level, self.OR(no_bindings, self.tag(Tag.SORT, Tag.CONST)))
        walking = self.AND(walking, self.NOT(intercepted),
            self.NOT(self.OR(self.task(Task.LEVEL_EQUAL), self.task(Task.LEVEL_NOT_ZERO), self.task(Task.LEVEL_OFFSET), self.task(Task.LEVEL_MAX), self.task(Task.LEVEL_IMAX), self.task(Task.LEVEL_ORDER), self.task(Task.LEVEL_MERGE), self.task(Task.LEVEL_EQUIVALENT), self.task(Task.LEVEL_GEQ), self.task(Task.LEVEL_GEQ_CORE), self.task(Task.EXPR_EQUAL), self.task(Task.VECTOR_EQUAL), self.task(Task.INFER), self.task(Task.CONVERT_POSITIVE), self.task(Task.ENV_LOOKUP), self.task(Task.LOAD_PARAMETERS), self.task(Task.CHECK_NAME), self.task(Task.CHECK_SOURCE), self.task(Task.CONSUME_PARAMETERS), self.task(Task.PREPARE_REUSE), self.task(Task.HAS_CONSTANTS), self.task(Task.ANALYZE_HEADERS), self.task(Task.HAS_FAMILIES), self.task(Task.FAMILY_APPLICATION), self.task(Task.FORMAL_LEVELS), self.task(Task.CHECK_POSITIVITY), self.task(Task.ABSTRACT_SCOPE), self.task(Task.RECURSIVE_ARGUMENT), self.task(Task.REVERSE_LIST), self.task(Task.CHECK_CONSTRUCTORS), self.task(Task.GET_NAME_PATH), self.task(Task.CHECK_RECURSOR_NAME), self.task(Task.CHECK_CORE_NAMES), self.task(Task.DECLARE_CONSTRUCTORS), self.task(Task.INIT_ELIMINATION), self.task(Task.FRESH_LOCAL), self.task(Task.APPLY_SCOPE), self.task(Task.BUILD_MOTIVES), self.task(Task.BLOCK_FLAGS), self.task(Task.INSTANTIATE_SCOPE), self.task(Task.SNAPSHOT_SCOPE), self.task(Task.OPEN_RECURSIVE_PREFIX), self.task(Task.APPLY_LIST), self.task(Task.FIND_MOTIVE), self.task(Task.BUILD_MINORS), self.task(Task.BUILD_RECURSOR_TYPES), self.task(Task.RESTORE_SCOPE), self.task(Task.BUILD_RECURSOR_RULES), self.task(Task.ASSEMBLE_RECURSORS), self.task(Task.INSTANTIATE_SCHEME), self.task(Task.SIGNATURE_VECTOR_LOOKUP), self.task(Task.SYMBOL_MEMBER), self.task(Task.CHECK_RECURSOR_CLAIMS), self.task(Task.APPLICATION_SPINE), self.task(Task.APPLY_VECTOR_SLICE), self.task(Task.APPLY_RECURSOR_RULE), self.task(Task.VECTOR_REFERENCE), self.task(Task.PREPARE_RECURSOR_MAJOR), self.task(Task.REDUCE_RECURSOR), self.task(Task.GATHER_RECURSOR_ARGUMENTS), self.task(Task.PRIOR_BLOCK_LOOKUP))))
        descending = self.AND(walking, branch)
        room = self.lt(r['sp'], self.cfg.stack)
        self.stop(self.AND(descending, self.NOT(room)), Outcome.RESOURCE, Reason.STACK)
        down = self.AND(descending, room)
        self.write('stack', down, r['sp'], (1, x, depth, task, 0, 0))
        self.emit(down, sp=self.add(r['sp'], 1), mode=Mode.WALK, x=self.mux(self.tag(Tag.PROJ), c, a))

        # Revisit a completed child using the original row and continuation data.
        resume_argument = self.AND(self.mode(Mode.RESUME), self.eq(frame['phase'], PENDING_ARGUMENT))
        valid_argument = self.AND(nonempty, self.tag(Tag.APP))
        self.stop(self.AND(resume_argument, self.NOT(valid_argument)), Outcome.INVALID, Reason.SYNTAX)
        resume_argument = self.AND(resume_argument, valid_argument)
        self.emit(resume_argument, sp=top)
        self.ret(self.AND(resume_argument, self.eq(a, result)), x)
        self.alloc(self.AND(resume_argument, self.NOT(self.eq(a, result))), (Tag.APP, result, frame['first'], 0))
        resuming = self.AND(self.mode(Mode.RESUME), self.NOT(self.eq(frame['phase'], PENDING_ARGUMENT)))
        child_count = self.mux(let, 3, self.mux(binary, 2, self.mux(unary, 1, 0)))
        phase_valid = self.AND(nonempty, self.NOT(self.eq(frame['phase'], 0)), self.NOT(self.lt(child_count, frame['phase'])))
        self.stop(self.AND(resuming, self.NOT(phase_valid)), Outcome.INVALID, Reason.SYNTAX)
        another = self.AND(resuming, phase_valid, self.lt(frame['phase'], child_count))
        first_phase = self.eq(frame['phase'], 1)
        binder_child = self.OR(self.AND(self.tag(Tag.PI, Tag.LAM), first_phase), self.AND(let, self.eq(frame['phase'], 2)))
        another, next_depth = self.checked_add(another, depth, self.mux(binder_child, 1, 0))
        self.write('stack', another, top, (self.add(frame['phase'], 1), x, depth, task,
            self.mux(first_phase, result, frame['first']), self.mux(first_phase, frame['second'], result)))
        self.emit(another, mode=Mode.WALK, x=self.mux(first_phase, b, c), depth=next_depth)

        finish = self.AND(resuming, phase_valid, self.eq(frame['phase'], child_count))
        normal = self.task(Task.LEVEL_NORMALIZE)
        normal_imax = self.AND(finish, normal, self.tag(CellTag.LEVEL_IMAX))
        self.emit(self.AND(finish, self.NOT(normal_imax)), sp=top)
        self.write('stack', normal_imax, top, (CALL_NORMAL_IMAX, 0, 0, Task.LEVEL_NORMALIZE, 0, 0))
        self.emit(normal_imax, mode=Mode.WALK, task=Task.LEVEL_IMAX, x=frame['first'], peer=result)
        self.emit(self.AND(finish, normal, self.tag(CellTag.LEVEL_MAX)), mode=Mode.WALK, task=Task.LEVEL_MERGE, x=frame['first'], peer=result)
        self.emit(self.AND(finish, normal, self.tag(CellTag.LEVEL_SUCC)), mode=Mode.WALK, task=Task.LEVEL_NORMAL_SUCC, x=result)
        first, second = frame['first'], frame['second']
        unchanged = self.OR(
            self.AND(unary, self.eq(result, self.mux(self.tag(Tag.PROJ), c, a))),
            self.AND(binary, self.eq(first, a), self.eq(result, b)),
            self.AND(let, self.eq(first, a), self.eq(second, b), self.eq(result, c)))
        self.ret(self.AND(finish, unchanged, self.NOT(normal)), x)
        rebuild = self.AND(finish, self.NOT(unchanged), self.NOT(normal))
        source_construct = self.AND(rebuild, self.task(Task.LEVEL_INSTANTIATE), self.tag(CellTag.LEVEL_MAX, CellTag.LEVEL_IMAX))
        self.emit(source_construct, mode=Mode.WALK, x=first, peer=result,
            task=self.mux(self.tag(CellTag.LEVEL_MAX), Task.LEVEL_MAX, Task.LEVEL_IMAX))
        self.alloc(self.AND(rebuild, binary, self.NOT(source_construct)), (node['tag'], first, result, c))
        self.alloc(self.AND(rebuild, let), (node['tag'], first, second, result))
        self.alloc(self.AND(rebuild, self.tag(Tag.PROJ)), (node['tag'], a, b, result))
        self.alloc(self.AND(rebuild, self.tag(Tag.MDATA)), (node['tag'], result, b, 0))
        self.alloc(self.AND(rebuild, self.tag(CellTag.LEVEL_SUCC)), (node['tag'], result, 0, 0))

        leaf = self.AND(walking, self.NOT(branch))
        normal_successor = self.AND(leaf, self.task(Task.LEVEL_NORMAL_SUCC))
        self.alloc(normal_successor, (CellTag.LEVEL_SUCC, x, 0, 0))
        scope_bad = self.AND(leaf, self.OR(self.task(Task.VARIABLE_SCOPE), self.task(Task.EXPR_SCOPE)),
            self.OR(self.tag(Tag.LOCAL), self.AND(self.tag(Tag.BVAR), self.NOT(self.lt(a, depth)))))
        self.stop(scope_bad, Outcome.INVALID, Reason.SCOPE)
        unbound_level = self.AND(leaf, self.task(Task.LEVEL_SCOPE), self.tag(CellTag.LEVEL_PARAM), self.eq(r['count'], 0))
        self.stop(unbound_level, Outcome.INVALID, Reason.UNIVERSE)
        substitute_level = self.AND(leaf, self.OR(self.task(Task.LEVEL_SUBSTITUTE), self.task(Task.LEVEL_INSTANTIATE)), self.tag(CellTag.LEVEL_PARAM), self.NOT(self.eq(r['count'], 0)))
        self.emit(substitute_level, mode=Mode.LEVEL_SELECT, i=0, parameter=a, lookup_level=x)
        abstract_one = self.AND(leaf, self.task(Task.ABSTRACT_ONE), self.tag(Tag.LOCAL), self.eq(a, r['abstract_uid']))
        self.alloc(abstract_one, (Tag.BVAR, depth, 0, 0))
        inst = self.OR(self.task(Task.INSTANTIATE), self.task(Task.INSTANTIATE_ONE))
        var_transform = self.AND(leaf, self.tag(Tag.BVAR), self.OR(self.task(Task.LIFT), inst))
        start = self.mux(self.task(Task.INSTANTIATE_ONE), 0, self.mux(self.task(Task.LIFT), r['cutoff'], r['start']))
        count = self.mux(self.task(Task.INSTANTIATE_ONE), 1, r['count'])
        offset_guard, offset = self.checked_add(var_transform, depth,
            start)
        under = self.lt(a, offset)
        self.ret(self.AND(offset_guard, under), x)
        above = self.AND(offset_guard, self.NOT(under))
        lifting = self.AND(above, self.task(Task.LIFT))
        lifting, lifted = self.checked_add(lifting, a, r['delta'])
        unchanged_lift = self.eq(lifted, a)
        self.ret(self.AND(lifting, unchanged_lift), x)
        self.alloc(self.AND(lifting, self.NOT(unchanged_lift)), (Tag.BVAR, lifted, 0, 0))
        instantiating = self.AND(above, inst)
        relative = self.sub(a, offset)
        within = self.lt(relative, count)
        beyond = self.AND(instantiating, self.NOT(within))
        self.ret(self.AND(beyond, self.eq(count, 0)), x)
        self.alloc(self.AND(beyond, self.NOT(self.eq(count, 0))), (Tag.BVAR, self.sub(a, count), 0, 0))
        substituting = self.AND(instantiating, within)
        operand = self.mux(self.task(Task.INSTANTIATE_ONE), r['substitution'], operand)
        valid_operand = self.AND(self.NOT(self.eq(operand, 0)), self.lt(operand, r['free']))
        self.stop(self.AND(substituting, self.NOT(valid_operand)), Outcome.INVALID, Reason.SYNTAX)
        substituting = self.AND(substituting, valid_operand)
        self.ret(self.AND(substituting, self.eq(depth, 0)), operand)
        self.emit(self.AND(substituting, self.NOT(self.eq(depth, 0))),
            x=operand, depth=0, task=Task.LIFT, delta=depth, cutoff=0)
        searching = self.AND(leaf, self.OR(self.AND(self.tag(Tag.LOCAL), self.task(Task.ABSTRACT)),
            self.AND(self.tag(Tag.CONST), self.task(Task.OCCURS)),
            self.AND(self.tag(CellTag.LEVEL_PARAM), self.task(Task.LEVEL_SCOPE))), self.NOT(self.eq(r['count'], 0)))
        self.emit(searching, mode=Mode.FIND, i=self.sub(r['count'], 1))
        self.ret(self.AND(leaf, self.NOT(normal_successor), self.NOT(var_transform), self.NOT(searching), self.NOT(scope_bad), self.NOT(abstract_one), self.NOT(unbound_level), self.NOT(substitute_level)), x)

    def finish(self, memory_update='attention_delta', target=None):
        if memory_update != 'attention_delta':
            raise ValueError('kernel traversal uses addressed native memory ABI')
        self.rules()
        outputs = []
        for name, _ in self.layout.fields:
            choices = self.choices[name]
            keep = self.NOT(self.OR(*(guard for guard, _ in choices)))
            for i, old in enumerate(self.r[name]):
                outputs.append(self.g.masked_or([(keep, old)]+[(guard, value[i]) for guard, value in choices], self.factor))
        for bank, fields in (('heap', 4), ('stack', 6), ('context', 1)):
            choices = self.writes[bank]
            bits = getattr(self.cfg, bank).bit_length()-1
            outputs.extend(self.g.masked_or([(guard, address[i]) for guard, address, row in choices], self.factor) for i in range(bits))
            outputs.append(self.OR(*(guard for guard, address, row in choices)))
            for field in range(fields):
                outputs.extend(self.g.masked_or([(guard, row[field][i]) for guard, address, row in choices], self.factor) for i in range(self.width))
        return self.g.compile(outputs, target)
