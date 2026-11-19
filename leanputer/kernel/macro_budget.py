"""Joint design gates for checker-transition operators, not a checker executor.

All figures are dense stock shapes or explicitly conditional schedule budgets.
No source/proof selects a different model or operator set. Reference step counts
are never labeled stock inference speed or successful full-rule lowering.
"""
from dataclasses import dataclass,asdict
from math import ceil

BASELINE_DENSE=48_290_654
BASELINE_CHECK_FORWARDS=230_432
TARGET_COMBINED_FORWARDS=4_000  # Explicit immediate milestone, 2026-11-19.


def paged_operator_shape(global_words=16,read_ports=3):
    """Necessary shape/slot arithmetic only; no complete allocation is implied."""
    if read_ports==3:h,i,l,mem=1152,128,78,6
    elif read_ports==4:h,i,l,mem=1280,128,63,7
    else:raise ValueError('bounded source-operator RF port count')
    inert=3*h*i+12*h+4;memory=inert+1790*h+3204
    dense=mem*memory+(l-mem)*inert+129*h
    columns=dict(global_words=global_words*16,rf_pending_page=112,selected_rf_operands=read_ports*64,
                 rf_merge_page=112,heap_pending=74,small_bank_pending_with_control_word=120,
                 controller_and_selector=48,deferred_context=20,rom_low_decoder=128,
                 rom_byte_accumulators=32,ballast_tau=h//64+1)
    return dict(hidden=h,intermediate=i,layers=l,active_gdn_layers=mem,
                memory_roles=f'{read_ports} selective RF reads, one RF page merge, heap, small banks',
                logical_dense_parameters=dense,baseline_dense_limit=BASELINE_DENSE,
                dense_shape_gate=dense<=BASELINE_DENSE,
                ffn_units=l*i,ffn_units_after_24_handover_reserve=l*(i-24),
                provisional_named_columns=columns,provisional_column_sum=sum(columns.values()),
                remaining_columns_before_unallocated_intermediates=h-sum(columns.values()),
                complete_descriptor_encoding_bits=None,complete_neural_operator_units=None,
                full_program_lifetime_allocation_verified=False,full_model_emitted=False,
                stock_forwards=None,joint_delivery_gate=False)


@dataclass(frozen=True)
class TransitionArchitecture:
    hidden: int = 1536
    intermediate: int = 192
    layers: int = 44
    active_memory_layers: int = 3
    value_heads: int = 4
    descriptor_bits: int = 256
    descriptor_capacity: int = 4096
    frame_words: int = 28
    global_words: int = 14
    operator_layers: int = 11

    def dense_parameters(self):
        h,i,v=self.hidden,self.intermediate,self.value_heads
        linear=3*h*i+(258+386*v)*h+1152+514*v
        inert=3*h*i+12*h+4
        return self.active_memory_layers*linear+(self.layers-self.active_memory_layers)*inert+129*h

    def rom_layers(self):
        pages=ceil(self.descriptor_capacity/128)
        columns=ceil(self.descriptor_bits/8)+1
        return 1+ceil(columns*pages/self.intermediate)+7

    def account(self):
        parameters=self.dense_parameters()
        # Boundary frame data is in the activation RF, not duplicated in the
        # feedback vector. A coherent whole-frame spill/read uses four V heads.
        retained=self.global_words*16+self.frame_words*16+74+103+32+20
        peak_rom=retained+self.frame_words*16+128+ceil(self.descriptor_bits/8)+self.hidden//64+1
        return dict(**asdict(self),logical_dense_parameters=parameters,parameter_limit=BASELINE_DENSE,parameter_shape_gate=parameters<=BASELINE_DENSE,rom_layer_budget=self.rom_layers(),operator_ffn_unit_budget=self.operator_layers*self.intermediate,operator_handoff_units=24*self.operator_layers,operator_compute_units=(self.intermediate-24)*self.operator_layers,retained_feedback_bits=retained,conditional_rom_phase_peak_channels=peak_rom,channel_budget=self.hidden,conditional_rom_phase_gate=peak_rom<=self.hidden,full_rule_descriptor_count=None,full_rule_live_frame_bound=None,full_rule_operator_schedule_verified=False,stock_emitted=False,joint_delivery_gate=False)


def source_step_allowance(row,boot_packets=692,prefill_chunk=32,observation_interval=32):
    """Conditional upper allowance, not measured native/model forward counts.

    One operator per original abstract transition; at most two extra call/restore
    operations per stack-write transition; serial context+frame collisions; and
    one bulk-row operation per extra group of seven modified register fields.
    These allowances require a full-rule compiler/semantic proof still absent.
    """
    steps=row['semantic_steps'];stack=row['bank_write_steps'].get('stack',0)
    conflict=sum(count for kinds,count in row['simultaneous_bank_steps'].items()if 'context'in kinds.split('+')and'stack'in kinds.split('+'))
    wide=sum((ceil(int(fields)/7)-1)*count for fields,count in row['updated_fields_histogram'].items())
    extras=2*stack+conflict+wide
    unrounded=steps+extras
    checking=ceil(unrounded/observation_interval)*observation_interval
    boot=ceil(boot_packets/prefill_chunk)
    setup=5 # Original path: hook-install eager call + three warmups + capture.
    init_publish=2
    combined=checking+boot+setup+init_publish
    return dict(name=row['name'],measured_reference_semantic_steps=steps,syntax_packets=boot_packets,syntax_boot_forwards=boot,conditional_call_restore_allowance=2*stack,conditional_small_bank_conflict_allowance=conflict,conditional_wide_update_allowance=wide,conditional_check_before_observation=unrounded,conditional_check_forwards=checking,setup_model_calls=setup,init_publish_allowance=init_publish,conditional_combined_forwards=combined,target_combined_forwards=TARGET_COMBINED_FORWARDS,conditional_step_budget_gate=combined<=TARGET_COMBINED_FORWARDS,actual_new_checker_forwards=None,full_rule_schedule_verified=False,stock_speed_measured=False,joint_delivery_gate=False)
