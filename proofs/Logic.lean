-- Integer-domain compiler lemmas. These do not verify PyTorch, softmax,
-- machine typing, or the Python compiler.
import Std

namespace Leanputer

def bit (b : Bool) : Int := if b then 1 else 0
def relu (x : Int) : Int := max 0 x

theorem not_gate (a : Bool) : relu (1 - bit a) = bit (!a) := by
  cases a <;> decide

theorem and_gate (a b : Bool) : relu (bit a + bit b - 1) = bit (a && b) := by
  cases a <;> cases b <;> decide

theorem or_gate (a b : Bool) :
    relu (bit a + bit b) - relu (bit a + bit b - 1) = bit (a || b) := by
  cases a <;> cases b <;> decide

theorem masked_write (enable old new : Bool) :
    ((enable && new) || (!enable && old)) = (if enable then new else old) := by
  cases enable <;> cases old <;> cases new <;> decide

-- Absorbing-outcome pattern used by both transition implementations.
def absorb {α : Type} (done : Bool) (step : α → α) (state : α) : α :=
  if done then state else step state

theorem terminal_absorbs {α : Type} (step : α → α) (state : α) :
    absorb true step state = state := rfl

#print axioms not_gate
#print axioms and_gate
#print axioms or_gate
#print axioms masked_write
#print axioms terminal_absorbs
end Leanputer

namespace Leanputer
-- N-ary gate arithmetic over the supported bounded integer domain. Floating
-- point execution of these integer formulas is a separate numerical argument.
theorem or_count (n : Nat) :
    relu ((n : Int)) - relu ((n : Int) - 1) = (if n = 0 then 0 else 1) := by
  by_cases h : n = 0
  · subst n; decide
  · have nonneg : (0 : Int) ≤ (n : Int) := by omega
    have previous : (0 : Int) ≤ (n : Int) - 1 := by omega
    rw [if_neg h]
    unfold relu
    rw [Int.max_eq_right nonneg, Int.max_eq_right previous]
    omega

theorem and_count (s n : Nat) (bounded : s ≤ n) :
    relu ((s : Int) + 1 - (n : Int)) = (if s = n then 1 else 0) := by
  by_cases h : s = n
  · rw [if_pos h]
    have value : (s : Int) + 1 - (n : Int) = 1 := by omega
    rw [value]
    decide
  · rw [if_neg h]
    have nonpos : (s : Int) + 1 - (n : Int) ≤ 0 := by omega
    exact Int.max_eq_left nonpos

#print axioms or_count
#print axioms and_count
end Leanputer

namespace Leanputer
theorem factor_shared_mask (mask left right : Bool) :
    ((mask && left) || (mask && right)) = (mask && (left || right)) := by
  cases mask <;> cases left <;> cases right <;> decide
#print axioms factor_shared_mask
end Leanputer
