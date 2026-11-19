"""Conditional row schedule counts for a complete fixed checker operator IR.

This is a cost model, not native emission or an inference interpreter. Operand
unions include all data branches of selected source control groups. Explicit
assumptions prevent these counts from being reported as measured forwards.
"""
from collections import Counter,defaultdict
from math import ceil
from .macro_budget import TARGET_COMBINED_FORWARDS


class OperatorBudget:
    def __init__(self,layout,read_ports=3):
        self.locations=layout.locations();self.check_forwards=0;self.steps=0
        self.read_ports=read_ports
        self.gathers=Counter();self.writes=Counter();self.bank_conflicts=0

    def add(self,access):
        pages=defaultdict(Counter)
        for name in access['reads']:
            if name in self.locations:
                row,slot=self.locations[name];pages[row][slot//7]+=1
        queries=sum(max(counts.values())for counts in pages.values())
        gathers=ceil(queries/self.read_ports)
        dirty={(row,slot//7)for name in access['updates']if name in self.locations for row,slot in(self.locations[name],)}
        self.gathers[gathers]+=1;self.writes[len(dirty)]+=1
        conflict=int('stack'in access['writes']and'context'in access['writes'])
        self.bank_conflicts+=conflict;self.steps+=1
        self.check_forwards+=1+max(0,gathers-1)+max(0,len(dirty)-1)+conflict

    def report(self,reloads=0):
        before_observation=self.check_forwards+reloads
        checking=ceil(before_observation/32)*32;combined=checking+22+5+2
        return dict(semantic_steps=self.steps,selective_rf_ports=self.read_ports,gather_forward_histogram=dict(sorted(self.gathers.items())),
                    dirty_seven_word_pages_histogram=dict(sorted(self.writes.items())),
                    small_bank_conflicts=self.bank_conflicts,selector_reload_forwards=reloads,
                    conditional_before_observation=before_observation,conditional_check_forwards=checking,
                    syntax_boot_forwards=22,setup_model_calls=5,init_publish_allowance=2,
                    conditional_combined_forwards=combined,target=TARGET_COMBINED_FORWARDS,
                    conditional_count_gate=combined<=TARGET_COMBINED_FORWARDS,actual_native_forwards=None,
                    assumptions=[f'{self.read_ports} independently addressed selective RF ports',
                                 'Operand gathers, source operator, first dirty-page merge fit one stock forward',
                                 'Every additional dirty seven-word page costs one merge/commit forward',
                                 'All bounds-latch, prefix/body guards and source memory-address computation fit',
                                 'Dirty page selection/value staging and atomic publication remain model-owned'],
                    complete_schedule_verified=False,joint_delivery_gate=False)
